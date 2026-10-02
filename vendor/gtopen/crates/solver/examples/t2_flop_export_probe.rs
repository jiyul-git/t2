//! E4 measurement only: solve ONE flop exactly like t2_cont_panel (same tree, keep-fraction weights, EPS floor,
//! target exploitability) and measure what a postflop strategy export would cost. Writes nothing into any panel dir.
//!
//!   t2_flop_export_probe <terminal.json> <menu.json> <board> <out_dir> <max_iters> <target_pct_pot> <check_every>
//!
//! Outputs in out_dir: probe.json (counts, sizes, timings), strategy_combo_f32.bin (average strategy of every action node,
//! combo level, f32, node order), strategy_class_f32.bin (same, aggregated to 169 classes by in-class mean over the combos
//! present), full.gtosolve (Solver::save: regrets + strategy sums, f32).
use solver::cards::{rank, suit};
use solver::preflop::equity::{class_index, class_label, NUM_CLASSES};
use solver::tree::{TreeConfig, KIND_ACTION, KIND_CHANCE};
use solver::{Solver, Spot, SpotConfig};
use std::io::Write;
use std::sync::Arc;
use std::time::Instant;

const EPS: f32 = 1e-3;

fn full_range() -> String {
    (0..NUM_CLASSES).map(class_label).collect::<Vec<_>>().join(",")
}

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 8 {
        return Err("terminal.json menu.json board out_dir max_iters target_pct check_every".into());
    }
    let read = |p: &str| -> Result<serde_json::Value, String> {
        serde_json::from_slice(&std::fs::read(p).map_err(|e| format!("{p}: {e}"))?).map_err(|e| format!("{p}: {e}"))
    };
    let term = read(&a[1])?;
    let menu = read(&a[2])?;
    let board = a[3].clone();
    let out = std::path::PathBuf::from(&a[4]);
    std::fs::create_dir_all(&out).map_err(|e| e.to_string())?;
    let max_iters: u32 = a[5].parse().map_err(|_| "max_iters")?;
    let target: f64 = a[6].parse().map_err(|_| "target")?;
    let every: u32 = a[7].parse().map_err(|_| "check_every")?;
    let pl = term["players"].as_array().ok_or("players")?;
    let pos: Vec<&str> = pl.iter().map(|p| p["position"].as_str().unwrap()).collect();
    let order = |i: usize| -> (usize, u64) {
        let p = pos[i];
        (if p == "SB" { 0 } else if p == "BB" { 1 } else { 2 }, pl[i]["seat"].as_u64().unwrap_or(99))
    };
    let oop_i = if order(0) <= order(1) { 0 } else { 1 };
    let ip_i = 1 - oop_i;
    let keep_of = |i: usize| -> Vec<f64> { pl[i]["class_keep_fraction"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect() };
    let keep = [keep_of(oop_i), keep_of(ip_i)];
    let pot = term["pot_bb"].as_f64().unwrap();
    let mut tree: TreeConfig = serde_json::from_value(menu["tree"].clone()).map_err(|e| format!("menu.tree: {e}"))?;
    tree.starting_pot = pot;
    tree.effective_stack = term["effective_behind_bb"].as_f64().unwrap();
    tree.rake_pct = 0.0;
    tree.rake_cap = 0.0;
    let mut spot = Spot::new(SpotConfig { board: board.clone(), range_oop: full_range(), range_ip: full_range(), tree })?;
    for p in 0..2 {
        for (i, h) in spot.hands[p].iter_mut().enumerate() {
            let w = (keep[p][class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2))] as f32).max(EPS);
            h.weight = w;
            spot.weights[p][i] = w;
        }
    }
    let mut s = Solver::new(Arc::new(spot));
    let t = Instant::now();
    let (mut iters, mut expl) = (0u32, f64::INFINITY);
    while iters < max_iters {
        for _ in 0..every {
            s.iterate();
            iters += 1;
        }
        expl = s.exploitability() / pot * 100.0;
        if expl <= target {
            break;
        }
    }
    let solve_s = t.elapsed().as_secs_f64();
    s.ensure_symmetric();
    let spot = s.spot.clone();
    let nodes = &spot.tree.nodes;
    // counts per street
    let mut action_nodes = [0u64; 3];
    let mut chance_nodes = [0u64; 3];
    let mut combo_floats = [0u64; 3];
    let mut class_floats = [0u64; 3];
    for n in nodes.iter() {
        let st = n.street as usize;
        if n.kind == KIND_ACTION {
            action_nodes[st] += 1;
            combo_floats[st] += n.num_children as u64 * spot.hands[n.player as usize].len() as u64;
            class_floats[st] += n.num_children as u64 * NUM_CLASSES as u64;
        } else if n.kind == KIND_CHANCE {
            chance_nodes[st] += 1;
        }
    }
    // export A (combo f32) and B (class f32)
    let t = Instant::now();
    let mut fa = std::io::BufWriter::new(std::fs::File::create(out.join("strategy_combo_f32.bin")).map_err(|e| e.to_string())?);
    let mut fb = std::io::BufWriter::new(std::fs::File::create(out.join("strategy_class_f32.bin")).map_err(|e| e.to_string())?);
    let cls: [Vec<usize>; 2] = [0, 1].map(|p| spot.hands[p].iter().map(|h| class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2))).collect());
    for (idx, n) in nodes.iter().enumerate() {
        if n.kind != KIND_ACTION {
            continue;
        }
        let sigma = s.average_strategy(idx as u32, n);
        let p = n.player as usize;
        let nh = spot.hands[p].len();
        let na = n.num_children as usize;
        let bytes: &[u8] = unsafe { std::slice::from_raw_parts(sigma.as_ptr() as *const u8, sigma.len() * 4) };
        fa.write_all(bytes).map_err(|e| e.to_string())?;
        let mut cl = vec![0f32; na * NUM_CLASSES];
        let mut cnt = vec![0f32; NUM_CLASSES];
        for j in 0..nh {
            cnt[cls[p][j]] += 1.0;
        }
        for ai in 0..na {
            for j in 0..nh {
                cl[ai * NUM_CLASSES + cls[p][j]] += sigma[ai * nh + j];
            }
            for k in 0..NUM_CLASSES {
                if cnt[k] > 0.0 {
                    cl[ai * NUM_CLASSES + k] /= cnt[k];
                }
            }
        }
        let bytes: &[u8] = unsafe { std::slice::from_raw_parts(cl.as_ptr() as *const u8, cl.len() * 4) };
        fb.write_all(bytes).map_err(|e| e.to_string())?;
    }
    fa.flush().map_err(|e| e.to_string())?;
    fb.flush().map_err(|e| e.to_string())?;
    let export_s = t.elapsed().as_secs_f64();
    let t = Instant::now();
    s.save(out.join("full.gtosolve").to_str().unwrap())?;
    let save_s = t.elapsed().as_secs_f64();
    let size = |f: &str| std::fs::metadata(out.join(f)).map(|m| m.len()).unwrap_or(0);
    let probe = serde_json::json!({
        "board": board, "terminal_pot_bb": pot, "iterations": iters, "exploitability_pct_pot": expl, "solve_s": solve_s,
        "tree_nodes": nodes.len(), "action_nodes_by_street": action_nodes, "chance_nodes_by_street": chance_nodes,
        "hands": [spot.hands[0].len(), spot.hands[1].len()],
        "strategy_floats_combo_by_street": combo_floats, "strategy_floats_class_by_street": class_floats,
        "bytes": {"strategy_combo_f32": size("strategy_combo_f32.bin"), "strategy_class_f32": size("strategy_class_f32.bin"),
                  "full_gtosolve": size("full.gtosolve")},
        "export_s_combo_and_class": export_s, "save_s_full": save_s,
        "note": "class export = unweighted in-class mean over the combos present (suit information lost); measurement only",
    });
    std::fs::write(out.join("probe.json"), serde_json::to_string_pretty(&probe).unwrap()).map_err(|e| e.to_string())?;
    println!("{}", serde_json::to_string(&probe).unwrap());
    Ok(())
}
