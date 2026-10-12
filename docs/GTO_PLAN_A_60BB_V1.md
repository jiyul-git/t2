# Plan A — opener vs 3-bet at 60 bb (pre-registered 2026-10-12, before any Plan A solve)

User decision (2026-10-12): Plan A. Parent full tree up to the 3-bet (4-bet jam only, fits this machine: 913k nodes, 1.23 GB);
from the HU 3-bet node on, an exact subgame with the T2-measured menu. Plan B (>= 32 GB machine, max_raises 4 full tree: 16.1M nodes,
21.7 GB arena, data/gto_validation/tree_size/tree_size_v1.json) is re-judged after Plan A's pipeline is verified end to end.
The J rebuild chain and the UTG-vs-BB grading check (P144, G6(a)) continue as planned.

## 1. Declared game
- 9-max, hand-start stack exactly 60 bb (cfg.stack = 60 - 1/9 = 59.888...), ante 1 bb shared (1/9 per seat), no limp, no rake.
- Opens 2.0 bb for every seat (T2: <= 80 bb opens 2.0; applied to the SB as well).
- 3-bet: 3.0x for UTG..BTN; blinds 3.5x (arm B35) or 4.0x (arm B40) — two parents, results compared (size-abstraction check).
- Parent (data/gto_spot/plan_a/cfg_p60_{b35,b40}.json): max_raises 3, 4-bet = jam only, static continuation (no solved flop tables).
- Subgame menu below the HU 3-bet node (hu_spot "menu"): 4-bet to = 3-bet-to x 2.15 when the 4-bettor is in position postflop vs the
  3-bettor, x 2.35 out of position, plus jam; facing a 4-bet: fold / call / jam (5-bet jam only); facing a jam: fold / call.
- Flop terminals of the subgame (3-bet-call, 4-bet-call): range-reactive matrices, rule v3 (standard amendment 2), panel_v1, then P144.
  All-in terminals: exact class equity. Folds: exact chips.

## 2. Spots (priority 1, T2 frequency)
| id | line (others fold) | 4-bettor position | arms |
|---|---|---|---|
| p60_co_vs_sb | CO opens, SB 3-bets | IP (2.15x) | B35, B40 |
| p60_utg1_vs_sb | UTG+1 opens, SB 3-bets | IP (2.15x) | B35, B40 |
| p60_utg_vs_btn | UTG opens, BTN 3-bets 6 | OOP (2.35x) | B35, B40 (parent differs only in blind sizes) |
| p60_btn_vs_bb | BTN opens, BB 3-bets | IP (2.15x) | B35, B40 |
| p60_hj_vs_bb | HJ opens, BB 3-bets | IP (2.15x) | B35, B40 |
Then 40 bb (cfg.stack 39.888...) and 100 bb (99.888...) with the same menu (T2: non-jam 5-bet only from 120 bb).

## 3. Parent solve
DCFR with the 1e-9 multiway skip; the parent gap is measured exactly (skip off) in a separate process; stop at exact gap_total
<= 0.010 bb or 400 iterations, whichever first; the gap is recorded in every spot record. Whole-tree dump (t2_tree_dump, reach >= 1e-6).

## 4. Status and gates
- Cap: `conditional_verified` (grade_spot status_cap). Reason: the subgame menu differs from the parent tree, the parent continuation
  is static, and the arriving ranges are the parent's. No Plan A record is `verified` until section 6 is done.
- Spot gates as standard v1 amendment 4: spot_exploitability <= 0.010 bb, G3 (rule v3 converged; P144 D144 <= U24), G4 static share
  <= 0.05, G6, P144 graded. G2 (parent gap) is reported; it does not lift the cap.
- G6(a) for Plan A = parent-menu reproduction: the subgame solved with the parent's own menu (4-bet jam only) and the parent's static
  terminals must reproduce the parent's frequencies at every subgame node within the G5 uncertainty (checks the subgame machinery and
  the root ranges; it is not a check of the new menu). G6(b) as amendment 4.
- Hand level as amendment 4: `stable` / `uncertainty_group` / `unreached`; DB promotion forbidden.

## 5. Arriving-range sensitivity (report, no pass / fail; computed at the accepted state with the continuation fixed)
- S1 / S2: the 3-bettor's arriving classes below / above the reach-weighted median equity vs the opener's arriving range, weight x 0.8 and
  x 1.2 (bluff-region and value-region shifts).
- S3: the opener's classes with parent open probability in (0.05, 0.95), weight x 0.8 and x 1.2.
- For each of the 6 perturbed solves: per class and node max |delta freq|, reach-weighted mean |delta|, share of reaching combos whose
  best action changes, node mix change. Classes moving > 10 pp under any perturbation are flagged `range_sensitive` in the record.

## 6. Outer loop to lift the cap (plan; each step pre-registered before it runs)
O1 Parent HU flop tables at 60 bb (8 SRP + the HU 3-bet pots) with the existing OL pipeline (H1 / OL / T3 at 60 bb).
O2 Preflop continuation injection: engine extension letting a preflop node (the opener's HU decision vs a 3-bet) be valued by the
   subgame's range-reactive per-class values (matrix over the opponent's classes), like t2_cont flop tables.
O3 Iterate parent <-> subgame: parent solve with injected values -> new arriving ranges -> subgame (+ its flop matrices) -> D <= U on the
   injected values and arriving-range change below the panel resolution.
O4 The game is then the composite (parent menu up to the HU 3-bet, subgame menu after it); verified requires G2 on the composite
   (parent gap with the injected values) plus all spot gates. Multiway 3-bet pots stay in the parent's menu and are declared as such.

## 7. Unsupported (status `unsupported`, never filled by constants or interpolation)
Cold 3-bet response (a third player facing open + 3-bet), squeeze (callers facing a 3-bet), any 3-bet / 4-bet node with three or more
live players: their continuation is 3-way, which is static until a 3-way method is validated (G4). 5-bet non-jam (>= 120 bb).

## 8. 3-way review plan (separate track, no compute before its own pre-registration)
(1) inventory at 60 bb from the parent dump: 3-way flop reach share and which T2 nodes (cold 3-bet response, squeeze) depend on it;
(2) capability check of the vendored postflop solver for 3 players (tree size and time per flop at one bet size);
(3) a one-terminal pilot comparing a 3-way flop solve with the static payoff; (4) decision on a 3-way table / matrix method.

## 9. Compute order
Parents B35 and B40 run concurrently with the rebuild chain (4 cores shared; both resumable); then the 10 subgame loops, P144,
sensitivity, grading. The rebuild chain keeps its order (OL -> s2 -> T3 -> J2 -> UTG-vs-BB P144 / G6(a)).

## Amendment A1 (2026-10-12, before any Plan A grade): G6(a) parent-menu reproduction, numeric
The subgame is re-solved without the menu (parent rules: 4-bet jam only), no tables, static terminals (the parent's own payoff),
CFR+ 3000 iterations, at the parent's arriving ranges. Compared with the parent dump's average strategy at every subgame node:
pass iff at every node the reach-weighted mean |delta freq| over reaching classes (>= 1e-3 combos) is <= 0.02, and every reaching
class with |delta| > 0.10 loses <= 0.05 bb (subgame EV of the parent's action mix vs the subgame's best action). Reported per node
with the classes over 0.10. It checks the subgame machinery and the root ranges against the parent; it does not test the new menu.

## Amendment A2 (2026-10-12): SB open declared as a deviation from T2; spot composition
- T2 measurement (user, 2026-10-12): SB first-in open is 2.15 + 0.6 = 2.75 bb in code, rounded to 0.5 bb steps -> almost always
  3.0 bb (tournament logs 2.3-3.0 bb, mode 2.7-2.9 bb at 35-80 bb); SB limp 0% for the baseline regular profile (5-7% only in the
  tendency layer; 7-19% in mixed tournament logs). The Plan A parents open the SB to 2.0 bb with no limp: **a declared condition that
  differs from T2**. None of the 5 priority pairs has an SB open on its line, so the subgames are not directly affected; the parent's
  equilibrium (blind-vs-blind lines) can shift the arriving ranges indirectly. Before the outer loop (section 6) or any blind-vs-blind
  spot the SB open is re-set (about 2.75-3.0 bb; limp excluded for the baseline-regular tree) and re-registered.
- Spot composition: the blind 3-bet arms only change the 3-bettor's size for SB / BB 3-bets, so the distinct subgames are 9:
  4 blind pairs x {B35, B40} + p60_utg_vs_btn (BTN 3-bets 3.0x) on the B40 parent. p60_utg_vs_btn_b35 is the same subgame on the
  B35 parent: kept only as a parent-arm sensitivity replicate (reported as such, never a separate result), run last.
- BvB controlled measurement (user, 2026-10-12; T2 real decision path, UTG..BTN fixed to fold, 15-300 bb x 11 stacks x 2 profiles x
  6,000 = 132k trials): SB open computed 2.75 bb, executed 3.0 bb at almost every stack (0.5 bb rounding below a 15k-chip BB);
  baseline-regular SB limp 0% (tendency layer 5-7%). Re-registration rule for the SB open (when section 6 or a BvB spot starts):
  representative 3.0 bb (what T2 executes), 2.75 bb as the size-abstraction comparison; no limp in the baseline-regular tree.
  T2 behaviour figures (SB raise 31-36% at 40-100 bb, BB vs a 3 bb SB open: 3-bet 5%, fold 45-47%, defect D8 = BB never raises an SB
  limp) are bot measurements, not references: they are never used as pass / fail for solver output.

## Amendment A3 (2026-10-12): T2 deep-stack measurement (user; 2 deep tournaments, first 3 h, 9,794 hands) — planning input only
- Node traffic peaks at 50-80 bb in deep events too (cold 3-bet response 646, opener vs 3-bet 355); overall cold response / opener
  response = 2,859 / 1,646 (~1.7x, same as turbo / standard). >= 120 bb still carries 499 / 343: 150 and 300 bb are computed
  independently (never scaled from 100 bb).
- Opener-vs-3-bet pairs are dominated by SB 3-bets: CO>SB 107, UTG+1>SB 90, UTG>SB 90, UTG+2>SB 86, BTN>SB 84. Next Plan A subgames
  after the current 9 (same parents, no new parent solve): UTG>SB, UTG+2>SB, BTN>SB (x B35 / B40), registered before they run.
- Sizes: opens 2.0 bb up to 120 bb, 2.0-2.7 at 120-200, 2.5 / 3.0 above 200; 3-bet IP 2.8-3.2x, blinds 3.4-3.9x (consistent with
  the 3.0x and 3.5x / 4.0x arms); 4-bet at 35-50 bb mixed jam / non-jam, >= 80 bb almost all non-jam (menu keeps both); 5-bet+ rare (22).
- Consequences for later stacks: the parent "up to the 3-bet" must stay jam-only for the 4-bet at every depth (at 100 bb a 10x
  4-bet no longer clamps to the jam: the parent config uses an explicit jam-only 4-bet); from 120 bb the subgame menu needs a non-jam
  5-bet (T2) — hu_spot supports a jam-only 5-bet today, the extension is registered with the 120+ bb plan.
- Not used: the < 15 bb IP "min-3-bets" (1.6-1.9x) — corrected by the user (2026-10-12): a measurement classification error, all 65
  cases are isolation raises after an effectively all-in opener (< 0.2 bb behind after the ante), not 3-bets; not a menu size either
  way. Defect D8 (bot-side; never a pass / fail reference).
