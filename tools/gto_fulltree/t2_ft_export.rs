//! Full-tree terminal export for the ft pilots (tools/gto_fulltree/ft60.py): per pot-share terminal line, the node, live mask,
//! pot, invested chips and the arriving class reaches of every live seat (average strategy), plus the continuation value per
//! class with (used_gross) and without (static_gross) the injected table T2_CONT_FILE.
//!
//!   t2_ft_export <config.json> <save.gtop | -> <jobs.txt> <out.jsonl>
//!
//! jobs.txt: one action line per row, "POS:label|POS:label|..." (labels as the tree dump prints them, folds included; also accepts the
//! loop-state spelling "POS:kind@to", e.g. "HJ:raise@2.000000", and a bare unique kind such as "fold").
//! With "-" no checkpoint is loaded: a fresh (unsolved) tree gives node numbers / masks / pots only (gross values are null).
//! Env: PREFLOP_EQ_SAMPLES / PREFLOP_EQ_SEED / PREFLOP_MULTIWAY_SEED as for the solve, T2_CONT_FILE for the table.
use solver::preflop::equity::EquityTable;
use solver::preflop::{PreflopConfig, PreflopSolver};
use std::sync::Arc;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 5 {
        return Err("config save.gtop|- jobs.txt out.jsonl".into());
    }
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let eq = Arc::new(EquityTable::build(samples));
    let fresh = a[2] == "-";
    let s = if fresh {
        let cfg: PreflopConfig = serde_json::from_str(&std::fs::read_to_string(&a[1]).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        PreflopSolver::new(cfg, eq)?
    } else {
        PreflopSolver::load_game(&a[2], eq)?
    };
    solver::preflop::t2cont::validate(&s)?;
    let jobs = std::fs::read_to_string(&a[3]).map_err(|e| e.to_string())?;
    let mut out = String::new();
    for line in jobs.lines().filter(|l| !l.trim().is_empty()) {
        let mut path = Vec::new();
        let mut node = 0usize;
        for item in line.split('|') {
            let (pos, label) = item.split_once(':').ok_or(format!("bad item {item}"))?;
            let nd = &s.nodes[node];
            if nd.kind != 0 {
                return Err(format!("line ends early at {item}: {line}"));
            }
            if s.cfg.positions[nd.actor as usize] != pos {
                return Err(format!("actor mismatch at {item} (node actor {}): {line}", s.cfg.positions[nd.actor as usize]));
            }
            // "label" (tree dump spelling, e.g. "Raise 2.5") or "kind@to" (loop state spelling, e.g. "raise@2.500000", "fold")
            let i = if let Some((k, to)) = label.split_once('@') {
                let to: f64 = to.parse().map_err(|_| format!("bad amount in {item}"))?;
                nd.actions.iter().position(|x| x.kind == k && (x.to - to).abs() < 1e-6)
            } else {
                nd.actions.iter().position(|x| x.label == label).or_else(|| {
                    let m: Vec<usize> = nd.actions.iter().enumerate().filter(|(_, x)| x.kind == label).map(|(i, _)| i).collect();
                    if m.len() == 1 { Some(m[0]) } else { None }
                })
            }.ok_or(format!("no action {label} at {item}: {line}"))?;
            path.push(i);
            node = s.child(node, i);
        }
        let (term, reaches) = s.walk(&path)?;
        let nd = &s.nodes[term];
        let kind = if nd.kind == 2 { "pot_share" } else { "other" };
        let seats: Vec<serde_json::Value> = (0..s.n).filter(|&p| nd.live & (1 << p) != 0).map(|p| {
            let (st, us) = if fresh || nd.kind != 2 { (None, None) } else {
                (s.t2_terminal_gross(term, p, &reaches, true).ok(), s.t2_terminal_gross(term, p, &reaches, false).ok())
            };
            serde_json::json!({"seat": p, "position": s.cfg.positions[p], "reach": reaches[p].iter().map(|&x| x as f64).collect::<Vec<_>>(),
                "static_gross": st, "used_gross": us})
        }).collect();
        let row = serde_json::json!({"kind": kind, "line": line, "node": term, "path": path, "live": nd.live, "pot_bb": nd.pot,
            "invested": nd.invested, "seats": seats});
        out.push_str(&row.to_string());
        out.push('\n');
    }
    let tmp = format!("{}.tmp", a[4]);
    std::fs::write(&tmp, out).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, &a[4]).map_err(|e| e.to_string())?;
    Ok(())
}
