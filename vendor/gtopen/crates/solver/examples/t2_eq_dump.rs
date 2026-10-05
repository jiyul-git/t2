//! Dump the preflop class-vs-class equity table (the one every preflop solve builds) as JSON.
//!   PREFLOP_EQ_SEED=202 PREFLOP_EQ_SAMPLES=1200 t2_eq_dump <out.json>
//! out: {"samples": n, "seed": s, "eq": [[eq(i, j) for j in 0..169] for i in 0..169]} (win + tie/2, class order of the solver).
use solver::preflop::equity::EquityTable;

fn main() {
    let out = std::env::args().nth(1).expect("usage: t2_eq_dump <out.json>");
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let t = EquityTable::build(samples);
    let eq: Vec<Vec<f32>> = (0..169).map(|i| (0..169).map(|j| t.eq(i, j)).collect()).collect();
    let v = serde_json::json!({"samples": samples, "seed": std::env::var("PREFLOP_EQ_SEED").unwrap_or_default(), "eq": eq});
    std::fs::write(out, serde_json::to_string(&v).unwrap()).expect("write");
}
