# A4c design review v2: downstream-aware allocation (before any new flop solve or prereg)

**What was used.** Only existing A4b artifacts, plus 192 preflop-only influence solves. No flop solve was run and nothing is pre-registered yet.

**Data.** `data/gto_terminal_expansion/a4c_preanalysis/`:

| file | content |
|---|---|
| `influence/results.json` | stratum-isolated runs, raw |
| `influence/summary.json` | stratum-isolated runs, summary |
| `reconstruction.json` | additive reconstruction and stability checks |
| `allocation_downstream.json` | downstream-aware allocations and options |
| `calibrated_options.json` | calibrated loss predictions per option |
| `design2.json` | estimator design bias and table-level allocation |
| `fpc_paired.json` | paired-strata FPC approximation |

## 1. Influence

**Run design.**
- One terminal and one stratum resampled at a time, 8 replicates each, 24 groups.
- Downstream measures:
  - seat-swap EV loss against G144;
  - class regret, as excess over G144's own residual, at BTN first-in, SB vs BTN, BB vs BTN, SB first-in and BB vs SB;
  - L1 distance and aggregate frequencies.

**Contributions** (BTN+SB+BB seat EV, bb/hand, at 12 boards):

| rank | group | contribution |
|---|---|---|
| 1 | node 6 twotone/J_or_lower | 0.00224 |
| 2 | node 6 rainbow/J_or_lower | 0.00213 |
| 3 | node 6 twotone/KQ | 0.00151 |
| 4 | node 6 paired/J_or_lower | 0.00129 |
| 5 | node 6 rainbow/KQ | 0.00093 |
| 6 | node 28 twotone/J_or_lower | 0.00089 |

- Node 6 carries **77%** of the total seat-EV contribution.
- The monotone strata are negligible: ≤ 2.3e-5 in either terminal.

## 2. Additive reconstruction against the pooled 60 A4b replicates

| metric | isolated sum | pooled observed | ratio |
|---|---|---|---|
| seat EV BTN | 0.00132 ± 0.00017 | 0.00091 ± 0.00007 | 1.46 |
| seat EV SB | 0.00560 ± 0.00047 | 0.00374 ± 0.00022 | **1.50** |
| seat EV BB | 0.00525 ± 0.00036 | 0.00380 ± 0.00027 | 1.38 |
| regret BTN first-in | 0.00167 | 0.00120 | 1.39 |
| regret SB first-in | 0.0115 | 0.0093 | 1.25 |
| regret BB vs SB | 0.0149 | 0.0103 | 1.45 |
| regret BB vs BTN | 0.0120 | 0.0108 | 1.11 |
| regret SB vs BTN | 0.00078 | 0.00019 | 4.07 (tiny absolute) |
| L1 (root-sum-square), 5 nodes | | | 0.93–1.51 |
| aggregate MSE, SB first-in | | | **2.1–2.6** |
| aggregate MSE, BB vs BTN | | | 0.95–1.14 |

**Reading.**
- The isolated contributions are **sub-additive**: their sum overpredicts the joint perturbation by about 1.4–1.5× for seat EV.
  - Part of this is design: the pooled bootstrap resampled old and new boards separately within each stratum, worth about 1.1×.
  - The rest is non-linearity: loss grows more slowly than the summed table variance. This matches the independently measured 72→144 exponent β = 0.70–0.87 (loss ∝ variance^β).
- **SB is the most non-additive.**
  - Its seat-EV ratio is 1.50.
  - Its first-in frequency MSE is overpredicted 2.1–2.6×. The SB frequency response saturates, as expected near mixing thresholds.
  - The SB residual is significant: about 0.0019 against SEs of about 0.0005.
- **Node-28 metrics are close to additive** (0.93–1.14).
- **L1 fails** the reconstruction (errors up to 51%), so it stays a diagnostic and is not part of the objective.

## 3. Replicate stability

- **Leave one replicate out:** top-5 set unchanged in 99.0% of cases; top-3 order unchanged in 98.4%.
- **Bootstrap over the 8 replicates:** the four node-6 strata above are in the top 5 in 99.3–100% of resamples.
- **The 5th slot is a toss-up:** node 6 rainbow/KQ (46%) against node 28 twotone/J_or_lower (43%). This hardly matters for the allocation.

## 4. Corrected allocation

- **Rule.** Exact integer allocation, FPC-aware SRSWOR with K classes per stratum, greedy on the marginal reduction of the seat-EV objective. Separate allocation per terminal.
- **Paired strata.** Scaling their contributions by ±2% (`fpc_paired.json` range) leaves the allocation exactly unchanged, so the effect is immaterial for this decision.
- **Allocation reproducing the equal-24 (equal-288) downstream objective: 124 new solves** (node 6 +96, node 28 +28), against 288 for equal allocation.

  | stratum | node 6 boards | node 28 boards |
  |---|---|---|
  | paired/J_or_lower | 27 | 15 |
  | rainbow/A | 13 | 12 |
  | rainbow/J_or_lower | 35 | 20 |
  | rainbow/KQ | 23 | 12 |
  | twotone/A | 18 | 12 |
  | twotone/J_or_lower | 35 | 22 |
  | twotone/KQ | 29 | 19 |
  | all other strata | 12 | 12 |

- **Allocation shape.** It depends only on the stratum weights. The sub-additivity, if it is a monotone transform of a weighted variance sum, does not change the shape, but it is an assumption (§6).

## 5. Options

- **Measured cost:** 5.69 CPU-min per node-6 flop, 6.83 per node-28 flop. Wall time assumes 4 cores.
- **Calibrated seat loss:** the pooled 144 observation × (V_option / V_144)^β.

| option | new solves (node 6 / node 28) | CPU-h | wall | calibrated loss BTN / SB / BB (bb/hand) | regret reduction vs 144 (linear) | outer-step reuse |
|---|---|---|---|---|---|---|
| current 144 | 0 | 0 | 0 | 0.00091 / 0.00374 / 0.00380 | — | anchor |
| D (small, 48) | 43 / 5 | 4.6 | 1.2 h | 0.00081 / 0.00249 / 0.00288 | 9–41% | best |
| B (108) | 85 / 23 | 10.7 | 2.7 h | 0.00061 / 0.00193 / 0.00234 | 31–57% | good |
| **B′ (124, = equal-288 downstream)** | **96 / 28** | **12.4** | **3.1 h** | **≈ 0.00047 / 0.0020 / 0.0022** | ≈ equal-288 | good |
| C (144) | 110 / 34 | 14.3 | 3.6 h | 0.00054 / 0.00171 / 0.00211 | 40–63% | medium |
| C (192) | 144 / 48 | 19.1 | 4.8 h | 0.00047 / 0.00148 / 0.00187 | 48–69% | medium |
| A (288, downstream) | 212 / 76 | 28.8 | 7.2 h | 0.00038 / 0.00116 / 0.00153 | 59–77% | poor |
| equal-24 (requested) | 144 / 144 | 30.0 | 7.5 h | 0.00047 / 0.00199 / 0.00220 | ≈ B′ | poor |

The equal-24 and B′ precision figures are the same by construction. Both are projections, not results.

## 6. Recommendation

**B′: a downstream-aware nested extension with 124 new flop solves** (node 6 +96, node 28 +28), about 12.4 CPU-h and about 3.1 h wall. Then go straight to a separately pre-registered self-consistency stage.

**Why.**
1. **Same downstream precision as the requested equal-288, at 43% of its cost.** Node 28 needs few boards; node 6 carries 77% of the influence.
2. **After B′, the panel error is at or below the frozen-range proxy.**
   - Panel: SB ≈ 0.0020, BB ≈ 0.0022.
   - Proxy (A3 k13 → k14 table, same boards; *a proxy, not the true fixed-point residual*): SB 0.0034, BB 0.0022.
   - Going further to A-288 buys about 0.0008 SB for +4.1 h of wall time, while the outer-loop error stays at the same order.
3. **Reuse.** The extension sits at P14 ranges and becomes the level anchor for a difference (control-variate) outer loop. Node 28's step-to-step difference variance is 1–3% of the level variance, so a small sub-panel suffices. Node 6 needs more (20–130%). One such step is about 11 CPU-h, against about 41 CPU-h for a full re-solve of the extended panel.

**Caveats** (pre-registered as predictions, not results).
- The calibrated losses use β from a single 72→144 comparison.
- The SB first-in frequency response is clearly non-additive, so SB frequency precision cannot be predicted from these numbers. EV and regret are better behaved.
- The 288-type projections are projections. The actual 144 ↔ extension seat-swap result is the out-of-sample check.
- The panel loss can never reach the preflop residual floor (about 1e-4) at any feasible size. A production tolerance in bb/hand per seat is still needed from the user.
