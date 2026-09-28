# Defense attack semantic-feature shadow

| model | lambda | train Brier | holdout Brier | holdout attack MAE |
|---|---:|---:|---:|---:|
| defender-isotonic base | - | 0.07006 | 0.06394 | 0.10848 |
| semantic | 1000.0 | 0.06367 | 0.05908 | 0.09651 |
| extended | 1000.0 | 0.06328 | 0.05890 | 0.09514 |

Top coefficients are stored in the JSON. Features are semantic hand properties, not 169 hand IDs. No production changes.
