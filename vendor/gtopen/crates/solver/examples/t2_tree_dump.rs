//! Read-only whole-tree strategy / EV dump from a saved solve (one average-strategy traversal per seat, in parallel).
//!   T2_CONT_FILE=<manifest> t2_tree_dump <config.json> <save.gtop> <min_reach> <out.jsonl>
//! One JSON line per decision node with reach probability >= min_reach: node, path (action indices), path labels, actor,
//! reach_prob, others_prob, actions, actor_reach[169], sigma[a][169], ev[a][169] (bb, net, given the node is reached).
//! Env: PREFLOP_EQ_SAMPLES / PREFLOP_EQ_SEED / PREFLOP_MULTIWAY_SEED as for the solve.
use rayon::prelude::*;
use solver::preflop::equity::{EquityTable, NUM_CLASSES};
use solver::preflop::PreflopSolver;
use std::io::Write;
use std::sync::Arc;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 5 {
        return Err("config save.gtop min_reach out.jsonl".into());
    }
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let eq = Arc::new(EquityTable::build(samples));
    let s = PreflopSolver::load_game(&a[2], eq)?;
    solver::preflop::t2cont::validate(&s)?;
    let min_reach: f64 = a[3].parse().map_err(|_| "min_reach")?;
    let t0 = std::time::Instant::now();
    let recs: Vec<Vec<solver::preflop::t2cont::T2NodeRecord>> = (0..s.n).into_par_iter().map(|p| s.t2_tree_values(p, min_reach)).collect();
    let secs = t0.elapsed().as_secs_f64();
    let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{}.tmp", a[4])).map_err(|e| e.to_string())?);
    let mut n = 0usize;
    for r in recs.iter().flatten() {
        let mut labels = Vec::new();
        let mut node = 0usize;
        for &i in &r.path {
            let nd = &s.nodes[node];
            labels.push(format!("{}:{}", s.cfg.positions[nd.actor as usize], nd.actions[i].label));
            node = s.child(node, i);
        }
        let nd = &s.nodes[r.node];
        let na = nd.actions.len();
        let line = serde_json::json!({
            "node": r.node, "path": r.path, "line": labels, "actor": s.cfg.positions[r.actor], "actor_seat": r.actor,
            "reach_prob": r.reach_prob, "others_prob": r.others_prob,
            "actions": nd.actions.iter().map(|x| x.label.clone()).collect::<Vec<_>>(),
            "actor_reach": r.actor_reach,
            "sigma": (0..na).map(|k| r.sigma[k * NUM_CLASSES..(k + 1) * NUM_CLASSES].to_vec()).collect::<Vec<_>>(),
            "ev": r.ev,
        });
        writeln!(f, "{}", line).map_err(|e| e.to_string())?;
        n += 1;
    }
    drop(f);
    std::fs::rename(format!("{}.tmp", a[4]), &a[4]).map_err(|e| e.to_string())?;
    eprintln!("{} nodes, traversal {:.1} s, iteration {}", n, secs, s.iteration);
    Ok(())
}
