//! T2 audit: is save -> load -> continue bit-identical to an uninterrupted solve,
//! and does load notice when the payoff game (equity table) changed?
//!
//!   cargo run --release -p solver --example t2_resume -- <config.json> <a> <dir>
//!
//! A: 2a iterations straight.  B: a iterations, save, load (same table), a more.
//! C: same checkpoint loaded with an equity table built from a different
//!    PREFLOP_EQ_SEED, then a more.  Prints one JSON object.
use solver::preflop::equity::EquityTable;
use solver::preflop::{PreflopConfig, PreflopSolver};
use std::sync::Arc;

fn arenas(path: &str) -> (Vec<u8>, Vec<u8>) {
    let b = std::fs::read(path).expect("read save");
    // 12-byte magic (ends in '\n'), then one JSON header line, then raw arenas
    let nl = 12 + b[12..].iter().position(|&c| c == b'\n').expect("header");
    (b[..nl].to_vec(), b[nl + 1..].to_vec())
}

fn f32s(b: &[u8]) -> Vec<f32> {
    b.chunks_exact(4).map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cfg: PreflopConfig =
        serde_json::from_str(&std::fs::read_to_string(&args[1]).expect("config")).expect("json");
    let a: u32 = args[2].parse().expect("a");
    let dir = &args[3];
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let seed = std::env::var("PREFLOP_EQ_SEED").unwrap_or_else(|_| "0".into());
    let eq = Arc::new(EquityTable::build(samples));

    let mut sa = PreflopSolver::new(cfg.clone(), eq.clone()).expect("solver");
    for _ in 0..2 * a { sa.iterate(); }
    let pa = format!("{dir}/resume_A.gtop");
    sa.save_game(&pa).expect("save A");
    let (ga, _) = sa.gaps_and_evs();

    let mut sb = PreflopSolver::new(cfg.clone(), eq.clone()).expect("solver");
    for _ in 0..a { sb.iterate(); }
    let pm = format!("{dir}/resume_mid.gtop");
    sb.save_game(&pm).expect("save mid");
    drop(sb);
    let mut sb = PreflopSolver::load_game(&pm, eq.clone()).expect("load mid");
    for _ in 0..a { sb.iterate(); }
    let pb = format!("{dir}/resume_B.gtop");
    sb.save_game(&pb).expect("save B");
    let (gb, _) = sb.gaps_and_evs();

    let (ha, xa) = arenas(&pa);
    let (hb, xb) = arenas(&pb);
    let (fa, fb) = (f32s(&xa), f32s(&xb));
    let maxdiff = fa.iter().zip(&fb).map(|(x, y)| (x - y).abs()).fold(0f32, f32::max);

    // C: other equity seed, same checkpoint
    std::env::set_var("PREFLOP_EQ_SEED", "777777");
    let eq2 = Arc::new(EquityTable::build(samples));
    let loaded = PreflopSolver::load_game(&pm, eq2.clone());
    let c = match loaded {
        Err(e) => serde_json::json!({"load_accepted": false, "error": e}),
        Ok(mut sc) => {
            for _ in 0..a { sc.iterate(); }
            let (gc, _) = sc.gaps_and_evs();
            let pc = format!("{dir}/resume_C.gtop");
            sc.save_game(&pc).expect("save C");
            let (_, xc) = arenas(&pc);
            let fc = f32s(&xc);
            let d = fc.iter().zip(&fb).map(|(x, y)| (x - y).abs()).fold(0f32, f32::max);
            serde_json::json!({"load_accepted": true, "gap_total": gc.iter().sum::<f64>(),
                "max_abs_arena_diff_vs_B": d, "arena_bytes_equal_B": xc == xb})
        }
    };
    let hdr: serde_json::Value = serde_json::from_slice(&ha[12..]).unwrap_or(serde_json::Value::Null);
    let keys: Vec<String> = hdr.as_object().map(|o| o.keys().cloned().collect()).unwrap_or_default();
    println!("{}", serde_json::json!({
        "a": a, "eq_samples": samples, "eq_seed": seed,
        "straight_vs_resumed": {"header_equal": ha == hb, "arena_bytes_equal": xa == xb,
            "arena_floats": fa.len(), "max_abs_diff": maxdiff,
            "gap_A": ga.iter().sum::<f64>(), "gap_B": gb.iter().sum::<f64>()},
        "other_eq_seed_resume": c,
        "header_keys": keys,
    }));
}
