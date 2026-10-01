//! T2 A4R: evaluate a saved preflop strategy profile under the continuation tables named by
//! T2_CONT_FILE (which may differ from the tables it was solved with). No iteration is run:
//! the loaded average strategy is held fixed and only best-response gaps and EVs are computed.
//!
//!   T2_CONT_FILE=<manifest> cargo run --release -p solver --features t2-cont --example t2_cross_eval -- <save.gtop> <out.json>
//!
//! gaps[p] = what seat p gains by best responding to the others' fixed strategies under these
//! tables (bb); their sum is the profile's exploitability in this game.
use solver::preflop::equity::EquityTable;
use solver::preflop::PreflopSolver;
use std::sync::Arc;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 3 {
        return Err("save.gtop out.json".into());
    }
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let eq = Arc::new(EquityTable::build(samples));
    let s = PreflopSolver::load_game(&a[1], eq)?;
    #[cfg(feature = "t2-cont")]
    solver::preflop::t2cont::validate(&s)?;
    let (gaps, evs) = s.gaps_and_evs();
    let out = serde_json::json!({
        "save": a[1], "t2_cont_file": std::env::var("T2_CONT_FILE").ok(), "eq_samples": samples,
        "iteration": s.iteration, "positions": s.cfg.positions,
        "gaps": gaps, "gap_total": gaps.iter().sum::<f64>(), "evs": evs,
    });
    std::fs::write(&a[2], serde_json::to_string_pretty(&out).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}
