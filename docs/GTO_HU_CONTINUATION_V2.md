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

---

## L1. Stage A result — sampling error at fixed P6d ranges

Numbers: `data/gto_hu_continuation/panel72/stageA/analysis.json`. Figure: [`GTO_HU_V2_PANEL72_CI.png`](GTO_HU_V2_PANEL72_CI.png).

### Runs and provenance

- **48/48 new flops solved**, 0 failed, all converged: 0.19–0.29% pot, 100–125 iterations. The 24 panel_v1 artifacts are reused under the nested rule.
  - Per-flop invariant error ≤ 6e-8 bb.
  - Peak RSS 2.12 GB per flop.
  - 4 processes × 1 thread; 175–1,088 s per flop.
- **Reproducibility:** two panel_v1 flops re-solved at 2 threads, with the solver built at the tooling commit, are bit-identical to the 4-thread originals (`reproducibility_check.json`).
- **P6d re-run:** reproduces ranges hash `875dc7760feb6422`, frequencies and gap exactly. The dumped call EV equals V − 2.25 to 3e-6.
- **72-flop table** (`stageA/table72.json`): unallocated **−0.006 bb** (24-flop: +0.023); BR − ε max 0.018 / 0.029 bb.
- **Interruptions, recorded as they happened:**
  - The first driver run was stopped by a container restart after 30 flops; no artifact was partial. The resume reused them through the provenance check.
  - The resumed run ran flops one at a time because of a worker-slot leak in `solve_panel.py`: unreferenced Popen objects were reaped by subprocess cleanup. It then ended in `ChildProcessError` after the last flop.
  - Values were not affected (ledger 48/48 solved). The leak is fixed in `b4bb773`.

### A. Sampling CI, 24 → 72 flops (95% half-width, bb, over the 169 classes)

| | BTN 24 | BTN 72 | BB 24 | BB 72 |
|---|---:|---:|---:|---:|
| mean | 0.356 | **0.293** | 0.474 | **0.425** |
| median | 0.322 | 0.271 | 0.421 | 0.392 |
| p90 | 0.540 | 0.411 | 0.725 | 0.641 |
| max | 1.192 | 0.751 | 1.502 | 0.963 |
| mean, in-range classes only | 0.381 | 0.301 | 0.475 | 0.422 |
| Kish design ESS (flops) | 16.1 | 48.4 | 16.1 | 48.4 |
| per-class ESS, mean / median | 35.6 / 28.7 | 69.2 / 60.1 | 49.4 / 35.7 | 88.4 / 71.1 |

Ratio 72/24 of the mean half-width:

| | measured | median per class | pre-registered | naive 1/√3 |
|---|---:|---:|---:|---:|
| BTN | **0.824** | 0.814 | 0.745 | 0.577 |
| BB | **0.895** | 0.890 | 0.745 | 0.577 |

**The measured reduction is smaller than both predictions. The cause is the 24-flop CI, not the 72-flop one.**

- **The 24-flop bootstrap under-covered.**
  - Evaluated over random nested 2-of-6 sub-panels of the 72 (finite-population corrected), the spread of a 24-flop estimate is a half-width of **0.507 (BTN) / 0.739 (BB)**.
  - The 24-flop bootstrap reported 0.356 / 0.474. That is 1.4–1.6× too narrow.
  - Two effects compound:
    1. Resampling 2 flops per stratum halves the variance (the √2 predicted in L0).
    2. A within-stratum variance estimated from 2 flops is itself very noisy. Classes whose 2 flops happened to agree got a tiny CI; many of their 72-flop CIs are larger than the 24-flop ones (figure, panels 1–2).
  - The √(n/(n−1))-rescaled CIs give 0.503 / 0.671 (24) → 0.321 / 0.465 (72): a ratio of 0.64 / 0.69, close to 1/√3.
- **Old 24 vs new 48 is consistent with pure flop sampling.**
  - Stratified difference ÷ SE from the 6-flop within-stratum variance: |z| > 1.96 in 2.4% (BTN) / 3.6% (BB) of classes, with z SD 0.95 / 0.96. Under pure sampling the expectation is 5% and SD 1.
  - Range-EV difference: z = −1.64 (BTN) / +1.01 (BB).
  - No stratum stands out beyond its own dispersion. Nothing here points to a bug, a drift or a texture-specific bias. The movement is what a 24-flop panel really carries.
- **Values moved accordingly.**
  - Mean |V72 − V24| = 0.19 bb (BTN) / 0.27 bb (BB), max 0.78 / 1.21.
  - 18% / 21% of classes moved outside their own 24-flop CI.
  - Range-EV shift: BTN +0.074 bb, BB −0.045 bb.
- **Consequence for C3.**
  - C3 listed 72o, 82o, 92o and T2o with the whole 24-flop CI below the 1.0 bb fold line. At 72 flops, 72o (0.48 → 1.16) and 82o (0.51 → 1.17) sit above the line; 92o (0.92) and T2o (0.98) sit just below it, with CIs that cross it.
  - The set of BB classes below the line changes from 16 to 11 classes: 11 move up, 6 move down. The "which trash hands fold" detail of v1 was mostly sampling.
- **Estimator sensitivity** (|HT/ρ − ratio| per class) halves: 0.20 / 0.23 → 0.09 / 0.12 bb.

### B. Watch classes (observed only; opponents fixed at P6d)

Definitions:
- **BB:** call − fold = V − 1.0; call − jam = V − 2.25 − EV_jam; "best" = arg-max of fold/call/3bet/jam EV. The margin is to the second-best action.
- **BTN:** EV_raise(V) = EV_raise(P6d) + q·(V − V5_used), with q = 0.291. The margin is raise − best other, also shown in units of q·CI.
- The "best" action implied by a measured table is not the solved strategy: P6d was solved with the damped table V5_used. Solved strategies at 72 flops come from stage B.

BB:

| class | V24 ± CI | V72 ± CI | call − fold 24 → 72 | best 24 → 72 (margin) | P6d strategy |
|---|---|---|---|---|---|
| 73o* | 1.05 ± 0.29 | 1.04 ± 0.28 | +0.05 → +0.04 | call → call (0.04) | call |
| A3o* | 1.87 ± 0.27 | 1.79 ± 0.24 | +0.87 → +0.79 | call → call (0.22) | call |
| 72s* | 1.00 ± 0.29 | 1.55 ± 0.38 | −0.00 → +0.55 | **fold → call** (0.55) | fold 0.67 |
| J2s* | 1.29 ± 0.38 | 1.35 ± 0.32 | +0.29 → +0.35 | call → call (0.17) | call |
| Q3s* | 1.95 ± 0.47 | 1.61 ± 0.39 | +0.95 → +0.61 | call → call (0.36) | call |
| A3s* | 2.15 ± 0.27 | 2.36 ± 0.21 | +1.15 → +1.36 | **jam → call** (0.11) | jam |
| JTs | 2.29 ± 0.58 | 2.18 ± 0.33 | +1.29 → +1.18 | jam → jam (0.19) | call |
| JTo | 1.60 ± 0.65 | 1.51 ± 0.36 | +0.60 → +0.51 | jam → jam (0.17) | call |
| KQo | 2.88 ± 0.28 | 2.99 ± 0.25 | +1.88 → +1.99 | jam → jam (0.03) | call 0.77 / jam 0.23 |
| T7o | 0.89 ± 0.20 | 1.44 ± 0.38 | −0.11 → +0.44 | **jam → call** (0.44) | fold 0.31 / jam 0.69 |
| A2o | 1.58 ± 0.26 | 1.79 ± 0.29 | +0.58 → +0.79 | call → call (0.22) | jam 0.96 |
| 85s | 1.59 ± 0.18 | 1.84 ± 0.31 | +0.59 → +0.84 | call → call (0.53) | call |
| 43s | 2.89 ± 0.61 | 1.93 ± 0.52 | +1.89 → +0.93 | call → call (0.61) | call |
| T7s | 1.61 ± 0.15 | 2.08 ± 0.37 | +0.61 → +1.08 | call → call (0.57) | call |

\* J2 menu flipper.

BTN:

| class | V24 ± CI | V72 ± CI | raise − best other 24 → 72 (÷ q·CI) | best 24 → 72 | P6d strategy |
|---|---|---|---|---|---|
| JTs | 3.66 ± 0.46 | 3.79 ± 0.26 | −0.24 → −0.20 (−2.6) | jam → jam | jam |
| JTo | 3.15 ± 0.51 | 3.31 ± 0.29 | +0.05 → +0.09 (+1.1) | raise → raise | raise |
| KQo | 3.69 ± 0.24 | 3.87 ± 0.18 | −0.00 → +0.05 (+1.0) | **jam → raise** | raise 0.45 / jam 0.55 |
| T7o | 2.79 ± 0.22 | 3.21 ± 0.27 | −1.18 → −1.06 | fold → fold | fold |
| A2o | 2.75 ± 0.22 | 2.83 ± 0.18 | −0.18 → −0.16 (−3.1) | fold → fold | fold |
| 85s | 3.48 ± 0.19 | 3.59 ± 0.22 | −0.02 → +0.02 (+0.2) | **fold → raise** | raise 0.98 |
| 43s | 3.64 ± 0.35 | 3.22 ± 0.32 | −0.03 → −0.15 (−1.6) | fold → fold | raise |
| T7s | 3.29 ± 0.16 | 3.66 ± 0.25 | +0.00 → +0.11 (+1.5) | raise → raise | fold 0.61 / raise 0.39 |

Reading:
- **BB J2 flippers.** 73o stays within 0.05 bb of the fold line at both panel sizes, so it remains unresolved. J2s and A3o stay calls. 72s moves from on the line to +0.55. A3s and T7o change their implied action.
- **BB call ↔ jam classes** (JTs, JTo, KQo) are decided by ≤ 0.19 bb margins against a 0.25–0.36 bb CI. KQo remains within 0.03.
- **BTN.**
  - 85s stays within 0.25·q·CI of indifference and is unresolved at 72 flops.
  - KQo and T7s move to about 1–1.5 q·CI from their boundary.
  - The BTN CI enters the raise EV only through q = 0.29, so BTN decisions are 3.4× less sensitive to the terminal value than BB decisions.

### C. Action abstraction ÷ sampling CI

| | BB ÷ 24 CI | BB ÷ 72 CI | BTN ÷ 24 CI | BTN ÷ 72 CI |
|---|---:|---:|---:|---:|
| J2 menu effect, BR values, ratio of means | 0.154 | **0.172** | 0.254 | **0.308** |
| ε values, ratio of means | 0.172 | 0.193 | 0.281 | 0.341 |
| BR, mean of per-class ratios (J2's reporting) | 0.196 | 0.189 | 0.299 | 0.328 |
| classes with \|M1 − M2\| > own CI | 1.2% | 1.2% | 0.6% | 3.0% |

Classification with the pre-set thresholds:
- **BB: 0.17–0.19, below 0.25.** Sampling is still clearly first.
- **BTN: 0.31–0.34, in the 0.25–0.5 band.** Action abstraction is approaching.
  - With the rescaled 72-flop CI (0.321) the ratio is 0.28, still in the band but close to 0.25.
  - The numerator comes from 4 M1 flops, so it has its own sampling error.
- The ratios **rose less than the √3 J2/J3 expected** because the bootstrap CI shrank less.
- **Against the calibrated 24-flop error** (0.51 / 0.74), the J2 ratios were really 0.18 (BTN) / 0.10 (BB), not 0.30 / 0.20. J2/J3 overstated how close abstraction already was, but the ranking is the same.

## L2. Stage B result — damped outer fixed point on the 72-flop panel

Numbers: `data/gto_hu_continuation/panel72/outer_v2_damped_a05/analysis.json`. Figure: [`GTO_HU_V2_STAGEB_LOOP.png`](GTO_HU_V2_STAGEB_LOOP.png).

- **Solves.** 216 flop solves (72 per step at P7, P8, P9), 0 failed, all converged: 0.18–0.30% pot, invariant ≤ 1e-7 bb.
- **Guard.** Every blended table passed at its step's ranges: −0.014 … +0.023 bb.
- **Preflop gap.** 0.00033–0.00046 per step.
- **Interruptions.** Two container restarts, both during k8. Finished per-flop artifacts were reused through the provenance check. Only the flops that were running (at most 4 each time) were redone.

| step | table injected | BB fold / call / jam | BTN raise / jam | range L1 vs previous (BTN / BB) | measured mean \|ΔV\| (BTN / BB) | mean CI half-width (BTN / BB) |
|---|---|---|---|---|---|---|
| P6d | V5_used (24-flop) | 0.128 / 0.712 / 0.160 | 0.341 / 0.046 | — | — | 0.293 / 0.425 |
| P7 | 0.5·V6′(72) + 0.5·V5_used | 0.112 / 0.732 / 0.156 | 0.361 / 0.041 | 0.252 / 0.253 | 0.046 / 0.065 | 0.305 / 0.432 |
| P8 | blend | 0.100 / 0.754 / 0.146 | 0.373 / 0.042 | 0.097 / 0.104 | 0.026 / 0.033 | 0.301 / 0.422 |
| P9 | blend | **0.100 / 0.756 / 0.144** | **0.368 / 0.041** | 0.085 / 0.063 | 0.015 / 0.015 | 0.302 / 0.427 |

Reading:
- **The panel change moved the fixed point.**
  - BB fold 0.128 → 0.100; BTN open 0.341 → 0.368.
  - Most of the move is in the first step (range L1 0.25).
  - BB fold was flat from P8 to P9 (0.0996 → 0.0999). BTN open turned back by 0.005.
- **The measured-table change fell to 0.015 bb per class.** That is half the v1 plateau (0.02–0.03) and about 1/20 of the class CI.
- **The class level is still not converged, and cannot be at this precision.** Classes changing by > 0.1 between P8 and P9:
  - BB: 72o 0.99, 82o 0.98, 95o 0.87, 83o 0.76, JTs 0.69, 33 0.46, 94o 0.36, KJo, A3s, KQo, JTo;
  - BTN: K2s 0.94, Q4s 0.89, K6o 0.75, 65o 0.72, 52s 0.51, A3o 0.40.
  - The BB fold/call switchers sit within ±0.05 bb of the fold line (72o +0.02, 82o +0.05, 95o −0.01, 83o −0.01, 94o +0.00) against a class CI of ±0.37–0.48.
  - **43 BB classes have a 72-flop CI that straddles the fold line.**
- **Which trash hands fold is not identified at 72 flops.** The fold > 50% set changes almost completely from P6d to P9:
  - P6d: 32o 42o 62o 72o 72s 82o 85o 92o J2o J5o K2o Q2o T2o T4o T5o;
  - P9: 83o 92o 93o 95o J2o J3o J4o J5o T2o T3o T4o.
  - Only 5 classes are common: 92o, J2o, J5o, T2o, T4o.
  - What is stable is the aggregate: about 10% BB folds, drawn from the weakest offsuit gappers.
  - A bootstrap CI of the BB fold frequency was not part of this phase's plan and was not computed.

**Watch classes, solved strategy P6d (24 flops) → P9 (72 flops)**, with the P9 margin to the next-best action and V ± CI:

| class | BB P6d → P9 | P9 margin (bb) | V24 ± CI → V72 ± CI (P9) |
|---|---|---|---|
| 73o* | call → call | 0.04 | 1.05 ± 0.29 → 1.04 ± 0.27 |
| A3o* | call → call | 0.16 | 1.87 ± 0.27 → 1.89 ± 0.26 |
| 72s* | fold 0.67 / call 0.33 → **call** | 0.43 | 1.00 ± 0.29 → 1.45 ± 0.37 |
| J2s* | call → call | 0.14 | 1.29 ± 0.38 → 1.38 ± 0.31 |
| Q3s* | call → call | 0.38 | 1.95 ± 0.47 → 1.72 ± 0.42 |
| A3s* | jam → **call** | 0.04 | 2.15 ± 0.27 → 2.43 ± 0.23 |
| JTs | call → call 0.98 / jam 0.02 | 0.02 | 2.29 ± 0.58 → 2.37 ± 0.34 |
| JTo | call → **jam 0.81** / call 0.19 | 0.00 | 1.60 ± 0.65 → 1.73 ± 0.37 |
| KQo | call 0.77 / jam 0.23 → call 0.53 / jam 0.47 | 0.00 | 2.88 ± 0.28 → 3.14 ± 0.25 |
| T7o | fold 0.31 / jam 0.69 → **call** | 0.14 | 0.89 ± 0.20 → 1.29 ± 0.34 |
| A2o | jam 0.96 → **call** | 0.07 | 1.58 ± 0.26 → 1.79 ± 0.29 |
| 85s | call → call | 0.30 | 1.59 ± 0.18 → 1.75 ± 0.30 |
| 43s | call → call | 0.67 | 2.89 ± 0.61 → 2.04 ± 0.53 |
| T7s | call → call | 0.32 | 1.61 ± 0.15 → 1.95 ± 0.35 |

| class | BTN P6d → P9 | P9 margin (bb) | V24 ± CI → V72 ± CI (P9) |
|---|---|---|---|
| JTs | jam → jam | 0.24 | 3.66 ± 0.46 → 3.63 ± 0.26 |
| JTo | raise → raise | 0.05 | 3.15 ± 0.51 → 3.10 ± 0.30 |
| KQo | raise 0.45 / jam 0.55 → same | 0.00 | 3.69 ± 0.24 → 3.73 ± 0.20 |
| T7o | fold → fold | 0.28 | 2.79 ± 0.22 → 3.03 ± 0.30 |
| A2o | fold → fold | 0.09 | 2.75 ± 0.22 → 2.91 ± 0.22 |
| 85s | raise 0.98 → raise | 0.03 | 3.48 ± 0.19 → 3.62 ± 0.20 |
| 43s | raise → **fold** | 0.05 | 3.64 ± 0.35 → 3.52 ± 0.37 |
| T7s | fold 0.61 / raise 0.39 → **raise** | 0.08 | 3.30 ± 0.17 → 3.51 ± 0.27 |

\* J2 menu flipper.

- Of the 22 rows, 8 changed their main action.
- **Every changed class has a P9 margin (≤ 0.14 bb) smaller than its own CI (0.20–0.37 bb).** The CI enters BTN decisions only through q = 0.29, so each margin is also compared with q·CI.
  - BB: 72s, A3s, JTo, T7o, A2o;
  - BTN: 43s and T7s.
- **The exception is 72s.** It moved from the fold line to +0.43 bb, which is about 1.2 × its 72-flop CI.
- **JTo, KQo (both seats), JTs, 73o and A3s remain within 0.04 bb of indifference.** These classes are not resolvable by a panel of this size. As in v1, their mixes are not identified.

## L3. Error budget, 24 → 72 flops (per-class continuation value, bb)

| source | how measured | 24 flops (v1.1 J3) | 72 flops (this phase) |
|---|---|---|---|
| **flop sampling**, bootstrap 95% half-width, mean (BTN / BB) | stratified bootstrap, same method | 0.356 / 0.474 | **0.293–0.305 / 0.422–0.432** (P6d–P9) |
| flop sampling, calibrated | 24: nested 2-of-6 sub-panels of the 72; 72: bootstrap × √(6/5) | **0.507 / 0.739** | **0.321 / 0.465** |
| flop sampling, max over classes | bootstrap | 1.19 / 1.50 | 0.75 / 0.96 |
| estimator choice (HT/ρ vs ratio), mean | same tables | 0.20 / 0.23 | 0.09 / 0.12 |
| **postflop action abstraction** (M1 vs M2) | J2, 4 flops, not re-measured | 0.090 / 0.073 (BR) | same (systematic; does not shrink with flops) |
| postflop solver residual (BR − ε), mean / max | same tables | 0.012 / 0.019 · 0.015 / 0.033 | 0.012 / 0.018 · 0.016 / 0.029 |
| storage quantisation | J2 (compressed only) | 0.03–0.04 in-range | not incurred: f32 throughout |
| fixed point vs joint CFR | J1, 6 flops, not re-measured | 0.011–0.019 | same |
| preflop 169-class / no card removal (\|unallocated\|, range level) | table invariant | 0.02–0.03 | 0.004–0.023 |
| outer-loop change of the last step (measured table, mean) | loop log | 0.023–0.033 | 0.015 |

Ratios:
- **Action abstraction ÷ sampling CI** (J2 BR effect ÷ 72-flop bootstrap mean): BB **0.17**, BTN **0.31**.
- With the calibrated CIs: BB 0.16, BTN 0.28. At 24 flops the calibrated ratios were BB 0.10, BTN 0.18.

## L4. Verdict (thresholds fixed in the instruction: < 0.25 / 0.25–0.5 / > 0.5)

**BB.**
- 0.16–0.19 (every variant < 0.25): **sampling is still clearly the first error**.
- 43 classes straddle the fold line; the fold set is unidentified.

**BTN.**
- 0.28–0.34 (every variant in 0.25–0.5): **action abstraction is approaching**, co-equal to within a factor of about 3.
- The calibrated value 0.28 is close to the 0.25 edge, so this is not a clear crossing.

**Next bottleneck.**
1. **BB-side values: flop sampling still.**
2. **BTN-side values: sampling and abstraction together.** The BTN CI enters BTN decisions only through q = 0.29, so the premium bias J2 found (−0.15…−0.35 bb under M1) is now the more decision-relevant systematic term there.
3. The method-side errors (fixed point vs joint, solver residual, card removal, loop plateau) are all ≤ 0.03 bb. They stay an order of magnitude below both.

**Is further panel expansion worth it?** Yes, for BB, but not by brute force alone.
- **The measured cost is steep.** From 24 to 72 flops (3× cost), the calibrated CI fell by 1.6× (0.51 / 0.74 → 0.32 / 0.47), as 1/√3 predicts.
- **Doubling to 144 flops** would give ≈ 0.23 / 0.33. That is still above the BB fold-line margins of most trash classes (≤ 0.05 bb).
- **Allocation is the cheaper lever.** The equal 6-per-stratum allocation spends 18 flops on monotone strata (P = 5%) while the paired and two-tone strata carry the variance.
  - From the observed stratum dispersions, a Neyman allocation of the same 72 flops (keeping ≥ 2 per stratum) would cut the mean SE by about 26% (BTN) / 20% (BB). That is worth roughly 1.6–1.8× more flops.
  - This is a design proposal for a *new* pre-registered panel. It was not applied here, because the allocation of this panel was fixed before results.
- **Identifying trash-hand fold/call mixes class by class needs precision this approach cannot reach cheaply.** The aggregate (≈ 10% BB fold) is what is identified.

**Unchanged caveats.**
- One injected terminal; all other terminals keep the old payoff.
- M2 menu.
- The public RFI was not used.
- **Nothing here is a GTO DB value.**

## L5. Runtime and resources

| part | flop solves | CPU-hours (1 thread) | wall | per flop (s) min / mean / max |
|---|---:|---:|---|---|
| stage A (48 new flops at P6d) | 48 | 5.6 | 13:21–17:26 (incl. restart and 1-worker leak) | 175 / 422 / 1,088 |
| stage B k7 | 72 | 7.0 | 1 h 47 min | 165 / 350 / 758 |
| stage B k8 | 72 | 7.9 | 2 h 10 min (2 restarts) | 149 / 397 / 781 |
| stage B k9 | 72 | 9.0 | 2 h 17 min | 197 / 451 / 1,205 |
| preflop solves (P7–P9, P6d re-run) | — | — | 30 s each | — |

- **Machine:** 4 cores, 15 GB. Peak RSS 2.12 GB per flop (M2 f32); 4 workers use about 8.5 GB.
- **Worker count** was set from a measured 2.18 GB peak and 15.2 GB MemAvailable with a 3 GB reserve.
- **4 processes × 1 thread** gave about 1.3–1.6× the throughput of the old 1 process × 4 threads (2-thread test: speed-up 4 vs 2 threads was only 1.7).
- One outer step on 72 flops costs about 2 h wall here.

**Provenance.**
- Every per-flop artifact carries the full provenance key (ranges hash, menu hash, panel hash, tree config, ε, target, storage), the solver commit, threads and peak RSS.
- Every table carries the terminal file, ranges hash, panel hash(es), flop directories and solver commits.
- Per-step ranges hashes and injected tables are in `analysis.json → provenance`.
- Run ledgers (`run_ledger.jsonl`), driver logs and loop logs, including the interrupted runs, are committed unchanged.
