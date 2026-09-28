//! T2 HU-continuation prototype (feature `t2-cont`, compiled out by default).
//!
//! Replaces the payoff of ONE heads-up pot-share terminal with externally solved
//! per-class continuation values, loaded from the JSON file named by T2_CONT_FILE:
//!
//! {"schema": "t2_hu_continuation_table_v1", "node": <terminal index>, "live": <mask>,
//!  "pot_bb": <pot>, "value_convention": "gross_share",
//!  "seats": [{"seat": s, "gross": [169 x bb]}, ...], ...provenance...}
//!
//! gross = expected chips of the terminal pot that the class ends with against the
//! opponent's arriving range (zero rake). terminal_value then pays gross - invested,
//! exactly like the pot-share branch. The table does not react to the opponent's
//! current reach inside the preflop CFR: it is the stationary value of one outer
//! fixed-point step. Every other terminal keeps the existing payoff.
use std::sync::OnceLock;

pub struct Table {
    pub node: usize,
    pub live: u32,
    pub pot: f64,
    pub gross: Vec<(usize, Vec<f64>)>,
}

static TABLE: OnceLock<Option<Table>> = OnceLock::new();

fn load() -> Option<Table> {
    let path = std::env::var("T2_CONT_FILE").ok()?;
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("T2_CONT_FILE {path}: {e}"));
    let v: serde_json::Value = serde_json::from_str(&text).unwrap_or_else(|e| panic!("T2_CONT_FILE {path}: {e}"));
    assert_eq!(v["schema"], "t2_hu_continuation_table_v1", "T2_CONT_FILE schema");
    assert_eq!(v["value_convention"], "gross_share", "T2_CONT_FILE value convention");
    let seats = v["seats"].as_array().expect("seats");
    let gross = seats.iter().map(|s| {
        let g: Vec<f64> = s["gross"].as_array().expect("gross").iter().map(|x| x.as_f64().expect("finite gross")).collect();
        assert_eq!(g.len(), super::NUM_CLASSES, "169 classes");
        (s["seat"].as_u64().expect("seat") as usize, g)
    }).collect();
    Some(Table {
        node: v["node"].as_u64().expect("node") as usize,
        live: v["live"].as_u64().expect("live") as u32,
        pot: v["pot_bb"].as_f64().expect("pot"),
        gross,
    })
}

pub fn table() -> Option<&'static Table> {
    TABLE.get_or_init(load).as_ref()
}

/// Gross values for traverser `p` at `node`, if this node is the injected terminal.
/// Panics if the file names this node but its pot / live mask disagree with the tree.
pub fn gross_for(node: usize, live: u32, pot: f64, p: usize) -> Option<&'static [f64]> {
    let t = table()?;
    if t.node != node {
        return None;
    }
    assert!(t.live == live && (t.pot - pot).abs() < 1e-9, "T2_CONT_FILE node {node} does not match the tree");
    t.gross.iter().find(|(s, _)| *s == p).map(|(_, g)| g.as_slice())
}
