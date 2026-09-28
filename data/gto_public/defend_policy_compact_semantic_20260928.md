# Defense compact semantic policy shadow

| model | holdout Brier | holdout attack MAE | holdout continue MAE |
|---|---:|---:|---:|
| current | 0.07568 | 0.10051 | 0.14449 |
| 6bin base | 0.06620 | 0.11718 | 0.13937 |
| 6bin + semantic | 0.06116 | 0.10067 | 0.13937 |
| 8bin base | 0.06614 | 0.11553 | 0.13776 |
| 8bin + semantic | 0.06101 | 0.09999 | 0.13776 |
| 10bin base | 0.06487 | 0.11471 | 0.13474 |
| 10bin + semantic | 0.05993 | 0.09928 | 0.13474 |

Winner: **10bin + semantic**, lambda=1000.0.
No production changes.
