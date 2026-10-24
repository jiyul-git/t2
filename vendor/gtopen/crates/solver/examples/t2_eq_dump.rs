//! Dump the 169x169 pairwise class equity table (row-major f32 text) for the ICM push/fold solver.
//!   t2_eq_dump <samples> <out.txt>
use solver::preflop::equity::EquityTable;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let eq = EquityTable::build(a[1].parse().unwrap());
    let mut s = String::new();
    for i in 0..169 { for j in 0..169 { s.push_str(&format!("{:.6} ", eq.eq(i, j))); } s.push('\n'); }
    std::fs::write(&a[2], s).unwrap();
}
