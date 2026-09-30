//! T2 3-way postflop RESEARCH prototype (not production, not a GTO claim).
//!
//!   t2_3way build <terminal.json> <board> [--alloc]
//!   t2_3way showdown <terminal.json> <board> [--brute-sample N]
//!   t2_3way preflop-equity <terminal.json> <boards>
//!   t2_3way solve <terminal.json> <board> <iters> <out.json> [--fold-first SEAT --nonblocking SEAT] [--checkpoints a,b,c]
//!
//! Game: the three players of a 3-way pot-share terminal (postflop order from the export),
//! combo-level ranges with EXACT card removal between all three hands and the board, the
//! M2-like menu of the HU pipeline: one 50% pot bet, raise = all-in only, at most one raise per
//! street, bets >= 85% of the stack become all-in, no lead ("donk") by a player who acts before
//! the previous street's aggressor (check-through clears it), equal stacks (no side pots).
//! A player who folds keeps blocking cards; a folded player's utility is constant, so its
//! subtree is not traversed. Runout probabilities are uniform over the cards not on the board
//! and not in any blocking hand (1 / (K - 2 * blockers) per dealt card).
//! Values use the table convention: gross share = share of the final pot minus postflop
//! contributions; the three players' gross values sum to the starting pot.
//! Storage: per action node (betting template x runout) regret + strategy sum, f32, 1326 combos
//! per acting player. The tree is a set of per-street betting templates instantiated once
//! (flop), per turn card (turn) and per (turn, river) pair (river).
use rayon::prelude::*;
use solver::cards::{card_from_str, combo_from_index, combo_index, rank, suit, Card, NUM_COMBOS};
use solver::evaluator::evaluate7;
use solver::preflop::equity::class_index;
use std::collections::HashMap;

const NP: usize = 3;

fn combo_cards() -> &'static [(Card, Card)] {
    static T: std::sync::OnceLock<Vec<(Card, Card)>> = std::sync::OnceLock::new();
    T.get_or_init(|| (0..NUM_COMBOS).map(combo_from_index).collect())
}

/// combos containing each card
fn card_combos() -> &'static [Vec<u16>] {
    static T: std::sync::OnceLock<Vec<Vec<u16>>> = std::sync::OnceLock::new();
    T.get_or_init(|| {
        let mut v = vec![Vec::new(); 52];
        for (i, &(a, b)) in combo_cards().iter().enumerate() {
            v[a as usize].push(i as u16);
            v[b as usize].push(i as u16);
        }
        v
    })
}

#[inline(always)]
fn cc(i: usize) -> (Card, Card) {
    combo_cards()[i]
}
const EPS: f32 = 1e-3;
const BET_FRAC: f64 = 0.5;
const ALLIN_THRESHOLD: f64 = 0.85;
const MAX_RAISES: u8 = 1;
const STREETS: [&str; 3] = ["flop", "turn", "river"];

// ------------------------------------------------------------------ game tree templates
#[derive(Clone, Copy, Debug, PartialEq)]
enum Act {
    Fold,
    Check,
    Call,
    Bet(f64),
    Raise(f64), // all-in
}

#[derive(Clone, Debug)]
struct State {
    street: u8,
    folded: [bool; NP],
    contrib: [f64; NP],     // postflop contribution
    street_bet: [f64; NP],  // this street
    acted: [bool; NP],
    to_act: usize,
    num_raises: u8,
    street_aggr: Option<usize>,
    prev_aggr: Option<usize>,
}

#[derive(Clone, Debug)]
enum TNode {
    Action { player: usize, acts: Vec<Act>, children: Vec<usize>, slot: usize, contrib: [f64; NP] },
    /// only one player left: `winner` takes the pot
    FoldWin { winner: usize, contrib: [f64; NP], folded: [bool; NP] },
    /// river closed with >= 2 players, or an all-in (runout to the river, no more betting)
    Showdown { contrib: [f64; NP], folded: [bool; NP] },
    /// street closed, go to the next street's template
    Next { template: usize },
}

struct Template {
    street: u8,
    nodes: Vec<TNode>,
    /// action slots and their action counts (data per instance = sum acts * 1326 per array)
    slots: Vec<(usize, usize)>, // (player, n_acts)
    entry: State,
}

struct Game {
    pot0: f64,
    stack: f64,
    templates: Vec<Template>,
    key: HashMap<String, usize>,
}

fn active(st: &State) -> Vec<usize> {
    (0..NP).filter(|&p| !st.folded[p]).collect()
}

fn behind(g: &Game, st: &State, p: usize) -> f64 {
    g.stack - st.contrib[p]
}

impl Game {
    fn template_for(&mut self, entry: State) -> usize {
        let k = format!("{}|{:?}|{:?}|{:?}", entry.street, entry.folded, entry.contrib.map(|x| (x * 1e6).round() as i64), entry.prev_aggr);
        if let Some(&t) = self.key.get(&k) {
            return t;
        }
        let id = self.templates.len();
        self.templates.push(Template { street: entry.street, nodes: vec![], slots: vec![], entry: entry.clone() });
        self.key.insert(k, id);
        let mut nodes = Vec::new();
        let mut slots = Vec::new();
        self.build(entry, &mut nodes, &mut slots);
        self.templates[id].nodes = nodes;
        self.templates[id].slots = slots;
        id
    }

    fn pot(&self, st: &State) -> f64 {
        self.pot0 + st.contrib.iter().sum::<f64>()
    }

    fn legal(&self, st: &State) -> Vec<Act> {
        let me = st.to_act;
        let max_bet = st.street_bet.iter().cloned().fold(0.0, f64::max);
        let facing = max_bet - st.street_bet[me];
        let stack_me = behind(self, st, me);
        let mut a = Vec::new();
        if facing > 1e-9 {
            a.push(Act::Fold);
            a.push(Act::Call);
            if stack_me > facing + 1e-9 && st.num_raises < MAX_RAISES {
                a.push(Act::Raise(st.street_bet[me] + stack_me));
            }
        } else {
            a.push(Act::Check);
            // lead forbidden for a player acting before the previous street's aggressor
            let donk = st.street > 0
                && st.prev_aggr.map_or(false, |ag| ag != me && !st.folded[ag] && !st.acted[ag]);
            if stack_me > 1e-9 && !donk {
                let pot = self.pot(st);
                let mut to = BET_FRAC * pot;
                if to >= stack_me - 1e-9 || to >= ALLIN_THRESHOLD * stack_me - 1e-9 {
                    to = stack_me;
                }
                a.push(Act::Bet(st.street_bet[me] + to));
            }
        }
        a
    }

    fn next_to_act(&self, st: &State, from: usize) -> Option<usize> {
        // next non-folded player with chips behind who still has to act or match
        let max_bet = st.street_bet.iter().cloned().fold(0.0, f64::max);
        for d in 1..=NP {
            let p = (from + d) % NP;
            if st.folded[p] || behind(self, st, p) <= 1e-9 {
                continue;
            }
            if !st.acted[p] || st.street_bet[p] < max_bet - 1e-9 {
                return Some(p);
            }
        }
        None
    }

    fn build(&mut self, st: State, nodes: &mut Vec<TNode>, slots: &mut Vec<(usize, usize)>) -> usize {
        let act = active(&st);
        if act.len() == 1 {
            nodes.push(TNode::FoldWin { winner: act[0], contrib: st.contrib, folded: st.folded });
            return nodes.len() - 1;
        }
        let acts = self.legal(&st);
        let me = st.to_act;
        let idx = nodes.len();
        let slot = slots.len();
        slots.push((me, acts.len()));
        nodes.push(TNode::Action { player: me, acts: acts.clone(), children: vec![], slot, contrib: st.contrib });
        let mut children = Vec::new();
        for &a in &acts {
            let mut s = st.clone();
            s.acted[me] = true;
            match a {
                Act::Fold => s.folded[me] = true,
                Act::Check => {}
                Act::Call => {
                    let max_bet = s.street_bet.iter().cloned().fold(0.0, f64::max);
                    let add = (max_bet - s.street_bet[me]).min(behind(self, &s, me));
                    s.street_bet[me] += add;
                    s.contrib[me] += add;
                }
                Act::Bet(to) | Act::Raise(to) => {
                    let add = to - s.street_bet[me];
                    s.street_bet[me] = to;
                    s.contrib[me] += add;
                    s.street_aggr = Some(me);
                    if matches!(a, Act::Raise(_)) {
                        s.num_raises += 1;
                    }
                    // everyone else must act again
                    for p in 0..NP {
                        if p != me {
                            s.acted[p] = false;
                        }
                    }
                }
            }
            let child = match self.next_to_act(&s, me) {
                Some(p) if active(&s).len() > 1 => {
                    s.to_act = p;
                    self.build(s, nodes, slots)
                }
                _ => self.street_end(s, nodes),
            };
            children.push(child);
        }
        if let TNode::Action { children: c, .. } = &mut nodes[idx] {
            *c = children;
        }
        idx
    }

    fn street_end(&mut self, st: State, nodes: &mut Vec<TNode>) -> usize {
        let act = active(&st);
        if act.len() == 1 {
            nodes.push(TNode::FoldWin { winner: act[0], contrib: st.contrib, folded: st.folded });
            return nodes.len() - 1;
        }
        let with_chips = act.iter().filter(|&&p| behind(self, &st, p) > 1e-9).count();
        if st.street == 2 || with_chips <= 1 {
            nodes.push(TNode::Showdown { contrib: st.contrib, folded: st.folded });
            return nodes.len() - 1;
        }
        let first = (0..NP).find(|&p| !st.folded[p]).unwrap();
        let entry = State {
            street: st.street + 1,
            folded: st.folded,
            contrib: st.contrib,
            street_bet: [0.0; NP],
            acted: [false; NP],
            to_act: first,
            num_raises: 0,
            street_aggr: None,
            prev_aggr: st.street_aggr,
        };
        let t = self.template_for(entry);
        nodes.push(TNode::Next { template: t });
        nodes.len() - 1
    }
}

fn build_game(pot0: f64, stack: f64, fold_first: Option<usize>) -> Game {
    let mut g = Game { pot0, stack, templates: vec![], key: HashMap::new() };
    let mut entry = State {
        street: 0,
        folded: [false; NP],
        contrib: [0.0; NP],
        street_bet: [0.0; NP],
        acted: [false; NP],
        to_act: 0,
        num_raises: 0,
        street_aggr: None,
        prev_aggr: None,
    };
    if let Some(p) = fold_first {
        // degeneration test: seat p is out before the flop action starts (it still may block)
        entry.folded[p] = true;
        entry.to_act = (0..NP).find(|&q| q != p).unwrap();
    }
    g.template_for(entry);
    g
}

/// instances of each template: flop 1, turn per turn card (49), river per (turn, river) (49*48)
fn instances(t: &Template) -> u64 {
    match t.street {
        0 => 1,
        1 => 49,
        _ => 49 * 48,
    }
}

// ------------------------------------------------------------------ build-only report
fn build_report(g: &Game, alloc: bool) -> serde_json::Value {
    let mut by_street = [[0u64; 6]; 3]; // action nodes 3-active, 2-active, foldwin, showdown, next, bytes
    let mut chance = [0u64; 3];
    let mut slots_total = 0u64;
    let mut bytes = [0u64; 3];
    let mut act_by_active = [[0u64; 2]; 3];
    for t in &g.templates {
        let inst = instances(t);
        let s = t.street as usize;
        let n_active = NP - t.entry.folded.iter().filter(|&&f| f).count();
        for n in &t.nodes {
            match n {
                TNode::Action { .. } => {
                    by_street[s][0] += inst;
                    act_by_active[s][if n_active == 3 { 0 } else { 1 }] += inst;
                }
                TNode::FoldWin { .. } => by_street[s][2] += inst,
                TNode::Showdown { .. } => by_street[s][3] += inst,
                TNode::Next { .. } => {
                    by_street[s][4] += inst;
                    chance[s] += inst;
                }
            }
        }
        for &(_, na) in &t.slots {
            slots_total += inst;
            bytes[s] += inst * na as u64 * NUM_COMBOS as u64 * 4 * 2; // regret + strategy sum, f32
        }
    }
    // node-level 3-active vs 2-active within templates whose entry has 3 active (fold happens inside)
    let mut inside = [[0u64; 2]; 3];
    let mut bytes_by_active = [[0u64; 2]; 3];
    for t in &g.templates {
        let inst = instances(t);
        let s = t.street as usize;
        // walk to get the number of folded players at each action node
        fn walk(t: &Template, i: usize, folded: usize, inst: u64, s: usize, out: &mut [[u64; 2]; 3], by: &mut [[u64; 2]; 3]) {
            if let TNode::Action { acts, children, .. } = &t.nodes[i] {
                let k = if folded == 0 { 0 } else { 1 };
                out[s][k] += inst;
                by[s][k] += inst * acts.len() as u64 * NUM_COMBOS as u64 * 4 * 2;
                for (a, &c) in acts.iter().zip(children) {
                    walk(t, c, folded + (*a == Act::Fold) as usize, inst, s, out, by);
                }
            }
        }
        let f0 = t.entry.folded.iter().filter(|&&f| f).count();
        walk(t, 0, f0, inst, s, &mut inside, &mut bytes_by_active);
    }
    let total_bytes: u64 = bytes.iter().sum();
    let mut out = serde_json::json!({
        "templates": g.templates.len(),
        "templates_by_street": (0..3).map(|s| g.templates.iter().filter(|t| t.street as usize == s).count()).collect::<Vec<_>>(),
        "streets": (0..3).map(|s| serde_json::json!({
            "street": STREETS[s],
            "action_nodes": by_street[s][0], "action_nodes_3_active": inside[s][0], "action_nodes_2_active": inside[s][1],
            "fold_win_terminals": by_street[s][2], "showdown_terminals": by_street[s][3],
            "chance_nodes_into_next_street": chance[s], "strategy_plus_regret_bytes_f32": bytes[s],
            "bytes_3_active_nodes": bytes_by_active[s][0], "bytes_2_active_nodes": bytes_by_active[s][1]})).collect::<Vec<_>>(),
        "bytes_regret_f32": total_bytes / 2, "bytes_strategy_sum_f32": total_bytes / 2,
        "bytes_if_2_active_subtrees_delegated": (0..3).map(|s| bytes_by_active[s][0]).sum::<u64>(),
        "action_slots_total": slots_total,
        "bytes_regret_plus_strategy_f32": total_bytes,
        "bytes_ev_scratch_estimate": 0,
        "note": "memory = sum over action nodes (template x runout) of actions x 1326 combos x 4 bytes x 2 arrays; EV vectors are transient (per recursion level), not stored",
    });
    if alloc {
        let limit = 10u64 << 30;
        let rss0 = peak_rss_kb();
        if total_bytes <= limit {
            let mut v: Vec<f32> = vec![0.0; (total_bytes / 4) as usize];
            for i in (0..v.len()).step_by(1024) {
                v[i] = 1.0;
            }
            std::hint::black_box(&v);
            out["alloc"] = serde_json::json!({"allocated_bytes": total_bytes, "peak_rss_kb_before": rss0, "peak_rss_kb_after": peak_rss_kb()});
        } else {
            // accounting check on a slice that fits: flop + turn + the river of ONE turn card
            let slice = bytes[0] + bytes[1] + bytes[2] / 49;
            let mut v: Vec<f32> = vec![0.0; (slice / 4) as usize];
            for i in (0..v.len()).step_by(1024) {
                v[i] = 1.0;
            }
            std::hint::black_box(&v);
            let rss1 = peak_rss_kb();
            out["alloc"] = serde_json::json!({"full": format!("{:.2} GB > 10 GB limit: not allocated", total_bytes as f64 / 1e9),
                "slice_allocated_bytes": slice, "peak_rss_kb_before": rss0, "peak_rss_kb_after": rss1,
                "rss_delta_over_accounted": rss1.zip(rss0).map(|(a, b)| (a - b) as f64 * 1024.0 / slice as f64)});
        }
    }
    out
}

fn peak_rss_kb() -> Option<u64> {
    let st = std::fs::read_to_string("/proc/self/status").ok()?;
    st.lines().find(|l| l.starts_with("VmHWM:"))?.split_whitespace().nth(1)?.parse().ok()
}

// ------------------------------------------------------------------ ranges
struct Spot {
    pos: Vec<String>,
    /// weights per player over 1326 combos (EPS floor for zero-reach classes, 0 on the board)
    w: Vec<Vec<f32>>,
    pot0: f64,
    stack: f64,
    board: Vec<Card>,
    labels: Vec<String>,
}

fn load_spot(path: &str, board: &str) -> Result<Spot, String> {
    let t: serde_json::Value = serde_json::from_slice(&std::fs::read(path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let order: Vec<String> = t["postflop_order"].as_array().ok_or("postflop_order")?.iter().map(|x| x.as_str().unwrap().to_string()).collect();
    if order.len() != NP {
        return Err("3-way terminal export required".into());
    }
    let b: Vec<Card> = (0..board.len() / 2).map(|i| card_from_str(&board[2 * i..2 * i + 2])).collect::<Result<_, _>>()?;
    let mut bm = 0u64;
    for &c in &b {
        bm |= 1 << c;
    }
    let mut w = Vec::new();
    for p in &order {
        let pl = t["players"].as_array().unwrap().iter().find(|x| x["position"] == p.as_str()).ok_or("player")?;
        let keep: Vec<f64> = pl["class_keep_fraction"].as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect();
        let mut v = vec![0f32; NUM_COMBOS];
        for i in 0..NUM_COMBOS {
            let (a, c) = combo_from_index(i);
            if bm & (1 << a) != 0 || bm & (1 << c) != 0 {
                continue;
            }
            v[i] = (keep[class_index(rank(a), rank(c), suit(a) == suit(c))] as f32).max(EPS);
        }
        w.push(v);
    }
    let labels = t["class_labels"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string()).collect();
    Ok(Spot { pos: order, w, pot0: t["pot_bb"].as_f64().unwrap(), stack: t["effective_behind_bb"].as_f64().unwrap(), board: b, labels })
}


// ------------------------------------------------------------------ exact showdown evaluation
/// strength of every combo on a complete 5-card board (0 = combo touches the board)
fn strengths(board: &[Card]) -> Vec<u32> {
    let mut bm = 0u64;
    for &c in board {
        bm |= 1 << c;
    }
    (0..NUM_COMBOS)
        .map(|i| {
            let (a, c) = cc(i);
            if bm & (1 << a) != 0 || bm & (1 << c) != 0 {
                return 0;
            }
            let mut cards = [a, c, 0, 0, 0, 0, 0];
            cards[2..7].copy_from_slice(board);
            evaluate7(&cards) + 1
        })
        .collect()
}

#[inline]
fn cidx(a: Card, b: Card) -> usize {
    combo_index(a, b)
}

/// Exact 3-way showdown sums for hero combos h against opponents q, r (pairwise disjoint
/// hands, both disjoint from the board): num[h] = sum_{x,y} wq(x) wr(y) share_h(x, y),
/// den[h] = sum_{x,y} wq(x) wr(y). If `q_in_showdown` is false, q has folded but still blocks
/// cards (its hand never wins). O(N_hero * N_q) with an O(1) inclusion-exclusion over r.
fn showdown_sums(st: &[u32], wq: &[f32], wr: &[f32], q_in_showdown: bool) -> (Vec<f64>, Vec<f64>) {
    // r aggregates by strength: for each hero strength level we need, over r's combos
    // disjoint from 4 given cards, the mass strictly below / equal to the hero strength.
    let mut order: Vec<usize> = (0..NUM_COMBOS).filter(|&i| st[i] > 0).collect();
    order.sort_by_key(|&i| st[i]);
    let mut num = vec![0f64; NUM_COMBOS];
    let mut den = vec![0f64; NUM_COMBOS];
    // prefix structures over r: total and per card for combos with strength < t, = t
    let mut lt_tot = 0f64;
    let mut lt_card = [0f64; 52];
    let all_tot: f64 = order.iter().map(|&i| wr[i] as f64).sum();
    let mut all_card = [0f64; 52];
    for &i in &order {
        let (a, b) = cc(i);
        all_card[a as usize] += wr[i] as f64;
        all_card[b as usize] += wr[i] as f64;
    }
    let mut k = 0;
    while k < order.len() {
        let t = st[order[k]];
        let mut e = k;
        while e < order.len() && st[order[e]] == t {
            e += 1;
        }
        let mut eq_tot = 0f64;
        let mut eq_card = [0f64; 52];
        for &i in &order[k..e] {
            let (a, b) = cc(i);
            eq_tot += wr[i] as f64;
            eq_card[a as usize] += wr[i] as f64;
            eq_card[b as usize] += wr[i] as f64;
        }
        // mass of r over combos disjoint from cards `cs` (4 distinct cards), for a set given by (tot, card sums, membership)
        let excl = |tot: f64, card: &[f64; 52], cs: [Card; 4], member: &dyn Fn(usize) -> bool| -> f64 {
            let mut m = tot;
            for &c in &cs {
                m -= card[c as usize];
            }
            for i in 0..4 {
                for j in i + 1..4 {
                    let ci = cidx(cs[i], cs[j]);
                    if member(ci) {
                        m += wr[ci] as f64;
                    }
                }
            }
            m
        };
        let is_lt = |ci: usize| st[ci] > 0 && st[ci] < t;
        let is_eq = |ci: usize| st[ci] == t;
        let is_any = |ci: usize| st[ci] > 0;
        for &h in &order[k..e] {
            let (ha, hb) = cc(h);
            let (mut n, mut d) = (0f64, 0f64);
            for &x in &order {
                let wx = wq[x] as f64;
                if wx == 0.0 {
                    continue;
                }
                let (xa, xb) = cc(x);
                if xa == ha || xa == hb || xb == ha || xb == hb {
                    continue;
                }
                let cs = [ha, hb, xa, xb];
                let r_all = excl(all_tot, &all_card, cs, &is_any);
                d += wx * r_all;
                let r_lt = excl(lt_tot, &lt_card, cs, &is_lt);
                let r_eq = excl(eq_tot, &eq_card, cs, &is_eq);
                if !q_in_showdown {
                    n += wx * (r_lt + 0.5 * r_eq);
                } else if st[x] < t {
                    n += wx * (r_lt + 0.5 * r_eq);
                } else if st[x] == t {
                    n += wx * (0.5 * r_lt + r_eq / 3.0);
                }
            }
            num[h] = n;
            den[h] = d;
        }
        for &i in &order[k..e] {
            let (a, b) = cc(i);
            lt_tot += wr[i] as f64;
            lt_card[a as usize] += wr[i] as f64;
            lt_card[b as usize] += wr[i] as f64;
        }
        k = e;
    }
    (num, den)
}

/// brute force of the same sums (validation only): O(N^3)
fn showdown_brute(st: &[u32], wq: &[f32], wr: &[f32], q_in_showdown: bool) -> (Vec<f64>, Vec<f64>) {
    let idx: Vec<usize> = (0..NUM_COMBOS).filter(|&i| st[i] > 0).collect();
    let mut num = vec![0f64; NUM_COMBOS];
    let mut den = vec![0f64; NUM_COMBOS];
    let cards = |i: usize| {
        let (a, b) = cc(i);
        (1u64 << a) | (1u64 << b)
    };
    for &h in &idx {
        let mh = cards(h);
        for &x in &idx {
            if wq[x] == 0.0 || cards(x) & mh != 0 {
                continue;
            }
            for &y in &idx {
                if wr[y] == 0.0 || cards(y) & (mh | cards(x)) != 0 {
                    continue;
                }
                let w = wq[x] as f64 * wr[y] as f64;
                den[h] += w;
                let (sh, sx, sy) = (st[h], st[x], st[y]);
                let best = if q_in_showdown { sh.max(sx).max(sy) } else { sh.max(sy) };
                if sh == best {
                    let ties = 1 + (q_in_showdown && sx == best) as u32 + (sy == best) as u32;
                    num[h] += w / ties as f64;
                }
            }
        }
    }
    (num, den)
}

fn board_cards(flop: &[Card]) -> Vec<Card> {
    (0..52u8).filter(|c| !flop.contains(c)).collect()
}

/// showdown-only game (no betting): per player, per combo, sums over all (turn, river)
/// runouts; EV(h) = sum_R num_R(h) / (C(K-6, 2) * den_flop(h)) with K = 49 unseen cards.
fn showdown_test(spot: &Spot, brute_sample: usize) -> serde_json::Value {
    let rest = board_cards(&spot.board);
    let runouts: Vec<(Card, Card)> = rest.iter().enumerate().flat_map(|(i, &a)| rest[i + 1..].iter().map(move |&b| (a, b))).collect();
    let mut res = serde_json::Map::new();
    let mut per_player = Vec::new();
    // validation: fast vs brute on reduced ranges for a few runouts
    let mut rng = 12345u64;
    let mut next = || {
        rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (rng >> 33) as usize
    };
    let mut max_rel = 0f64;
    for trial in 0..brute_sample {
        let (t, r) = runouts[next() % runouts.len()];
        let mut b = spot.board.clone();
        b.push(t);
        b.push(r);
        let st = strengths(&b);
        let red: Vec<Vec<f32>> = spot.w.iter().map(|w| {
            let mut v = vec![0f32; NUM_COMBOS];
            for i in 0..NUM_COMBOS {
                if st[i] > 0 && w[i] > 0.0 && next() % 12 == 0 {
                    v[i] = w[i];
                }
            }
            v
        }).collect();
        for p in 0..NP {
            let (q, r_) = ((p + 1) % NP, (p + 2) % NP);
            let (nf, df) = showdown_sums(&st, &red[q], &red[r_], trial % 2 == 0);
            let (nb, db) = showdown_brute(&st, &red[q], &red[r_], trial % 2 == 0);
            for h in 0..NUM_COMBOS {
                for (f, bb) in [(nf[h], nb[h]), (df[h], db[h])] {
                    let rel = (f - bb).abs() / bb.abs().max(1e-12);
                    if bb.abs() > 1e-12 && rel > max_rel {
                        max_rel = rel;
                    }
                }
            }
        }
    }
    res.insert("fast_vs_brute_force".into(), serde_json::json!({"runouts_checked": brute_sample, "max_relative_difference": max_rel,
        "note": "reduced random ranges (~1/12 of combos), alternately q in / out of the showdown"}));
    // full showdown-only values
    let sums: Vec<Vec<(Vec<f64>, Vec<f64>)>> = runouts.par_iter().map(|&(t, r)| {
        let mut b = spot.board.clone();
        b.push(t);
        b.push(r);
        let st = strengths(&b);
        (0..NP).map(|p| showdown_sums(&st, &spot.w[(p + 1) % NP], &spot.w[(p + 2) % NP], true)).collect()
    }).collect();
    let flop_st: Vec<u32> = (0..NUM_COMBOS).map(|i| {
        let (a, b) = cc(i);
        (!spot.board.contains(&a) && !spot.board.contains(&b)) as u32
    }).collect();
    let n_runouts_per_triple = ((49 - 6) * (49 - 7) / 2) as f64;
    let mut total_value = 0f64;
    let mut masses = Vec::new();
    for p in 0..NP {
        let (q, r_) = ((p + 1) % NP, (p + 2) % NP);
        // den on the flop only (all combos equal strength -> den = joint compatible mass)
        let (_, den_flop) = showdown_brute_den(&flop_st, &spot.w[q], &spot.w[r_]);
        let mut num = vec![0f64; NUM_COMBOS];
        let mut den_chk = vec![0f64; NUM_COMBOS];
        for s in &sums {
            for h in 0..NUM_COMBOS {
                num[h] += s[p].0[h];
                den_chk[h] += s[p].1[h];
            }
        }
        // check: sum over runouts of den_R(h) = C(K-6,2) * den_flop(h)
        let mut max_den_rel = 0f64;
        for h in 0..NUM_COMBOS {
            if den_flop[h] > 0.0 {
                max_den_rel = max_den_rel.max((den_chk[h] / (n_runouts_per_triple * den_flop[h]) - 1.0).abs());
            }
        }
        let ev: Vec<f64> = (0..NUM_COMBOS).map(|h| if den_flop[h] > 0.0 { num[h] / (n_runouts_per_triple * den_flop[h]) } else { 0.0 }).collect();
        // class values: den-weighted mean of pot*ev over the class's combos
        let mut cn = vec![0f64; 169];
        let mut cd = vec![0f64; 169];
        for h in 0..NUM_COMBOS {
            if den_flop[h] > 0.0 {
                let (a, b) = cc(h);
                let k = class_index(rank(a), rank(b), suit(a) == suit(b));
                cn[k] += den_flop[h] * ev[h] * spot.pot0;
                cd[k] += den_flop[h];
            }
        }
        let cls: Vec<Option<f64>> = (0..169).map(|k| if cd[k] > 0.0 { Some(cn[k] / cd[k]) } else { None }).collect();
        // range-weighted value (own weights x compatible opponent mass): conservation
        let mass: f64 = (0..NUM_COMBOS).map(|h| spot.w[p][h] as f64 * den_flop[h]).sum();
        let val: f64 = (0..NUM_COMBOS).map(|h| spot.w[p][h] as f64 * den_flop[h] * ev[h] * spot.pot0).sum::<f64>() / mass;
        total_value += val;
        masses.push(mass);
        per_player.push(serde_json::json!({"position": spot.pos[p], "class_gross_showdown_only": cls, "range_value": val,
            "runout_den_identity_max_rel_error": max_den_rel}));
    }
    res.insert("players".into(), serde_json::Value::Array(per_player));
    res.insert("conservation".into(), serde_json::json!({"sum_range_values": total_value, "pot": spot.pot0, "error": total_value - spot.pot0,
        "joint_mass_by_hero_player": masses, "note": "each player's range value is the pot share over the SAME joint (w0 w1 w2, disjoint) mass"}));
    serde_json::Value::Object(res)
}

/// den only (no strengths): joint compatible mass of q, r for each hero combo
fn showdown_brute_den(valid: &[u32], wq: &[f32], wr: &[f32]) -> (Vec<f64>, Vec<f64>) {
    showdown_sums(valid, wq, wr, true)
}

/// Preflop-level exact card-removal 3-way showdown equity per class (hero uniform within the
/// class, opponents' combos by weight, all three hands and the board pairwise disjoint),
/// Monte Carlo over uniformly drawn complete boards; compared with coupled_deck_v1.
fn preflop_equity(t_path: &str, n_boards: usize, seed: u64) -> Result<serde_json::Value, String> {
    let t: serde_json::Value = serde_json::from_slice(&std::fs::read(t_path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let order: Vec<String> = t["postflop_order"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string()).collect();
    let pls: Vec<&serde_json::Value> = order.iter().map(|p| t["players"].as_array().unwrap().iter().find(|x| x["position"] == p.as_str()).unwrap()).collect();
    // opponent weights: class reach spread over the class's combos (no EPS floor: legacy model uses arriving reach)
    let w: Vec<Vec<f32>> = pls.iter().map(|pl| {
        let keep: Vec<f64> = pl["class_keep_fraction"].as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect();
        (0..NUM_COMBOS).map(|i| {
            let (a, b) = cc(i);
            keep[class_index(rank(a), rank(b), suit(a) == suit(b))] as f32
        }).collect()
    }).collect();
    let mut rng = seed;
    let mut next = move || {
        rng = rng.wrapping_add(0x9e3779b97f4a7c15);
        let mut z = rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
        z ^ (z >> 31)
    };
    let boards: Vec<Vec<Card>> = (0..n_boards).map(|_| {
        let mut deck: Vec<Card> = (0..52).collect();
        for i in 0..5 {
            let j = i + (next() as usize) % (52 - i);
            deck.swap(i, j);
        }
        deck[..5].to_vec()
    }).collect();
    let acc: Vec<[Vec<f64>; 6]> = boards.par_iter().map(|b| {
        let st = strengths(b);
        let mut out: [Vec<f64>; 6] = Default::default();
        for p in 0..NP {
            let (n, d) = showdown_sums(&st, &w[(p + 1) % NP], &w[(p + 2) % NP], true);
            let mut cn = vec![0f64; 169];
            let mut cd = vec![0f64; 169];
            for h in 0..NUM_COMBOS {
                if st[h] > 0 {
                    let (a, c) = cc(h);
                    let k = class_index(rank(a), rank(c), suit(a) == suit(c));
                    cn[k] += n[h];
                    cd[k] += d[h];
                }
            }
            out[2 * p] = cn;
            out[2 * p + 1] = cd;
        }
        out
    }).collect();
    let pot = t["pot_bb"].as_f64().unwrap();
    let mut players = Vec::new();
    for p in 0..NP {
        let mut cn = vec![0f64; 169];
        let mut cd = vec![0f64; 169];
        for a in &acc {
            for k in 0..169 {
                cn[k] += a[2 * p][k];
                cd[k] += a[2 * p + 1][k];
            }
        }
        let exact: Vec<f64> = (0..169).map(|k| pot * cn[k] / cd[k]).collect();
        let cdk: Vec<f64> = pls[p]["coupled_deck_gross_f64"].as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect();
        let r: Vec<f64> = pls[p]["class_reach_normalized"].as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect();
        let d: Vec<f64> = (0..169).map(|k| exact[k] - cdk[k]).collect();
        players.push(serde_json::json!({"position": order[p], "exact_card_removal_gross": exact, "coupled_deck_gross": cdk,
            "mean_abs_diff": d.iter().map(|x| x.abs()).sum::<f64>() / 169.0,
            "reach_weighted_abs_diff": (0..169).map(|k| r[k] * d[k].abs()).sum::<f64>(),
            "range_ev_exact": (0..169).map(|k| r[k] * exact[k]).sum::<f64>(), "range_ev_coupled": (0..169).map(|k| r[k] * cdk[k]).sum::<f64>(),
            "max_abs_diff": d.iter().fold(0f64, |m, x| m.max(x.abs()))}));
    }
    Ok(serde_json::json!({"boards": n_boards, "seed": seed, "players": players,
        "note": "range EV of the exact side uses the arriving class reach (class_reach_normalized) as weights, like the legacy check; the exact sums already condition on disjoint hands"}))
}

// ------------------------------------------------------------------ CFR engine
#[derive(Clone, Copy)]
enum Mode {
    Update(u32),
    Avg,
    Br,
}

struct Ptr(*mut f32);
unsafe impl Sync for Ptr {}
unsafe impl Send for Ptr {}

struct Engine {
    g: Game,
    w: Vec<Vec<f32>>,
    flop: Vec<Card>,
    nonblocking: [bool; NP],
    base: Vec<usize>,
    size: Vec<usize>,
    slot_off: Vec<Vec<usize>>,
    regret: Vec<f32>,
    strat: Vec<f32>,
    rest: Vec<Card>,
    /// strengths and ascending order per river instance (turn_i * 48 + river_i)
    river_st: Vec<Vec<u32>>,
    river_order: Vec<Vec<u16>>,
}

impl Engine {
    fn new(spot: &Spot, fold_first: Option<usize>, nonblocking: [bool; NP]) -> Engine {
        let g = build_game(spot.pot0, spot.stack, fold_first);
        let mut base = Vec::new();
        let mut size = Vec::new();
        let mut slot_off = Vec::new();
        let mut tot = 0usize;
        for t in &g.templates {
            let mut off = Vec::new();
            let mut sz = 0usize;
            for &(_, na) in &t.slots {
                off.push(sz);
                sz += na * NUM_COMBOS;
            }
            base.push(tot);
            size.push(sz);
            slot_off.push(off);
            tot += sz * instances(t) as usize;
        }
        let rest = board_cards(&spot.board);
        let mut river_st = Vec::with_capacity(49 * 48);
        let mut river_order = Vec::with_capacity(49 * 48);
        for (ti, &tc) in rest.iter().enumerate() {
            let _ = ti;
            for &rc in rest.iter().filter(|&&c| c != tc) {
                let mut b = spot.board.clone();
                b.push(tc);
                b.push(rc);
                let st = strengths(&b);
                let mut o: Vec<u16> = (0..NUM_COMBOS as u16).filter(|&i| st[i as usize] > 0).collect();
                o.sort_by_key(|&i| st[i as usize]);
                river_st.push(st);
                river_order.push(o);
            }
        }
        Engine { g, w: spot.w.clone(), flop: spot.board.clone(), nonblocking, base, size, slot_off,
                 regret: vec![0.0; tot], strat: vec![0.0; tot], rest, river_st, river_order }
    }

    fn bytes(&self) -> usize {
        (self.regret.len() + self.strat.len()) * 4
    }

    fn inst_of(&self, card: Card, turn_i: Option<usize>) -> (usize, usize) {
        // returns (instance index for the next street, index of the card)
        match turn_i {
            None => {
                let ti = self.rest.iter().position(|&c| c == card).unwrap();
                (ti, ti)
            }
            Some(ti) => {
                let tc = self.rest[ti];
                let ri = self.rest.iter().filter(|&&c| c != tc).position(|&c| c == card).unwrap();
                (ti * 48 + ri, ri)
            }
        }
    }

    fn blockers(&self) -> usize {
        self.nonblocking.iter().filter(|&&b| !b).count()
    }

    /// joint compatible mass of p's opponents (blocking ones) for each hero combo on `board`
    fn den(&self, p: usize, reach: &[Vec<f32>], board: &[Card]) -> Vec<f64> {
        let opp: Vec<usize> = (0..NP).filter(|&q| q != p && !self.nonblocking[q]).collect();
        let mut bm = 0u64;
        for &c in board {
            bm |= 1 << c;
        }
        let valid = |i: usize| {
            let (a, b) = cc(i);
            bm & (1 << a) == 0 && bm & (1 << b) == 0
        };
        if opp.len() == 1 {
            let o = &reach[opp[0]];
            let mut tot = 0f64;
            let mut card = [0f64; 52];
            for i in 0..NUM_COMBOS {
                if valid(i) && o[i] > 0.0 {
                    let (a, b) = cc(i);
                    tot += o[i] as f64;
                    card[a as usize] += o[i] as f64;
                    card[b as usize] += o[i] as f64;
                }
            }
            (0..NUM_COMBOS).map(|h| {
                if !valid(h) {
                    return 0.0;
                }
                let (a, b) = cc(h);
                tot - card[a as usize] - card[b as usize] + o[h] as f64
            }).collect()
        } else {
            let st: Vec<u32> = (0..NUM_COMBOS).map(|i| valid(i) as u32).collect();
            let wq: Vec<f32> = (0..NUM_COMBOS).map(|i| if valid(i) { reach[opp[0]][i] } else { 0.0 }).collect();
            let wr: Vec<f32> = (0..NUM_COMBOS).map(|i| if valid(i) { reach[opp[1]][i] } else { 0.0 }).collect();
            showdown_sums(&st, &wq, &wr, true).1
        }
    }

    /// counterfactual showdown value for p on a complete board (river instance `ri`)
    fn showdown(&self, p: usize, reach: &[Vec<f32>], ri: usize, contrib: &[f64; NP], folded: &[bool; NP]) -> Vec<f64> {
        let st = &self.river_st[ri];
        let pot = self.g.pot0 + contrib.iter().sum::<f64>();
        let opp: Vec<usize> = (0..NP).filter(|&q| q != p && !self.nonblocking[q]).collect();
        if opp.len() == 1 {
            // HU sweep, O(N)
            let o = &reach[opp[0]];
            let order = &self.river_order[ri];
            let mut out = vec![0f64; NUM_COMBOS];
            let (mut lt, mut lt_c) = (0f64, [0f64; 52]);
            let (mut tot, mut tot_c) = (0f64, [0f64; 52]);
            for &i in order {
                let i = i as usize;
                let (a, b) = cc(i);
                tot += o[i] as f64;
                tot_c[a as usize] += o[i] as f64;
                tot_c[b as usize] += o[i] as f64;
            }
            let mut k = 0;
            while k < order.len() {
                let t = st[order[k] as usize];
                let mut e = k;
                let (mut eq, mut eq_c) = (0f64, [0f64; 52]);
                while e < order.len() && st[order[e] as usize] == t {
                    let i = order[e] as usize;
                    let (a, b) = cc(i);
                    eq += o[i] as f64;
                    eq_c[a as usize] += o[i] as f64;
                    eq_c[b as usize] += o[i] as f64;
                    e += 1;
                }
                for &h in &order[k..e] {
                    let h = h as usize;
                    let (a, b) = cc(h);
                    let (a, b) = (a as usize, b as usize);
                    let win = lt - lt_c[a] - lt_c[b];
                    let tie = eq - eq_c[a] - eq_c[b] + o[h] as f64;
                    let all = tot - tot_c[a] - tot_c[b] + o[h] as f64;
                    out[h] = pot * (win + 0.5 * tie) - contrib[p] * all;
                }
                for &i in &order[k..e] {
                    let i = i as usize;
                    let (a, b) = cc(i);
                    lt += o[i] as f64;
                    lt_c[a as usize] += o[i] as f64;
                    lt_c[b as usize] += o[i] as f64;
                }
                k = e;
            }
            out
        } else {
            let (q, r) = (opp[0], opp[1]);
            // active opponents enter the showdown; a folded opponent only blocks
            let (fq, act) = if folded[q] { (q, r) } else if folded[r] { (r, q) } else { (q, r) };
            let both_in = !folded[q] && !folded[r];
            let (n, d) = showdown_sums(st, &reach[fq], &reach[act], both_in);
            (0..NUM_COMBOS).map(|h| pot * n[h] - contrib[p] * d[h]).collect()
        }
    }

    fn strategy(&self, off: usize, na: usize, mode: Mode) -> Vec<f32> {
        let mut sig = vec![0f32; na * NUM_COMBOS];
        let src = match mode {
            Mode::Update(_) => &self.regret,
            _ => &self.strat,
        };
        for h in 0..NUM_COMBOS {
            let mut sum = 0f32;
            for a in 0..na {
                let v = src[off + a * NUM_COMBOS + h];
                let v = if matches!(mode, Mode::Update(_)) { v.max(0.0) } else { v };
                sig[a * NUM_COMBOS + h] = v;
                sum += v;
            }
            for a in 0..na {
                sig[a * NUM_COMBOS + h] = if sum > 0.0 { sig[a * NUM_COMBOS + h] / sum } else { 1.0 / na as f32 };
            }
        }
        sig
    }

    #[allow(clippy::too_many_arguments)]
    fn walk(&self, tpl: usize, node: usize, inst: usize, turn_i: Option<usize>, ri: Option<usize>, board: &[Card],
            p: usize, reach: &[Vec<f32>], mode: Mode, rp: &Ptr, sp: &Ptr) -> Vec<f64> {
        match &self.g.templates[tpl].nodes[node] {
            TNode::Action { player, acts, children, slot, contrib } => {
                let q = *player;
                let na = acts.len();
                let off = self.base[tpl] + inst * self.size[tpl] + self.slot_off[tpl][*slot];
                let sig = self.strategy(off, na, mode);
                if q == p {
                    let mut child_v: Vec<Vec<f64>> = Vec::with_capacity(na);
                    for (a, &c) in children.iter().enumerate() {
                        if acts[a] == Act::Fold {
                            let d = self.den(p, reach, board);
                            child_v.push(d.iter().map(|x| -contrib[p] * x).collect());
                        } else {
                            child_v.push(self.walk(tpl, c, inst, turn_i, ri, board, p, reach, mode, rp, sp));
                        }
                    }
                    let mut v = vec![0f64; NUM_COMBOS];
                    for h in 0..NUM_COMBOS {
                        if matches!(mode, Mode::Br) {
                            v[h] = (0..na).map(|a| child_v[a][h]).fold(f64::NEG_INFINITY, f64::max);
                        } else {
                            v[h] = (0..na).map(|a| sig[a * NUM_COMBOS + h] as f64 * child_v[a][h]).sum();
                        }
                    }
                    if let Mode::Update(t) = mode {
                        let tt = t as f64;
                        let ta = tt.powf(1.5);
                        let (dpos, dneg, dstr) = ((ta / (ta + 1.0)) as f32, 0.5f32, (tt / (tt + 1.0)).powi(2) as f32);
                        unsafe {
                            for a in 0..na {
                                for h in 0..NUM_COMBOS {
                                    let i = off + a * NUM_COMBOS + h;
                                    let r = rp.0.add(i);
                                    let inst_r = (child_v[a][h] - v[h]) as f32;
                                    *r = *r * if *r > 0.0 { dpos } else { dneg } + inst_r;
                                    let sgp = sp.0.add(i);
                                    *sgp = *sgp * dstr + reach[p][h] * sig[a * NUM_COMBOS + h];
                                }
                            }
                        }
                    }
                    v
                } else {
                    let mut v = vec![0f64; NUM_COMBOS];
                    for (a, &c) in children.iter().enumerate() {
                        let mut r2: Vec<Vec<f32>> = reach.to_vec();
                        for h in 0..NUM_COMBOS {
                            r2[q][h] *= sig[a * NUM_COMBOS + h];
                        }
                        let cv = self.walk(tpl, c, inst, turn_i, ri, board, p, &r2, mode, rp, sp);
                        for h in 0..NUM_COMBOS {
                            v[h] += cv[h];
                        }
                    }
                    v
                }
            }
            TNode::FoldWin { winner, contrib, .. } => {
                let pot = self.g.pot0 + contrib.iter().sum::<f64>();
                let u = if *winner == p { pot } else { 0.0 } - contrib[p];
                self.den(p, reach, board).iter().map(|x| u * x).collect()
            }
            TNode::Showdown { contrib, folded } => {
                if board.len() == 5 {
                    self.showdown(p, reach, ri.unwrap(), contrib, folded)
                } else {
                    // all-in runout: deal the remaining cards without betting
                    self.deal(board, turn_i, p, reach, &|nb, nti, nri, r2| {
                        if nb.len() == 5 {
                            self.showdown(p, r2, nri.unwrap(), contrib, folded)
                        } else {
                            self.deal(nb, nti, p, r2, &|nb2, _nti2, nri2, r3| {
                                let _ = nb2;
                                self.showdown(p, r3, nri2.unwrap(), contrib, folded)
                            })
                        }
                    })
                }
            }
            TNode::Next { template } => {
                let nt = *template;
                self.deal(board, turn_i, p, reach, &|nb, nti, nri, r2| {
                    let inst2 = if nb.len() == 4 { nti.unwrap() } else { nri.unwrap() };
                    self.walk(nt, 0, inst2, nti, nri, nb, p, r2, mode, rp, sp)
                })
            }
        }
    }

    /// chance: deal one card to `board` (flop -> turn in parallel), call `f` with the new board,
    /// turn index, river instance and the reach with the dealt card's combos removed;
    /// average with weight 1 / (K - 2 * blockers) over the undealt cards.
    fn deal(&self, board: &[Card], turn_i: Option<usize>, p: usize, reach: &[Vec<f32>],
            f: &(dyn Fn(&[Card], Option<usize>, Option<usize>, &[Vec<f32>]) -> Vec<f64> + Sync)) -> Vec<f64> {
        let _ = p;
        let cards: Vec<Card> = (0..52u8).filter(|c| !board.contains(c)).collect();
        let norm = (cards.len() - 2 * self.blockers()) as f64;
        let one = |c: Card| -> Vec<f64> {
            let mut nb = board.to_vec();
            nb.push(c);
            let r2: Vec<Vec<f32>> = reach.iter().map(|w| {
                let mut v = w.clone();
                for &i in &card_combos()[c as usize] {
                    v[i as usize] = 0.0;
                }
                v
            }).collect();
            let (nti, nri) = if board.len() == 3 {
                (Some(self.inst_of(c, None).0), None)
            } else {
                (turn_i, Some(self.inst_of(c, turn_i).0))
            };
            f(&nb, nti, nri, &r2)
        };
        let parts: Vec<Vec<f64>> = if board.len() == 3 { cards.par_iter().map(|&c| one(c)).collect() } else { cards.iter().map(|&c| one(c)).collect() };
        let mut v = vec![0f64; NUM_COMBOS];
        for part in parts.iter() {
            for h in 0..NUM_COMBOS {
                v[h] += part[h];
            }
        }
        // hero combos containing a dealt card get nothing from that branch (their den is 0 there)
        for x in v.iter_mut() {
            *x /= norm;
        }
        v
    }

    fn root(&self, p: usize, mode: Mode) -> Vec<f64> {
        let rp = Ptr(self.regret.as_ptr() as *mut f32);
        let sp = Ptr(self.strat.as_ptr() as *mut f32);
        self.walk(0, 0, 0, None, None, &self.flop.clone(), p, &self.w, mode, &rp, &sp)
    }

    fn players(&self) -> Vec<usize> {
        let t0 = &self.g.templates[0];
        (0..NP).filter(|&q| !t0.entry.folded[q]).collect()
    }

    /// per player: range value (avg strategies), BR value, gain; conservation
    fn evaluate(&self) -> serde_json::Value {
        let mut rows = Vec::new();
        let mut total = 0f64;
        let mut gains = 0f64;
        for p in self.players() {
            let avg = self.root(p, Mode::Avg);
            let br = self.root(p, Mode::Br);
            let den = self.den(p, &self.w, &self.flop);
            let z: f64 = (0..NUM_COMBOS).map(|h| self.w[p][h] as f64 * den[h]).sum();
            let va: f64 = (0..NUM_COMBOS).map(|h| self.w[p][h] as f64 * avg[h]).sum::<f64>() / z;
            let vb: f64 = (0..NUM_COMBOS).map(|h| self.w[p][h] as f64 * br[h]).sum::<f64>() / z;
            // class values: den-weighted mean over the class's combos (as t2_cont_panel)
            let mut cn = vec![0f64; 169];
            let mut cd = vec![0f64; 169];
            for h in 0..NUM_COMBOS {
                if den[h] > 0.0 {
                    let (a, b) = cc(h);
                    let k = class_index(rank(a), rank(b), suit(a) == suit(b));
                    cn[k] += avg[h];
                    cd[k] += den[h];
                }
            }
            let cls: Vec<Option<f64>> = (0..169).map(|k| if cd[k] > 0.0 { Some(cn[k] / cd[k] + self.g.pot0 * 0.0) } else { None }).collect();
            total += va;
            gains += vb - va;
            rows.push(serde_json::json!({"player": p, "range_value": va, "br_value": vb, "br_gain_bb": vb - va,
                                         "br_gain_pct_pot": (vb - va) / self.g.pot0 * 100.0, "class_gross": cls}));
        }
        // gross convention: utilities are share of the final pot minus postflop contributions
        serde_json::json!({"players": rows, "sum_range_values": total, "pot": self.g.pot0,
                           "conservation_error": total - self.g.pot0,
                           "exploitability_pct_pot": gains / self.players().len() as f64 / self.g.pot0 * 100.0})
    }

    /// aggregate strategy (average) at the first decision of each player on the flop path of checks
    fn root_mix(&self) -> serde_json::Value {
        let t0 = &self.g.templates[0];
        let mut out = Vec::new();
        let mut node = 0usize;
        // follow checks from the root; report every decision met
        for _ in 0..NP {
            if let TNode::Action { player, acts, children, slot, .. } = &t0.nodes[node] {
                let off = self.base[0] + self.slot_off[0][*slot];
                let sig = self.strategy(off, acts.len(), Mode::Avg);
                let w = &self.w[*player];
                let tot: f64 = w.iter().map(|&x| x as f64).sum();
                let mix: Vec<f64> = (0..acts.len()).map(|a| (0..NUM_COMBOS).map(|h| w[h] as f64 * sig[a * NUM_COMBOS + h] as f64).sum::<f64>() / tot).collect();
                out.push(serde_json::json!({"player": player, "actions": acts.iter().map(|x| format!("{:?}", x)).collect::<Vec<_>>(), "mix": mix}));
                match acts.iter().position(|x| *x == Act::Check) {
                    Some(ci) => node = children[ci],
                    None => break,
                }
            } else {
                break;
            }
        }
        serde_json::Value::Array(out)
    }
}

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    match a.get(1).map(|s| s.as_str()) {
        Some("build") => {
            let spot = load_spot(&a[2], &a[3])?;
            let g = build_game(spot.pot0, spot.stack, None);
            let mut r = build_report(&g, a.iter().any(|x| x == "--alloc"));
            r["spot"] = serde_json::json!({"positions": spot.pos, "pot": spot.pot0, "stack": spot.stack, "board": a[3]});
            let g2 = build_game(spot.pot0, spot.stack, Some(0));
            r["hu_degenerate_tree"] = build_report(&g2, false);
            println!("{}", serde_json::to_string_pretty(&r).unwrap());
            Ok(())
        }
        Some("showdown") => {
            let spot = load_spot(&a[2], &a[3])?;
            let n = a.iter().position(|x| x == "--brute-sample").map(|i| a[i + 1].parse().unwrap()).unwrap_or(6);
            let t = std::time::Instant::now();
            let mut r = showdown_test(&spot, n);
            r["seconds"] = serde_json::json!(t.elapsed().as_secs_f64());
            r["board"] = serde_json::json!(a[3]);
            r["labels"] = serde_json::json!(spot.labels);
            println!("{}", serde_json::to_string(&r).unwrap());
            Ok(())
        }
        Some("solve") => {
            let spot = load_spot(&a[2], &a[3])?;
            let iters: u32 = a[4].parse().map_err(|_| "iters")?;
            let out = &a[5];
            let seat = |name: &str| -> Option<usize> {
                a.iter().position(|x| x == name).map(|i| spot.pos.iter().position(|p| *p == a[i + 1]).expect("seat name"))
            };
            let fold_first = seat("--fold-first");
            let mut nb = [false; NP];
            if let Some(q) = seat("--nonblocking") {
                nb[q] = true;
            }
            let every: u32 = a.iter().position(|x| x == "--every").map(|i| a[i + 1].parse().unwrap()).unwrap_or(25);
            let target: f64 = a.iter().position(|x| x == "--target").map(|i| a[i + 1].parse().unwrap()).unwrap_or(0.3);
            let t0 = std::time::Instant::now();
            let e = Engine::new(&spot, fold_first, nb);
            eprintln!("engine: {:.2} GB, players {:?}, build {:.1}s, rss {:?} kB", e.bytes() as f64 / 1e9, e.players(), t0.elapsed().as_secs_f64(), peak_rss_kb());
            let mut trace = Vec::new();
            let mut last = serde_json::Value::Null;
            for t in 1..=iters {
                for p in e.players() {
                    e.root(p, Mode::Update(t));
                }
                if t % every == 0 || t == iters {
                    let ev = e.evaluate();
                    let x = ev["exploitability_pct_pot"].as_f64().unwrap();
                    eprintln!("it {t} expl {x:.4}% pot, conservation {:.2e}, {:.0}s", ev["conservation_error"].as_f64().unwrap(), t0.elapsed().as_secs_f64());
                    trace.push(serde_json::json!({"iteration": t, "seconds": t0.elapsed().as_secs_f64(), "eval": ev.clone()}));
                    last = ev;
                    if x <= target {
                        break;
                    }
                }
            }
            let res = serde_json::json!({"positions": spot.pos, "board": a[3], "fold_first": fold_first, "nonblocking": nb,
                "bytes": e.bytes(), "peak_rss_kb": peak_rss_kb(), "final": last, "trace": trace, "root_mix": e.root_mix(),
                "labels": spot.labels});
            std::fs::write(out, serde_json::to_vec(&res).unwrap()).map_err(|e| e.to_string())?;
            Ok(())
        }
        Some("preflop-equity") => {
            let seed = a.get(4).and_then(|x| x.parse().ok()).unwrap_or(20260930);
            let r = preflop_equity(&a[2], a[3].parse().map_err(|_| "boards")?, seed)?;
            println!("{}", serde_json::to_string(&r).unwrap());
            Ok(())
        }
        _ => Err("usage: t2_3way build|showdown|preflop-equity|solve ...".into()),
    }
}
