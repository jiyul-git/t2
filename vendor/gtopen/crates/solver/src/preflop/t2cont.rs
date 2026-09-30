//! T2 HU-continuation prototype (feature `t2-cont`, compiled out by default).
//!
//! Replaces the payoff of selected heads-up pot-share terminals with externally solved
//! per-class continuation values. T2_CONT_FILE names either ONE table
//!
//! {"schema": "t2_hu_continuation_table_v1", "node": <terminal index>, "live": <mask>,
//!  "pot_bb": <pot>, "value_convention": "gross_share",
//!  "seats": [{"seat": s, "gross": [169 x bb]}, ...], ...provenance...}
//!
//! or a manifest of tables (paths relative to the manifest's directory):
//!
//! {"schema": "t2_hu_continuation_manifest_v1", "tables": [{"file": "node28.json"}, ...]}
//!
//! gross = expected chips of the terminal pot that the class ends with against the
//! opponent's arriving range (zero rake). terminal_value then pays gross - invested,
//! exactly like the pot-share branch. A table does not react to the opponent's current
//! reach inside the preflop CFR: it is the stationary value of one outer fixed-point
//! step. Every terminal not named by a table keeps the existing payoff.
//! Loading fails closed (panic) on: unknown schema, value convention other than
//! gross_share, a duplicate node, a seat not in the live mask or a live seat without
//! values, anything but 169 finite values per seat, a non-finite pot. `validate` checks
//! every table against the tree (node exists, is a pot-share terminal, live mask equal,
//! pot within 1e-9); `gross_for` keeps the per-lookup live/pot guard.
use std::collections::BTreeMap;
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
    pub file: String,
}

pub struct Tables {
    pub by_node: BTreeMap<usize, Table>,
    pub source: String,
}

static TABLES: OnceLock<Option<Tables>> = OnceLock::new();

fn parse_table(v: &serde_json::Value, file: &str) -> Result<Table, String> {
    if v["schema"] != "t2_hu_continuation_table_v1" {
        return Err(format!("{file}: schema {} is not t2_hu_continuation_table_v1", v["schema"]));
    }
    if v["value_convention"] != "gross_share" {
        return Err(format!("{file}: value_convention {} is not gross_share", v["value_convention"]));
    }
    let node = v["node"].as_u64().ok_or(format!("{file}: node"))? as usize;
    let live = v["live"].as_u64().ok_or(format!("{file}: live"))? as u32;
    let pot = v["pot_bb"].as_f64().filter(|x| x.is_finite() && *x > 0.0).ok_or(format!("{file}: pot_bb"))?;
    let seats = v["seats"].as_array().ok_or(format!("{file}: seats"))?;
    let mut gross: Vec<(usize, Vec<f64>)> = Vec::new();
    for s in seats {
        let seat = s["seat"].as_u64().ok_or(format!("{file}: seat"))? as usize;
        if seat >= 32 || live & (1 << seat) == 0 {
            return Err(format!("{file}: seat {seat} is not in live mask {live}"));
        }
        if gross.iter().any(|(q, _)| *q == seat) {
            return Err(format!("{file}: seat {seat} listed twice"));
        }
        let g = s["gross"].as_array().ok_or(format!("{file}: seat {seat} gross"))?;
        if g.len() != super::NUM_CLASSES {
            return Err(format!("{file}: seat {seat} has {} values, not 169", g.len()));
        }
        let mut vals = Vec::with_capacity(super::NUM_CLASSES);
        for x in g {
            match x.as_f64() {
                Some(f) if f.is_finite() => vals.push(f),
                _ => return Err(format!("{file}: seat {seat} has a non-finite or non-numeric value")),
            }
        }
        gross.push((seat, vals));
    }
    if gross.len() != live.count_ones() as usize {
        return Err(format!("{file}: {} seats for a live mask with {} seats", gross.len(), live.count_ones()));
    }
    Ok(Table { node, live, pot, gross, file: file.to_string() })
}

/// Parse a single table or a manifest of tables (fail closed; no tree needed).
pub fn parse_file(path: &str) -> Result<Tables, String> {
    let read = |p: &str| -> Result<serde_json::Value, String> {
        let text = std::fs::read_to_string(p).map_err(|e| format!("{p}: {e}"))?;
        serde_json::from_str(&text).map_err(|e| format!("{p}: {e}"))
    };
    let v = read(path)?;
    let mut list = Vec::new();
    if v["schema"] == "t2_hu_continuation_manifest_v1" {
        let dir = std::path::Path::new(path).parent().map(|d| d.to_path_buf()).unwrap_or_default();
        let entries = v["tables"].as_array().ok_or(format!("{path}: tables"))?;
        if entries.is_empty() {
            return Err(format!("{path}: empty manifest"));
        }
        for e in entries {
            let f = e["file"].as_str().ok_or(format!("{path}: table entry without file"))?;
            let fp = if std::path::Path::new(f).is_absolute() { f.to_string() } else { dir.join(f).to_string_lossy().into_owned() };
            list.push(parse_table(&read(&fp)?, &fp)?);
        }
    } else {
        list.push(parse_table(&v, path)?);
    }
    let mut by_node = BTreeMap::new();
    for t in list {
        if let Some(prev) = by_node.get(&t.node) {
            let prev: &Table = prev;
            return Err(format!("duplicate node {}: {} and {}", t.node, prev.file, t.file));
        }
        by_node.insert(t.node, t);
    }
    Ok(Tables { by_node, source: path.to_string() })
}

fn load() -> Option<Tables> {
    let path = std::env::var("T2_CONT_FILE").ok()?;
    Some(parse_file(&path).unwrap_or_else(|e| panic!("T2_CONT_FILE {e}")))
}

pub fn tables() -> Option<&'static Tables> {
    TABLES.get_or_init(load).as_ref()
}

/// Backward-compatible accessor: the table when exactly one is loaded.
pub fn table() -> Option<&'static Table> {
    let t = tables()?;
    if t.by_node.len() == 1 { t.by_node.values().next() } else { None }
}

/// Check every loaded table against the tree: node exists and is a pot-share terminal,
/// live mask identical, pot within 1e-9. Call before solving (fail closed).
pub fn validate(s: &super::PreflopSolver) -> Result<(), String> {
    let Some(t) = tables() else { return Ok(()) };
    for (node, tb) in &t.by_node {
        let nd = s.nodes.get(*node).ok_or(format!("{}: node {node} does not exist", tb.file))?;
        if nd.kind != super::KIND_POT_SHARE {
            return Err(format!("{}: node {node} is not a pot-share terminal", tb.file));
        }
        if nd.live != tb.live {
            return Err(format!("{}: node {node} live mask {} != tree {}", tb.file, tb.live, nd.live));
        }
        if (nd.pot - tb.pot).abs() >= 1e-9 {
            return Err(format!("{}: node {node} pot {} != tree {}", tb.file, tb.pot, nd.pot));
        }
    }
    Ok(())
}

/// Gross values for traverser `p` at `node`, if a table names this node.
/// Panics if the table's pot / live mask disagree with the tree.
pub fn gross_for(node: usize, live: u32, pot: f64, p: usize) -> Option<&'static [f64]> {
    if BYPASS.load(Ordering::Relaxed) {
        return None;
    }
    let t = tables()?.by_node.get(&node)?;
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

