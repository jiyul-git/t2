# Verified GTO frequency — standard v1 (fixed 2026-10-06, before any frequency is labelled)

Goal (user, 2026-10-06): keep working, by the most efficient route, until T2 can read **verified** GTO frequencies.
This document fixes what "verified" means before any record is produced. A record that fails any gate is stored with the failing
gate named and is never presented as verified.

## Scope statement
A frequency is "GTO" only relative to a declared game: 9-max, stacks, ante model, action menu (open sizes, 3-bet sizes, 4-bet = jam
only until tested otherwise, no limp), and continuation model. Every record carries that declaration (sk1 key + tree id). No record is
"GTO for real-world 9-max" beyond its declared abstraction.

## Gates (per spot = one decision node; per hand class inside it)
G1 Tree: the adopted tree for the spot's stack depth (30 bb: decided by plan J). Records from a superseded tree are never verified.
G2 Preflop convergence: gap_total <= 0.010 bb per hand (sum of the 9 seats' best-response gains, average strategy, same tree and
   tables). Above it, every record is `unconverged`.
G3 Continuation self-consistency: every solved table the spot depends on passed the outer-loop rule (D <= U for every node-seat, OL
   definition) at the adopted state.
G4 Static dependency: s(spot) = reach-weighted share of the spot's flop-reaching continuation (all lines below the node, under the
   average strategy) that ends at a static (unsolved) pot-share terminal. Verified requires s <= 0.05. 0.05 < s <= 0.25: `partial`
   (frequency shown with the static share); s > 0.25: `static_dependent`. 3-way terminals count as static until a 3-way method is
   validated; results from the 3-way research game are never called GTO.
G5 Hand-level stability (per class): EV gap g = EV(best action) - EV(second); u = u_panel + u_outer + u_solver with
   - u_panel: first-order propagation of the solved tables' stratified standard errors through the action EVs
     (u_panel(a) = sqrt(sum_t (q_t(a) * se_t)^2), q_t = reach factor from the action to terminal t, se_t = class standard error of t);
   - u_outer: |g(state k) - g(state k-1)| over the last outer step;
   - u_solver: the node's own regret floor (gap share).
   Class status: `stable` if g > 2u; `near_indifferent` if g <= 2u (mix reported as a group, raw frequencies kept); a spot is verified
   when G1-G4 pass and >= 95% of the reaching combos are `stable` or `near_indifferent` with every near-indifferent group's members
   listed.
G6 Independent checks (spot sample, must pass before the first verified release):
   (a) HU subgame re-solve: for sampled HU spots, re-solve the subgame below the node with the node's arriving ranges fixed and the
       same tables; frequencies must match the full-tree solve within the G5 uncertainty;
   (b) invariants: no dominated actions with material frequency (e.g. AA folding preflop), chip conservation of exports;
   (c) near-references are shown for orientation only and never used as pass / fail.

## Efficiency decisions
- u_panel from first-order sensitivity instead of replicate preflop solves (each 9-max preflop solve costs hours).
- One-pass whole-tree export (all action nodes above a reach threshold, strategy + action EVs) instead of per-path exports.
- Solver speed work (iteration time grew 73 s -> ~390 s on the mr3 tree) before any further multi-hour solve loop.
- 3-way: measure s(spot) first; work on 3-way values only where it blocks high-traffic spots.

## Amendment 1 (2026-10-06, before any step >= 3 of any spot): spot local outer loop rule v2
Observed on j30_utg_open_bb (steps 0-2, rule v1 alpha 0.5 / max 3 steps): the SRP terminal converged (D 0.02-0.03 << U), the
BB-3-bet-pot terminal drifted monotonically (BB signed change -2.45 then -2.10 bb, U 0.5) after its 3-bet range grew from 20 to
~100 combos; v1 stopped "not converged". Rule v2 for every spot step >= 3 (and all steps of spots not yet started):
- per terminal: alpha = 1.0 (undamped) when every seat's signed change has the same sign as at the previous step (monotone drift),
  else alpha = 0.5;
- at most 8 steps (k = 0..7); stop when every terminal-seat has D <= U (k >= 1), as before.
- G3 for a spot = converged under v2. The v1 verdict of j30_utg_open_bb is kept in its step-2 report.

## Amendment 2 (2026-10-06, before any v3 step): spot loop rule v3 (range-reactive matrices for 3-bet pots)
Observed on j30_utg_open_bb under v2 (steps 3-5): the BB-3-bet-pot ranges cycled (BB 3-bet range 20 -> 100 -> 95 -> 69 -> 94 combos,
UTG calling range 94 -> 135 -> 104 -> 187 -> 56) and the BB table kept moving by 0.6-2.8 bb (U 0.5-0.75): stationary per-class tables
do not react to the opponent's range inside the spot CFR, which a thin 3-bet range needs.
Rule v3 (new spot ids `*_v3`, all steps):
- terminals with two or more raises on the line use a range-reactive matrix: per flop, gross of own class h vs each single opponent
  class j under the solved strategies (t2_cont_panel T2_PANEL_MATRIX=1; columns = the opponent's classes with positive reach at the
  spot root), aggregated over panel_v1 by the ratio estimator sum_b w_b c_b(h) c_b(j) v_b(h, j) / sum_b w_b c_b(h) c_b(j);
  the spot pays g(h) = sum_j dist(j) M[h][j] against the opponent's current distribution;
- matrix terminals are replaced each step (alpha 1); D = weighted |M_new dist_k - value used at step k| at the step-k ranges,
  U as before; reported next to it: |M_new dist_k - A4c table at the solve ranges| (consistency of the matrix with the table);
- SRP terminals keep tables under rule v2; at most 6 steps; stop when every terminal-seat has D <= U (k >= 1).

## Amendment 3 (2026-10-07, before any P144 solve): precision pass on panel_v3_144
Observed on j30_utg_open_bb_v3 (converged; "G2" here was the local spot exploitability, see amendment 4 — the doc G2 fails): only 21.5% of reaching combos are `stable`; the panel_v1 standard error
(~0.35 bb weighted, class level) dominates u. Variance-reduction checks on the same data: ratio estimator SE not smaller (0.45 vs 0.41
for the BB SRP seat); equity control variate -20 to -28% SE (within-stratum correlation 0.55-0.74) — not adopted. Flop target 0.6% / 1.0%
instead of 0.3%: 75 vs 125 iterations, ~30% less time, mean |delta class value| 0.02 bb (max 0.18).
Precision pass P144 (after a spot converges): at the accepted step, re-solve every terminal at that step's ranges on the nested
panel_v3_144 (24 panel_v1 boards reused, 120 extension boards at target 0.6% pot); re-estimate tables and 3-bet-pot matrices on 144
boards; re-solve the spot; grade with the 144-board standard errors and u_outer = |gap_144 - gap_24|. G3 additionally requires
D144 <= U24 for every terminal-seat (the precision update stays inside the 24-board resolution at which the loop converged).
Records carry `panel: panel_v3_144`. The verified label of a spot is the P144 grade when it exists.

## Amendment 4 (2026-10-12, user review 2026-10-08): label semantics — the grader matches this document
Review finding: the grader labelled j30_utg_open_bb_v3 `verified` while (1) its "G2" was the local HU spot exploitability
(4.4e-5 bb), not the doc G2 (parent full-tree gap 0.042 bb > 0.010); (2) G6 was not part of `verified`; (3) G5 was always PASS
(the >= 95% rule counted `stable` + `near_indifferent`, which is every class; stable share was 21.5%); (4) cfg.stack 30 with ante
1/9 was called 30 bb. The record was never promoted to a DB. Fixed in tools/gto_spot/grade_spot.py (schema spot_record_v2;
`--relabel` re-derives labels of stored records without a solve).

Gates, as computed:
- `spot_exploitability_bb` <= 0.010: local HU subgame solver accuracy. Separate gate; never reported as G2.
- G2 = parent full-tree gap_total <= 0.010 bb (doc definition). J (100 it): 0.042 -> G2 FAIL -> no record of J is `verified`.
- G3 spot outer loop converged (P144: also D144 <= U24). G4 static share as before (`pass` / `partial` / `static_dependent`).
- G6 is a condition: (a) HU subgame vs parent full-tree solve on the same tables, (b) invariants — no clearly dominated action
  (EV loss > 2u) at >= 5% for a reaching class, no AA / KK fold > 1%, spot chip conservation |EV_a + EV_b - dead money| <= 0.010 bb.
  (a) is `not_run` until implemented, so G6 FAILS for every record today.
- Classes with < 1e-3 reaching combos at a node are `unreached` there: no frequency reported, not graded. (Set after the first
  run of (b) found 26 dominated-action hits on j30_utg_open_bb_v3, all at classes with reach < 5e-5 combos; reported in the record
  as `n_dominated_at_unreached_classes`.)

Two layers:
1. `status` (spot / game solution) — research < provisional < conditional_verified < verified:
   - research: spot loop not converged, spot exploitability > 0.010, static_dependent, or a superseded rule;
   - provisional: spot-level pass but P144 not graded, G6 not passed, or G4 partial;
   - conditional_verified: every spot-level gate incl. P144 and G6 passes, G2 fails — an exact HU subgame equilibrium of the two
     live seats GIVEN the parent's arriving ranges, not a full 9-max solution;
   - verified: all of the above and G2. `verified: true` only here.
2. `hand_frequency.status`: `blocked_by_solution` below conditional_verified; else `complete` if the stable combo share >= 0.95,
   otherwise `partial`. Per class `frequency_label`: `stable` (point frequency, at the record's status), `uncertainty_group`
   (near-indifferent: raw mix kept and grouped by the two best actions, never called a verified frequency), `unreached`.
   The G5 text "stable or near_indifferent >= 95%" is superseded.

Stack: records carry `stack`: cfg.stack + ante = hand-start stack. J30 = "30bb-labelled (hand-start 30.111bb)", not exact 30 bb;
an exact 30 bb game is cfg.stack 29.888... (= 30 - 1/9). DB rows are keyed by hand_start_bb.

DB promotion stays forbidden for every status (`db_promotion: forbidden` in each record) until the user lifts it.

Relabelled records (2026-10-12):
| record | status | blockers |
|---|---|---|
| j30_utg_open_bb_v3 | provisional | P144 not graded; G6(a) not run; G2 parent gap 0.042 (global FAIL) |
| j30_utg_open_bb_rule_v1_unconverged | research | superseded rule v1; G3 not converged |

Hand level of j30_utg_open_bb_v3 (shown for orientation, status provisional): stable 21.5% of reaching combos; 11 uncertainty
groups (largest: BB root Call 2 ~ Fold, 85 classes / 756 combos). BB root mix fold 36.5 / call 57.8 / 3-bet 3.2 / jam 2.6 is a
provisional, subgame-conditional result on the 30bb-labelled (30.111 bb) game.

## Amendment 5 (2026-10-13, user decision): first T2 connection criterion
A record is `t2_connection: eligible_first` when its status is `conditional_verified`, the parent's exact gap_total is <= 0.05 bb
per hand, and an arriving-range sensitivity report exists for its accepted state. Only `stable` classes carry point frequencies;
`uncertainty_group` and `unreached` classes are passed as such; classes flagged `range_sensitive` are marked. The T2-side per-hand
comparison (spotcmp) and the sensitivity report supplement the missing G2. Eligibility is a label: integrating a record set into T2
is still approved by the user per set, and `db_promotion` (the production DB) stays `forbidden` until lifted. `verified` keeps its
amendment-4 meaning (G2 <= 0.010 and all spot gates).

## Amendment 6 (2026-10-13, before any v4 step): spot loop rule v4 (damped range-reactive matrices)
Observed on p60_co_vs_sb_b40 under v3 (steps 0-4): a period-2 cycle of the spot strategy — CO 4-bet 0% / 8.6% / 0% / 10.4% and CO
fold 61% / 28% / 58% / 29% at steps 1-4 (class means) — with the 4-bet-pot matrix terminal moving D = 1.4 -> 3.8 -> 6.9 -> 5.7 (CO) and
4.1 -> 2.6 -> 4.7 -> 8.0 (SB) against U 1.1-2.4: v3 replaces each matrix by the newest estimate (no damping), so the ranges chase each
other. Also fixed: under v3 a spot that reached the step cap without D <= U ended without a stop decision (no final_step), which made
the grader fail; the cap now always produces "stop: not converged".
Rule v4 (spec rule "v4"; all Plan A specs from now on):
- matrix terminals: step 0 replaces the static payoff by the raw matrix (as v3); from step 1 on M_{k+1} = 0.5 M_k + 0.5 M_raw,k
  (cell-wise; a cell missing in M_k takes the raw value); tables keep rule v2;
- D, U and the stop rule unchanged (every terminal-seat D <= U, k >= 1); at most 12 steps (k = 0..11).
- p60_co_vs_sb_b40 continues under v4 from its v3 state after step 5 (its v3 verdict "not converged after 6 steps" stays in the step-5
  report). Spots running elsewhere under v3 that reach step 5 without converging continue the same way (rule "v4" in the spec,
  resume from the saved state).
- Second instance (T2-side session backup, branch ccr-9a10123b-0lyye0 at 0f190813, p60_utg_vs_btn_b40 under v3): UTG root fold
  (class mean) 62% / 79% / 7% / 80% at steps 0-3, 4-bet-pot D (UTG) 15.2 / 2.0 / 3.2 / 11.1 vs U 1.0-3.2 — the same period-2 cycle.
  p60_co_vs_sb_b40 step 5 (v3, last): 4-bet-pot D 10.0 (CO) / 4.9 (SB), 3-bet-pot D 1.9 / 1.9 vs U 1.1 / 0.8 -> v3 not converged;
  continues under v4 from k = 6.

## Amendment 7 (2026-10-13, before the rerun): flop non-convergence handling; p60_co_vs_sb_b40 restarted under v4
- Observed: p60_co_vs_sb_b40 step 6 (first v4 step after the v3 state), 4-bet-pot terminal, board 9c7d4h: the flop solve stops at
  max_iters 1000 with exploitability 6.47% pot (target 0.3%), flat from ~iteration 300 (7.01 -> 6.55 -> 6.49 -> 6.47) — a floor, not a
  budget shortfall. Ranges at that terminal are degenerate: SB 16.5 combos in 4 classes (99, 44, AA, QQ: sets on 9c7d4h; SB holds
  36.38 of the 36.4 bb pot), CO 42.7 combos; the other 23 boards converge (<= 0.283%). Cause not isolated (f32 storage with an extreme
  value split, or the EPS keep-fraction floor); the solver has no f64 option.
- Rule: a panel flop that ends unconverged at its iteration budget is never accepted silently. The spot loop stops that spot with
  decision "stop: flop solver did not converge (board, terminal, step, exploitability)"; the spot is graded `research` and the chain
  moves on.
- The degenerate 4-bet-pot ranges come from the v3 cycle (step 5: CO 4-bet range 0 combos). p60_co_vs_sb_b40 therefore restarts under
  v4 from step 0 (step 0 is identical under v3 and v4: its flops are reused) instead of continuing from the v3 state; the v3 run and the
  failed v4 step 6 are archived (/home/user/gto_ckpt/spots/p60_co_vs_sb_b40_v3archive, reports summarised here).
- Archived run summary (p60_co_vs_sb_b40, v3 steps 0-5 + v4 step 6): 3-bet-pot D/U CO 1.75/1.21, 1.71/1.10, 1.96/1.21, 2.00/1.10,
  1.80/1.18, 1.92/1.12; SB 2.58/0.85, 1.83/0.83, 1.59/0.83, 1.87/0.83, 1.42/0.80, 1.94/0.84; 4-bet-pot D/U CO 15.5/1.5, 1.45/2.36,
  3.80/1.36, 6.93/1.70, 5.70/2.25, 10.0/1.74; SB 15.7/1.0, 4.08/1.14, 2.55/1.45, 4.65/1.19, 7.99/1.50, 4.90/1.07; step 6 stopped on
  the 9c7d4h flop floor. The new run starts at step 0 (flops reused) under v4.
