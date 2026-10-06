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
