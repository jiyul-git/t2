//! T2 audit: isolated prototype timings for the multiway terminal (coupled_deck_v1).
//! Numerics of the solver are untouched; this only compares, on the SAME particles
//! (CoupledDeck::shared()), the per-traverser production routine against
//!   E: an f32, h-contiguous (auto-vectorizable) rewrite of the same integral
//!   F: one joint pass per terminal giving every live player's equity
//!      (shared CDFs + leave-one-out products; needs simultaneous updates in CFR)
//!   H: the production routine restricted to m of the 1024 particles (MCCFR-style
//!      chance sampling; unbiased for the 1024-particle mean)
//!
//!   cargo run --release -p solver --example t2_mw_bench
//! Prints one JSON object (single thread).
use solver::preflop::equity::NUM_CLASSES;
use solver::preflop::multiway::{CoupledDeck, SAMPLES};
use std::time::Instant;

const N: usize = NUM_CLASSES;

fn rule(opp: usize) -> (Vec<f32>, Vec<f32>) {
    match opp {
        0..=1 => (vec![0.5], vec![1.0]),
        2..=3 => (vec![0.211324865405187, 0.788675134594813], vec![0.5, 0.5]),
        4..=5 => (vec![0.112701665379258, 0.5, 0.887298334620742], vec![0.277777777777778, 0.444444444444444, 0.277777777777778]),
        _ => (vec![0.069431844202974, 0.330009478207572, 0.669990521792428, 0.930568155797026],
              vec![0.173927422568727, 0.326072577431273, 0.326072577431273, 0.173927422568727]),
    }
}

/// E: same integral, f32 lanes over hero classes; per-particle sums promoted to f64.
fn equities_f32(d: &CoupledDeck, opps: &[Vec<f32>], samples: std::ops::Range<usize>) -> Vec<f64> {
    let (t, w) = rule(opps.len());
    let q = t.len();
    let mut sums = vec![0f64; N];
    let mut cdf = vec![0f32; N + 1];
    let mut vals = vec![1f32; q * N];
    let mut lo = vec![0f32; N];
    let mut eq = vec![0f32; N];
    let n = samples.len();
    for s in samples {
        let base = s * N;
        let (low, up, ord) = (&d.lower[base..base + N], &d.upper[base..base + N], &d.order[base..base + N]);
        vals.iter_mut().for_each(|v| *v = 1.0);
        for dist in opps {
            for i in 0..N {
                cdf[i + 1] = cdf[i] + dist[ord[i] as usize];
            }
            for h in 0..N {
                let l = cdf[low[h] as usize];
                lo[h] = l;
                eq[h] = cdf[up[h] as usize] - l;
            }
            for k in 0..q {
                let tk = t[k];
                let row = &mut vals[k * N..(k + 1) * N];
                for h in 0..N {
                    row[h] *= lo[h] + tk * eq[h];
                }
            }
        }
        for h in 0..N {
            let mut acc = 0f32;
            for k in 0..q {
                acc += vals[k * N + h] * w[k];
            }
            sums[h] += acc as f64;
        }
    }
    sums.iter_mut().for_each(|x| *x /= n as f64);
    sums
}

/// E2: production structure (per-h values in registers, f64) but the k opponent
/// prefix sums are interleaved in one pass so their serial add chains overlap.
fn equities_interleaved(d: &CoupledDeck, opps: &[Vec<f32>]) -> Vec<f64> {
    let (t, w) = rule(opps.len());
    let q = t.len();
    let k = opps.len();
    let mut sums = vec![0f64; N];
    let mut cdf = vec![0f64; k * (N + 1)]; // [q][i]
    for s in 0..SAMPLES {
        let base = s * N;
        let (low, up, ord) = (&d.lower[base..base + N], &d.upper[base..base + N], &d.order[base..base + N]);
        let mut run = [0f64; 8];
        for i in 0..N {
            let c = ord[i] as usize;
            for j in 0..k {
                run[j] += opps[j][c] as f64;
                cdf[j * (N + 1) + i + 1] = run[j];
            }
        }
        for h in 0..N {
            let (lo, hi) = (low[h] as usize, up[h] as usize);
            let mut v = [1f64; 4];
            for j in 0..k {
                let row = &cdf[j * (N + 1)..(j + 1) * (N + 1)];
                let less = row[lo];
                let equal = row[hi] - less;
                for m in 0..q {
                    v[m] *= less + t[m] as f64 * equal;
                }
            }
            let mut a = 0f64;
            for m in 0..q {
                a += v[m] * w[m] as f64;
            }
            sums[h] += a;
        }
    }
    sums.iter_mut().for_each(|x| *x /= SAMPLES as f64);
    sums
}

/// F: all live players at once. dists[p] for every live player p; returns eq[p][h].
fn equities_joint(d: &CoupledDeck, dists: &[Vec<f32>]) -> Vec<Vec<f64>> {
    let l = dists.len();
    let (t, w) = rule(l - 1);
    let q = t.len();
    let mut sums = vec![vec![0f64; N]; l];
    let mut cdf = vec![0f32; N + 1];
    let mut term = vec![0f32; l * q * N]; // [player][k][h]
    let mut pre = vec![1f32; q * N];
    let mut acc = vec![vec![0f32; q * N]; l];
    for s in 0..SAMPLES {
        let base = s * N;
        let (low, up, ord) = (&d.lower[base..base + N], &d.upper[base..base + N], &d.order[base..base + N]);
        for (p, dist) in dists.iter().enumerate() {
            for i in 0..N {
                cdf[i + 1] = cdf[i] + dist[ord[i] as usize];
            }
            for k in 0..q {
                let row = &mut term[(p * q + k) * N..(p * q + k + 1) * N];
                for h in 0..N {
                    let a = cdf[low[h] as usize];
                    row[h] = a + t[k] * (cdf[up[h] as usize] - a);
                }
            }
        }
        // leave-one-out products: prefix pass then suffix pass
        pre.iter_mut().for_each(|v| *v = 1.0);
        for p in 0..l {
            acc[p].copy_from_slice(&pre);
            let tp = &term[p * q * N..(p + 1) * q * N];
            for i in 0..q * N {
                pre[i] *= tp[i];
            }
        }
        pre.iter_mut().for_each(|v| *v = 1.0); // now suffix
        for p in (0..l).rev() {
            let tp = &term[p * q * N..(p + 1) * q * N];
            let a = &mut acc[p];
            for i in 0..q * N {
                a[i] *= pre[i];
                pre[i] *= tp[i];
            }
            for h in 0..N {
                let mut v = 0f32;
                for k in 0..q {
                    v += a[k * N + h] * w[k];
                }
                sums[p][h] += v as f64;
            }
        }
    }
    for s in &mut sums {
        s.iter_mut().for_each(|x| *x /= SAMPLES as f64);
    }
    sums
}

fn main() {
    let d = CoupledDeck::shared();
    let mut x: u64 = 0x2545_f491_4f6c_dd1d;
    let mut rnd = || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; (x >> 11) as f64 / (1u64 << 53) as f64 };
    let mut rows = Vec::new();
    for live in 3..=9usize {
        // live players' normalized ranges: ~40% of classes zero, rest random
        let dists: Vec<Vec<f32>> = (0..live).map(|_| {
            let v: Vec<f32> = (0..N).map(|_| { let r = rnd(); if r < 0.4 { 0.0 } else { r as f32 } }).collect();
            let s: f32 = v.iter().sum();
            v.iter().map(|a| a / s).collect()
        }).collect();
        let opps_of = |p: usize| -> Vec<Vec<f32>> { (0..live).filter(|&q| q != p).map(|q| dists[q].clone()).collect() };
        let reps: usize = std::env::var("T2_REPS").ok().and_then(|v| v.parse().ok()).unwrap_or(6);
        // baseline: production routine, once per live traverser
        let t = Instant::now();
        let mut base = Vec::new();
        for _ in 0..reps { base = (0..live).map(|p| d.equities(&opps_of(p)).to_vec()).collect::<Vec<_>>(); }
        let base_ms = t.elapsed().as_secs_f64() * 1e3 / reps as f64;
        // E
        let t = Instant::now();
        let mut e = Vec::new();
        for _ in 0..reps { e = (0..live).map(|p| equities_f32(&d, &opps_of(p), 0..SAMPLES)).collect::<Vec<_>>(); }
        let e_ms = t.elapsed().as_secs_f64() * 1e3 / reps as f64;
        // E2
        let t = Instant::now();
        let mut e2 = Vec::new();
        for _ in 0..reps { e2 = (0..live).map(|p| equities_interleaved(&d, &opps_of(p))).collect::<Vec<_>>(); }
        let e2_ms = t.elapsed().as_secs_f64() * 1e3 / reps as f64;
        // F
        let t = Instant::now();
        let mut f = Vec::new();
        for _ in 0..reps { f = equities_joint(&d, &dists); }
        let f_ms = t.elapsed().as_secs_f64() * 1e3 / reps as f64;
        // H: m particles (a contiguous block starting at a random offset)
        let mut h_rows = Vec::new();
        for m in [64usize, 128, 256] {
            let mut err = Vec::new();
            let t = Instant::now();
            let draws = 16;
            for _ in 0..draws {
                let off = (rnd() * (SAMPLES - m) as f64) as usize;
                let est = equities_f32(&d, &opps_of(0), off..off + m);
                let mae: f64 = (0..N).map(|h| (est[h] - base[0][h]).abs()).sum::<f64>() / N as f64;
                err.push(mae);
            }
            let ms = t.elapsed().as_secs_f64() * 1e3 / draws as f64 * live as f64;
            h_rows.push(serde_json::json!({"m": m, "ms_all_live_f32": ms, "mae_single_draw_vs_1024": err.iter().sum::<f64>() / draws as f64}));
        }
        let maxdiff = |a: &Vec<Vec<f64>>| a.iter().zip(&base).flat_map(|(u, v)| u.iter().zip(v).map(|(x, y)| (x - y).abs())).fold(0f64, f64::max);
        rows.push(serde_json::json!({
            "live": live, "baseline_ms_all_live": base_ms,
            "E_f32_ms": e_ms, "E_speedup": base_ms / e_ms, "E_max_abs_diff": maxdiff(&e),
            "E2_interleaved_ms": e2_ms, "E2_speedup": base_ms / e2_ms, "E2_max_abs_diff": maxdiff(&e2),
            "F_joint_ms": f_ms, "F_speedup": base_ms / f_ms, "F_max_abs_diff": maxdiff(&f),
            "H_sampled": h_rows,
        }));
    }
    println!("{}", serde_json::json!({"threads": 1, "samples": SAMPLES, "rows": rows}));
}
