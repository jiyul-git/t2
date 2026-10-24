# ICM push/fold plan (pre-registered 2026-10-24, before any scenario was solved)

Task: item 4 of docs/T2_HANDOFF.md section 8 ("ICM push/fold table"). The board rule "no ICM (chip EV)" applied to the symmetric
bucket runs; it is lifted for this task only. Nothing here is connected to the T2 runtime (needs user approval).

## 1. What T2 does today (read from test3)
- Payouts: `formats.payouts(n_paid, flat)` = BASE_PAYOUT curve [100, 62, 44, 34, 27, 22, 18, 15, ...] normalised to 100, flattened by
  `payout_flat` (0 normal, 0.35 bounty, 1.0 satellite). `itm_frac` 0.10-0.15 of the field are paid. Stacks 50-300 bb at the start.
- `icm.py`: exact Malmuth-Harville ICM (subset DP, 2..9 players), `bubble_factor`, `icm_pressure`, `table_bf`, `field_bf`.
- `preflop.py` switches the GTO reference OFF when BF > 1.05 or the money-jump model reports pressure / brake / risk share
  (`gto_pf_first_in_choice`, `gto_pf_call_choice`, `gto_pf_aggr_choice`), then uses the older judgement.
- So the missing piece is a reference for exactly those spots: a table that knows the payout structure and unequal stacks.

## 2. Can the vendored solver do it? No (checked)
- `vendor/gtopen` PreflopConfig: `stack` is ONE number ("v1: must be equal for all seats - no side pots"); terminal payoffs are
  chips (`terminal_value`, pot shares). No stack vector, no ICM terminals. Adding both to the Rust DCFR core (side pots, per-seat
  utility, the GPU/multiway paths) is a large change, not a quick record.
- Cheapest exact alternative (used here): own small jam/fold solver `tools/gto_icm/icm_pushfold.py` (numpy, 169 classes, same
  pairwise equity table as gtopen, 20000 samples, dumped by `crates/solver/examples/t2_eq_dump.rs`). Terminals = T2's own `icm_equity`
  of the final stack vector (side pots handled by min-stack), scaled to bb (mean stack = mean prize). Same stop rule as the pf runs.
- Declared simplifications (apply to the ICM run and to its chip-EV control alike): jam/fold only (the menu of the 10 bb record);
  only the FIRST caller can call (no overcalls); class-level hands, card removal only through the pairwise equity table;
  win+tie/2 equity used as win probability (no chop branch); ante 1 bb total split 1/n; blinds 0.5 / 1; preflop only.
- Solver validation (chip mode, 9 x 10 bb, run before any scenario): first-in jam UTG 13.7 % / BTN 42.0 % / SB 71.8 % vs gtopen
  pf10 record 14.3 / 43.3 / 72.8 % (record allows overcalls). Gap 0.00997 bb at 6.6k iterations.

## 3. Pre-registered scenarios (single table, all remaining players in the hand; seat 0 = first to act ... last = BB)
Payouts from `formats.payouts`. Stack vectors in bb, hand-start (blinds and ante included).
| id | players / paid | payout | stacks (seat order) | purpose |
|---|---|---|---|---|
| B1 | 9 / 8 | top-8 curve | 15 x 9 | pure bubble effect, no stack asymmetry |
| B2 | 9 / 8 | top-8 curve | 12,30,8,20,15,10,25,9,6 | PILOT: bubble, unequal stacks, mean 15 |
| B3 | 9 / 8 | top-8 curve | 20,50,13,33,25,17,42,15,10 (mean 25) | depth |
| B4 | 9 / 8 | top-8 curve | 8,20,5,13,10,7,17,6,4 (mean 10) | shallow |
| F1 | 9 / 9 | top-9 curve | 15 x 9 | final table, top-heavy payouts |
| F2 | 9 / 9 | top-9 curve | 12,30,8,20,15,10,25,9,6 | final table, unequal |
| F3 | 6 / 6 | top-6 curve | 12,30,8,20,15,5 | 6-handed final table |
| H1 | 3 / 3 | top-3 curve (100,62,44) | 20,15,10 (BTN,SB,BB) | three-handed |
| S1 | 4 / 3 | flat tickets (flat = 1.0) | 25,15,12,8 | satellite bubble |
Each scenario is also solved in chip-EV mode with the same code and stacks (control). 9 scenarios x 2 modes.

## 4. Stop rule and outputs (fixed before computing)
- Stop at exact gap_total <= 0.010 bb (sum over all seats of the best-response gain, ICM units for ICM mode, chips for control) or
  60000 iterations, whichever first. Gap measured every 25 iterations by exact class-level best response. Unconverged runs are
  labelled and not used for conclusions.
- Record per scenario: per seat jam range (first-in) and call range per (jammer, caller) pair, EV per seat, gap, iterations.
- Comparison: classes whose first-in action flips between ICM and chip-EV control at probability 0.5, per seat; same for calls.
- Compute: pilot-size scenario ~ tens of seconds on one core; all 18 runs well under one hour. No GPU, no long jobs.

## 5. What T2 would need to look up
Key = (players left n, paid places / payout curve id, stack vector in bb per seat relative to the hero seat). The stack vector
space is too large for a full table. Options in section 7 (decisions).
