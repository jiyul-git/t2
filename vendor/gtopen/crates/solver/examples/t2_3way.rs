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
use std::collections::{BTreeMap, HashMap};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Mutex, RwLock};

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
    Action { player: usize, acts: Vec<Act>, children: Vec<usize>, slot: usize, contrib: [f64; NP], nact: usize },
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
    /// One template per distinct betting history: templates are NOT shared between histories
    /// that happen to reach the same state (sharing would merge information sets = imperfect
    /// recall; found by the HU degeneration test, run 2).
    fn template_for(&mut self, entry: State) -> usize {
        let id = self.templates.len();
        self.templates.push(Template { street: entry.street, nodes: vec![], slots: vec![], entry: entry.clone() });
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
        nodes.push(TNode::Action { player: me, acts: acts.clone(), children: vec![], slot, contrib: st.contrib, nact: act.len() });
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

/// HU frontiers of the full game: fold children of 3-active nodes, per street, and the storage
/// (regret + strategy sum, f32) of each frontier subtree including its later-street instances
fn frontier_report(g: &Game) -> serde_json::Value {
    fn sub(g: &Game, t: usize, n: usize) -> u64 {
        match &g.templates[t].nodes[n] {
            TNode::Action { acts, children, .. } => {
                (acts.len() * NUM_COMBOS * 8) as u64 + children.iter().map(|&c| sub(g, t, c)).sum::<u64>()
            }
            TNode::Next { template } => {
                let mult = if g.templates[t].street == 0 { 49 } else { 48 };
                mult * sub(g, *template, 0)
            }
            _ => 0,
        }
    }
    let mut per = [(0u64, 0u64, 0u64); 3]; // count, total bytes, max bytes
    for (t, tp) in g.templates.iter().enumerate() {
        for n in &tp.nodes {
            if let TNode::Action { acts, children, nact, .. } = n {
                if *nact != NP {
                    continue;
                }
                for (a, &c) in children.iter().enumerate() {
                    if acts[a] == Act::Fold {
                        let b = sub(g, t, c);
                        let s = tp.street as usize;
                        per[s].0 += 1;
                        per[s].1 += b;
                        per[s].2 = per[s].2.max(b);
                    }
                }
            }
        }
    }
    let inst = [1u64, 49, 49 * 48];
    let rows: Vec<serde_json::Value> = (0..3).map(|s| serde_json::json!({"street": STREETS[s], "fold_nodes": per[s].0,
        "instances": per[s].0 * inst[s], "bytes_all_instances": per[s].1 * inst[s], "max_frontier_bytes": per[s].2,
        "value_store_bytes_f32_3players": per[s].0 * inst[s] * 3 * NUM_COMBOS as u64 * 4})).collect();
    serde_json::json!({"by_street": rows})
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

// ------------------------------------------------------------------ fast exact 3-player sums
/// Incremental inclusion-exclusion aggregates for Den_{S,T}(h) = sum_{x in S, y in T, x,y,h pairwise
/// disjoint} wq(x) wr(y). insert_* is O(52), a query is O(1).
struct Agg {
    /// dense 52x52 weight matrices of the inserted combos (0 on the diagonal / not inserted)
    mq: Vec<f64>,
    mr: Vec<f64>,
    tq: f64,
    tr: f64,
    cq: [f64; 52],
    cr: [f64; 52],
    dot: f64,
    e: f64,
    ec: [f64; 52],
    g: [f64; 52],
    hh: [f64; 52],
    k: Vec<f64>,
}

impl Agg {
    fn new() -> Self {
        Agg { mq: vec![0.0; 52 * 52], mr: vec![0.0; 52 * 52], tq: 0.0, tr: 0.0, cq: [0.0; 52], cr: [0.0; 52],
              dot: 0.0, e: 0.0, ec: [0.0; 52], g: [0.0; 52], hh: [0.0; 52], k: vec![0.0; 52 * 52] }
    }
    #[inline(always)]
    fn wqs(&self, a: usize, b: usize) -> f64 {
        self.mq[a * 52 + b]
    }
    #[inline(always)]
    fn wrt(&self, a: usize, b: usize) -> f64 {
        self.mr[a * 52 + b]
    }
    fn insert_r(&mut self, x: usize, v: f64) {
        if v == 0.0 {
            return;
        }
        let (x1, x2) = cc(x);
        let (x1, x2) = (x1 as usize, x2 as usize);
        {
            let (q1, q2) = (&self.mq[x1 * 52..x1 * 52 + 52], &self.mq[x2 * 52..x2 * 52 + 52]);
            for a in 0..52 {
                self.g[a] += v * (q1[a] + q2[a]);
            }
            for b in 0..52 {
                if b == x1 || b == x2 {
                    continue;
                }
                self.k[x1 * 52 + b] += v * q2[b];
                self.k[x2 * 52 + b] += v * q1[b];
            }
        }
        self.hh[x1] += v * self.cq[x2];
        self.hh[x2] += v * self.cq[x1];
        self.dot += v * (self.cq[x1] + self.cq[x2]);
        let wqx = self.wqs(x1, x2);
        self.e += v * wqx;
        self.ec[x1] += v * wqx;
        self.ec[x2] += v * wqx;
        self.tr += v;
        self.cr[x1] += v;
        self.cr[x2] += v;
        self.mr[x1 * 52 + x2] = v;
        self.mr[x2 * 52 + x1] = v;
    }
    fn insert_q(&mut self, x: usize, u: f64) {
        if u == 0.0 {
            return;
        }
        let (x1, x2) = cc(x);
        let (x1, x2) = (x1 as usize, x2 as usize);
        self.g[x1] += u * self.cr[x2];
        self.g[x2] += u * self.cr[x1];
        {
            let (r1, r2) = (&self.mr[x1 * 52..x1 * 52 + 52], &self.mr[x2 * 52..x2 * 52 + 52]);
            for i in 0..52 {
                self.hh[i] += u * (r1[i] + r2[i]);
            }
            for a in 0..52 {
                if a == x1 || a == x2 {
                    continue;
                }
                self.k[a * 52 + x1] += u * r2[a];
                self.k[a * 52 + x2] += u * r1[a];
            }
        }
        self.dot += u * (self.cr[x1] + self.cr[x2]);
        let wrx = self.wrt(x1, x2);
        self.e += u * wrx;
        self.ec[x1] += u * wrx;
        self.ec[x2] += u * wrx;
        self.tq += u;
        self.cq[x1] += u;
        self.cq[x2] += u;
        self.mq[x1 * 52 + x2] = u;
        self.mq[x2 * 52 + x1] = u;
    }
    /// Den_{S,T}(h) = sum over x in S, y in T, x, y, h pairwise disjoint of wq(x) wr(y)
    fn den(&self, h: usize) -> f64 {
        let (a, b) = cc(h);
        let (ai, bi) = (a as usize, b as usize);
        let wqh = self.wqs(ai, bi);
        let wrh = self.wrt(ai, bi);
        let q = self.tq - self.cq[ai] - self.cq[bi] + wqh;
        let rh = self.tr - self.cr[ai] - self.cr[bi] + wrh;
        let bb = self.dot - (self.cq[ai] * self.cr[ai] + self.g[ai]) - (self.cq[bi] * self.cr[bi] + self.g[bi]) + wqh * (self.cr[ai] + self.cr[bi]);
        let c = self.e - self.ec[ai] - self.ec[bi] + wqh * wrh;
        let d = (self.hh[ai] - wrh * self.cq[bi] - self.ec[ai] + wrh * wqh - self.k[ai * 52 + bi])
            + (self.hh[bi] - wrh * self.cq[ai] - self.ec[bi] + wrh * wqh - self.k[bi * 52 + ai]);
        q * rh - bb + c + d
    }
}

#[inline(always)]
fn disjoint(h: usize, x: usize) -> bool {
    let (a, b) = cc(h);
    let (c, d) = cc(x);
    a != c && a != d && b != c && b != d
}

/// Same contract as showdown_sums, O(52 N) per call instead of O(N^2).
/// Levels of equal strength E, strictly weaker set L (grows level by level):
///   in showdown: num = Den_{L,L} + (Den_{L,L+E} - Den_{L,L} + Den_{L+E,L+E} - Den_{L,L+E} - Den_{E,E}) / 2 + Den_{E,E} / 3
///   q folded:    num = Den_{All,L} + (Den_{All,L+E} - Den_{All,L}) / 2
/// read off one aggregate before and after inserting the level (r side first, then q side).
fn showdown_sums_fast(st: &[u32], wq: &[f32], wr: &[f32], q_in_showdown: bool) -> (Vec<f64>, Vec<f64>) {
    let mut order: Vec<usize> = (0..NUM_COMBOS).filter(|&i| st[i] > 0).collect();
    order.sort_by_key(|&i| st[i]);
    let mut num = vec![0f64; NUM_COMBOS];
    let mut den = vec![0f64; NUM_COMBOS];
    let mut lo = Agg::new();
    if !q_in_showdown {
        for &i in &order {
            lo.insert_q(i, wq[i] as f64);
        }
    }
    let (mut d0, mut d1) = (vec![0f64; 64], vec![0f64; 64]);
    let mut k = 0;
    while k < order.len() {
        let t = st[order[k]];
        let mut e = k;
        while e < order.len() && st[order[e]] == t {
            e += 1;
        }
        let lvl = &order[k..e];
        if d0.len() < lvl.len() {
            d0.resize(lvl.len(), 0.0);
            d1.resize(lvl.len(), 0.0);
        }
        for (j, &h) in lvl.iter().enumerate() {
            d0[j] = lo.den(h);
        }
        for &i in lvl {
            lo.insert_r(i, wr[i] as f64);
        }
        if !q_in_showdown {
            for (j, &h) in lvl.iter().enumerate() {
                num[h] = 0.5 * (d0[j] + lo.den(h));
            }
        } else {
            for (j, &h) in lvl.iter().enumerate() {
                d1[j] = lo.den(h);
            }
            for &i in lvl {
                lo.insert_q(i, wq[i] as f64);
            }
            // Den_{E,E}: direct for small levels, own aggregate for large ones
            let ee: Vec<f64> = if lvl.len() > 40 {
                let mut a = Agg::new();
                for &i in lvl {
                    a.insert_r(i, wr[i] as f64);
                    a.insert_q(i, wq[i] as f64);
                }
                lvl.iter().map(|&h| a.den(h)).collect()
            } else {
                lvl.iter().map(|&h| {
                    let mut s = 0f64;
                    for &x in lvl {
                        if x == h || wq[x] == 0.0 || !disjoint(h, x) { continue; }
                        for &y in lvl {
                            if y == h || y == x || !disjoint(h, y) || !disjoint(x, y) { continue; }
                            s += wq[x] as f64 * wr[y] as f64;
                        }
                    }
                    s
                }).collect()
            };
            for (j, &h) in lvl.iter().enumerate() {
                let d2 = lo.den(h);
                num[h] = d0[j] + 0.5 * (d2 - d0[j] - ee[j]) + ee[j] / 3.0;
            }
        }
        k = e;
    }
    for &h in &order {
        den[h] = lo.den(h);
    }
    (num, den)
}

/// joint compatible opponent mass per hero combo (all of `valid`), O(52 N)
fn den_fast(valid: &[bool], wq: &[f32], wr: &[f32]) -> Vec<f64> {
    let mut a = Agg::new();
    for i in 0..NUM_COMBOS {
        if valid[i] {
            a.insert_r(i, wr[i] as f64);
            a.insert_q(i, wq[i] as f64);
        }
    }
    (0..NUM_COMBOS).map(|h| if valid[h] { a.den(h) } else { 0.0 }).collect()
}

fn evalcheck(spot: &Spot, n_boards: usize) -> serde_json::Value {
    let rest = board_cards(&spot.board);
    let mut rng = 777u64;
    let mut next = || {
        rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (rng >> 33) as usize
    };
    let (mut max_rel, mut max_rel_brute) = (0f64, 0f64);
    let (mut t_fast, mut t_slow) = (0f64, 0f64);
    let mut calls = 0usize;
    for trial in 0..n_boards {
        let t1 = rest[next() % rest.len()];
        let mut t2 = rest[next() % rest.len()];
        while t2 == t1 {
            t2 = rest[next() % rest.len()];
        }
        let mut b = spot.board.clone();
        b.push(t1);
        b.push(t2);
        let st = strengths(&b);
        for p in 0..NP {
            let (q, r) = (&spot.w[(p + 1) % NP], &spot.w[(p + 2) % NP]);
            for inq in [true, false] {
                let t0 = std::time::Instant::now();
                let (nf, df) = showdown_sums_fast(&st, q, r, inq);
                t_fast += t0.elapsed().as_secs_f64();
                let t0 = std::time::Instant::now();
                let (ns, ds) = showdown_sums(&st, q, r, inq);
                t_slow += t0.elapsed().as_secs_f64();
                calls += 1;
                for h in 0..NUM_COMBOS {
                    for (f, s_) in [(nf[h], ns[h]), (df[h], ds[h])] {
                        if s_.abs() > 1e-9 {
                            max_rel = max_rel.max((f - s_).abs() / s_.abs());
                        }
                    }
                }
            }
        }
        if trial < 2 {
            // brute force on reduced ranges
            let red: Vec<Vec<f32>> = spot.w.iter().map(|w| (0..NUM_COMBOS).map(|i| if st[i] > 0 && next() % 10 == 0 { w[i] } else { 0.0 }).collect()).collect();
            for inq in [true, false] {
                let (nf, df) = showdown_sums_fast(&st, &red[1], &red[2], inq);
                let (nb, db) = showdown_brute(&st, &red[1], &red[2], inq);
                for h in 0..NUM_COMBOS {
                    for (f, s_) in [(nf[h], nb[h]), (df[h], db[h])] {
                        if s_.abs() > 1e-12 {
                            max_rel_brute = max_rel_brute.max((f - s_).abs() / s_.abs());
                        }
                    }
                }
            }
        }
    }
    serde_json::json!({"boards": n_boards, "calls_each": calls, "max_rel_diff_fast_vs_quadratic": max_rel, "max_rel_diff_fast_vs_brute": max_rel_brute,
        "ms_per_call_fast": t_fast / calls as f64 * 1e3, "ms_per_call_quadratic": t_slow / calls as f64 * 1e3, "speedup": t_slow / t_fast})
}

// ------------------------------------------------------------------ CFR engine
#[derive(Clone, Copy)]
enum Mode {
    Update(u32),
    Avg,
    Br,
    /// average strategies, leaf utility 1: reached opponent mass (normaliser of the reduced game)
    Mass,
}

/// one HU frontier (subtree below a fold at a 3-active node) at one runout instance
struct Frontier {
    tpl: usize,
    node: usize,
    inst: usize,
    turn_i: Option<usize>,
    ri: Option<usize>,
    board: Vec<Card>,
    folder: usize,
    reach: Vec<Vec<f32>>,
    vals: Vec<Option<Vec<f64>>>,
}

#[derive(Default)]
struct Counters {
    sd3: AtomicU64,
    sd3_ns: AtomicU64,
    sd2: AtomicU64,
    sd2_ns: AtomicU64,
    den3: AtomicU64,
    den3_ns: AtomicU64,
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
    /// chance support: turn cards, river cards per turn index (full game: every undealt card)
    turns: Vec<Card>,
    rivers: Vec<Vec<Card>>,
    restricted: bool,
    /// active players per (template, slot)
    slot_nact: Vec<Vec<usize>>,
    snap: Vec<f32>,
    /// diagnostic: DCFR-weighted sum over trunk iterations of the frontier average strategies
    /// (the CFR-D-consistent frontier average), frontier slots only
    fsum: Vec<f32>,
    use_snap: AtomicBool,
    cut: AtomicBool,
    fstore: RwLock<BTreeMap<(usize, usize, usize), Frontier>>,
    cnt: Counters,
}

impl Engine {
    fn new(spot: &Spot, fold_first: Option<usize>, nonblocking: [bool; NP], restrict: Option<(Vec<Card>, Vec<Card>)>) -> Engine {
        let g = build_game(spot.pot0, spot.stack, fold_first);
        let rest = board_cards(&spot.board);
        let restricted = restrict.is_some();
        let turns: Vec<Card> = match &restrict {
            Some((t, _)) => t.clone(),
            None => rest.clone(),
        };
        let rivers: Vec<Vec<Card>> = turns.iter().map(|&tc| match &restrict {
            Some((_, r)) => r.iter().cloned().filter(|&c| c != tc).collect(),
            None => rest.iter().cloned().filter(|&c| c != tc).collect(),
        }).collect();
        let nr = rivers[0].len();
        assert!(rivers.iter().all(|r| r.len() == nr), "river support must have equal size per turn");
        let n_inst = |t: &Template| -> usize { match t.street { 0 => 1, 1 => turns.len(), _ => turns.len() * nr } };
        let mut slot_nact = Vec::new();
        for t in &g.templates {
            let mut v = vec![0usize; t.slots.len()];
            for n in &t.nodes {
                if let TNode::Action { slot, nact, .. } = n {
                    v[*slot] = *nact;
                }
            }
            slot_nact.push(v);
        }
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
            tot += sz * n_inst(t);
        }
        let mut river_st = Vec::new();
        let mut river_order = Vec::new();
        for (ti, &tc) in turns.iter().enumerate() {
            for &rc in &rivers[ti] {
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
                 regret: vec![0.0; tot], strat: vec![0.0; tot], rest, river_st, river_order, turns, rivers, restricted, slot_nact,
                 snap: Vec::new(), fsum: Vec::new(), use_snap: AtomicBool::new(false), cut: AtomicBool::new(false), fstore: RwLock::new(BTreeMap::new()),
                 cnt: Counters::default() }
    }

    fn bytes(&self) -> usize {
        (self.regret.len() + self.strat.len()) * 4
    }

    fn inst_of(&self, card: Card, turn_i: Option<usize>) -> (usize, usize) {
        // returns (instance index for the next street, index of the card)
        match turn_i {
            None => {
                let ti = self.turns.iter().position(|&c| c == card).unwrap();
                (ti, ti)
            }
            Some(ti) => {
                let ri = self.rivers[ti].iter().position(|&c| c == card).unwrap();
                (ti * self.rivers[0].len() + ri, ri)
            }
        }
    }

    fn river_board(&self, ri: usize) -> Vec<Card> {
        let nr = self.rivers[0].len();
        let mut b = self.flop.clone();
        b.push(self.turns[ri / nr]);
        b.push(self.rivers[ri / nr][ri % nr]);
        b
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
            let t0 = std::time::Instant::now();
            let vm: Vec<bool> = (0..NUM_COMBOS).map(valid).collect();
            let wq: Vec<f32> = (0..NUM_COMBOS).map(|i| if vm[i] { reach[opp[0]][i] } else { 0.0 }).collect();
            let wr: Vec<f32> = (0..NUM_COMBOS).map(|i| if vm[i] { reach[opp[1]][i] } else { 0.0 }).collect();
            let d = den_fast(&vm, &wq, &wr);
            self.cnt.den3.fetch_add(1, Ordering::Relaxed);
            self.cnt.den3_ns.fetch_add(t0.elapsed().as_nanos() as u64, Ordering::Relaxed);
            d
        }
    }

    /// counterfactual showdown value for p on a complete board (river instance `ri`)
    fn showdown(&self, p: usize, reach: &[Vec<f32>], ri: usize, contrib: &[f64; NP], folded: &[bool; NP], mass: bool) -> Vec<f64> {
        let t0 = std::time::Instant::now();
        let st = &self.river_st[ri];
        let pot = self.g.pot0 + contrib.iter().sum::<f64>();
        let opp: Vec<usize> = (0..NP).filter(|&q| q != p && !self.nonblocking[q]).collect();
        if folded[p] {
            // folder carried through (reduced game): constant utility times the reached mass
            let vm: Vec<bool> = st.iter().map(|&x| x > 0).collect();
            let d = if opp.len() == 2 { den_fast(&vm, &reach[opp[0]], &reach[opp[1]]) } else {
                self.den(p, reach, &self.river_board(ri))
            };
            self.cnt.den3.fetch_add(1, Ordering::Relaxed);
            self.cnt.den3_ns.fetch_add(t0.elapsed().as_nanos() as u64, Ordering::Relaxed);
            let u = if mass { 1.0 } else { -contrib[p] };
            return d.iter().map(|x| u * x).collect();
        }
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
                    out[h] = if mass { all } else { pot * (win + 0.5 * tie) - contrib[p] * all };
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
            self.cnt.sd2.fetch_add(1, Ordering::Relaxed);
            self.cnt.sd2_ns.fetch_add(t0.elapsed().as_nanos() as u64, Ordering::Relaxed);
            out
        } else {
            let (q, r) = (opp[0], opp[1]);
            // active opponents enter the showdown; a folded opponent only blocks
            let (fq, act) = if folded[q] { (q, r) } else if folded[r] { (r, q) } else { (q, r) };
            let both_in = !folded[q] && !folded[r];
            let (n, d) = showdown_sums_fast(st, &reach[fq], &reach[act], both_in);
            let out = (0..NUM_COMBOS).map(|h| if mass { d[h] } else { pot * n[h] - contrib[p] * d[h] }).collect();
            self.cnt.sd3.fetch_add(1, Ordering::Relaxed);
            self.cnt.sd3_ns.fetch_add(t0.elapsed().as_nanos() as u64, Ordering::Relaxed);
            out
        }
    }

    fn strategy(&self, off: usize, na: usize, mode: Mode) -> Vec<f32> {
        let mut sig = vec![0f32; na * NUM_COMBOS];
        let src = match mode {
            Mode::Update(_) if self.use_snap.load(Ordering::Relaxed) => &self.snap,
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
            TNode::Action { player, acts, children, slot, contrib, nact } => {
                let q = *player;
                let na = acts.len();
                let off = self.base[tpl] + inst * self.size[tpl] + self.slot_off[tpl][*slot];
                let sig = self.strategy(off, na, mode);
                if q == p {
                    let mut child_v: Vec<Vec<f64>> = Vec::with_capacity(na);
                    for (a, &c) in children.iter().enumerate() {
                        if acts[a] == Act::Fold && self.restricted {
                            // reduced game: later cards can still collide with the folder's hand, so the
                            // folder's (constant) utility has to be carried through the rest of the tree
                            if *nact == NP && self.cut.load(Ordering::Relaxed) {
                                let fs = self.fstore.read().unwrap();
                                let fr = fs.get(&(tpl, c, inst)).expect("frontier value missing");
                                child_v.push(fr.vals[p].clone().expect("folder value"));
                            } else {
                                let mut r2: Vec<Vec<f32>> = reach.to_vec();
                                if matches!(mode, Mode::Update(_)) {
                                    for h in 0..NUM_COMBOS {
                                        r2[p][h] *= sig[a * NUM_COMBOS + h];
                                    }
                                }
                                child_v.push(self.walk(tpl, c, inst, turn_i, ri, board, p, &r2, mode, rp, sp));
                            }
                        } else if acts[a] == Act::Fold {
                            let d = self.den(p, reach, board);
                            let u = if matches!(mode, Mode::Mass) { 1.0 } else { -contrib[p] };
                            child_v.push(d.iter().map(|x| u * x).collect());
                        } else {
                            // own reach scaled by the action probability: it weights the strategy
                            // sums below (counterfactual values never use the traverser's own reach)
                            let mut r2: Vec<Vec<f32>> = reach.to_vec();
                            if matches!(mode, Mode::Update(_)) {
                                for h in 0..NUM_COMBOS {
                                    r2[p][h] *= sig[a * NUM_COMBOS + h];
                                }
                            }
                            child_v.push(self.walk(tpl, c, inst, turn_i, ri, board, p, &r2, mode, rp, sp));
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
                    let cut = *nact == NP && self.cut.load(Ordering::Relaxed);
                    for (a, &c) in children.iter().enumerate() {
                        if cut && acts[a] == Act::Fold {
                            // factorized trunk: the frontier's value is fixed for this trunk iteration
                            let fs = self.fstore.read().unwrap();
                            let fr = fs.get(&(tpl, c, inst)).expect("frontier value missing");
                            let fv = fr.vals[p].as_ref().expect("frontier value for player");
                            for h in 0..NUM_COMBOS {
                                v[h] += fv[h];
                            }
                            continue;
                        }
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
                let u = if matches!(mode, Mode::Mass) { 1.0 } else { (if *winner == p { pot } else { 0.0 }) - contrib[p] };
                self.den(p, reach, board).iter().map(|x| u * x).collect()
            }
            TNode::Showdown { contrib, folded } => {
                let m = matches!(mode, Mode::Mass);
                if board.len() == 5 {
                    self.showdown(p, reach, ri.unwrap(), contrib, folded, m)
                } else {
                    // all-in runout: deal the remaining cards without betting
                    self.deal(board, turn_i, p, reach, &|nb, nti, nri, r2| {
                        if nb.len() == 5 {
                            self.showdown(p, r2, nri.unwrap(), contrib, folded, m)
                        } else {
                            self.deal(nb, nti, p, r2, &|nb2, _nti2, nri2, r3| {
                                let _ = nb2;
                                self.showdown(p, r3, nri2.unwrap(), contrib, folded, m)
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
        let cards: Vec<Card> = if board.len() == 3 { self.turns.clone() } else { self.rivers[turn_i.unwrap()].clone() };
        // reduced game: uniform over the listed cards, colliding combos lose their mass
        let norm = if self.restricted { cards.len() as f64 } else { (cards.len() - 2 * self.blockers()) as f64 };
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
            let mass = self.root(p, Mode::Mass);
            let den = self.den(p, &self.w, &self.flop);
            let z: f64 = (0..NUM_COMBOS).map(|h| self.w[p][h] as f64 * den[h]).sum();
            let zm: f64 = (0..NUM_COMBOS).map(|h| self.w[p][h] as f64 * mass[h]).sum();
            // range value conditional on the reached mass (= z in the full game); BR gain per flop mass
            let va: f64 = (0..NUM_COMBOS).map(|h| self.w[p][h] as f64 * avg[h]).sum::<f64>() / zm;
            let gain: f64 = (0..NUM_COMBOS).map(|h| self.w[p][h] as f64 * (br[h] - avg[h])).sum::<f64>() / z;
            let vb = va + gain;
            // class values: den-weighted mean over the class's combos (as t2_cont_panel)
            let mut cn = vec![0f64; 169];
            let mut cd = vec![0f64; 169];
            for h in 0..NUM_COMBOS {
                if mass[h] > 0.0 {
                    let (a, b) = cc(h);
                    let k = class_index(rank(a), rank(b), suit(a) == suit(b));
                    cn[k] += avg[h];
                    cd[k] += mass[h];
                }
            }
            let cls: Vec<Option<f64>> = (0..169).map(|k| if cd[k] > 0.0 { Some(cn[k] / cd[k] + self.g.pot0 * 0.0) } else { None }).collect();
            total += va;
            gains += vb - va;
            rows.push(serde_json::json!({"player": p, "range_value": va, "br_value": vb, "br_gain_bb": vb - va, "reached_mass_fraction": zm / z,
                                         "br_gain_pct_pot": (vb - va) / self.g.pot0 * 100.0, "class_gross": cls}));
        }
        // gross convention: utilities are share of the final pot minus postflop contributions
        serde_json::json!({"players": rows, "sum_range_values": total, "pot": self.g.pot0,
                           "conservation_error": total - self.g.pot0,
                           "exploitability_pct_pot": gains / self.players().len() as f64 / self.g.pot0 * 100.0})
    }

    /// aggregate average strategy (weights: arriving range, no own earlier action on these lines)
    /// at the decisions met on the flop lines: root, check, check-check, bet, bet-call, bet-fold
    fn root_mix(&self) -> serde_json::Value {
        let t0 = &self.g.templates[0];
        let lines: [&[&str]; 6] = [&[], &["Check"], &["Check", "Check"], &["Bet"], &["Bet", "Call"], &["Bet", "Fold"]];
        let mut out = Vec::new();
        'l: for line in lines {
            let mut node = 0usize;
            for step in line {
                match &t0.nodes[node] {
                    TNode::Action { acts, children, .. } => {
                        match acts.iter().position(|x| format!("{:?}", x).starts_with(step)) {
                            Some(k) => node = children[k],
                            None => continue 'l,
                        }
                    }
                    _ => continue 'l,
                }
            }
            if let TNode::Action { player, acts, slot, nact, .. } = &t0.nodes[node] {
                let off = self.base[0] + self.slot_off[0][*slot];
                let sig = self.strategy(off, acts.len(), Mode::Avg);
                let w = &self.w[*player];
                let tot: f64 = w.iter().map(|&x| x as f64).sum();
                let mix: Vec<f64> = (0..acts.len()).map(|a| (0..NUM_COMBOS).map(|h| w[h] as f64 * sig[a * NUM_COMBOS + h] as f64).sum::<f64>() / tot).collect();
                out.push(serde_json::json!({"line": line.join("-"), "player": player, "active": nact,
                    "actions": acts.iter().map(|x| format!("{:?}", x)).collect::<Vec<_>>(), "mix": mix}));
            }
        }
        serde_json::Value::Array(out)
    }

    // ---------------------------------------------------------------- HU-frontier factorization
    fn cards_after(&self, board: &[Card], turn_i: Option<usize>) -> Vec<Card> {
        if board.len() == 3 { self.turns.clone() } else { self.rivers[turn_i.unwrap()].clone() }
    }

    /// walk the trunk with `mode`'s strategies (Update(_) = current regret matching, Avg = average)
    /// and record the arriving reach of every frontier (fold child of a 3-active node) per runout
    #[allow(clippy::too_many_arguments)]
    fn collect(&self, tpl: usize, node: usize, inst: usize, turn_i: Option<usize>, ri: Option<usize>, board: &[Card],
               reach: &[Vec<f32>], mode: Mode, out: &Mutex<Vec<Frontier>>) {
        match &self.g.templates[tpl].nodes[node] {
            TNode::Action { player, acts, children, slot, nact, .. } => {
                if *nact < NP {
                    return;
                }
                let na = acts.len();
                let off = self.base[tpl] + inst * self.size[tpl] + self.slot_off[tpl][*slot];
                let sig = self.strategy(off, na, mode);
                for (a, &c) in children.iter().enumerate() {
                    let mut r2: Vec<Vec<f32>> = reach.to_vec();
                    for h in 0..NUM_COMBOS {
                        r2[*player][h] *= sig[a * NUM_COMBOS + h];
                    }
                    if acts[a] == Act::Fold {
                        out.lock().unwrap().push(Frontier { tpl, node: c, inst, turn_i, ri, board: board.to_vec(), folder: *player,
                                                            reach: r2, vals: vec![None; NP] });
                    } else {
                        self.collect(tpl, c, inst, turn_i, ri, board, &r2, mode, out);
                    }
                }
            }
            TNode::Next { template } => {
                let nt = *template;
                let one = |c: Card| {
                    let mut nb = board.to_vec();
                    nb.push(c);
                    let r2: Vec<Vec<f32>> = reach.iter().map(|w| {
                        let mut v = w.clone();
                        for &i in &card_combos()[c as usize] {
                            v[i as usize] = 0.0;
                        }
                        v
                    }).collect();
                    let (nti, nri, inst2) = if board.len() == 3 {
                        let ti = self.inst_of(c, None).0;
                        (Some(ti), None, ti)
                    } else {
                        let r = self.inst_of(c, turn_i).0;
                        (turn_i, Some(r), r)
                    };
                    self.collect(nt, 0, inst2, nti, nri, &nb, &r2, mode, out);
                };
                let cards = self.cards_after(board, turn_i);
                if board.len() == 3 { cards.par_iter().for_each(|&c| one(c)) } else { cards.iter().for_each(|&c| one(c)) }
            }
            _ => {}
        }
    }

    /// ranges (offset, length) of every 2-active slot instance
    fn frontier_ranges(&self) -> Vec<(usize, usize)> {
        let mut v = Vec::new();
        for (t, tp) in self.g.templates.iter().enumerate() {
            let n = match tp.street { 0 => 1, 1 => self.turns.len(), _ => self.turns.len() * self.rivers[0].len() };
            for (sl, &(_, na)) in tp.slots.iter().enumerate() {
                if self.slot_nact[t][sl] != NP {
                    for inst in 0..n {
                        v.push((self.base[t] + inst * self.size[t] + self.slot_off[t][sl], na * NUM_COMBOS));
                    }
                }
            }
        }
        v
    }

    /// fsum = fsum * (t/(t+1))^2 + strat / W, W = DCFR weight total of `inner` iterations (same decay as the trunk)
    fn accumulate_frontier_avg(&mut self, t: u32, inner: u32) {
        if self.fsum.is_empty() {
            self.fsum = vec![0.0; self.strat.len()];
        }
        let mut w = 0f64;
        for j in 1..=inner {
            let jj = j as f64;
            w = w * (jj / (jj + 1.0)).powi(2) + 1.0;
        }
        let tt = t as f64;
        let d = (tt / (tt + 1.0)).powi(2) as f32;
        let inv = (1.0 / w) as f32;
        for (o, l) in self.frontier_ranges() {
            for i in o..o + l {
                self.fsum[i] = self.fsum[i] * d + self.strat[i] * inv;
            }
        }
    }

    /// put the accumulated CFR-D frontier average into the strategy sums (evaluation only)
    fn load_frontier_avg(&mut self) {
        for (o, l) in self.frontier_ranges() {
            self.strat[o..o + l].copy_from_slice(&self.fsum[o..o + l]);
        }
    }

    /// zero regrets and strategy sums of every 2-active slot (all frontier subtrees)
    fn reset_frontiers(&mut self) {
        for (t, tp) in self.g.templates.iter().enumerate() {
            let n = match tp.street { 0 => 1, 1 => self.turns.len(), _ => self.turns.len() * self.rivers[0].len() };
            for (sl, &(_, na)) in tp.slots.iter().enumerate() {
                if self.slot_nact[t][sl] == NP {
                    continue;
                }
                for inst in 0..n {
                    let o = self.base[t] + inst * self.size[t] + self.slot_off[t][sl];
                    self.regret[o..o + na * NUM_COMBOS].fill(0.0);
                    self.strat[o..o + na * NUM_COMBOS].fill(0.0);
                }
            }
        }
    }

    /// synchronous re-solve: arriving reaches of ALL frontiers from one snapshot of the trunk
    /// (`mode`), every frontier reset and solved `inner` DCFR iterations on its own (exact HU
    /// subgame, the folder only blocks), then its values fixed for both active players.
    /// Returns (seconds collect, seconds solve+values, number of frontiers).
    fn resolve_frontiers(&mut self, mode: Mode, inner: u32, with_values: bool) -> (f64, f64, usize) {
        let t0 = std::time::Instant::now();
        let out = Mutex::new(Vec::new());
        self.collect(0, 0, 0, None, None, &self.flop.clone(), &self.w, mode, &out);
        let fr = out.into_inner().unwrap();
        let tc = t0.elapsed().as_secs_f64();
        self.reset_frontiers();
        let t1 = std::time::Instant::now();
        let rp = Ptr(self.regret.as_ptr() as *mut f32);
        let sp = Ptr(self.strat.as_ptr() as *mut f32);
        let me = &*self;
        let solved: Vec<Frontier> = fr.into_par_iter().map(|mut f| {
            let act: Vec<usize> = (0..NP).filter(|&q| q != f.folder).collect();
            for j in 1..=inner {
                for &p in &act {
                    me.walk(f.tpl, f.node, f.inst, f.turn_i, f.ri, &f.board, p, &f.reach, Mode::Update(j), &rp, &sp);
                }
            }
            if with_values {
                let who: Vec<usize> = if me.restricted { (0..NP).collect() } else { act.clone() };
                for &p in &who {
                    f.vals[p] = Some(me.walk(f.tpl, f.node, f.inst, f.turn_i, f.ri, &f.board, p, &f.reach, Mode::Avg, &rp, &sp));
                }
            }
            f
        }).collect();
        let n = solved.len();
        let mut fs = self.fstore.write().unwrap();
        fs.clear();
        for f in solved {
            fs.insert((f.tpl, f.node, f.inst), f);
        }
        (tc, t1.elapsed().as_secs_f64(), n)
    }

    /// inner-solve residual of every stored frontier (its current average strategy against its stored
    /// arriving reach): per active player p, gap_p = sum_h reach_p(h) (BR_p(h) - AVG_p(h)); mass = joint
    /// arriving mass sum_h reach_a(h) den_a(h). Values are per flop mass z (bb, comparable to BR gains).
    fn frontier_residuals(&self) -> serde_json::Value {
        let rp = Ptr(self.regret.as_ptr() as *mut f32);
        let sp = Ptr(self.strat.as_ptr() as *mut f32);
        let den0 = self.den(0, &self.w, &self.flop);
        let z: f64 = (0..NUM_COMBOS).map(|h| self.w[0][h] as f64 * den0[h]).sum();
        let fs = self.fstore.read().unwrap();
        let fr: Vec<&Frontier> = fs.values().collect();
        let rows: Vec<serde_json::Value> = fr.par_iter().map(|f| {
            let act: Vec<usize> = (0..NP).filter(|&q| q != f.folder).collect();
            // chance probability of the frontier's runout (the walk divides at each deal)
            let norm = |k: usize| if self.restricted { k as f64 } else { (k - 2 * self.blockers()) as f64 };
            let mut cw = 1.0;
            if f.board.len() >= 4 {
                cw /= norm(self.turns.len());
            }
            if f.board.len() == 5 {
                cw /= norm(self.rivers[0].len());
            }
            let z = z / cw;
            let d = self.den(act[0], &f.reach, &f.board);
            let mass: f64 = (0..NUM_COMBOS).map(|h| f.reach[act[0]][h] as f64 * d[h]).sum::<f64>() / z;
            let mut gaps = Vec::new();
            for &p in &act {
                let br = self.walk(f.tpl, f.node, f.inst, f.turn_i, f.ri, &f.board, p, &f.reach, Mode::Br, &rp, &sp);
                let av = self.walk(f.tpl, f.node, f.inst, f.turn_i, f.ri, &f.board, p, &f.reach, Mode::Avg, &rp, &sp);
                let g: f64 = (0..NUM_COMBOS).map(|h| f.reach[p][h] as f64 * (br[h] - av[h])).sum::<f64>() / z;
                gaps.push(serde_json::json!({"player": p, "gap_bb": g}));
            }
            serde_json::json!({"tpl": f.tpl, "node": f.node, "inst": f.inst, "street": f.board.len() - 3, "folder": f.folder,
                               "mass": mass, "gaps": gaps})
        }).collect();
        serde_json::Value::Array(rows)
    }

    fn counters(&self) -> serde_json::Value {
        let c = &self.cnt;
        let g = |a: &AtomicU64| a.load(Ordering::Relaxed);
        serde_json::json!({"showdown3_calls": g(&c.sd3), "showdown3_seconds": g(&c.sd3_ns) as f64 / 1e9,
            "showdown2_calls": g(&c.sd2), "showdown2_seconds": g(&c.sd2_ns) as f64 / 1e9,
            "den3_calls": g(&c.den3), "den3_seconds": g(&c.den3_ns) as f64 / 1e9})
    }

    /// bytes of trunk (3-active) and frontier (2-active) storage
    fn bytes_split(&self) -> (usize, usize) {
        let (mut tr, mut fr) = (0usize, 0usize);
        for (t, tp) in self.g.templates.iter().enumerate() {
            let n = match tp.street { 0 => 1, 1 => self.turns.len(), _ => self.turns.len() * self.rivers[0].len() };
            for (sl, &(_, na)) in tp.slots.iter().enumerate() {
                let b = 2 * 4 * na * NUM_COMBOS * n;
                if self.slot_nact[t][sl] == NP { tr += b } else { fr += b }
            }
        }
        (tr, fr)
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
            r["frontiers"] = frontier_report(&g);
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
            let arg = |name: &str| a.iter().position(|x| x == name).map(|i| a[i + 1].clone());
            let seat = |name: &str| -> Option<usize> { arg(name).map(|v| spot.pos.iter().position(|p| *p == v).expect("seat name")) };
            let fold_first = seat("--fold-first");
            let mut nb = [false; NP];
            if let Some(q) = seat("--nonblocking") {
                nb[q] = true;
            }
            let every: u32 = arg("--every").map(|v| v.parse().unwrap()).unwrap_or(25);
            let target: f64 = arg("--target").map(|v| v.parse().unwrap()).unwrap_or(0.3);
            let cards = |v: String| -> Vec<Card> { v.split(',').map(|c| card_from_str(c).unwrap()).collect() };
            let restrict = match (arg("--turns"), arg("--rivers")) {
                (Some(t), Some(r)) => Some((cards(t), cards(r))),
                (None, None) => None,
                _ => return Err("--turns and --rivers go together".into()),
            };
            // mono-alt (default, B2), mono-sim (all players from one snapshot), factor (HU frontiers)
            let scheme = arg("--scheme").unwrap_or_else(|| "mono-alt".into());
            let inner: u32 = arg("--inner").map(|v| v.parse().unwrap()).unwrap_or(100);
            // factor checkpoints: "resolve" (registered: frontiers re-solved against the trunk-average reach) or
            // "cfrd-avg" (diagnostic: frontier average strategies accumulated over trunk iterations)
            let feval = arg("--frontier-eval").unwrap_or_else(|| "resolve".into());
            let t0 = std::time::Instant::now();
            let mut e = Engine::new(&spot, fold_first, nb, restrict.clone());
            let (btr, bfr) = e.bytes_split();
            eprintln!("engine: {:.3} GB (trunk {:.3}, frontier {:.3}), players {:?}, scheme {scheme}, build {:.1}s, rss {:?} kB",
                      e.bytes() as f64 / 1e9, btr as f64 / 1e9, bfr as f64 / 1e9, e.players(), t0.elapsed().as_secs_f64(), peak_rss_kb());
            let mut trace = Vec::new();
            let mut last = serde_json::Value::Null;
            let (mut s_collect, mut s_front, mut s_trunk, mut s_eval) = (0f64, 0f64, 0f64, 0f64);
            let mut n_front = 0usize;
            let mut resid_iter = serde_json::Value::Null;
            for t in 1..=iters {
                match scheme.as_str() {
                    "mono-alt" => {
                        let t1 = std::time::Instant::now();
                        for p in e.players() {
                            e.root(p, Mode::Update(t));
                        }
                        s_trunk += t1.elapsed().as_secs_f64();
                    }
                    "mono-sim" => {
                        let t1 = std::time::Instant::now();
                        e.snap = e.regret.clone();
                        e.use_snap.store(true, Ordering::Relaxed);
                        for p in e.players() {
                            e.root(p, Mode::Update(t));
                        }
                        e.use_snap.store(false, Ordering::Relaxed);
                        s_trunk += t1.elapsed().as_secs_f64();
                    }
                    "factor" => {
                        let (c, f, n) = e.resolve_frontiers(Mode::Update(0), inner, true);
                        s_collect += c;
                        s_front += f;
                        n_front = n;
                        if feval != "resolve" {
                            e.accumulate_frontier_avg(t, inner);
                        }
                        if feval == "both" && (t % every == 0 || t == iters) {
                            let t1 = std::time::Instant::now();
                            resid_iter = e.frontier_residuals();
                            eprintln!("it {t} residuals (iteration solve) {:.1}s", t1.elapsed().as_secs_f64());
                        }
                        let t1 = std::time::Instant::now();
                        // trunk regrets of all players from the same snapshot; frontier values fixed
                        e.snap = e.regret.clone();
                        e.use_snap.store(true, Ordering::Relaxed);
                        e.cut.store(true, Ordering::Relaxed);
                        for p in e.players() {
                            e.root(p, Mode::Update(t));
                        }
                        e.cut.store(false, Ordering::Relaxed);
                        e.use_snap.store(false, Ordering::Relaxed);
                        s_trunk += t1.elapsed().as_secs_f64();
                    }
                    _ => return Err(format!("unknown scheme {scheme}")),
                }
                if t % every == 0 || t == iters {
                    let t1 = std::time::Instant::now();
                    let mut ev_cfrd = serde_json::Value::Null;
                    if scheme == "factor" && feval == "both" {
                        e.load_frontier_avg();
                        ev_cfrd = e.evaluate();
                        ev_cfrd["root_mix"] = e.root_mix();
                        eprintln!("it {t} [cfrd-avg frontier] expl {:.4}% pot, conservation {:.2e}", ev_cfrd["exploitability_pct_pot"].as_f64().unwrap(),
                                  ev_cfrd["conservation_error"].as_f64().unwrap());
                    }
                    if scheme == "factor" && feval == "cfrd-avg" {
                        e.load_frontier_avg();
                    } else if scheme == "factor" {
                        // final strategy: trunk average + frontiers re-solved against the trunk average reach
                        e.resolve_frontiers(Mode::Avg, inner, false);
                    }
                    let resid_ck = if scheme == "factor" && feval == "both" { e.frontier_residuals() } else { serde_json::Value::Null };
                    let ev = e.evaluate();
                    s_eval += t1.elapsed().as_secs_f64();
                    let x = ev["exploitability_pct_pot"].as_f64().unwrap();
                    eprintln!("it {t} expl {x:.4}% pot, conservation {:.2e}, {:.0}s (collect {s_collect:.1} frontier {s_front:.1} trunk {s_trunk:.1} eval {s_eval:.1}) rss {:?}",
                              ev["conservation_error"].as_f64().unwrap(), t0.elapsed().as_secs_f64(), peak_rss_kb());
                    trace.push(serde_json::json!({"iteration": t, "seconds": t0.elapsed().as_secs_f64(), "eval": ev.clone(), "root_mix": e.root_mix(), "eval_cfrd_avg": ev_cfrd,
                        "frontier_residual_checkpoint_resolve": resid_ck, "frontier_residual_iteration_solve": resid_iter.clone(),
                        "time_split": {"collect": s_collect, "frontier_solve": s_front, "trunk_update": s_trunk, "evaluation": s_eval}}));
                    last = ev;
                    // partial result at every checkpoint (output only; the computation is unchanged)
                    let part = serde_json::json!({"positions": spot.pos, "board": a[3], "scheme": scheme, "inner": inner, "partial": true,
                        "bytes": e.bytes(), "bytes_trunk": btr, "bytes_frontier": bfr, "frontiers": n_front, "peak_rss_kb": peak_rss_kb(),
                        "final": last, "trace": trace, "root_mix": e.root_mix(), "counters": e.counters(),
                        "time_split": {"collect": s_collect, "frontier_solve": s_front, "trunk_update": s_trunk, "evaluation": s_eval}});
                    std::fs::write(format!("{out}.partial"), serde_json::to_vec(&part).unwrap()).map_err(|e| e.to_string())?;
                    if x <= target {
                        break;
                    }
                }
            }
            let res = serde_json::json!({"positions": spot.pos, "board": a[3], "fold_first": fold_first, "nonblocking": nb,
                "scheme": scheme, "inner": inner, "frontier_eval": feval, "restrict": restrict.as_ref().map(|(t, r)| serde_json::json!({"turns": t, "rivers": r})),
                "bytes": e.bytes(), "bytes_trunk": btr, "bytes_frontier": bfr, "frontiers": n_front,
                "peak_rss_kb": peak_rss_kb(), "final": last, "trace": trace, "root_mix": e.root_mix(), "counters": e.counters(),
                "time_split": {"collect": s_collect, "frontier_solve": s_front, "trunk_update": s_trunk, "evaluation": s_eval},
                "labels": spot.labels});
            std::fs::write(out, serde_json::to_vec(&res).unwrap()).map_err(|e| e.to_string())?;
            Ok(())
        }
        Some("evalcheck") => {
            let spot = load_spot(&a[2], &a[3])?;
            let r = evalcheck(&spot, a.get(4).and_then(|x| x.parse().ok()).unwrap_or(10));
            println!("{}", serde_json::to_string_pretty(&r).unwrap());
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
