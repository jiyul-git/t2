//! Pot-share terminals of a preflop config (planning only): t2_terminal_census <config.json> > rows.jsonl
use solver::preflop::{terminal_census, PreflopConfig};
fn main() -> Result<(), String> {
    let p = std::env::args().nth(1).ok_or("config")?;
    let cfg: PreflopConfig = serde_json::from_str(&std::fs::read_to_string(&p).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    for r in terminal_census(&cfg)? { println!("{}", serde_json::to_string(&r).unwrap()); }
    Ok(())
}
