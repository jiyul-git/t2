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
