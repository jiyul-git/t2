//! T2 joint-CFR prototype (feature `t2-joint`, compiled out by default).
//!
//! One heads-up pot-share terminal of the preflop tree is continued by a fixed flop
//! panel of postflop solvers that learn TOGETHER with the preflop CFR (upstream
//! `integrated_continuation` style), instead of a stationary value table:
//! - regret pass (traverse mode 0): each postflop solver on the panel runs one
//!   alternating update for the traverser with the CURRENT preflop reaches
//!   (own reach -> postflop strategy sums; opponent reach x folded seats' mass ->
//!   counterfactual weights) and returns the traverser's counterfactual values;
//! - evaluation (checkpoint gaps): average-strategy values and best-response values
//!   of the postflop panel at the average preflop reaches.
//! Per-class payoff uses the SAME functional as the outer fixed-point tables
//! (value_convention gross_share, panel weights x board availability, divided by a
//! fixed per-player normaliser), so both methods solve the identical game.
use super::{PreflopSolver, NUM_CLASSES};
use crate::game::Dealt;
use crate::Solver;
use std::sync::{Mutex, OnceLock};

pub struct Flop {
    pub board: String,
    pub weight: f64,
    pub solver: Solver,
    /// class index per combo, per postflop role (0 = OOP, 1 = IP)
    pub cls: [Vec<usize>; 2],
    /// share of each class's combos not blocked by the board
    pub avail: Vec<f64>,
}

pub struct Joint {
    pub node: usize,
    pub live: u32,
    pub pot: f64,
    /// preflop seat of postflop role 0 (OOP) and 1 (IP)
    pub seat: [usize; 2],
    /// fixed class-independent normaliser per role
    pub norm: [f64; 2],
    pub flops: Vec<Mutex<Flop>>,
}

static JOINT: OnceLock<Joint> = OnceLock::new();

pub fn install(j: Joint) {
    if JOINT.set(j).is_err() {
        panic!("t2 joint already installed");
    }
}

pub fn get() -> Option<&'static Joint> {
    JOINT.get()
}

fn combo_reach(f: &Flop, role: usize, class_reach: &[f32], scale: f32) -> Vec<f32> {
    // class reach = class prior x strategy products; spread evenly over the class's
    // combos (6 / 4 / 12), so combo reach = class reach / combos-in-class
    f.cls[role].iter().map(|&k| {
        let n = super::equity::class_combos(k);
        class_reach[k] / n * scale
    }).collect()
}

/// Per-class gross share (bb) of `role` given its per-combo CFVs against `opp`.
fn gross_from_cfv(j: &Joint, f: &Flop, role: usize, cfv: &[f32], opp: &[f32], acc: &mut [f64]) {
    let spot = &*f.solver.spot;
    let oh = &spot.hands[1 - role];
    let (mut tot, mut by) = (0f64, [0f64; 52]);
    for (i, h) in oh.iter().enumerate() {
        let w = opp[i] as f64;
        tot += w;
        by[h.c1 as usize] += w;
        by[h.c2 as usize] += w;
    }
    let mut num = [0f64; NUM_CLASSES];
    let mut den = [0f64; NUM_CLASSES];
    for (i, h) in spot.hands[role].iter().enumerate() {
        let same = spot.same_combo[role][i];
        let corr = if same != crate::tree::SENTINEL { opp[same as usize] as f64 } else { 0.0 };
        let valid = tot - by[h.c1 as usize] - by[h.c2 as usize] + corr;
        let k = f.cls[role][i];
        num[k] += cfv[i] as f64;
        den[k] += valid;
    }
    for k in 0..NUM_CLASSES {
        if den[k] > 0.0 {
            acc[k] += f.weight * f.avail[k] * (num[k] / den[k] + j.pot / 2.0) / j.norm[role];
        }
    }
}

#[derive(Clone, Copy, PartialEq)]
pub enum Eval {
    Update(u32),
    Average,
    BestResponse,
}

/// Gross per class for preflop seat `p` at the joint terminal, or None if this is
/// not the joint terminal / p is not live there.
pub fn gross(s: &PreflopSolver, node: usize, p: usize, reaches: &[Vec<f32>], how: Eval) -> Option<Vec<f64>> {
    let j = get()?;
    if node != j.node {
        return None;
    }
    let nd = &s.nodes[node];
    assert!(nd.live == j.live && (nd.pot - j.pot).abs() < 1e-9, "t2 joint terminal mismatch");
    let role = j.seat.iter().position(|&x| x == p)?;
    let q = j.seat[1 - role];
    // folded seats' mass scales the opponent's counterfactual weight
    let folded: f32 = (0..s.n).filter(|&x| x != p && x != q).map(|x| reaches[x].iter().sum::<f32>()).product();
    let mut acc = vec![0f64; NUM_CLASSES];
    for fl in &j.flops {
        let mut f = fl.lock().unwrap();
        let own = combo_reach(&f, role, &reaches[p], 1.0);
        let opp = combo_reach(&f, 1 - role, &reaches[q], folded);
        let cfv = match how {
            Eval::Update(t) => f.solver.t2_joint_sweep(role, t, &own, &opp).expect("joint sweep"),
            Eval::Average => f.solver.traverse_avg(0, role, &opp, Dealt::default()),
            Eval::BestResponse => f.solver.traverse_br(0, role, &opp, Dealt::default()),
        };
        gross_from_cfv(j, &f, role, &cfv, &opp, &mut acc);
    }
    Some(acc)
}

/// Terminal payoff vector in the preflop CFR convention (prob x (gross - invested)).
pub fn payoff(s: &PreflopSolver, node: usize, p: usize, reaches: &[Vec<f32>], how: Eval) -> Option<Vec<f32>> {
    let g = gross(s, node, p, reaches, how)?;
    let nd = &s.nodes[node];
    let mut prob = 1f64;
    for q in 0..s.n {
        if q != p {
            prob *= reaches[q].iter().sum::<f32>() as f64;
        }
    }
    if prob <= 0.0 {
        return Some(vec![0.0; NUM_CLASSES]);
    }
    Some(g.iter().map(|&v| (prob * (v - nd.invested[p])) as f32).collect())
}

/// Postflop exploitability of the panel at the given (average) preflop reaches:
/// per flop, mean over roles of (BR value - average value) weighted by own reach,
/// in % of the pot, plus the panel-weighted mean.
pub fn postflop_exploitability(reaches: &[Vec<f32>], folded: f32) -> Vec<(String, f64)> {
    let j = get().expect("joint");
    let mut out = Vec::new();
    for fl in &j.flops {
        let f = fl.lock().unwrap();
        let mut gain = 0f64;
        let mut mass = 0f64;
        for role in 0..2 {
            let own = combo_reach(&f, role, &reaches[j.seat[role]], 1.0);
            let opp = combo_reach(&f, 1 - role, &reaches[j.seat[1 - role]], folded);
            let br = f.solver.traverse_br(0, role, &opp, Dealt::default());
            let av = f.solver.traverse_avg(0, role, &opp, Dealt::default());
            gain += own.iter().zip(br.iter().zip(&av)).map(|(&w, (&b, &a))| w as f64 * (b - a) as f64).sum::<f64>();
            if role == 0 {
                // pair mass (card-compatible) for normalisation
                let spot = &*f.solver.spot;
                let oh = &spot.hands[1];
                let (mut tot, mut by) = (0f64, [0f64; 52]);
                for (i, h) in oh.iter().enumerate() {
                    tot += opp[i] as f64;
                    by[h.c1 as usize] += opp[i] as f64;
                    by[h.c2 as usize] += opp[i] as f64;
                }
                for (i, h) in spot.hands[0].iter().enumerate() {
                    let same = spot.same_combo[0][i];
                    let corr = if same != crate::tree::SENTINEL { opp[same as usize] as f64 } else { 0.0 };
                    mass += own[i] as f64 * (tot - by[h.c1 as usize] - by[h.c2 as usize] + corr);
                }
            }
        }
        out.push((f.board.clone(), gain / 2.0 / mass.max(1e-300) / j.pot * 100.0));
    }
    out
}
