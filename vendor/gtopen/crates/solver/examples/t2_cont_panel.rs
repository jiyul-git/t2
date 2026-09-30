//! T2 HU-continuation prototype, step C3: solve every flop of a pre-registered panel at
//! the terminal's arriving ranges and write one provenance-stamped artifact per flop.
//!
//!   t2_cont_panel <terminal.json> <menu.json> <panel.json> <out_dir> <max_iters> <target_pct_pot> <check_every>
//!
//! One solve per flop with every class's keep fraction floored at EPS (decision C0-2:
//! eps_tremble_avg is the primary value; hand-level BR from the same solve is kept as the
//! sensitivity bound). Existing per-flop files are reused ONLY if their provenance key
//! (ranges hash, menu hash, panel hash, tree config, eps, target) matches exactly;
//! a mismatch is an error, never a silent reuse.
//! Env: T2_SOURCE_COMMIT (recorded), T2_STORAGE=compressed (optional),
//! T2_PANEL_BOARDS=b1,b2,... (optional: solve only these panel boards, so independent
//! processes can share one panel; the provenance key is the same either way).
use solver::cards::{rank, suit};
use solver::game::Dealt;
use solver::preflop::equity::{class_index, class_label, NUM_CLASSES};
use solver::tree::TreeConfig;
use solver::{Solver, Spot, SpotConfig};
use std::sync::Arc;
use std::time::Instant;

const EPS: f32 = 1e-3;

fn fnv(bytes: &[u8]) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in bytes {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    format!("{h:016x}")
}

/// VmHWM of this process (peak resident set), kB; None off Linux.
fn peak_rss_kb() -> Option<u64> {
    let st = std::fs::read_to_string("/proc/self/status").ok()?;
    st.lines().find(|l| l.starts_with("VmHWM:"))?.split_whitespace().nth(1)?.parse().ok()
}

fn full_range() -> String {
    (0..NUM_CLASSES).map(class_label).collect::<Vec<_>>().join(",")
}

fn cls(h: &solver::game::HandInfo) -> usize {
    class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2))
}

/// gross-share class values and valid (opponent-compatible) mass per class
fn class_values(s: &Solver, p: usize, cfv: &[f32]) -> (Vec<Option<f64>>, Vec<f64>, Vec<u32>) {
    let spot = &*s.spot;
    let pot = spot.tree.config.starting_pot;
    let opp = &spot.hands[1 - p];
    let (mut tot, mut by) = (0f64, [0f64; 52]);
    for h in opp {
        tot += h.weight as f64;
        by[h.c1 as usize] += h.weight as f64;
        by[h.c2 as usize] += h.weight as f64;
    }
    let mut num = vec![0f64; NUM_CLASSES];
    let mut den = vec![0f64; NUM_CLASSES];
    let mut combos = vec![0u32; NUM_CLASSES];
    for (i, h) in spot.hands[p].iter().enumerate() {
        let same = spot.same_combo[p][i];
        let corr = if same != solver::tree::SENTINEL { opp[same as usize].weight as f64 } else { 0.0 };
        let valid = tot - by[h.c1 as usize] - by[h.c2 as usize] + corr;
        let k = cls(h);
        num[k] += cfv[i] as f64;
        den[k] += valid;
        combos[k] += 1;
    }
    let vals = (0..NUM_CLASSES).map(|k| if den[k] > 0.0 { Some(num[k] / den[k] + pot / 2.0) } else { None }).collect();
    (vals, den, combos)
}

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 8 {
        return Err("terminal.json menu.json panel.json out_dir max_iters target_pct check_every".into());
    }
    let read = |p: &str| -> Result<(Vec<u8>, serde_json::Value), String> {
        let b = std::fs::read(p).map_err(|e| format!("{p}: {e}"))?;
        let v = serde_json::from_slice(&b).map_err(|e| format!("{p}: {e}"))?;
        Ok((b, v))
    };
    let (_, term) = read(&a[1])?;
    let (menu_b, menu) = read(&a[2])?;
    let (_, panel) = read(&a[3])?;
    let out_dir = std::path::PathBuf::from(&a[4]);
    std::fs::create_dir_all(&out_dir).map_err(|e| e.to_string())?;
    let max_iters: u32 = a[5].parse().map_err(|_| "max_iters")?;
    let target: f64 = a[6].parse().map_err(|_| "target")?;
    let every: u32 = a[7].parse().map_err(|_| "check_every")?;
    let pl = term["players"].as_array().ok_or("players")?;
    let pos: Vec<&str> = pl.iter().map(|p| p["position"].as_str().unwrap()).collect();
    if pl.len() != 2 {
        return Err("heads-up terminals only (the postflop solver is heads-up)".into());
    }
    // OOP = first to act postflop: SB, then BB, then the earlier seat (CO before BTN)
    let order = |i: usize| -> (usize, u64) {
        let p = pos[i];
        (if p == "SB" { 0 } else if p == "BB" { 1 } else { 2 }, pl[i]["seat"].as_u64().unwrap_or(99))
    };
    let oop_i = if order(0) <= order(1) { 0 } else { 1 };
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
    let storage_name = std::env::var("T2_STORAGE").unwrap_or_else(|_| "f32".into());
    let storage = if storage_name == "compressed" { solver::store::Storage::Compressed } else { solver::store::Storage::F32 };
    let key = serde_json::json!({
        "value_convention": "gross_share", "zero_reach_definition": "eps_tremble_avg",
        "eps": EPS, "ranges_hash_fnv1a64": term["ranges_hash_fnv1a64"], "menu_hash_fnv1a64": fnv(&menu_b),
        "menu_id": menu["id"], "panel_hash_sha256": panel["panel_hash_sha256"], "tree_config": tree,
        "pot_bb": pot, "effective_behind_bb": behind, "target_exploitability_pct_pot": target,
        "max_iters": max_iters, "storage": storage_name,
        "terminal_path_spec": term["path_spec"], "aggressor": term["aggressor"],
        "roles": {"OOP": pos[oop_i], "IP": pos[ip_i]},
    });
    let commit = std::env::var("T2_SOURCE_COMMIT").unwrap_or_else(|_| "unknown".into());
    let only: Option<Vec<String>> = std::env::var("T2_PANEL_BOARDS").ok().map(|v| v.split(',').map(|x| x.to_string()).collect());
    let boards: Vec<&str> = panel["panel"].as_array().ok_or("panel")?.iter().map(|f| f["board"].as_str().unwrap()).collect();
    if let Some(o) = &only {
        if let Some(b) = o.iter().find(|b| !boards.contains(&b.as_str())) {
            return Err(format!("T2_PANEL_BOARDS: {b} is not on the panel"));
        }
    }
    for f in panel["panel"].as_array().ok_or("panel")? {
        let board = f["board"].as_str().unwrap();
        if only.as_ref().map_or(false, |o| !o.iter().any(|b| b == board)) {
            continue;
        }
        let path = out_dir.join(format!("{board}.json"));
        if path.exists() {
            let (_, old) = read(path.to_str().unwrap())?;
            if old["provenance_key"] != key {
                return Err(format!("{board}: existing artifact has a different provenance key; refusing to reuse or overwrite"));
            }
            eprintln!("reuse {board}");
            continue;
        }
        let t = Instant::now();
        let mut spot = Spot::new(SpotConfig { board: board.into(), range_oop: full_range(), range_ip: full_range(), tree: tree.clone() })?;
        for p in 0..2 {
            for (i, h) in spot.hands[p].iter_mut().enumerate() {
                let w = (keep[p][class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2))] as f32).max(EPS);
                h.weight = w;
                spot.weights[p][i] = w;
            }
        }
        let build_ms = t.elapsed().as_secs_f64() * 1e3;
        let nodes = spot.tree.nodes.len();
        let mut s = Solver::with_storage(Arc::new(spot), storage);
        let t = Instant::now();
        let (mut iters, mut expl) = (0u32, f64::INFINITY);
        let mut trace = Vec::new();
        while iters < max_iters {
            for _ in 0..every {
                s.iterate();
                iters += 1;
            }
            expl = s.exploitability() / pot * 100.0;
            trace.push(serde_json::json!([iters, expl]));
            if expl <= target {
                break;
            }
        }
        let solve_ms = t.elapsed().as_secs_f64() * 1e3;
        s.ensure_symmetric();
        let denom = s.pair_weight_sum();
        let mut players = Vec::new();
        let mut inv = [0f64; 2];
        for p in 0..2 {
            let w_o = s.spot.weights[1 - p].clone();
            let c_avg = s.traverse_avg(0, p, &w_o, Dealt::default());
            let c_br = s.traverse_br(0, p, &w_o, Dealt::default());
            inv[p] = s.spot.weights[p].iter().zip(&c_avg).map(|(&w, &v)| w as f64 * v as f64).sum::<f64>() / denom + pot / 2.0;
            let (va, valid, combos) = class_values(&s, p, &c_avg);
            let (vb, _, _) = class_values(&s, p, &c_br);
            let eq = s.equity(p, &w_o, Dealt::default());
            let mut qn = vec![0f64; NUM_CLASSES];
            let mut qc = vec![0f64; NUM_CLASSES];
            for (i, h) in s.spot.hands[p].iter().enumerate() {
                if eq[i].is_finite() {
                    qn[cls(h)] += eq[i] as f64;
                    qc[cls(h)] += 1.0;
                }
            }
            let equity: Vec<Option<f64>> = (0..NUM_CLASSES).map(|k| if qc[k] > 0.0 { Some(qn[k] / qc[k]) } else { None }).collect();
            players.push(serde_json::json!({
                "position": if p == 0 { pos[oop_i] } else { pos[ip_i] }, "postflop_role": if p == 0 { "OOP" } else { "IP" },
                "gross_eps": va, "gross_br": vb, "equity": equity, "valid_mass": valid, "combos_on_board": combos,
            }));
        }
        let out = serde_json::json!({
            "schema": "t2_hu_continuation_flop_v1", "board": board, "stratum": f["stratum"], "panel_weight": f["weight"],
            "provenance_key": key, "solver_commit": commit, "solver": "vendored GTOpen CPU postflop Solver (DCFR), isomorphism on",
            "iterations": iters, "exploitability_pct_pot": expl, "trace": trace,
            "converged": expl <= target,
            "cost": {"build_ms": build_ms, "solve_ms": solve_ms, "tree_nodes": nodes, "arena_bytes": s.arena_bytes(),
                     "threads": rayon::current_num_threads(), "peak_rss_kb": peak_rss_kb()},
            "invariant": {"range_mean_gross": inv, "sum": inv[0] + inv[1], "pot": pot, "error": inv[0] + inv[1] - pot,
                          "note": "at the EPS-floored ranges the solve used"},
            "players": players,
        });
        let tmp = path.with_extension("partial");
        std::fs::write(&tmp, serde_json::to_vec(&out).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        std::fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
        eprintln!("{board} {} iters {:.3}%pot solve {:.0}s inv_err {:.1e}", iters, expl, solve_ms / 1e3, inv[0] + inv[1] - pot);
    }
    Ok(())
}
