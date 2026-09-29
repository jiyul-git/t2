//! Enumerate every flop-reaching preflop pot-share terminal and measure its
//! average-strategy reach under the current preflop solution.
//!
//! Usage:
//!   cargo run --release --example t2_cont_census --features t2-cont -- \
//!     <config.json> <iterations> <out.json> [save.gtop]
//!
//! If T2_CONT_FILE is set, the preflop solve uses that injected continuation
//! table first. This makes the census suitable for ranking the *next* terminals
//! from an already-updated outer fixed-point state.
//!
//! Reach probabilities use the preflop model's class-independent abstraction:
//! product over seats of the total average-strategy reach mass. They therefore
//! intentionally share the existing model's no-inter-player-card-removal caveat.
use serde::Serialize;
use solver::preflop::equity::EquityTable;
use solver::preflop::{PreflopConfig, PreflopSolver};
use std::sync::Arc;

#[derive(Serialize)]
struct ActionStep {
    actor_seat: usize,
    actor: String,
    action_index: usize,
    kind: String,
    to_bb: f64,
    label: String,
}

#[derive(Serialize)]
struct SeatReach {
    seat: usize,
    position: String,
    live: bool,
    invested_bb: f64,
    behind_bb: f64,
    range_mass: f64,
    classes_with_positive_reach: usize,
}

#[derive(Serialize)]
struct TerminalRow {
    terminal_node: usize,
    path_action_indices: Vec<usize>,
    path_labels: Vec<String>,
    actions: Vec<ActionStep>,
    terminal_live_mask: u32,
    live_count: u32,
    live_positions: Vec<String>,
    aggressor_seat: i32,
    aggressor: String,
    raise_count: usize,
    pot_type: String,
    pot_bb: f64,
    effective_behind_bb: f64,
    spr: f64,
    reach_probability: f64,
    share_of_flop_reach: f64,
    seat_reach: Vec<SeatReach>,
    current_injected_terminal: bool,
}

fn pot_type(raises: usize) -> String {
    match raises {
        0 => "limped".into(),
        1 => "srp".into(),
        2 => "3bet".into(),
        3 => "4bet".into(),
        4 => "5bet".into(),
        _ => format!("{}bet+", raises + 1),
    }
}

fn terminal_row(
    s: &PreflopSolver,
    node: usize,
    path: &[usize],
    injected_node: Option<usize>,
) -> Result<Option<TerminalRow>, String> {
    let nd = &s.nodes[node];
    if nd.kind != 2 || nd.live.count_ones() < 2 {
        return Ok(None);
    }

    let (walk_node, reaches) = s.walk(path)?;
    if walk_node != node {
        return Err(format!(
            "walk/path mismatch: enumerated node {node}, walk returned {walk_node}"
        ));
    }

    let live: Vec<usize> = (0..s.n)
        .filter(|&p| nd.live & (1 << p) != 0)
        .collect();
    let behind: Vec<f64> = live
        .iter()
        .map(|&p| s.cfg.stack - nd.invested[p] + s.cfg.ante)
        .collect();
    let eff = behind.iter().copied().fold(f64::INFINITY, f64::min);

    // If any live player is all-in there is no postflop decision tree to solve.
    if !eff.is_finite() || eff <= 1e-9 {
        return Ok(None);
    }

    let mut reach_probability = 1.0f64;
    let mut seat_reach = Vec::with_capacity(s.n);
    for p in 0..s.n {
        let mass: f64 = reaches[p].iter().map(|&x| x as f64).sum();
        reach_probability *= mass;
        seat_reach.push(SeatReach {
            seat: p,
            position: s.cfg.positions[p].clone(),
            live: nd.live & (1 << p) != 0,
            invested_bb: nd.invested[p],
            behind_bb: s.cfg.stack - nd.invested[p] + s.cfg.ante,
            range_mass: mass,
            classes_with_positive_reach: reaches[p]
                .iter()
                .filter(|&&x| x > 1e-12)
                .count(),
        });
    }

    let mut cur = 0usize;
    let mut actions = Vec::with_capacity(path.len());
    let mut path_labels = Vec::with_capacity(path.len());
    let mut raises = 0usize;
    for &ai in path {
        let pnd = &s.nodes[cur];
        if pnd.kind != 0 || ai >= pnd.actions.len() {
            return Err(format!("invalid action index {ai} at node {cur}"));
        }
        let act = &pnd.actions[ai];
        if act.kind == "raise" || act.kind == "jam" {
            raises += 1;
        }
        let actor = pnd.actor as usize;
        path_labels.push(format!(
            "{}:{}",
            s.cfg.positions.get(actor).cloned().unwrap_or_else(|| format!("seat{actor}")),
            act.label
        ));
        actions.push(ActionStep {
            actor_seat: actor,
            actor: s
                .cfg
                .positions
                .get(actor)
                .cloned()
                .unwrap_or_else(|| format!("seat{actor}")),
            action_index: ai,
            kind: act.kind.clone(),
            to_bb: act.to,
            label: act.label.clone(),
        });
        cur = s.child(cur, ai);
    }
    if cur != node {
        return Err(format!("path reconstruction ended at {cur}, expected {node}"));
    }

    let aggressor_seat = nd.aggressor as i32;
    let aggressor = if aggressor_seat >= 0 && (aggressor_seat as usize) < s.n {
        s.cfg.positions[aggressor_seat as usize].clone()
    } else {
        "none".into()
    };

    Ok(Some(TerminalRow {
        terminal_node: node,
        path_action_indices: path.to_vec(),
        path_labels,
        actions,
        terminal_live_mask: nd.live,
        live_count: nd.live.count_ones(),
        live_positions: live
            .iter()
            .map(|&p| s.cfg.positions[p].clone())
            .collect(),
        aggressor_seat,
        aggressor,
        raise_count: raises,
        pot_type: pot_type(raises),
        pot_bb: nd.pot,
        effective_behind_bb: eff,
        spr: eff / nd.pot,
        reach_probability,
        share_of_flop_reach: 0.0,
        seat_reach,
        current_injected_terminal: injected_node == Some(node),
    }))
}

fn enumerate(
    s: &PreflopSolver,
    node: usize,
    path: &mut Vec<usize>,
    injected_node: Option<usize>,
    rows: &mut Vec<TerminalRow>,
) -> Result<(), String> {
    let kind = s.nodes[node].kind;
    if kind != 0 {
        if let Some(row) = terminal_row(s, node, path, injected_node)? {
            rows.push(row);
        }
        return Ok(());
    }

    let n_actions = s.nodes[node].actions.len();
    for ai in 0..n_actions {
        let child = s.child(node, ai);
        path.push(ai);
        enumerate(s, child, path, injected_node, rows)?;
        path.pop();
    }
    Ok(())
}

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 4 {
        return Err("config iterations out.json [save.gtop]".into());
    }

    let cfg_text = std::fs::read_to_string(&a[1]).map_err(|e| e.to_string())?;
    let cfg: PreflopConfig = serde_json::from_str(&cfg_text).map_err(|e| e.to_string())?;
    let iters: u32 = a[2].parse().map_err(|_| "iterations")?;
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(1200);

    let eq = Arc::new(EquityTable::build(samples));
    let mut s = PreflopSolver::new(cfg, eq)?;
    for _ in 0..iters {
        s.iterate();
    }
    let (gaps, evs) = s.gaps_and_evs();
    if let Some(p) = a.get(4) {
        s.save_game(p)?;
    }

    let injected_node = solver::preflop::t2cont::table().map(|t| t.node);
    let mut rows = Vec::new();
    enumerate(&s, 0, &mut Vec::new(), injected_node, &mut rows)?;

    let total_flop_reach: f64 = rows.iter().map(|r| r.reach_probability).sum();
    if total_flop_reach > 0.0 {
        for r in &mut rows {
            r.share_of_flop_reach = r.reach_probability / total_flop_reach;
        }
    }
    rows.sort_by(|a, b| {
        b.reach_probability
            .partial_cmp(&a.reach_probability)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let hu_reach: f64 = rows
        .iter()
        .filter(|r| r.live_count == 2)
        .map(|r| r.reach_probability)
        .sum();
    let multiway_reach = total_flop_reach - hu_reach;
    let srp_reach: f64 = rows
        .iter()
        .filter(|r| r.raise_count == 1)
        .map(|r| r.reach_probability)
        .sum();

    let out = serde_json::json!({
        "schema": "t2_terminal_census_v1",
        "config_file": a[1],
        "config": s.cfg,
        "iterations": s.iteration,
        "gap_total": gaps.iter().sum::<f64>(),
        "gaps": gaps,
        "evs": evs,
        "eq_samples": samples,
        "multiway_model": s.multiway_equity_model(),
        "t2_cont_file": std::env::var("T2_CONT_FILE").ok(),
        "current_injected_node": injected_node,
        "reach_definition": "product over seats of total average-strategy class reach; no inter-player card removal",
        "filter": "KIND_POT_SHARE with >=2 live seats and effective behind > 0",
        "summary": {
            "flop_reaching_terminals": rows.len(),
            "total_flop_reach_probability": total_flop_reach,
            "hu_flop_reach_probability": hu_reach,
            "multiway_flop_reach_probability": multiway_reach,
            "srp_flop_reach_probability": srp_reach,
            "hu_share_of_flop_reach": if total_flop_reach > 0.0 { hu_reach / total_flop_reach } else { 0.0 },
            "multiway_share_of_flop_reach": if total_flop_reach > 0.0 { multiway_reach / total_flop_reach } else { 0.0 },
        },
        "terminals": rows,
    });

    std::fs::write(
        &a[3],
        serde_json::to_vec_pretty(&out).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;

    eprintln!(
        "gap {:.5}  flop terminals {}  flop reach {:.6}  HU share {:.3}",
        gaps.iter().sum::<f64>(),
        out["summary"]["flop_reaching_terminals"],
        total_flop_reach,
        if total_flop_reach > 0.0 { hu_reach / total_flop_reach } else { 0.0 }
    );
    Ok(())
}
