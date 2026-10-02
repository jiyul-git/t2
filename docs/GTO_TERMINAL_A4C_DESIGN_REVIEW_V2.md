# A4c design review (before any 288 solve)

**Scope.**
- No new flop solve was run. All numbers come from existing A3/A4b artifacts, plus three frozen-table preflop solves on A3 tables. A3/A4/A4b/A4R verdicts are unchanged.
- Artifacts: `data/gto_terminal_expansion/a4c_preanalysis/` (`loss_scaling.json`, `design.json`, `difference_variance.json`, `range_step/`).

## 1. What the requested plan would find, projected

**Bootstrap EV error of the panel-N policy.** σ_N*_r is swapped seat by seat into the point game G_N. This is a proxy for the policy's EV loss versus the true table at P14 ranges. Mean bb/hand over 60 replicates:

| seat | N = 72 | N = 144 | ratio | loss ∝ var^β | projected equal-288 | projected Neyman-288 |
|---|---|---|---|---|---|---|
| BTN | 0.0017 | 0.0009 | 0.55 | β 0.87 | 0.0005 | 0.0003 |
| SB | 0.0066 | 0.0037 | 0.57 | β 0.81 | 0.0021 | 0.0015 |
| BB | 0.0062 | 0.0038 | 0.61 | β 0.70 | 0.0023 | 0.0017 |

- The own residual gap of the preflop solve is about 1e-4 per seat.
- Reaching it by panel size alone would need a variance reduction of 19× (BTN), 71× (SB) and 330× (BB). That is thousands of boards.
- **So the amendment-3 rule will almost surely label 144 ↔ 288 "EV-sensitive".** The projected loss is about 15–20× the floor. The formal label is predictable and does not answer whether 288 is good enough.

## 2. A second error source of the same size: frozen ranges / outer non-convergence

Same 72 boards, measured tables at P13 and P12 versus P14. g(V_k) is swapped into G = g(V14):

| | BTN | SB | BB |
|---|---|---|---|
| g(V13) → G14 | 0.0005 | 0.0034 | 0.0022 |
| g(V12) → G14 | 0.0001 | 0.0011 | 0.0021 |

- One outer step moves the policy's EV by as much as the whole 144-board panel error.
- A3 is not at a fixed point; it shows period-2 behaviour.
- Refining the panel at frozen P14 ranges cannot reduce this part.

## 3. Sampling design

| finding | detail | consequence |
|---|---|---|
| Equal allocation is inefficient | Within-stratum SD of the reach-weighted value ranges from 0.09 to 0.35 bb, and P(s) from 0.012 to 0.195 | Neyman allocation (n_s ∝ P_s·SD_s, at least 12 per stratum, sampling fraction ≤ 0.25) on 288 boards gives 0.63× the variance of equal-24; it is equivalent to about 457 equally allocated boards. About 199 boards reach equal-288 precision |
| Equal-24 pushes small strata to large sampling fractions | paired/A: 24 of 49 classes (0.49). The panel is drawn sequentially, proportional to raw-flop count, without replacement, and the estimator is the equal-weight mean | The without-replacement bias grows with the sampling fraction. At 144 the Des Raj minus equal-weight difference is at most 0.015 bb, below the SE (paired/A SE ≈ 0.10). The bootstrap also omits the finite-population correction |
| Estimator unchanged | Stratified mean, P(s) × mean of the stratum's boards, for any n_s | aggregate.py and the paired bootstrap (old/new groups per stratum, some new groups empty) work unchanged |

## 4. Self-consistency cost

- **Node 28.** Difference variance between consecutive steps on the same boards is 1–3% of the level variance. A difference (control-variate) design is very efficient: big panel for the level, small panel for the step-to-step change.
- **Node 6.** The ranges moved a lot, and the difference variance is 20–130% of the level variance, so a difference design gains little there today.
- **Consequence.** Every full outer step on a 288 panel costs 2 × 288 flop solves, about 32 CPU-h. Doing self-consistency with 288 boards per step is the expensive path.

## 5. Numerical validation (proposal for A4c)

- **Measured floor.** |dEV − gap difference| and the BR identity reach at most 6.7e-11 over 1 224 records (A4R and pre-analysis). The floor is deterministic, thread-independent, and quantized (2.2475e-11). The median is 8e-17.
- **(i) Structural identities, exact.** Self-splice byte identity, all-seat splice = donor byte identity, point-solve reproduction.
- **(ii) Mathematical identities in floating point.** Tolerance 1e-9 bb/hand: 15× the measured maximum, fixed before results.
- **(iii) Decision robustness.** The classification must not change when every E is moved by ±1e-9. Otherwise the label is "numerically undecidable" (inconclusive).

## 6. Hand-level outputs

- **What the exports contain.** Per-class action EVs are exported for SB first-in, BB vs SB (node 4) and BB vs BTN (node 26). BTN first-in has frequencies only.
- **Primary hand-level stability metric.** The per-class regret of the stored strategy under the refined game: max_a EV_B(a|h) − Σ_a σ_A(a|h) EV_B(a|h).
- **Reported alongside, not primary.** L1, argmax switches and the mixed subset. A mixed class's frequency is not identified when its action EVs are equal.

## 7. Recommendation

1. **A4c with a Neyman-allocated nested extension instead of equal-24.**
   - **(a) Same cost as requested (Neyman-288).** About 143 new boards per terminal, roughly 32 CPU-h, about 9–10 h wall plus restarts. Variance 0.63× equal-288.
   - **(b) Cheaper (Neyman-199).** About 55 new boards per terminal, roughly 12 CPU-h, about 3.5 h wall. Precision about equal-288.
   - Both keep all 144 existing boards, the same estimator, ranges, solver settings, paired bootstrap (60 replicates; decision margins at 144 were far from the quantile resolution) and seat-swap A4R.
2. **Make the scientific readout the out-of-sample check of the projected scaling** (table above), together with the bootstrap EV-error estimate at the new size.
   - Keep the amendment-3 label for continuity, and pre-register that it is expected to be EV-sensitive.
   - A production decision needs a tolerance per seat in bb/hand from the user. The scaling gives the panel size needed for any such tolerance.
3. **Plan self-consistency as the next separate step.** It needs its own pre-registration and possibly warm-started flop solves. Size it with the difference-variance numbers above. Its error is currently the same size as the panel error.
