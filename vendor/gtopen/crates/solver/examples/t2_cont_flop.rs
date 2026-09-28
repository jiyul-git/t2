//! T2 HU-continuation prototype, step C2: cost and per-class continuation values of
//! ONE flop, solved with the vendored CPU postflop solver at the preflop terminal's
//! actual arriving ranges.
//!
//!   t2_cont_flop <terminal.json> <menu.json> <board> <max_iters> <target_pct_pot> <check_every> <out.json>
//!
//! Terminal JSON comes from t2_cont_terminal. Postflop OOP = BB (players[1]),
//! IP = BTN (players[0]) for the BTN-open/BB-call terminal (checked by position names).
//! Ranges are class-uniform: every combo of a class gets that class's keep fraction.
//! All 1326 combos stay in the hand list, so zero-reach classes get strategies/values.
//!
//! Values per class (value_convention = gross_share, bb, zero rake):
//!   avg   : CFV under the average strategy (zero own reach -> uniform fallback play)
//!   br    : hand-level best response vs the opponent's fixed average strategy
//!   eps   : second solve with every class's keep fraction floored at EPS, avg CFV
//! Also raw equity vs the opponent range (for realization = gross/(pot*equity)).
use solver::cards::{rank, suit};
use solver::game::Dealt;
use solver::preflop::equity::{class_index, class_label, NUM_CLASSES};
use solver::tree::TreeConfig;
use solver::{Solver, Spot, SpotConfig};
use std::sync::Arc;
use std::time::Instant;

const EPS: f32 = 1e-3;

fn vm_hwm_kb() -> u64 {
    std::fs::read_to_string("/proc/self/status").ok().and_then(|s| {
        s.lines().find(|l| l.starts_with("VmHWM:")).and_then(|l| l.split_whitespace().nth(1)?.parse().ok())
    }).unwrap_or(0)
}

fn full_range() -> String {
    (0..NUM_CLASSES).map(class_label).collect::<Vec<_>>().join(",")
}

/// Build a spot with all combos, then install class-uniform weights (zeros allowed).
fn build(board: &str, tree: &TreeConfig, keep: [&[f64]; 2], floor: f32) -> Result<(Spot, f64), String> {
    let t = Instant::now();
    let mut spot = Spot::new(SpotConfig {
        board: board.into(), range_oop: full_range(), range_ip: full_range(), tree: tree.clone(),
    })?;
    for p in 0..2 {
        for (i, h) in spot.hands[p].iter_mut().enumerate() {
            let k = class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2));
            let w = (keep[p][k] as f32).max(floor);
            h.weight = w;
            spot.weights[p][i] = w;
        }
    }
    Ok((spot, t.elapsed().as_secs_f64() * 1e3))
}

struct Solved {
    solver: Solver,
    iters: u32,
    trace: Vec<serde_json::Value>,
    solve_ms: f64,
    exploit_pct: f64,
}

fn solve(spot: Spot, max_iters: u32, target: f64, every: u32) -> Solved {
    let pot = spot.tree.config.starting_pot;
    let storage = if std::env::var("T2_STORAGE").ok().as_deref() == Some("compressed") {
        solver::store::Storage::Compressed
    } else {
        solver::store::Storage::F32
    };
    let mut s = Solver::with_storage(Arc::new(spot), storage);
    let t = Instant::now();
    let mut trace = Vec::new();
    let mut exploit_pct = f64::INFINITY;
    let mut iters = 0;
    while iters < max_iters {
        for _ in 0..every {
            s.iterate();
            iters += 1;
        }
        exploit_pct = s.exploitability() / pot * 100.0;
        trace.push(serde_json::json!({"iteration": iters, "exploitability_pct_pot": exploit_pct,
            "elapsed_ms": t.elapsed().as_secs_f64() * 1e3}));
        if exploit_pct <= target {
            break;
        }
    }
    Solved { solver: s, iters, trace, solve_ms: t.elapsed().as_secs_f64() * 1e3, exploit_pct }
}

/// Per-class gross share (bb) and per-class valid mass for player p.
fn class_values(s: &Solver, p: usize, cfv: &[f32]) -> (Vec<Option<f64>>, Vec<f64>) {
    let spot = &*s.spot;
    let pot = spot.tree.config.starting_pot;
    let opp = &spot.hands[1 - p];
    let mut tot = 0f64;
    let mut by = [0f64; 52];
    for h in opp {
        tot += h.weight as f64;
        by[h.c1 as usize] += h.weight as f64;
        by[h.c2 as usize] += h.weight as f64;
    }
    let mut num = vec![0f64; NUM_CLASSES];
    let mut den = vec![0f64; NUM_CLASSES];
    for (i, h) in spot.hands[p].iter().enumerate() {
        let same = spot.same_combo[p][i];
        let corr = if same != solver::tree::SENTINEL { opp[same as usize].weight as f64 } else { 0.0 };
        let valid = tot - by[h.c1 as usize] - by[h.c2 as usize] + corr;
        let k = class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2));
        num[k] += cfv[i] as f64;
        den[k] += valid;
    }
    // engine utility is relative to having put pot/2 in -> gross = u + pot/2
    let vals = (0..NUM_CLASSES).map(|k| if den[k] > 0.0 { Some(num[k] / den[k] + pot / 2.0) } else { None }).collect();
    (vals, den)
}

fn class_equity(s: &Solver, p: usize) -> Vec<Option<f64>> {
    let spot = &*s.spot;
    let eq = s.equity(p, &spot.weights[1 - p], Dealt::default());
    let mut num = vec![0f64; NUM_CLASSES];
    let mut cnt = vec![0f64; NUM_CLASSES];
    for (i, h) in spot.hands[p].iter().enumerate() {
        if eq[i].is_finite() {
            let k = class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2));
            num[k] += eq[i] as f64;
            cnt[k] += 1.0;
        }
    }
    (0..NUM_CLASSES).map(|k| if cnt[k] > 0.0 { Some(num[k] / cnt[k]) } else { None }).collect()
}

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 8 {
        return Err("terminal.json menu.json board max_iters target_pct check_every out.json".into());
    }
    let term: serde_json::Value = serde_json::from_slice(&std::fs::read(&a[1]).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let menu: serde_json::Value = serde_json::from_slice(&std::fs::read(&a[2]).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let board = a[3].clone();
    let max_iters: u32 = a[4].parse().map_err(|_| "max_iters")?;
    let target: f64 = a[5].parse().map_err(|_| "target")?;
    let every: u32 = a[6].parse().map_err(|_| "check_every")?;
    let pl = term["players"].as_array().ok_or("players")?;
    let pos: Vec<&str> = pl.iter().map(|p| p["position"].as_str().unwrap()).collect();
    // postflop OOP index into players[]: the blind acts first
    let oop_i = pos.iter().position(|p| *p == "BB" || *p == "SB").ok_or("no blind in terminal")?;
    let ip_i = 1 - oop_i;
    let keep_of = |i: usize| -> Vec<f64> { pl[i]["class_keep_fraction"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect() };
    let keep = [keep_of(oop_i), keep_of(ip_i)];
    let pot = term["pot_bb"].as_f64().unwrap();
    let behind = term["effective_behind_bb"].as_f64().unwrap();
    let mut tree: TreeConfig = serde_json::from_value(menu["tree"].clone()).map_err(|e| format!("menu.tree: {e}"))?;
    tree.starting_pot = pot;
    tree.effective_stack = behind;
    tree.rake_pct = 0.0;
    tree.rake_cap = 0.0;

    let (spot, build_ms) = build(&board, &tree, [&keep[0], &keep[1]], 0.0)?;
    let nodes = spot.tree.nodes.len();
    if std::env::var("T2_BUILD_ONLY").ok().as_deref() == Some("1") {
        println!("{}", serde_json::json!({"board": board, "menu": menu["id"], "tree_nodes": nodes,
            "action_nodes": spot.num_action_nodes(), "hands": [spot.hands[0].len(), spot.hands[1].len()],
            "arena_bytes_f32": spot.arena_bytes(), "tree_bytes": spot.tree_bytes(),
            "arena_bytes_compressed": spot.arena_bytes_for(solver::store::Storage::Compressed),
            "build_ms": build_ms, "vm_hwm_kb": vm_hwm_kb()}));
        return Ok(());
    }
    let hands = [spot.hands[0].len(), spot.hands[1].len()];
    let mut solved = solve(spot, max_iters, target, every);
    let arena = solved.solver.arena_bytes();
    let t = Instant::now();
    // make the queried policy suit-symmetric, as upstream does before reading values
    solved.solver.ensure_symmetric();
    let mut avg = Vec::new();
    let mut br = Vec::new();
    let mut invariant = [0f64; 2];
    let denom = solved.solver.pair_weight_sum();
    for p in 0..2 {
        let w_o = solved.solver.spot.weights[1 - p].clone();
        let c_avg = solved.solver.traverse_avg(0, p, &w_o, Dealt::default());
        let c_br = solved.solver.traverse_br(0, p, &w_o, Dealt::default());
        invariant[p] = solved.solver.spot.weights[p].iter().zip(&c_avg).map(|(&w, &v)| w as f64 * v as f64).sum::<f64>() / denom + pot / 2.0;
        avg.push(class_values(&solved.solver, p, &c_avg).0);
        br.push(class_values(&solved.solver, p, &c_br).0);
    }
    let equity = [class_equity(&solved.solver, 0), class_equity(&solved.solver, 1)];
    let query_ms = t.elapsed().as_secs_f64() * 1e3;
    drop(solved.solver);

    // eps-tremble re-solve
    let (spot_e, _) = build(&board, &tree, [&keep[0], &keep[1]], EPS)?;
    let mut se = solve(spot_e, max_iters, target, every);
    se.solver.ensure_symmetric();
    let mut eps = Vec::new();
    for p in 0..2 {
        let w_o = se.solver.spot.weights[1 - p].clone();
        let c = se.solver.traverse_avg(0, p, &w_o, Dealt::default());
        eps.push(class_values(&se.solver, p, &c).0);
    }
    let names = [pos[oop_i], pos[ip_i]];
    let rows: Vec<serde_json::Value> = (0..2).map(|p| {
        serde_json::json!({
            "position": names[p], "postflop_role": if p == 0 { "OOP" } else { "IP" },
            "class_keep_fraction": keep[p],
            "gross_avg": avg[p], "gross_br": br[p], "gross_eps": eps[p], "equity": equity[p],
        })
    }).collect();
    let out = serde_json::json!({
        "value_convention": "gross_share",
        "board": board, "pot_bb": pot, "effective_behind_bb": behind, "spr": behind / pot,
        "aggressor": term["aggressor"], "ranges_hash_fnv1a64": term["ranges_hash_fnv1a64"],
        "terminal_path_spec": term["path_spec"], "menu": menu, "tree_config": tree,
        "cost": {"build_ms": build_ms, "tree_nodes": nodes, "hands": hands, "arena_bytes": arena,
                 "solve_ms": solved.solve_ms, "iterations": solved.iters, "exploitability_pct_pot": solved.exploit_pct,
                 "query_ms": query_ms, "vm_hwm_kb": vm_hwm_kb(),
                 "cfv_floats_per_player": hands, "class_values_per_player": NUM_CLASSES,
                 "eps_solve_ms": se.solve_ms, "eps_iterations": se.iters, "eps_exploitability_pct_pot": se.exploit_pct},
        "trace": solved.trace, "eps_trace": se.trace,
        "invariant": {"range_mean_gross": invariant, "sum": invariant[0] + invariant[1], "pot": pot,
                      "error": invariant[0] + invariant[1] - pot},
        "eps": EPS, "players": rows,
        "solver": "vendored GTOpen CPU postflop Solver (DCFR default), isomorphism on",
        "storage": std::env::var("T2_STORAGE").unwrap_or_else(|_| "f32".into()),
    });
    std::fs::write(&a[7], serde_json::to_vec_pretty(&out).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    eprintln!("board {board} nodes {nodes} build {build_ms:.0}ms solve {:.0}ms iters {} expl {:.3}%pot arena {:.1}MB hwm {:.0}MB inv_err {:.2e}",
        out["cost"]["solve_ms"].as_f64().unwrap(), out["cost"]["iterations"], out["cost"]["exploitability_pct_pot"].as_f64().unwrap(),
        arena as f64 / 1e6, vm_hwm_kb() as f64 / 1e3, out["invariant"]["error"].as_f64().unwrap());
    Ok(())
}
