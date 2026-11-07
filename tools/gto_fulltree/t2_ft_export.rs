//! ft export (docs/GTO_FULLTREE_PILOT_60BB.md, reconstructed 2026-11-07 for ft30 — the ft60 original was never committed).
//!   t2_ft_export <config.json> <save.gtop | -> <jobs.txt> <out.jsonl>
//! jobs.txt: one action line per row, "UTG:Fold|UTG+1:Raise 2.5|..." (same labels as t2_tree_dump "line").
//! With "-" no strategies are loaded (fresh tree: node, kind, live, pot, invested only; used_gross/static_gross/reach null).
//! Else for every line: reach (class reach of each live seat = combos/1326 x action probabilities, as `walk`),
//! static_gross (legacy=true, continuation tables bypassed) and used_gross (T2_CONT_FILE tables applied) for heads-up pot-share terminals.
use solver::preflop::equity::EquityTable;
use solver::preflop::{PreflopConfig, PreflopSolver};
use std::io::Write;
use std::sync::Arc;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 5 {
        return Err("config save.gtop|- jobs.txt out.jsonl".into());
    }
    let cfg: PreflopConfig = serde_json::from_str(&std::fs::read_to_string(&a[1]).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let fresh = a[2] == "-";
    let eq = Arc::new(EquityTable::build(if fresh { 1 } else { samples }));
    let s = if fresh { PreflopSolver::new(cfg, eq)? } else { PreflopSolver::load_game(&a[2], eq)? };
    #[cfg(feature = "t2-cont")]
    solver::preflop::t2cont::validate(&s)?;
    let jobs: Vec<String> = std::fs::read_to_string(&a[3]).map_err(|e| e.to_string())?.lines().filter(|l| !l.trim().is_empty()).map(|l| l.trim().to_string()).collect();
    let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{}.tmp", a[4])).map_err(|e| e.to_string())?);
    for line in &jobs {
        let mut path = Vec::new();
        let mut node = 0usize;
        for item in line.split('|') {
            let nd = &s.nodes[node];
            if nd.kind != 0 {
                return Err(format!("line ends early at {item}: {line}"));
            }
            let (pos, label) = item.split_once(':').ok_or(format!("bad item {item}"))?;
            if s.cfg.positions[nd.actor as usize] != pos {
                return Err(format!("actor mismatch at {item} (node actor {}): {line}", s.cfg.positions[nd.actor as usize]));
            }
            // two spellings: tree label ("Raise 2.5") or spot-loop style "kind@to" ("raise@2.500000", "fold", "call@2.500000")
            let idx = if let Some((k, to)) = label.split_once('@') {
                let to: f64 = to.parse().map_err(|_| format!("bad amount in {item}"))?;
                nd.actions.iter().position(|x| x.kind == k && (x.to - to).abs() < 1e-4)
            } else if label.chars().next().map_or(false, |c| c.is_lowercase()) {
                nd.actions.iter().position(|x| x.kind == label)
            } else {
                nd.actions.iter().position(|x| x.label == label)
            }.ok_or(format!("no action '{label}' at {pos} node {node}: {line}"))?;
            path.push(idx);
            node = s.child(node, idx);
        }
        let nd = &s.nodes[node];
        let kind = match nd.kind { 0 => "action", 2 => "pot_share", _ => "fold_win" };
        let live: Vec<usize> = (0..s.n).filter(|&p| nd.live & (1 << p) != 0).collect();
        let mut seats = Vec::new();
        if !fresh && kind == "pot_share" {
            let (_, reaches) = s.walk(&path)?;
            for &p in &live {
                #[cfg(feature = "t2-cont")]
                let (st, us) = (s.t2_terminal_gross(node, p, &reaches, true).ok(), s.t2_terminal_gross(node, p, &reaches, false).ok());
                #[cfg(not(feature = "t2-cont"))]
                let (st, us): (Option<Vec<f64>>, Option<Vec<f64>>) = (None, None);
                seats.push(serde_json::json!({"seat": p, "position": s.cfg.positions[p], "reach": reaches[p],
                    "static_gross": st, "used_gross": us}));
            }
        } else {
            for &p in &live { seats.push(serde_json::json!({"seat": p, "position": s.cfg.positions[p]})); }
        }
        let row = serde_json::json!({"line": line, "path": path, "node": node, "kind": kind, "live": nd.live, "pot_bb": nd.pot,
            "invested": nd.invested, "seats": seats});
        writeln!(f, "{}", row).map_err(|e| e.to_string())?;
    }
    drop(f);
    std::fs::rename(format!("{}.tmp", a[4]), &a[4]).map_err(|e| e.to_string())?;
    Ok(())
}
