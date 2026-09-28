# Defense attack hand-residual shadow

| model | shrink | train Brier | holdout Brier | holdout attack MAE |
|---|---:|---:|---:|---:|
| none | 0.00 | 0.07006 | 0.06394 | 0.10848 |
| global | 1.00 | 0.06297 | 0.05916 | 0.09172 |
| defender | 1.00 | 0.06169 | 0.05854 | 0.08668 |

- same-sign residual across 10/20/50bb among top-50 residual hands: 70.0%

No production behavior changed.
