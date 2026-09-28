//! T2 audit: card-math cost and accuracy of the current evaluator / equity table.
//!
//!   cargo run --release -p solver --example t2_eval_bench -- [pairs]
//!
//! 1. evaluate7 throughput (single thread)
//! 2. exact HU equity cost: preflop (C(48,5)), flop (C(45,2)), turn (44), river (1)
//! 3. exact class-vs-class preflop equity for a fixed list of class pairs
//!    (every compatible combo pair x every board), compared with the Monte-Carlo
//!    EquityTable at 1200 and 20000 samples (the pilot / server defaults).
//! Prints one JSON object on the last line.
use rayon::prelude::*;
use solver::cards::make_card;
use solver::evaluator::evaluate7;
use solver::preflop::equity::{class_index, class_label, class_parts, EquityTable, NUM_CLASSES};
use std::time::Instant;

fn combos_of(class: usize) -> Vec<[u8; 2]> {
    let mut out = Vec::new();
    for a in 0..52u8 {
        for b in a + 1..52u8 {
            if class_index(a / 4, b / 4, a % 4 == b % 4) == class {
                out.push([a, b]);
            }
        }
    }
    out
}

/// Exact equity of hand h vs hand v over all boards from the remaining deck,
/// given `fixed` board cards. Returns (equity, boards).
fn exact_hu(h: [u8; 2], v: [u8; 2], fixed: &[u8]) -> (f64, u64) {
    let used: u64 = (1u64 << h[0]) | (1u64 << h[1]) | (1u64 << v[0]) | (1u64 << v[1])
        | fixed.iter().fold(0u64, |m, &c| m | (1u64 << c));
    let deck: Vec<u8> = (0..52u8).filter(|c| used & (1u64 << c) == 0).collect();
    let need = 5 - fixed.len();
    let mut board = [0u8; 5];
    board[..fixed.len()].copy_from_slice(fixed);
    let (mut won, mut n) = (0f64, 0u64);
    let mut idx = vec![0usize; need];
    fn rec(k: usize, start: usize, need: usize, deck: &[u8], idx: &mut Vec<usize>, fixed_len: usize,
           board: &mut [u8; 5], h: [u8; 2], v: [u8; 2], won: &mut f64, n: &mut u64) {
        if k == need {
            let a = evaluate7(&[board[0], board[1], board[2], board[3], board[4], h[0], h[1]]);
            let b = evaluate7(&[board[0], board[1], board[2], board[3], board[4], v[0], v[1]]);
            if a > b { *won += 1.0 } else if a == b { *won += 0.5 }
            *n += 1;
            return;
        }
        for i in start..deck.len() {
            idx[k] = i;
            board[fixed_len + k] = deck[i];
            rec(k + 1, i + 1, need, deck, idx, fixed_len, board, h, v, won, n);
        }
    }
    rec(0, 0, need, &deck, &mut idx, fixed.len(), &mut board, h, v, &mut won, &mut n);
    (won / n as f64, n)
}

fn exact_class(i: usize, j: usize) -> (f64, u64) {
    let ci = combos_of(i);
    let cj = combos_of(j);
    let pairs: Vec<([u8; 2], [u8; 2])> = ci.iter().flat_map(|a| cj.iter().map(move |b| (*a, *b)))
        .filter(|(a, b)| a[0] != b[0] && a[0] != b[1] && a[1] != b[0] && a[1] != b[1]).collect();
    let res: Vec<(f64, u64)> = pairs.par_iter().map(|(a, b)| exact_hu(*a, *b, &[])).collect();
    let n = res.len() as f64;
    (res.iter().map(|r| r.0).sum::<f64>() / n, res.iter().map(|r| r.1).sum())
}

fn main() {
    // 1. evaluate7 throughput
    let mut x: u64 = 0x1234_5678_9abc_def1;
    let mut hands = Vec::with_capacity(1 << 20);
    while hands.len() < (1 << 20) {
        let mut m = 0u64;
        let mut h = [0u8; 7];
        let mut k = 0;
        while k < 7 {
            x ^= x << 13; x ^= x >> 7; x ^= x << 17;
            let c = (x % 52) as u8;
            if m & (1 << c) == 0 { m |= 1 << c; h[k] = c; k += 1; }
        }
        hands.push(h);
    }
    let t = Instant::now();
    let mut acc = 0u64;
    for _ in 0..8 {
        for h in &hands { acc = acc.wrapping_add(evaluate7(h) as u64); }
    }
    let ev_s = t.elapsed().as_secs_f64();
    let evals_per_s = (8 * hands.len()) as f64 / ev_s;

    // 2. exact HU equity cost per street (AhKh vs QsQd on Jh Ts 2c 7d 9s)
    let c = |r: u8, s: u8| make_card(r, s);
    let h = [c(12, 2), c(11, 2)];
    let v = [c(10, 3), c(10, 1)];
    let board = [c(9, 2), c(8, 3), c(0, 0), c(5, 1), c(7, 3)];
    let mut street = serde_json::Map::new();
    for (name, k) in [("preflop", 0usize), ("flop", 3), ("turn", 4), ("river", 5)] {
        let t = Instant::now();
        let (e, n) = exact_hu(h, v, &board[..k]);
        street.insert(name.into(), serde_json::json!({"equity": e, "boards": n,
            "ms_single_thread": t.elapsed().as_secs_f64() * 1e3}));
    }

    // 3. exact class-vs-class vs Monte-Carlo tables
    let list: Vec<(&str, &str)> = vec![
        ("AA", "KK"), ("AKs", "QQ"), ("AKo", "22"), ("A5s", "KQo"), ("72o", "AA"),
        ("T9s", "AKo"), ("JJ", "AQs"), ("K2o", "Q9o"), ("54s", "A9o"), ("88", "AKs"),
        ("QJs", "JTs"), ("A2o", "K7s"), ("33", "22"), ("KTo", "KJo"), ("96s", "76o"),
        ("AQo", "AJs"), ("J4o", "T6o"), ("65s", "65o"), ("A8s", "A8o"), ("Q2s", "32o"),
    ];
    let idx_of = |l: &str| (0..NUM_CLASSES).find(|&k| class_label(k) == l).expect(l);
    let t = Instant::now();
    let mc1 = EquityTable::build(1200);
    let mc1_ms = t.elapsed().as_secs_f64() * 1e3;
    let t = Instant::now();
    let mc20 = EquityTable::build(20000);
    let mc20_ms = t.elapsed().as_secs_f64() * 1e3;
    let mut rows = Vec::new();
    let (mut e1, mut e20) = (Vec::new(), Vec::new());
    let t_ex = Instant::now();
    let mut boards_total = 0u64;
    for (a, b) in &list {
        let (i, j) = (idx_of(a), idx_of(b));
        let (ex, nb) = exact_class(i, j);
        boards_total += nb;
        let (m1, m20) = (mc1.eq(i, j) as f64, mc20.eq(i, j) as f64);
        e1.push((m1 - ex).abs());
        e20.push((m20 - ex).abs());
        rows.push(serde_json::json!({"hero": a, "villain": b, "exact": ex, "mc1200": m1, "mc20000": m20,
            "err1200": m1 - ex, "err20000": m20 - ex}));
    }
    let exact_ms = t_ex.elapsed().as_secs_f64() * 1e3;
    // count of unordered class pairs and of combo-pairs for a full exact table
    let mut combo_pairs = 0u64;
    for i in 0..NUM_CLASSES {
        for j in i..NUM_CLASSES {
            let ci = combos_of(i);
            let cj = combos_of(j);
            for a in &ci {
                for b in &cj {
                    if a[0] != b[0] && a[0] != b[1] && a[1] != b[0] && a[1] != b[1] { combo_pairs += 1; }
                }
            }
        }
    }
    let _ = class_parts(0);
    let mean = |v: &Vec<f64>| v.iter().sum::<f64>() / v.len() as f64;
    let maxv = |v: &Vec<f64>| v.iter().cloned().fold(0.0, f64::max);
    println!("{}", serde_json::json!({
        "threads": rayon::current_num_threads(),
        "evaluate7_per_s_single_thread": evals_per_s, "checksum": acc,
        "exact_hu_by_street": street,
        "mc_table_build_ms": {"1200": mc1_ms, "20000": mc20_ms},
        "class_pairs": rows,
        "mae_vs_exact": {"1200": mean(&e1), "20000": mean(&e20)},
        "max_abs_err": {"1200": maxv(&e1), "20000": maxv(&e20)},
        "exact_sample_ms": exact_ms, "exact_sample_boards": boards_total,
        "full_table_combo_pairs_upper_triangle": combo_pairs,
    }));
}
