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

## 6. Results (2026-10-24; all 18 runs met the stop rule, exact gap <= 0.010; records data/gto_spot/icm/run_<id>_<icm|chip>.json,
tables data/gto_spot/icm/compare.txt, code tools/gto_icm/). Own jam/fold solver with the simplifications of section 2.
First-in jam frequency (%), chip control -> ICM, by seat (stack bb):
- **B2 pilot (bubble 9/8, mean 15 bb)**: UTG(12) 12.9->9.7, UTG+1(30) 11.6->49.6, UTG+2(8) 20.6->13.6, LJ(20) 16.6->35.4, HJ(15) 24.1->29.7,
  CO(10) 33.0->31.7, BTN(25) 44.5->99.9, SB(9) 81.6->99.9. Calls shrink: mean call frequency over jammer/caller pairs 17.7 -> 6.1 %.
- Pattern: big stacks jam far wider (they cannot be hurt: callers fold), short stacks jam NARROWER (UTG+2 8 bb: 15 hands jam -> fold, none the
  other way: 22 87s A8o 98s A9o T8s T9s ATo KJo Q9s KQo K9s + A2s A6s A7s), and calls fall hard (SB 9 bb calling BB 6 bb: 75 % -> 39 %;
  BTN 25 bb vs SB 9 bb jam: 34 % -> 6.7 %; the calling ranges lose every pair below AA-style value, e.g. 22-66, A2o-A9o, KQs).
- B1 (bubble, equal 15 bb): everyone jams wider (UTG 9.5->15.1, BTN 35.6->89.5, SB 63.5->99.9) and calls drop 9.8 -> 2.5 %: with equal
  stacks and 1 place from the money nobody calls, so steals are almost free (pure bubble effect).
- F1/F2 (final table, top-heavy): milder, same direction (F1 BTN 35.6->49.3, calls 9.8->3.9 %); short stack still tightens (F2 UTG+2).
- B3/B4 (25 / 10 bb mean): same signs as B2; at 10 bb the short seat (5 bb) goes 34 -> 15 %.
- F3 (6-handed), H1 (3-handed), S1 (4-handed satellite): H1 changes little (BTN 37.4->40.6, calls 36.6->23.7); S1 chip leader
  25 bb jams 29.7->75.7, 15 bb seat 40.7->27.2, calls 32.7->7.5 %.
Reading: ICM changes the answer a lot. The old T2 fallback ("GTO off, older judgement") cannot be better than a table that has these
shapes: calls must be much tighter (chip-EV GTO calls are too loose under ICM) and steals depend on whether the seat is covered.

## 7. Open decisions for the user
1. Method for T2: (a) a small precomputed table keyed by scenario type (needs a stack-relative key, many buckets), or
   (b) solve live inside T2 with this solver (1-30 s numpy for one table; tens of ms would need caching/port) - NOT done, hard rule says
   no runtime connection without approval, or (c) bubble-factor-adjusted chip-EV tables (cheapest, approximate, no stack asymmetry).
2. Is the declared simplification set acceptable (jam/fold only, first caller only, no flop play, win/lose without chop)? Real T2 pots at
   15-25 bb also include opens and 3-bets; exact gtopen ICM terminals would need a Rust change (stack vector + ICM utility).
3. Which payout structures and sizes matter most: T2 pays 10-15 % of the field with BASE_PAYOUT; ~10 scenarios above cover
   bubble 8/9, final table 9/9 and 6/6, 3-handed, satellite. Multi-table bubbles (other tables' stacks matter in ICM) are not covered.
4. Accept stack-bucket granularity for lookup (key = players left, paid places, hero stack and each other seat's stack relative to hero).
5. Next compute if approved: the 25-40 bb depth with 2.0 bb opens (needs the Rust path) or a denser jam/fold scenario grid (cost: minutes).
