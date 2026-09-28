//! T2 audit instrumentation (feature `t2-profile` only; compiled out otherwise).
//!
//! Counts terminal evaluations per payoff kind and accumulates the CPU time
//! spent inside them (summed over rayon threads, so it can exceed wall time).
//! Also records phase wall times of `try_iterate` (traversal vs DCFR discount).
//! No numeric path of the solver changes: timers only read the clock. The one
//! exception is `real_k`, which returns the production 0.16 unless T2_REAL_K is set.
use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
use std::time::Instant;

pub const K_FOLD: usize = 0;
pub const K_DEAD: usize = 1; // traverser folded before a pot-share terminal
pub const K_HU_STATIC: usize = 2; // HU pairwise table x static realization
pub const K_HU_BALANCED: usize = 3;
pub const K_HU_FIT: usize = 4; // legacy calibrated fit
pub const K_MW3: usize = 5; // coupled deck, 2 opponents
pub const K_MW4: usize = 6; // 3 opponents
pub const K_MW5P: usize = 7; // 4+ opponents
pub const K_ZERO: usize = 8; // other players' reach mass 0 -> early return
pub const NK: usize = 9;
pub const NAMES: [&str; NK] = [
    "fold_win", "dead_seat", "hu_static", "hu_balanced", "hu_fit",
    "mw_3way", "mw_4way", "mw_5plus", "zero_reach",
];

pub static CALLS: [AtomicU64; NK] = [const { AtomicU64::new(0) }; NK];
pub static NANOS: [AtomicU64; NK] = [const { AtomicU64::new(0) }; NK];
pub static ACTION_VISITS: AtomicU64 = AtomicU64::new(0);
pub static TRAVERSE_NS: AtomicU64 = AtomicU64::new(0);
pub static DISCOUNT_NS: AtomicU64 = AtomicU64::new(0);

pub struct Timer {
    t0: Instant,
    kind: usize,
}

impl Timer {
    #[inline]
    pub fn start(kind: usize) -> Self {
        Timer { t0: Instant::now(), kind }
    }
    #[inline]
    pub fn set(&mut self, kind: usize) {
        self.kind = kind;
    }
}

impl Drop for Timer {
    #[inline]
    fn drop(&mut self) {
        let ns = self.t0.elapsed().as_nanos() as u64;
        CALLS[self.kind].fetch_add(1, Relaxed);
        NANOS[self.kind].fetch_add(ns, Relaxed);
    }
}

pub fn reset() {
    for k in 0..NK {
        CALLS[k].store(0, Relaxed);
        NANOS[k].store(0, Relaxed);
    }
    ACTION_VISITS.store(0, Relaxed);
    TRAVERSE_NS.store(0, Relaxed);
    DISCOUNT_NS.store(0, Relaxed);
}

/// (name, calls, cpu_ms) per kind plus action visits and phase wall ms.
pub fn snapshot() -> (Vec<(&'static str, u64, f64)>, u64, f64, f64) {
    let rows = (0..NK)
        .map(|k| (NAMES[k], CALLS[k].load(Relaxed), NANOS[k].load(Relaxed) as f64 / 1e6))
        .collect();
    (
        rows,
        ACTION_VISITS.load(Relaxed),
        TRAVERSE_NS.load(Relaxed) as f64 / 1e6,
        DISCOUNT_NS.load(Relaxed) as f64 / 1e6,
    )
}

/// Positional realization coefficient of the static model (production: 0.16).
/// Overridable with T2_REAL_K for the audit's sensitivity runs only.
pub fn real_k() -> f64 {
    static K: std::sync::OnceLock<f64> = std::sync::OnceLock::new();
    *K.get_or_init(|| std::env::var("T2_REAL_K").ok().and_then(|v| v.parse().ok()).unwrap_or(0.16))
}
