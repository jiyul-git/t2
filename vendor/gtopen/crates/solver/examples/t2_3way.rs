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
    Action { player: usize, acts: Vec<Act>, children: Vec<usize>, slot: usize },
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
        nodes.push(TNode::Action { player: me, acts: acts.clone(), children: vec![], slot });
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
        _ => Err("usage: t2_3way build|showdown|preflop-equity|solve ...".into()),
    }
}
