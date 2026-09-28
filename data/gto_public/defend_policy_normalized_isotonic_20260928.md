# Defense normalized-isotonic shadow

| model | train Brier | holdout Brier | holdout attack MAE | holdout continue MAE |
|---|---:|---:|---:|---:|
| current | 0.09245 | 0.07568 | 0.10051 | 0.14449 |
| global normalized isotonic | 0.07722 | 0.06853 | 0.11324 | 0.15066 |
| defender-specific normalized isotonic | 0.07006 | 0.06394 | 0.10848 | 0.13113 |

Normalized axes: attack uses hand_pct/tp, continue uses hand_pct/tot. Train 10/20/50bb; holdout 15/30/100bb. No production changes.
