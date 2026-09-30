//! Solve one HU spot exactly as t2_cont_panel does (EPS-floored class keep fractions, menu,
//! f32, target exploitability) and print the aggregate average strategy at the root and after
//! a root check, plus class gross values (reference for the 3-way engine HU degeneration test).
//!   t2_hu_rootmix <hu_terminal.json> <menu.json> <board> <max_iters> <target_pct> <every> <out.json>
use solver::cards::{rank, suit};
use solver::preflop::equity::{class_index, class_label, NUM_CLASSES};
use solver::query::PathStep;
use solver::tree::TreeConfig;
use solver::{Solver, Spot, SpotConfig};
use std::sync::Arc;

const EPS: f32 = 1e-3;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    let term: serde_json::Value = serde_json::from_slice(&std::fs::read(&a[1]).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let menu: serde_json::Value = serde_json::from_slice(&std::fs::read(&a[2]).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let board = &a[3];
    let (max_iters, target, every): (u32, f64, u32) = (a[4].parse().unwrap(), a[5].parse().unwrap(), a[6].parse().unwrap());
    let pl = term["players"].as_array().unwrap();
    let pos: Vec<&str> = pl.iter().map(|p| p["position"].as_str().unwrap()).collect();
    let oop_i = if pos[0] == "SB" || (pos[0] == "BB" && pos[1] != "SB") { 0 } else { 1 };
    let keep = |i: usize| -> Vec<f64> { pl[i]["class_keep_fraction"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect() };
    let keep = [keep(oop_i), keep(1 - oop_i)];
    let pot = term["pot_bb"].as_f64().unwrap();
    let mut tree: TreeConfig = serde_json::from_value(menu["tree"].clone()).map_err(|e| e.to_string())?;
    tree.starting_pot = pot;
    tree.effective_stack = term["effective_behind_bb"].as_f64().unwrap();
    tree.rake_pct = 0.0;
    tree.rake_cap = 0.0;
    let full = (0..NUM_CLASSES).map(class_label).collect::<Vec<_>>().join(",");
    let mut spot = Spot::new(SpotConfig { board: board.clone(), range_oop: full.clone(), range_ip: full, tree })?;
    for p in 0..2 {
        for (i, h) in spot.hands[p].iter_mut().enumerate() {
            let w = (keep[p][class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2))] as f32).max(EPS);
            h.weight = w;
            spot.weights[p][i] = w;
        }
    }
    let mut s = Solver::new(Arc::new(spot));
    let t = std::time::Instant::now();
    let (mut it, mut expl) = (0u32, f64::INFINITY);
    let mut trace = Vec::new();
    while it < max_iters {
        for _ in 0..every {
            s.iterate();
            it += 1;
        }
        expl = s.exploitability() / pot * 100.0;
        trace.push(serde_json::json!([it, expl, t.elapsed().as_secs_f64()]));
        if expl <= target {
            break;
        }
    }
    let mix = |path: &[PathStep]| -> Result<serde_json::Value, String> {
        let v = s.node_view(path)?;
        let p = v.player.ok_or("not an action node")? as usize;
        let mut m = vec![0f64; v.actions.len()];
        let mut tot = 0f64;
        for h in &v.players[p].hands {
            if let Some(st) = &h.strategy {
                for (k, x) in st.iter().enumerate() {
                    m[k] += h.reach as f64 * *x as f64;
                }
                tot += h.reach as f64;
            }
        }
        Ok(serde_json::json!({"player": if p == 0 { pos[oop_i] } else { pos[1 - oop_i] },
            "actions": v.actions.iter().map(|x| x.label.clone()).collect::<Vec<_>>(), "mix": m.iter().map(|x| x / tot).collect::<Vec<_>>()}))
    };
    let root = mix(&[])?;
    let chk = mix(&[PathStep::Action { index: 0 }])?;
    let out = serde_json::json!({"board": board, "iterations": it, "exploitability_pct_pot": expl, "trace": trace,
        "root_mix": [root, chk], "seconds": t.elapsed().as_secs_f64()});
    std::fs::write(&a[7], serde_json::to_vec_pretty(&out).unwrap()).map_err(|e| e.to_string())?;
    eprintln!("{it} iters {expl:.3}% pot");
    Ok(())
}
