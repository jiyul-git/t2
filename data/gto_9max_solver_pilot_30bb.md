# 9-max 30bb solver pilot cross-check

Solver: 9-max, 30bb, no limp, 2.0bb opens (SB 2.5bb), open+3bet cap, all-in available.
Ante approximation: 1/9bb per player, same total dead money as T2's 1bb BBA but not the same stack distribution.

| Position | Solver RFI | External 9-max MTT check | Delta |
|---|---:|---:|---:|
| UTG | 10.609% | 16.500% | -5.89% |
| UTG+1 | 12.151% | 18.600% | -6.45% |
| UTG+2 | 12.634% | 21.700% | -9.07% |
| LJ | 15.481% | 25.700% | -10.22% |
| HJ | 20.145% | 29.900% | -9.75% |
| CO | 26.050% | 37.500% | -11.45% |
| BTN | 35.624% | 48.700% | -13.08% |

Mean absolute aggregate difference: **9.42%**.

External values are a small manual cross-check only, not bulk-vendored source data.
Do not mark this pilot exact GTO: GTOpen uses an approximate preflop continuation model and the ante is only same-total-pot BBA approximation.
