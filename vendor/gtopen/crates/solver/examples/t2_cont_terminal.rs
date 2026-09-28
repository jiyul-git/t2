//! T2 HU-continuation prototype, step C1: solve a preflop config and extract the
//! arriving ranges at one heads-up terminal.
//!
//!   t2_cont_terminal <config.json> <iterations> <path-spec> <out.json> [save.gtop]
//!
//! path-spec: comma-separated action kinds from the root, e.g. "fold,raise,fold,call";
//! "raise" picks the smallest raise-to on offer. Reaches are the AVERAGE-strategy
//! class reaches (combos/1326 x action probabilities), exactly as `walk` defines them.
//! Env: PREFLOP_EQ_SAMPLES / PREFLOP_EQ_SEED / PREFLOP_MULTIWAY_SEED as usual.
use solver::preflop::equity::{class_label, EquityTable, NUM_CLASSES};
use solver::preflop::{PreflopConfig, PreflopSolver};
use std::sync::Arc;

pub fn fnv1a64(parts: &[&[f32]]) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for p in parts {
        for x in *p {
            for b in x.to_le_bytes() {
                h ^= b as u64;
                h = h.wrapping_mul(0x100000001b3);
            }
        }
    }
    format!("{h:016x}")
}

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 5 {
        return Err("config iterations path-spec out.json [save.gtop]".into());
    }
    let cfg_text = std::fs::read_to_string(&a[1]).map_err(|e| e.to_string())?;
    let cfg: PreflopConfig = serde_json::from_str(&cfg_text).map_err(|e| e.to_string())?;
    let iters: u32 = a[2].parse().map_err(|_| "iterations")?;
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let eq = Arc::new(EquityTable::build(samples));
    let mut s = PreflopSolver::new(cfg, eq)?;
    for _ in 0..iters {
        s.iterate();
    }
    let (gaps, evs) = s.gaps_and_evs();
    if let Some(p) = a.get(5) {
        s.save_game(p)?;
    }
    // resolve the path spec
    let mut path = Vec::new();
    let mut node = 0usize;
    for kind in a[3].split(',') {
        let nd = &s.nodes[node];
        if nd.kind != 0 {
            return Err(format!("path ends early at {kind}"));
        }
        let idx = nd.actions.iter().enumerate().filter(|(_, x)| x.kind == kind)
            .min_by(|x, y| x.1.to.partial_cmp(&y.1.to).unwrap()).map(|(i, _)| i)
            .ok_or(format!("no {kind} at node {node}"))?;
        path.push(idx);
        node = s.child(node, idx);
    }
    let (term, reaches) = s.walk(&path)?;
    let nd = &s.nodes[term];
    if nd.kind != 2 || nd.live.count_ones() != 2 {
        return Err("path does not end at a heads-up pot-share terminal".into());
    }
    let live: Vec<usize> = (0..s.n).filter(|&p| nd.live & (1 << p) != 0).collect();
    // postflop order: seat order with SB/BB first (BB acts before BTN postflop)
    let behind: Vec<f64> = live.iter().map(|&p| s.cfg.stack - nd.invested[p] + s.cfg.ante).collect();
    let eff = behind.iter().cloned().fold(f64::INFINITY, f64::min);
    let norm: Vec<Vec<f32>> = live.iter().map(|&p| {
        let m: f32 = reaches[p].iter().sum();
        reaches[p].iter().map(|x| x / m).collect()
    }).collect();
    let players: Vec<serde_json::Value> = live.iter().enumerate().map(|(i, &p)| {
        let mass: f32 = reaches[p].iter().sum();
        // fraction of each class's combos that reach (reach / class prior)
        let keep: Vec<f64> = (0..NUM_CLASSES).map(|h| {
            let prior = solver::preflop::equity::class_prob(h) as f64;
            reaches[p][h] as f64 / prior
        }).collect();
        let in_range = keep.iter().filter(|&&k| k > 1e-6).count();
        serde_json::json!({
            "seat": p, "position": s.cfg.positions[p], "invested_bb": nd.invested[p],
            "behind_bb": behind[i], "range_mass": mass,
            "classes_with_positive_reach": in_range,
            "class_keep_fraction": keep,
            "class_reach_normalized": norm[i],
        })
    }).collect();
    // outer-loop diagnostics: first-in mixes and the BB response to the BTN open
    let mix = |path: &[usize]| -> Option<serde_json::Value> {
        let (n, r) = s.walk(path).ok()?;
        let nd = &s.nodes[n];
        if nd.kind != 0 { return None; }
        let actor = nd.actor as usize;
        let sigma = s.average_strategy(n);
        let tot: f64 = r[actor].iter().map(|&x| x as f64).sum();
        let mut m = serde_json::Map::new();
        for (ai, act) in nd.actions.iter().enumerate() {
            let f: f64 = (0..NUM_CLASSES).map(|h| r[actor][h] as f64 * sigma[ai * NUM_CLASSES + h] as f64).sum::<f64>() / tot;
            let key = if act.kind == "raise" || act.kind == "jam" { format!("{}_{}", act.kind, act.to) } else { act.kind.clone() };
            *m.entry(key).or_insert(serde_json::json!(0.0)) = serde_json::json!(f);
        }
        Some(serde_json::json!({"actor": s.cfg.positions[actor], "mix": m,
            "class_strategy": (0..nd.actions.len()).map(|ai| sigma[ai*NUM_CLASSES..(ai+1)*NUM_CLASSES].to_vec()).collect::<Vec<_>>(),
            "actions": nd.actions.iter().map(|x| x.label.clone()).collect::<Vec<_>>()}))
    };
    let mut freq = serde_json::Map::new();
    for k in 0..s.n - 1 {
        if let Some(m) = mix(&vec![0usize; k]) { freq.insert(format!("rfi_{}", s.cfg.positions[k]), m); }
    }
    if path.len() >= 1 {
        if let Some(m) = mix(&path[..path.len() - 1]) { freq.insert("terminal_parent".into(), m); }
    }
    let labels: Vec<String> = (0..NUM_CLASSES).map(class_label).collect();
    let out = serde_json::json!({
        "config_file": a[1], "config": s.cfg, "iterations": s.iteration,
        "gap_total": gaps.iter().sum::<f64>(), "gaps": gaps, "evs": evs,
        "eq_samples": samples, "multiway_model": s.multiway_equity_model(),
        "path_spec": a[3], "path": path, "terminal_node": term,
        "pot_bb": nd.pot, "effective_behind_bb": eff, "spr": eff / nd.pot,
        "aggressor_seat": nd.aggressor,
        "aggressor": if (nd.aggressor as usize) < s.n { s.cfg.positions[nd.aggressor as usize].clone() } else { "none".into() },
        "players": players, "class_labels": labels, "frequencies": freq,
        "terminal_live_mask": nd.live, "t2_cont_file": std::env::var("T2_CONT_FILE").ok(),
        "ranges_hash_fnv1a64": fnv1a64(&norm.iter().map(|v| v.as_slice()).collect::<Vec<_>>()),
        "note": "average-strategy reaches; class-level (no card removal between seats); ante counted in invested",
    });
    std::fs::write(&a[4], serde_json::to_vec_pretty(&out).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    eprintln!("gap {:.5}  pot {}  spr {:.3}  hash {}", gaps.iter().sum::<f64>(), nd.pot, eff / nd.pot, out["ranges_hash_fnv1a64"]);
    Ok(())
}
