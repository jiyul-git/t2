//! Tree size of preflop configs without allocating (solver::preflop::estimate_tree, the builder's own counting walk).
//!   PREFLOP_MAX_NODES=<cap> t2_tree_estimate <config.json>...   -> one JSON line per config: nodes, action_nodes, arena_len,
//!   arena_gb (regret + strategy-sum f32 arenas), truncated (walk stopped past the cap).
use solver::preflop::{estimate_tree, PreflopConfig};

fn main() -> Result<(), String> {
    for path in std::env::args().skip(1) {
        let text = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let cfg: PreflopConfig = serde_json::from_str(&text).map_err(|e| e.to_string())?;
        let e = estimate_tree(&cfg)?;
        println!("{}", serde_json::json!({"config": path, "nodes": e.nodes, "action_nodes": e.action_nodes,
            "arena_len": e.arena_len, "arena_gb": e.arena_len as f64 * 8.0 / 1e9, "truncated": e.truncated}));
    }
    Ok(())
}
