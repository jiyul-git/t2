# HU continuation value v2 — 72-flop panel (sampling error only)

Branch `claude/gto-hu-continuation-v1-20260928`, starting from commit `1099069` (v1.1, J1–J3).

**Purpose.** J3 found flop sampling to be the largest error of the continuation values. This phase measures how much a 72-flop panel actually reduces it. Nothing else changes:
- terminal structure, preflop model and human model are unchanged;
- no M1 solve;
- the flop list and weights are not revised after results are seen;
- the public RFI is not a target.

Nothing here is a GTO DB value.

## L0. Pre-registration (written and committed before any new flop was solved)

### Panel `panel_v2_72.json` (sha256 `e0df1324fcb2ddd3…`)

- **Nested.** `panel_v1`'s 24 flops are kept verbatim.
- **48 new flops.** Each of the same 12 strata (structure × top card) continues `panel_v1`'s own draw:
  - proportional to raw-flop count, without replacement;
  - from the stratum's pool minus the flops already drawn.
- The 6 flops of a stratum therefore have the distribution of a 6-draw sequence of the v1 scheme.
- Weight per flop = P(stratum)/6. The estimator is unchanged.
- **Coverage rule, fixed before drawing (restricted randomisation):**
  - At least 3 flops per texture: monotone, paired, rainbow dry/connected, two-tone dry/connected.
  - At least 3 flops per rank bucket: A, K–Q, middle (J–8), low (7–2); paired by pair rank high (A–T), mid (9–6), low (5–2).
  - A failing draw is rejected and the seed advances by one.
  - Seed 20260929 was rejected (only 2 low boards). Seed **20260930** was accepted. Both are recorded in the manifest.
- **Definitions.** Connected = the three ranks fit in a 5-rank window, so a straight is possible (A also counts low). The tags are descriptive only; they do not enter the estimator.
  - J2 called Tc9d5h "rainbow connected" informally. Under this rule it is rainbow_dry.
- **Coverage of the accepted draw:**
  - monotone 18, paired 18;
  - rainbow dry 12 / connected 6;
  - two-tone dry 15 / connected 3;
  - A-high 18, K/Q-high 18, middle 15, low 3;
  - paired high 10 / mid 3 / low 5.
  - Two-tone connected, low and paired-mid sit exactly at the minimum. Each of these subgroups is thin.

### Stage A — sampling isolated (primary)

- **Ranges.** Fixed at P6d, the last step of the 24-flop damped fixed point:
  - `outer_v1_damped_a05/k6/terminal.json`, ranges hash `875dc7760feb6422`.
- **Solver settings.** Identical to the 24-flop tables:
  - M2 menu, f32, ε-tremble 1e-3;
  - 1,000-iteration cap, target 0.3% pot, check every 25 iterations.
- **Flops solved.** Only the 48 new flops.
  - The 24 panel_v1 artifacts at P6d are reused under a nested-provenance rule: the key must be identical except for the panel hash, which must be the parent panel's.
  - Before relying on reuse, two panel_v1 flops are re-solved and compared value-by-value.
- **Aggregation.** Same as before:
  - `aggregate.py`, estimator `ht_rho`;
  - stratified bootstrap B = 2000, seed 20260928 + 6;
  - guard |unallocated| ≤ 0.05 bb.
- The 24-flop numbers are the existing `k6/table_measured.json`.

**Reported per seat (BTN, BB):**
- 95% CI half-width over the 169 classes: mean, median, p90, max — for 24 and 72 flops.
- Effective sample size:
  - Kish design ESS of the flop weights;
  - per-class ESS = (design-weighted flop-to-flop variance of the class value) ÷ (bootstrap variance of the estimate).

**Prediction written before results.**
- The percentile bootstrap that resamples n flops within a stratum has variance factor (n−1)/n relative to the usual unbiased estimate. With n = 2 this halves the variance.
- So even at equal within-stratum dispersion, the 24→72 half-width ratio expected from the **existing method** is √((5/6)/6) ÷ √((1/2)/2) = **0.745**, not 1/√3 = 0.577.
- J2/J3's expectation of 0.21–0.27 bb (1/√3) is therefore expected to be optimistic. About 0.27–0.35 bb is expected.
- Diagnostics:
  - both CIs are also reported rescaled by √(n/(n−1));
  - the spread of 24-flop estimates across random nested 2-of-6 sub-panels of the 72 is shown.

**Watch classes (observed only, not modified):**
- BB call/fold flippers from J2: 73o, A3o, 72s, J2s, Q3s, A3s.
- Watch list: JTs, JTo, KQo, T7o, A2o, 85s, 43s, T7s (both seats).

For each class: value at 24 and at 72, CI, distance to the decision boundary, and whether the judgment changes.
- **BB** (opponent strategies fixed at P6d):
  - call − fold = V − 1.0 bb;
  - call − jam = (V − 2.25) − EV_jam, with EV_jam from the P6d preflop solve;
  - judgment = arg-max action.
- **BTN:**
  - EV_raise(V) = EV_raise(P6d) + q·(V − V_used at P6d), where q = P(SB folds, BB calls | BTN raises);
  - boundary = raise vs the best other action.
- The P6d action values come from a deterministic re-run of the P6d preflop solve with a read-only per-action value dump. It must reproduce ranges hash `875dc7760feb6422`.

**Action abstraction ÷ sampling CI.**
- J2's menu effect is used unchanged: mean |M1−M2| BB 0.073 / BTN 0.090 (BR values), 0.082 / 0.100 (ε values).
- It is divided by the 72-flop mean CI half-width, per seat.
- Classification, as given:
  - < 0.25: sampling still clearly first;
  - 0.25–0.5: abstraction approaching;
  - > 0.5: abstraction next.
- A value near a boundary is reported as such.
- J2's numerator itself comes from 4 flops; that caveat is stated with the ratio.

### Stage B — production loop with the 72-flop panel (damped outer fixed point, M2 f32)

- **Warm start.**
  - k6′ = P6d ranges; V6′_meas = the stage-A 72-flop table.
  - V6′_used = 0.5·V6′_meas + 0.5·V5_used — the same α = 0.5 rule. V5_used is the 24-flop table that P6d was solved with.
  - Then P7 → V7 → … with the 72-flop panel.
- **Steps.** k7, k8 and k9: three new preflop solves (J3 predicted 2–3). The same per-step metrics as `outer_loop.py` are recorded. No new stopping threshold; the run stops at k9.
- **Watch classes** are reported from the re-solved class strategies (24-flop P6d vs 72-flop final).

### Execution rules

- One process per flop (board filter), each writing its own provenance-stamped artifact.
  - A finished artifact is never recomputed. It is reused only if its provenance key matches.
  - A failed flop is logged and does not stop the others.
- **Workers:** min(4 cores, ⌊(MemAvailable − 3 GB) ÷ max per-flop peak RSS⌋), from measurements on this machine. Threads per worker = 4 ÷ workers.
- Per flop: iterations, exploitability, solve time, peak RSS, invariant error and converged/capped status.
