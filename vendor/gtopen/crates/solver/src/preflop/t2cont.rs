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
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;

/// Set only inside `t2_terminal_gross(.., legacy = true)`: makes `gross_for` report no
/// table so terminal_value falls through to the legacy payoff. Read-only diagnostics.
static BYPASS: AtomicBool = AtomicBool::new(false);

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
    if BYPASS.load(Ordering::Relaxed) {
        return None;
    }
    let t = table()?;
    if t.node != node {
        return None;
    }
    assert!(t.live == live && (t.pot - pot).abs() < 1e-9, "T2_CONT_FILE node {node} does not match the tree");
    t.gross.iter().find(|(s, _)| *s == p).map(|(_, g)| g.as_slice())
}

impl super::PreflopSolver {
    /// Read-only diagnostic (no strategy or regret is touched): at the node reached by
    /// `path` under the average strategy, the acting seat's expected value of each action
    /// per class (bb, net of everything invested, same units as the terminal payoffs),
    /// conditional on the node being reached — the counterfactual value of the average
    /// strategy divided by the other seats' reach product at the node. Class-level, like
    /// the solver itself (no card removal between seats).
    pub fn t2_action_values(&self, path: &[usize]) -> Result<(usize, Vec<Vec<f64>>), String> {
        let (node, reaches) = self.walk(path)?;
        let nd = &self.nodes[node];
        if nd.kind != super::KIND_ACTION {
            return Err("path does not end at an action node".into());
        }
        let actor = nd.actor as usize;
        let norm: f64 = (0..self.n).filter(|&q| q != actor).map(|q| reaches[q].iter().map(|&x| x as f64).sum::<f64>()).product();
        if norm <= 0.0 {
            return Err("node not reached by the other seats".into());
        }
        let mut out = Vec::with_capacity(nd.actions.len());
        for a in 0..nd.actions.len() {
            let mut r = reaches.clone();
            let v = self
                .traverse_checkpoint(self.child(node, a), actor, &mut r, 3, super::CheckpointNeeds { br: false, avg: true }, super::PAR_DEPTH)
                .ok_or("cancelled")?;
            let v = v.avg.unwrap_or_else(|| vec![0.0; super::NUM_CLASSES]);
            out.push(v.iter().map(|&x| x as f64 / norm).collect());
        }
        Ok((node, out))
    }
}

impl super::PreflopSolver {
    /// Read-only diagnostic: gross value per class (bb, gross share of the pot, the same
    /// convention as the continuation tables) of live seat `p` at terminal `node` reached
    /// with `reaches`, taken from the solver's own `terminal_value`:
    /// gross = payoff / prob + invested, prob = product of the other seats' reach masses.
    /// `legacy = true` bypasses an injected continuation table (the pre-injection payoff).
    /// Not thread-safe with a concurrent CFR run (the bypass flag is global).
    pub fn t2_terminal_gross(&self, node: usize, p: usize, reaches: &[Vec<f32>], legacy: bool) -> Result<Vec<f64>, String> {
        let nd = &self.nodes[node];
        if nd.kind != super::KIND_POT_SHARE || nd.live & (1 << p) == 0 {
            return Err("not a pot-share terminal with this seat live".into());
        }
        let mut prob = 1f64;
        for q in 0..self.n {
            if q != p {
                prob *= reaches[q].iter().sum::<f32>() as f64;
            }
        }
        if prob <= 0.0 {
            return Err("terminal not reached by the other seats".into());
        }
        let mut out = vec![0f32; super::NUM_CLASSES];
        BYPASS.store(legacy, Ordering::Relaxed);
        self.terminal_value(node, p, reaches, &mut out);
        BYPASS.store(false, Ordering::Relaxed);
        Ok(out.iter().map(|&v| v as f64 / prob + nd.invested[p]).collect())
    }

    /// Read-only diagnostic for 3+ live seats: the coupled-deck gross pot * equity per class
    /// in f64 (terminal_value rounds the same number to f32), plus the normalised opponent
    /// distributions it integrates against (seat order).
    pub fn t2_multiway_gross_f64(&self, node: usize, p: usize, reaches: &[Vec<f32>]) -> Option<(Vec<f64>, Vec<Vec<f32>>)> {
        let nd = &self.nodes[node];
        let model = self.multiway.as_ref()?;
        if nd.live.count_ones() < 3 || nd.live & (1 << p) == 0 {
            return None;
        }
        let mut dists: Vec<Vec<f32>> = Vec::new();
        for q in 0..self.n {
            if q != p && nd.live & (1 << q) != 0 {
                let s: f32 = reaches[q].iter().sum();
                if s > 0.0 {
                    dists.push(reaches[q].iter().map(|&x| x / s).collect());
                }
            }
        }
        let pot_eff = nd.pot - self.rake_of(nd.pot);
        let eq = model.equities(&dists);
        Some((eq.iter().map(|&e| pot_eff * e).collect(), dists))
    }
}
