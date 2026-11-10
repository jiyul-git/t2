//! Full-tree terminal export for the ft<stack> runs (tools/gto_fulltree/ft60.py `export`).
//!   [T2_CONT_FILE=<manifest>] t2_ft_export <config.json> <save.gtop | -> <jobs.txt> <out.jsonl>
//! jobs.txt: one action line per row, "Pos:Label|Pos:Label|..." (tree-dump labels, e.g. "HJ:Raise 2.5|BB:3-bet 8.8")
//! or "Pos:kind[@to]|..." (loop labels, e.g. "HJ:raise@2.500000|BB:call@2.500000"). Every action from the root is listed (folds too).
//! save.gtop "-": build the tree only (node numbers; no strategy, reaches = root, no gross values).
//! out.jsonl: one row per job: line, kind ("pot_share" | "other"), node, path, live (seat mask), pot_bb (= sum of invested incl. ante),
//! invested[seat], seats[] for live seats: {seat, position, reach[169] (average-strategy class reach, combos/1326 x action probs),
//! static_gross (table bypassed), used_gross (T2_CONT_FILE tables applied)} -- gross values only for pot-share terminals and a save.gtop.
use solver::preflop::equity::EquityTable;
use solver::preflop::{PreflopConfig, PreflopSolver};
use std::sync::Arc;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 5 {
        return Err("config save.gtop|- jobs.txt out.jsonl".into());
    }
    let cfg: PreflopConfig = serde_json::from_str(&std::fs::read_to_string(&a[1]).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let eq = Arc::new(EquityTable::build(samples));
    let tree_only = a[2] == "-";
    let s = if tree_only { PreflopSolver::new(cfg, eq)? } else { PreflopSolver::load_game(&a[2], eq)? };
    #[cfg(feature = "t2-cont")]
    solver::preflop::t2cont::validate(&s)?;
    let jobs = std::fs::read_to_string(&a[3]).map_err(|e| e.to_string())?;
    let mut out = String::new();
    for spec in jobs.lines().map(|l| l.trim()).filter(|l| !l.is_empty()) {
        let mut path = Vec::new();
        let mut node = 0usize;
        for item in spec.split('|') {
            let (pos, act) = item.split_once(':').ok_or(format!("bad item {item}"))?;
            let nd = &s.nodes[node];
            if nd.kind != 0 {
                return Err(format!("line ends early at {item} ({spec})"));
            }
            if s.cfg.positions[nd.actor as usize] != pos {
                return Err(format!("actor {} != {pos} in {spec}", s.cfg.positions[nd.actor as usize]));
            }
            let (kind, to) = match act.split_once('@') {
                Some((k, t)) => (Some(k), Some(t.parse::<f64>().map_err(|_| format!("bad amount {item}"))?)),
                None if ["fold", "check", "call", "raise", "jam"].contains(&act) => (Some(act), None),
                None => (None, None),
            };
            let idx = nd.actions.iter().position(|x| match kind {
                None => x.label == act,
                Some(k) => x.kind == k && to.map_or(true, |t| (x.to - t).abs() < 1e-6),
            }).ok_or(format!("no action {item} at node {node} ({spec})"))?;
            path.push(idx);
            node = s.child(node, idx);
        }
        let nd = &s.nodes[node];
        let pot: f64 = nd.invested.iter().sum();
        let mut row = serde_json::json!({"line": spec, "kind": if nd.kind == 2 { "pot_share" } else { "other" }, "node": node, "path": path,
            "live": nd.live, "pot_bb": pot, "invested": nd.invested});
        if nd.kind == 2 {
            let reaches = if tree_only { vec![(0..solver::preflop::equity::NUM_CLASSES).map(|h| solver::preflop::equity::class_prob(h)).collect::<Vec<f32>>(); s.n] } else { s.walk(&path)?.1 };
            let mut seats = Vec::new();
            for p in (0..s.n).filter(|&p| nd.live & (1 << p) != 0) {
                #[allow(unused_mut)]
                let mut seat = serde_json::json!({"seat": p, "position": s.cfg.positions[p], "reach": reaches[p]});
                #[cfg(feature = "t2-cont")]
                if !tree_only {
                    seat["static_gross"] = serde_json::json!(s.t2_terminal_gross(node, p, &reaches, true).ok());
                    seat["used_gross"] = serde_json::json!(s.t2_terminal_gross(node, p, &reaches, false).ok());
                }
                #[cfg(feature = "t2-cont")]
                if !tree_only && std::env::var("T2_EXPORT_STATIC_MATRIX").is_ok() {
                    // ft matrix terminals: the static (no-table) payoff as a hand-vs-hand matrix M[h*169+j], one opponent class at a time
                    // (exact where the static payoff is linear in the opponent distribution; the pot clip in the static branch is not).
                    if let Some(q) = (0..s.n).find(|&q| q != p && nd.live & (1 << q) != 0) {
                        let nc = solver::preflop::equity::NUM_CLASSES;
                        let mut m = vec![0f64; nc * nc];
                        for j in 0..nc {
                            let mut r = reaches.clone();
                            r[q] = vec![0f32; nc];
                            r[q][j] = 1.0;
                            if let Ok(g) = s.t2_terminal_gross(node, p, &r, true) {
                                for h in 0..nc {
                                    m[h * nc + j] = g[h];
                                }
                            }
                        }
                        seat["static_matrix"] = serde_json::json!(m);
                    }
                }
                seats.push(seat);
            }
            row["seats"] = serde_json::Value::Array(seats);
        }
        out.push_str(&serde_json::to_string(&row).unwrap());
        out.push('\n');
    }
    std::fs::write(&a[4], out).map_err(|e| e.to_string())?;
    Ok(())
}
