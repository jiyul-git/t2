//! T2 audit: is "fold" dominated for every BB class under the static model?
//! For opening ranges of the top x% of combos (ranked by equity vs a random hand,
//! using the same MC EquityTable the solver uses), print the minimum class equity
//! and the static-model break-even equity for a BB call vs a 2bb open
//! (pot 5.5bb after the call, SB folds, 30bb, 1bb total ante, k=0.16).
//!
//!   PREFLOP_EQ_SEED=202 cargo run --release -p solver --example t2_defend_check
use solver::preflop::equity::{class_label, class_prob, EquityTable, NUM_CLASSES};

fn main() {
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let t = EquityTable::build(samples);
    let vs_random: Vec<f64> = (0..NUM_CLASSES)
        .map(|h| (0..NUM_CLASSES).map(|j| class_prob(j) as f64 * t.eq(h, j) as f64).sum())
        .collect();
    let mut order: Vec<usize> = (0..NUM_CLASSES).collect();
    order.sort_by(|&a, &b| vs_random[b].partial_cmp(&vs_random[a]).unwrap());
    // static realization for the OOP caller: spr = (30 - 2.25 + 0.25) / 5.5
    let spr: f64 = 28.0 / 5.5;
    let r_oop = 1.0 - 0.16 * 0.5 * (spr.min(8.0) / 8.0);
    let break_even = 1.0 / (5.5 * r_oop);
    let mut rows = Vec::new();
    for pct in [0.25f64, 0.30, 0.37, 0.45, 0.60] {
        let mut dist = vec![0f64; NUM_CLASSES];
        let mut mass = 0.0;
        for &h in &order {
            if mass >= pct { break; }
            let w = (class_prob(h) as f64).min(pct - mass);
            dist[h] = w;
            mass += w;
        }
        let (mut worst, mut worst_h) = (1.0f64, 0usize);
        for h in 0..NUM_CLASSES {
            let e: f64 = (0..NUM_CLASSES).map(|j| dist[j] * t.eq(h, j) as f64).sum::<f64>() / mass;
            if e < worst { worst = e; worst_h = h; }
        }
        rows.push(serde_json::json!({"open_range_top": pct, "min_class_equity": worst,
            "min_class": class_label(worst_h), "fold_dominated_for_all": worst >= break_even}));
    }
    println!("{}", serde_json::json!({"eq_samples": samples, "r_oop": r_oop, "break_even_equity": break_even, "rows": rows}));
}
