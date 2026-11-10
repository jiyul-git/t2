//! Push/fold bucket solve (docs/GTO_PUSHFOLD_10_25_V1.md): solve a preflop config with checkpoint resume and write the exact
//! gaps (no terminal export, so trees without a flop-reaching pot exist too, e.g. 10 bb jam / fold).
//!
//!   t2_pf_solve <config.json> <iterations> <checkpoint.gtop> <out.json>
//!
//! Resumes from the checkpoint when it exists (save -> load -> continue is bit-identical, t2_resume audit), saves every
//! T2_CHECKPOINT_EVERY (default 10) iterations. Env: PREFLOP_EQ_SAMPLES / PREFLOP_EQ_SEED / PREFLOP_MULTIWAY_SEED /
//! PREFLOP_MW_SKIP_BELOW as usual.
use solver::preflop::equity::EquityTable;
use solver::preflop::{PreflopConfig, PreflopSolver};
use std::sync::Arc;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 5 {
        return Err("config iterations checkpoint.gtop out.json".into());
    }
    let cfg: PreflopConfig = serde_json::from_str(&std::fs::read_to_string(&a[1]).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    let iters: u32 = a[2].parse().map_err(|_| "iterations")?;
    let ck = &a[3];
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let every: u32 = std::env::var("T2_CHECKPOINT_EVERY").ok().and_then(|v| v.parse().ok()).unwrap_or(10).max(1);
    let eq = Arc::new(EquityTable::build(samples));
    let mut s = if std::path::Path::new(ck).exists() { PreflopSolver::load_game(ck, eq)? } else { PreflopSolver::new(cfg, eq)? };
    let t0 = std::time::Instant::now();
    while s.iteration < iters {
        s.iterate();
        if s.iteration % every == 0 || s.iteration >= iters {
            let tmp = format!("{ck}.tmp");
            s.save_game(&tmp)?;
            std::fs::rename(&tmp, ck).map_err(|e| e.to_string())?;
        }
    }
    let solve_s = t0.elapsed().as_secs_f64();
    let (gaps, evs) = s.gaps_and_evs();
    let out = serde_json::json!({
        "config_file": a[1], "config": s.cfg, "iterations": s.iteration, "gap_total": gaps.iter().sum::<f64>(),
        "gaps": gaps, "evs": evs, "eq_samples": samples, "multiway_model": s.multiway_equity_model(),
        "mw_skip_below": std::env::var("PREFLOP_MW_SKIP_BELOW").ok(), "nodes": s.nodes.len(), "solve_s_this_call": solve_s,
    });
    let tmp = format!("{}.tmp", a[4]);
    std::fs::write(&tmp, serde_json::to_vec_pretty(&out).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, &a[4]).map_err(|e| e.to_string())?;
    eprintln!("iterations {} gap {:.6} ({:.1}s)", s.iteration, gaps.iter().sum::<f64>(), solve_s);
    Ok(())
}
