# A4c design review v2c: seat-wise check of the allocation (corrects v2b)

**Correction to v2b.**
- The B′124 calibrated seat losses in v2b (0.00047 / 0.0020 / 0.0022) were copied from equal-24; they were not computed.
- B′124 matched only the summed objective, not each seat. The "same downstream precision as equal-288" claim is withdrawn.

**Source.** `data/gto_terminal_expansion/a4c_preanalysis/seatwise.json` and `tools/gto_hu_continuation/a4c_seatwise.py`. No solve was run.

## Objective used in v2b

- Unweighted sum of BTN + SB + BB seat-swap dEV, in bb per hand dealt.
- Terminal reach is already inside the seat EV.
- No seat weights.
- Regret not included.

## B′124 versus equal-24

Ratios of predicted loss (FPC-aware additive predictions):

| metric | ratio |
|---|---|
| seat BTN | **1.28** |
| seat SB | 0.90 |
| seat BB | 1.02 |
| regret BTN first-in | 1.26 |
| regret SB vs BTN | 1.53 |
| regret BB vs BTN | 1.40 |
| regret SB first-in | 0.87 |
| regret BB vs SB | 0.87 |

- **Calibrated seat losses**, B′124 versus equal-24 (bb/hand):

  | seat | B′124 | equal-24 |
  |---|---|---|
  | BTN | 0.00058 | 0.00047 |
  | SB | 0.00183 | 0.00199 |
  | BB | 0.00223 | 0.00220 |

- The summed optimum under-allocates node 28: BTN and the node-28 regrets are traded for SB.
- The scalar-sum path is monotone in every metric; B108 SB 0.964 → B124 SB 0.901.

## Minimum new boards to keep metrics at or below equal-24

| criterion | new (node 6 / node 28) | CPU-h | wall (4 cores) |
|---|---|---|---|
| all three seats (constrained Lagrangian sweep) | 132 (81 / 51) | 13.5 | 3.4 h |
| all three seats (minimax) | 134 (80 / 54) | 13.7 | 3.4 h |
| seats + 4 regret nodes (SB vs BTN excluded) | **162 (88 / 74)** | **16.8** | **4.2 h** |
| seats + all 5 regret nodes | 221 (126 / 95) | 22.8 | 5.7 h |
| equal-24 (requested) | 288 (144 / 144) | 30.0 | 7.5 h |

- **SB vs BTN regret** is the binding constraint for 221. Its isolated → pooled reconstruction ratio is 4.07, so its prediction is unreliable. Its pooled excess is 0.00019, the smallest of the five nodes. At 162 it is predicted at 1.18× equal-24.
- **Paired ±2% sensitivity:** allocation unchanged.
