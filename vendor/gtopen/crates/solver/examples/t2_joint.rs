//! T2 joint-CFR prototype (J1): the preflop tree and a fixed flop panel at ONE heads-up
//! terminal are solved together (feature `t2-joint`), for comparison with the damped
//! outer fixed point on the identical game (same panel, menu, weights, normaliser).
//!
//!   t2_joint <config.json> <menu.json> <panel.json> <iterations> <check_every> <out.json> [path-spec]
//!
//! Env: PREFLOP_EQ_SAMPLES/SEED, PREFLOP_MULTIWAY_SEED, T2_STORAGE=compressed.
//! Output mirrors t2_cont_terminal (players / frequencies) at the final checkpoint and
//! adds a "checkpoints" trace.
use solver::cards::{rank, suit};
use solver::preflop::equity::{class_combos, class_index, class_label, class_prob, EquityTable, NUM_CLASSES};
use solver::preflop::t2joint::{self, Eval, Flop, Joint};
use solver::preflop::{PreflopConfig, PreflopSolver};
use solver::tree::TreeConfig;
use solver::{Solver, Spot, SpotConfig};
use std::sync::{Arc, Mutex};
use std::time::Instant;

fn vm_kb(key: &str) -> u64 {
    std::fs::read_to_string("/proc/self/status").ok().and_then(|s| {
        s.lines().find(|l| l.starts_with(key)).and_then(|l| l.split_whitespace().nth(1)?.parse().ok())
    }).unwrap_or(0)
}

fn fnv(parts: &[&[f32]]) -> String {
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
    if a.len() < 7 {
        return Err("config menu panel iterations check_every out.json [path-spec]".into());
    }
    let read = |p: &str| -> Result<(Vec<u8>, serde_json::Value), String> {
        let b = std::fs::read(p).map_err(|e| format!("{p}: {e}"))?;
        Ok((b.clone(), serde_json::from_slice(&b).map_err(|e| format!("{p}: {e}"))?))
    };
    let cfg: PreflopConfig = serde_json::from_slice(&read(&a[1])?.0).map_err(|e| e.to_string())?;
    let (menu_b, menu) = read(&a[2])?;
    let (_, panel) = read(&a[3])?;
    let iters: u32 = a[4].parse().map_err(|_| "iterations")?;
    let every: u32 = a[5].parse().map_err(|_| "check_every")?;
    let spec = a.get(7).cloned().unwrap_or_else(|| "fold,raise,fold,call".into());
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let eq = Arc::new(EquityTable::build(samples));
    let mut s = PreflopSolver::new(cfg, eq)?;
    // terminal
    let mut path = Vec::new();
    let mut node = 0usize;
    for kind in spec.split(',') {
        let nd = &s.nodes[node];
        let idx = nd.actions.iter().enumerate().filter(|(_, x)| x.kind == kind)
            .min_by(|x, y| x.1.to.partial_cmp(&y.1.to).unwrap()).map(|(i, _)| i).ok_or("bad path")?;
        path.push(idx);
        node = s.child(node, idx);
    }
    let term = node;
    let nd = &s.nodes[term];
    if nd.kind != 2 || nd.live.count_ones() != 2 {
        return Err("not a heads-up pot-share terminal".into());
    }
    let live: Vec<usize> = (0..s.n).filter(|&p| nd.live & (1 << p) != 0).collect();
    let oop = *live.iter().find(|&&p| s.cfg.positions[p] == "BB" || s.cfg.positions[p] == "SB").ok_or("no blind")?;
    let ip = *live.iter().find(|&&p| p != oop).unwrap();
    let pot = nd.pot;
    let behind = live.iter().map(|&p| s.cfg.stack - nd.invested[p] + s.cfg.ante).fold(f64::INFINITY, f64::min);
    let mut tree: TreeConfig = serde_json::from_value(menu["tree"].clone()).map_err(|e| e.to_string())?;
    tree.starting_pot = pot;
    tree.effective_stack = behind;
    tree.rake_pct = 0.0;
    tree.rake_cap = 0.0;
    let storage_name = std::env::var("T2_STORAGE").unwrap_or_else(|_| "f32".into());
    let storage = if storage_name == "compressed" { solver::store::Storage::Compressed } else { solver::store::Storage::F32 };
    let full = (0..NUM_CLASSES).map(class_label).collect::<Vec<_>>().join(",");
    let t_build = Instant::now();
    let mut flops = Vec::new();
    let mut arena = 0u64;
    for f in panel["panel"].as_array().ok_or("panel")? {
        let board = f["board"].as_str().unwrap().to_string();
        let spot = Spot::new(SpotConfig { board: board.clone(), range_oop: full.clone(), range_ip: full.clone(), tree: tree.clone() })?;
        let cls: [Vec<usize>; 2] = std::array::from_fn(|r| spot.hands[r].iter().map(|h| class_index(rank(h.c1), rank(h.c2), suit(h.c1) == suit(h.c2))).collect());
        let mut cnt = vec![0f64; NUM_CLASSES];
        for &k in &cls[0] {
            cnt[k] += 1.0;
        }
        let avail = (0..NUM_CLASSES).map(|k| cnt[k] / class_combos(k) as f64).collect();
        let mut solver = Solver::with_storage(Arc::new(spot), storage);
        solver.use_isomorphism = false;
        arena += solver.arena_bytes();
        flops.push(Mutex::new(Flop { board, weight: f["weight"].as_f64().unwrap(), solver, cls, avail }));
    }
    let norm_of = |p: usize| panel["fixed_normaliser"][&s.cfg.positions[p]].as_f64().expect("fixed_normaliser");
    t2joint::install(Joint { node: term, live: nd.live, pot, seat: [oop, ip], norm: [norm_of(oop), norm_of(ip)], flops });
    let build_ms = t_build.elapsed().as_secs_f64() * 1e3;
    eprintln!("built {} flops, arena {:.1} GB, {:.0} ms", panel["panel"].as_array().unwrap().len(), arena as f64 / 1e9, build_ms);

    let mix = |s: &PreflopSolver, path: &[usize]| -> Option<serde_json::Value> {
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
            m.insert(key, serde_json::json!(f));
        }
        Some(serde_json::json!({"actor": s.cfg.positions[actor], "mix": m,
            "class_strategy": (0..nd.actions.len()).map(|ai| sigma[ai*NUM_CLASSES..(ai+1)*NUM_CLASSES].to_vec()).collect::<Vec<_>>(),
            "actions": nd.actions.iter().map(|x| x.label.clone()).collect::<Vec<_>>()}))
    };
    let snapshot = |s: &PreflopSolver, elapsed: f64| -> serde_json::Value {
        let (gaps, evs) = s.gaps_and_evs();
        let (_, reaches) = s.walk(&path).unwrap();
        let mut freq = serde_json::Map::new();
        for k in 0..s.n - 1 {
            if let Some(m) = mix(s, &vec![0usize; k]) { freq.insert(format!("rfi_{}", s.cfg.positions[k]), m); }
        }
        if let Some(m) = mix(s, &path[..path.len() - 1]) { freq.insert("terminal_parent".into(), m); }
        let mut players = Vec::new();
        let mut invariant = 0f64;
        for &p in &live {
            let mass: f32 = reaches[p].iter().sum();
            let normed: Vec<f32> = reaches[p].iter().map(|x| x / mass).collect();
            let g_avg = t2joint::gross(s, term, p, &reaches, Eval::Average).unwrap();
            let g_br = t2joint::gross(s, term, p, &reaches, Eval::BestResponse).unwrap();
            invariant += (0..NUM_CLASSES).map(|h| normed[h] as f64 * g_avg[h]).sum::<f64>();
            players.push(serde_json::json!({
                "seat": p, "position": s.cfg.positions[p], "invested_bb": s.nodes[term].invested[p], "range_mass": mass,
                "class_keep_fraction": (0..NUM_CLASSES).map(|h| reaches[p][h] as f64 / class_prob(h) as f64).collect::<Vec<_>>(),
                "class_reach_normalized": normed, "gross_avg": g_avg, "gross_br": g_br,
            }));
        }
        let folded: f32 = (0..s.n).filter(|x| !live.contains(x)).map(|x| reaches[x].iter().sum::<f32>()).product();
        let pe = t2joint::postflop_exploitability(&reaches, folded);
        let norm: Vec<Vec<f32>> = live.iter().map(|&p| { let m: f32 = reaches[p].iter().sum(); reaches[p].iter().map(|x| x / m).collect() }).collect();
        serde_json::json!({
            "iteration": s.iteration, "elapsed_s": elapsed, "gap_total": gaps.iter().sum::<f64>(), "gaps": gaps, "evs": evs,
            "frequencies": freq, "players": players,
            "invariant": {"sum_range_weighted_gross": invariant, "pot": pot, "unallocated_bb": pot - invariant},
            "postflop_exploitability_pct_pot": pe.iter().map(|(b, e)| serde_json::json!({"board": b, "pct_pot": e})).collect::<Vec<_>>(),
            "ranges_hash_fnv1a64": fnv(&norm.iter().map(|v| v.as_slice()).collect::<Vec<_>>()),
            "vm_rss_kb": vm_kb("VmRSS:"), "vm_hwm_kb": vm_kb("VmHWM:"),
        })
    };
    let t0 = Instant::now();
    let mut checkpoints = Vec::new();
    let mut per_iter = Vec::new();
    for i in 0..iters {
        let t = Instant::now();
        s.iterate();
        per_iter.push(t.elapsed().as_secs_f64());
        if (i + 1) % every == 0 || i + 1 == iters {
            let tc = Instant::now();
            let mut snap = snapshot(&s, t0.elapsed().as_secs_f64());
            snap["checkpoint_s"] = serde_json::json!(tc.elapsed().as_secs_f64());
            eprintln!("joint it {} gap {:.5} unalloc {:+.4} BTNopen {} BBfold {} ({:.0}s)", s.iteration,
                snap["gap_total"].as_f64().unwrap(), snap["invariant"]["unallocated_bb"].as_f64().unwrap(),
                snap["frequencies"]["rfi_BTN"]["mix"]["raise_2"], snap["frequencies"]["terminal_parent"]["mix"]["fold"],
                t0.elapsed().as_secs_f64());
            checkpoints.push(snap);
            let last = checkpoints.last().unwrap().clone();
            let out = serde_json::json!({
                "schema": "t2_joint_cfr_v1", "config": s.cfg, "config_file": a[1], "menu_id": menu["id"], "menu_hash_fnv1a64": fnv(&[&menu_b.iter().map(|&b| b as f32).collect::<Vec<_>>()]),
                "panel_id": panel["id"], "panel_hash_sha256": panel["panel_hash_sha256"], "fixed_normaliser": panel["fixed_normaliser"],
                "tree_config": tree, "storage": storage_name, "postflop_algorithm": "DCFR (solver default), isomorphism off, one alternating update per role per preflop iteration",
                "eq_samples": samples, "path_spec": spec, "path": path, "terminal_node": term, "terminal_live_mask": s.nodes[term].live,
                "pot_bb": pot, "effective_behind_bb": behind, "spr": behind / pot, "roles": {"OOP": s.cfg.positions[oop], "IP": s.cfg.positions[ip]},
                "value_convention": "gross_share", "zero_reach_definition": "none needed in the regret path (current-strategy CFVs); average-strategy evaluation of never-reached hands uses the solver's uniform fallback",
                "build_ms": build_ms, "postflop_arena_bytes": arena, "per_iteration_s": per_iter,
                "class_labels": (0..NUM_CLASSES).map(class_label).collect::<Vec<_>>(),
                "gap_total": last["gap_total"], "frequencies": last["frequencies"], "players": last["players"],
                "ranges_hash_fnv1a64": last["ranges_hash_fnv1a64"], "checkpoints": checkpoints,
                "source_commit": std::env::var("T2_SOURCE_COMMIT").unwrap_or_else(|_| "unknown".into()),
            });
            std::fs::write(&a[6], serde_json::to_vec(&out).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}
