//! T2 A4R: seat-swap evaluation. Copies one seat's strategy blocks (optionally only those in the
//! subtree below a given node) from a donor save into a base save, then evaluates the spliced
//! profile under the continuation tables named by T2_CONT_FILE. No iteration is run.
//!
//!   T2_CONT_FILE=<manifest> t2_splice_eval <base.gtop> <donor.gtop> <seat> <subtree-root|all> <out.json> [spliced.gtop]
//!
//! Both saves must come from the same config (same tree and arena layout). Save layout:
//! 12-byte magic, one JSON header line, then [u64 len][f32 x len] regrets, [u64 len][f32 x len] strat_sum.
use solver::preflop::equity::EquityTable;
use solver::preflop::PreflopSolver;
use std::sync::Arc;

struct Layout { hdr: serde_json::Value, reg: usize, strat: usize, len: usize }

fn layout(b: &[u8]) -> Result<Layout, String> {
    let nl = 12 + b[12..].iter().position(|&c| c == b'\n').ok_or("no header line")?;
    let hdr: serde_json::Value = serde_json::from_slice(&b[12..nl]).map_err(|e| e.to_string())?;
    let rl = u64::from_le_bytes(b[nl + 1..nl + 9].try_into().unwrap()) as usize;
    let reg = nl + 9;
    let sl_at = reg + 4 * rl;
    let sl = u64::from_le_bytes(b[sl_at..sl_at + 8].try_into().unwrap()) as usize;
    if sl != rl { return Err("regret / strat_sum arena lengths differ".into()); }
    Ok(Layout { hdr, reg, strat: sl_at + 8, len: rl })
}

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 6 {
        return Err("base.gtop donor.gtop seat subtree-root|all out.json [spliced.gtop]".into());
    }
    let seat: usize = a[3].parse().map_err(|_| "seat")?;
    let samples: u32 = std::env::var("PREFLOP_EQ_SAMPLES").ok().and_then(|v| v.parse().ok()).unwrap_or(1200);
    let eq = Arc::new(EquityTable::build(samples));
    let base_s = PreflopSolver::load_game(&a[1], eq.clone())?;
    let (mut base, donor) = (std::fs::read(&a[1]).map_err(|e| e.to_string())?, std::fs::read(&a[2]).map_err(|e| e.to_string())?);
    let (lb, ld) = (layout(&base)?, layout(&donor)?);
    if lb.hdr["config"] != ld.hdr["config"] || lb.len != ld.len || base[..12] != donor[..12] {
        return Err("base and donor saves differ in config / layout".into());
    }
    // action nodes owned by `seat`, optionally restricted to the subtree below `root`
    let mut nodes: Vec<usize> = Vec::new();
    if a[4] == "all" {
        nodes = (0..base_s.nodes.len()).filter(|&n| base_s.nodes[n].kind == 0 && base_s.nodes[n].actor as usize == seat).collect();
    } else {
        let root: usize = a[4].parse().map_err(|_| "subtree root")?;
        let mut stack = vec![root];
        while let Some(n) = stack.pop() {
            let nd = &base_s.nodes[n];
            if nd.kind != 0 { continue; }
            if nd.actor as usize == seat { nodes.push(n); }
            for i in 0..nd.actions.len() { stack.push(base_s.child(n, i)); }
        }
        nodes.sort();
    }
    let mut floats = 0usize;
    for &n in &nodes {
        let nd = &base_s.nodes[n];
        let (off, len) = (nd.data_off, nd.actions.len() * 169);
        for arena in [lb.reg, lb.strat] {
            let (s, e) = (arena + 4 * off, arena + 4 * (off + len));
            base[s..e].copy_from_slice(&donor[s..e]);
        }
        floats += len;
    }
    let tmp = a.get(6).cloned().unwrap_or_else(|| format!("{}.spliced.gtop", a[5]));
    std::fs::write(&tmp, &base).map_err(|e| e.to_string())?;
    let s = PreflopSolver::load_game(&tmp, eq)?;
    #[cfg(feature = "t2-cont")]
    solver::preflop::t2cont::validate(&s)?;
    let (gaps, evs) = s.gaps_and_evs();
    if a.get(6).is_none() { std::fs::remove_file(&tmp).ok(); }
    let out = serde_json::json!({
        "base": a[1], "donor": a[2], "seat": seat, "position": s.cfg.positions[seat], "subtree_root": a[4],
        "t2_cont_file": std::env::var("T2_CONT_FILE").ok(), "nodes_swapped": nodes.len(), "floats_swapped": floats,
        "positions": s.cfg.positions, "gaps": gaps, "gap_total": gaps.iter().sum::<f64>(), "evs": evs,
        "br_values": gaps.iter().zip(&evs).map(|(g, e)| g + e).collect::<Vec<f64>>(),
    });
    std::fs::write(&a[5], serde_json::to_string_pretty(&out).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}
