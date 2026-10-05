# 9-max 30bb: full HU SRP set (H1) -> outer loop (OL) -> 3-bet / 3-way plan — design v1

Decided 2026-10-03 after the S pilot (`GTO_CONTINUATION_PILOT_9MAX_RESULT_V1.md`); the user asked to proceed in this order and
delegated the design judgments. Same solver config / tree / seeds as the pilot (cfg_pilot.json, 100 iterations, seeds 202).
Unchanged holds: E1 paused at 24/450, Termux DB on hold, no DB promotion, no T2 body / human-model code change.

## H1 — full HU SRP set (8 terminals, 37.4% of flop reach)
C0: HU SRP flop reach 0.2733 is exactly the 8 "open, all fold, BB call" terminals (open -> SB call -> BB fold is negligible).
- New tables: SB (11), LJ (795), UTG+2 (2548), UTG+1 (7997) -> BB, panel_v1 (24 boards), menu_m2_single_v1, at the **S state's**
  endpoint ranges (the current best state; their openers / BB responses barely moved O -> S). The 4 S tables stay as they are.
- SB is the postflop OOP opener (pot 6 bb, SPR 4.58); `t2_cont_panel` assigns OOP = SB already.
- One preflop solve (100 it from scratch) with all 8 tables -> state H. H - S is the effect of adding the 4 tables.
- Judgment: no frozen-static control arm for the new nodes. C1b bounded the freezing effect (RFI +-0.08 pp, BB responses <= 0.15 pp,
  one 1.1 pp cell), and H1's job is to build the full-HU state for the outer loop, not to re-test the mechanism.
- Expected direction (new nodes, per node): opener RFI up, BB fold up / call down, opener jam share down. Opposite moves are reported.
- There is no untouched HU opener control any more; specificity is read from the 4 old nodes (should move little) and the SB
  response lines (still static via 3-way terminals).

## OL — outer loop on the 8 HU SRP tables
State k = (8 tables V_k, preflop sigma_k at 100 it, endpoint ranges R_k); start k = 0 at H. Panel fixed (panel_v1, the same 24 boards at
every step and node: common random numbers).
1. export the 8 terminals at sigma_k; solve panel_v1 at R_k; V_raw,k = A4c stratified estimator (undamped).
2. raw residual per node n and seat s: D(n,s) = sum_c w_c |V_raw,k(c) - V_k(c)| / sum_c w_c, w_c = combos(c) x keep_{s,k}(c)
   (the seat's own terminal range at state k); the signed weighted mean is reported next to it.
3. panel uncertainty U(n,s) = same weights over the analytic stratified standard error of V_raw,k(c)
   (se_c^2 = sum_strata p^2 s^2 / n, n = 2 boards per stratum, s^2 with n - 1).
4. damped update V_{k+1} = 0.5 V_k + 0.5 V_raw,k (tables only) -> preflop solve -> sigma_{k+1}.
5. stop: all 16 D <= U -> "converged at panel_v1 resolution (value space)"; max_(n,s) D/U grows two steps in a row -> stop and
   report; after 3 steps (k = 0, 1, 2) without meeting the rule -> "not yet converged", stop (no 4th step).
6. minimum one update: step 0 always continues to state 1, because the 4 S-pilot tables were computed at O's ranges (two preflop
   states back); the stop test applies from step 1. Reason: U (one estimate's panel error) is 0.2-0.4 bb per seat on panel_v1, so a
   stale table could pass step 0 inside the noise.
7. report only: U_paired = the same weighting over the stratified SE of the per-board change (raw minus state-k board values, same
   boards). D / U_paired near 1 means the step's move is not detectable on this panel; D / U_paired >> 1 with D <= U means the loop
   still moves, but by less than the panel's own error. Tables are linear in board values, so state-k per-board values are carried
   (damped) and the estimator reproduces every table exactly (checked, < 1e-9).
Reported every step (not stop criteria): RFI per position, BB / SB responses per opener, focus hands, ranges L1 change.

Judgment vs E1: E1's primary residual is the seat-swap dEV of sigma_k in G_raw,k with U from 60 replicate preflop solves. In 9-max one
preflop solve costs ~30-40 min, so 60 replicates per step (~35 h) are not affordable; OL uses a value-space residual instead. It answers
"do the tables still move by more than panel noise", not "is sigma_k a best response in G_raw,k". The wording above keeps that apart.
Cost per step: 192 flop solves (~5 h wall on 4 workers) + one preflop solve (~40 min); at most ~18 h for 3 steps. The 24-board panel
limits resolution: it is a self-consistency loop at pilot resolution, not a production panel.

## Step 3 — 3-bet and 3-way terminals (plan after OL)
Remaining static share after H1 (C0 reach): 3-bet pots 0.261 (35.7% of flop reach; HU 0.194, multiway 0.067), 3-way+ SRPs 0.196 (26.8%).
- HU 3-bet pots first: they are HU, so the existing machinery applies (lower SPR -> smaller postflop trees). C0 lists 18158 3-bet
  terminals; step 3 starts with a reach ranking to see how many terminals cover most of the 0.194.
- 3-way SRPs: only the 3-way research game exists (B-series); results from it are never called GTO. Default: keep static, and mark
  every DB spot whose preflop line feeds mainly into 3-way terminals with that remaining static share.
- Order and size are fixed after OL's result, before any solve.

## Step 3a — HU 3-bet terminals (decided 2026-10-05 after OL)
- Census at OL state 2 (`/home/user/gto_ckpt/step3/census_s2.json`): share of flop reach srp/hu 29.5%, srp/mw 28.2%, **3bet/hu 30.4%**,
  3bet/mw 11.8%. HU 3-bet pots are now the largest unsolved share and the HU machinery applies to them directly.
- Selection: the smallest reach-ranked set covering >= 80% of HU 3-bet reach = 25 terminals (80.8%; 24.6% of flop reach), listed in
  `data/gto_validation/pilot9/step3/t3_selection.json` (pot 14.5-21 bb, SPR 0.95-1.66).
- Cost probe (node 51, BTN open / SB 3-bet / BTN call, 4 boards): 89-132 s per board on one thread, 1.0 GB, <= 0.25% pot -> about
  12 min wall per terminal on 4 workers, about 5 h for the 25.
- T (one outer step for the 3-bet tables): panel_v1 at state-2 ranges; the 8 SRP tables stay at state 2; one preflop solve with 33 tables.
  Reported as T - S2 per opener / 3-bettor position; no expected direction is pre-registered for 3-bet pots (the static payoff at
  SPR ~1.2-1.7 has r ~ 1 +- 0.01, so the bias comes from pot x equity ignoring postflop play, sign unknown a priori).
- After T: a joint OL over all 33 tables with the same rule (max 3 steps) only if T moves preflop frequencies by more than the OL
  step-2 residual scale; otherwise T is reported and the loop is not run.
- 3-way terminals stay static (research game only); every DB record carries the static share of its line.
