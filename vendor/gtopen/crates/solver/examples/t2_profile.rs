//! T2 audit: wall-clock decomposition of one preflop solve.
//!
//!   cargo run --release -p solver --features t2-profile --example t2_profile -- \
//!       <config.json> <iterations> [gap_every] [save_path]
//!
//! Env: PREFLOP_EQ_SAMPLES (default 1200), PREFLOP_EQ_SEED, PREFLOP_MULTIWAY_SEED,
//!      SOLVER_THREADS, T2_ESTIMATE_ONLY=1 (tree size only), T2_LOAD=<save.gtop> (start from a checkpoint).
//! Prints one JSON object on the last line.
use solver::preflop::equity::EquityTable;
use solver::preflop::multiway::CoupledDeck;
use solver::preflop::t2prof;
use solver::preflop::{estimate_tree, PreflopConfig, PreflopSolver};
use std::sync::Arc;
use std::time::Instant;

fn ms(t: Instant) -> f64 {
    t.elapsed().as_secs_f64() * 1e3
}

fn prof_json() -> serde_json::Value {
    let (rows, visits, trav, disc) = t2prof::snapshot();
    serde_json::json!({
        "terminal": rows.iter().map(|(n, c, m)| serde_json::json!({"kind": n, "calls": c, "cpu_ms": m})).collect::<Vec<_>>(),
        "action_visits": visits, "traverse_wall_ms": trav, "discount_wall_ms": disc,
    })
}

fn mix(s: &PreflopSolver, path: &[usize]) -> Option<(usize, serde_json::Value)> {
    let (node, reaches) = s.walk(path).ok()?;
    let nd = &s.nodes[node];
    if nd.kind != 0 {
        return None;
    }
    let actor = nd.actor as usize;
    let sigma = s.average_strategy(node);
    let tot: f64 = reaches[actor].iter().map(|&x| x as f64).sum();
    let mut out = serde_json::Map::new();
    for (a, act) in nd.actions.iter().enumerate() {
        let f: f64 = (0..169).map(|h| reaches[actor][h] as f64 * sigma[a * 169 + h] as f64).sum::<f64>() / tot.max(1e-12);
        out.insert(format!("{}{}", act.kind, if act.kind == "raise" || act.kind == "jam" { format!("_{}", act.to) } else { String::new() }), serde_json::json!(f));
    }
    Some((node, serde_json::Value::Object(out)))
}

fn idx_of(s: &PreflopSolver, path: &[usize], kind: &str) -> Option<usize> {
    let (node, _) = s.walk(path).ok()?;
    s.nodes[node].actions.iter().position(|a| a.kind == kind)
}

/// Aggregate RFI per position + a few response nodes, from the AVERAGE strategy.
fn report(s: &PreflopSolver) -> serde_json::Value {
    let mut rfi = serde_json::Map::new();
    for k in 0..s.n - 1 {
        let path = vec![0usize; k];
        if let Some((node, m)) = mix(s, &path) {
            let o: f64 = m.as_object().unwrap().iter()
                .filter(|(k, _)| k.starts_with("raise") || k.starts_with("jam") || k.starts_with("call"))
                .map(|(_, v)| v.as_f64().unwrap()).sum();
            rfi.insert(s.cfg.positions[s.nodes[node].actor as usize].clone(), serde_json::json!({"enter": o, "mix": m}));
        }
    }
    let mut resp = serde_json::Map::new();
    // BTN (seat n-3) opens: SB, BB responses; BTN vs BB 3bet
    let btn = s.n - 3;
    let mut p = vec![0usize; btn];
    if let Some(o) = idx_of(s, &p, "raise") {
        p.push(o);
        if let Some((_, m)) = mix(s, &p) { resp.insert("SB_vs_BTN_open".into(), m); }
        p.push(0);
        if let Some((_, m)) = mix(s, &p) { resp.insert("BB_vs_BTN_open".into(), m); }
        if let Some(t) = idx_of(s, &p, "raise") {
            p.push(t);
            if let Some((_, m)) = mix(s, &p) { resp.insert("BTN_vs_BB_3bet".into(), m); }
        }
    }
    // UTG opens: everyone folds to BB
    let mut p = vec![];
    if let Some(o) = idx_of(s, &p, "raise") {
        p.push(o);
        let mut q = p.clone();
        for _ in 1..s.n - 1 { q.push(0); }
        if let Some((_, m)) = mix(s, &q) { resp.insert("BB_vs_UTG_open".into(), m); }
        if let Some(t) = idx_of(s, &q, "raise") {
            q.push(t);
            if let Some((_, m)) = mix(s, &q) { resp.insert("UTG_vs_BB_3bet".into(), m); }
        }
    }
    serde_json::json!({"iteration": s.iteration, "rfi": rfi, "responses": resp})
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cfg: PreflopConfig =
        serde_json::from_str(&std::fs::read_to_string(&args[1]).expect("config")).expect("json");
    let iters: u32 = args.get(2).and_then(|v| v.parse().ok()).unwrap_or(2);
    let gap_every: u32 = args.get(3).and_then(|v| v.parse().ok()).unwrap_or(0);
    let save_path = args.get(4).cloned();
    if let Ok(t) = std::env::var("SOLVER_THREADS") {
        if let Ok(n) = t.parse::<usize>() {
            rayon::ThreadPoolBuilder::new().num_threads(n).build_global().ok();
        }
    }
    let threads = rayon::current_num_threads();
    let t = Instant::now();
    let est = estimate_tree(&cfg).expect("estimate");
    let estimate_ms = ms(t);
    let arena_mb = est.arena_len as f64 * 8.0 / 1e6;
    if std::env::var("T2_ESTIMATE_ONLY").ok().as_deref() == Some("1") {
        println!("{}", serde_json::json!({"estimate": {"nodes": est.nodes, "action_nodes": est.action_nodes,
            "arena_len": est.arena_len, "arena_mb": arena_mb, "truncated": est.truncated, "ms": estimate_ms}}));
        return;
    }
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let t = Instant::now();
    let eq = Arc::new(EquityTable::build(samples));
    let equity_build_ms = ms(t);
    let t = Instant::now();
    let _deck = CoupledDeck::shared();
    let multiway_build_ms = ms(t);
    let t = Instant::now();
    // T2_LOAD=<save.gtop>: continue from a checkpoint (iteration timing at a converged state); default: fresh solver
    let mut s = match std::env::var("T2_LOAD") {
        Ok(p) => PreflopSolver::load_game(&p, eq.clone()).expect("load"),
        Err(_) => PreflopSolver::new(cfg, eq.clone()).expect("solver"),
    };
    let tree_build_ms = ms(t);
    if let Ok(m) = std::env::var("T2_MW_MODEL") {
        s.set_multiway_equity_model(&m).expect("multiway model");
    }
    let (mut n_fold, mut n_share, mut n_act) = (0u64, 0u64, 0u64);
    let mut share_by_live = [0u64; 10];
    for nd in &s.nodes {
        match nd.kind {
            0 => n_act += 1,
            1 => n_fold += 1,
            _ => {
                n_share += 1;
                share_by_live[nd.live.count_ones() as usize] += 1;
            }
        }
    }
    let mut per_iter = Vec::new();
    let mut gaps = Vec::new();
    let mut prof_iters = serde_json::Value::Null;
    t2prof::reset();
    let t_all = Instant::now();
    for i in 0..iters {
        let t = Instant::now();
        s.iterate();
        per_iter.push(ms(t));
        if gap_every > 0 && (i + 1) % gap_every == 0 {
            if prof_iters.is_null() {
                prof_iters = prof_json();
                t2prof::reset();
            }
            let t = Instant::now();
            let (g, e) = s.gaps_and_evs();
            let gm = ms(t);
            let rep = if std::env::var("T2_REPORT").ok().as_deref() == Some("1") { report(&s) } else { serde_json::Value::Null };
            eprintln!("{}", serde_json::json!({"iteration": s.iteration, "gap_total": g.iter().sum::<f64>(), "gap_ms": gm}));
            gaps.push(serde_json::json!({"iteration": s.iteration, "gap_total": g.iter().sum::<f64>(), "gaps": g, "evs": e, "gap_ms": gm, "report": rep}));
        }
    }
    let solve_ms = ms(t_all);
    if prof_iters.is_null() {
        prof_iters = prof_json();
    }
    let prof_gap = if gap_every > 0 { prof_json() } else { serde_json::Value::Null };
    let (mut save_ms, mut load_ms, mut save_bytes) = (0.0, 0.0, 0u64);
    if let Some(p) = save_path {
        let t = Instant::now();
        s.save_game(&p).expect("save");
        save_ms = ms(t);
        save_bytes = std::fs::metadata(&p).map(|m| m.len()).unwrap_or(0);
        let t = Instant::now();
        let s2 = PreflopSolver::load_game(&p, eq.clone()).expect("load");
        load_ms = ms(t);
        assert_eq!(s2.iteration, s.iteration);
    }
    println!("{}", serde_json::json!({
        "threads": threads, "eq_samples": samples, "multiway_model": s.multiway_equity_model(),
        "realization": s.cfg.realization.clone(), "realization_note": s.realization_note.clone(),
        "estimate": {"nodes": est.nodes, "action_nodes": est.action_nodes, "arena_len": est.arena_len,
                     "arena_mb": arena_mb, "truncated": est.truncated, "ms": estimate_ms},
        "built": {"nodes": s.nodes.len(), "action": n_act, "fold_win": n_fold, "pot_share": n_share,
                  "pot_share_by_live": share_by_live},
        "equity_build_ms": equity_build_ms, "multiway_build_ms": multiway_build_ms,
        "tree_build_ms": tree_build_ms,
        "iterations": iters, "solve_ms": solve_ms, "per_iter_ms": per_iter,
        "profile_iterations": prof_iters, "profile_gap_checks": prof_gap, "gaps": gaps,
        "save_ms": save_ms, "load_ms": load_ms, "save_bytes": save_bytes,
    }));
}
