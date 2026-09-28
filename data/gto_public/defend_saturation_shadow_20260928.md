# Defense saturation shadow audit

| mode | Brier | continue MAE | attack MAE |
|---|---:|---:|---:|
| current | 0.09996 | 0.1235 | 0.0432 |
| identity_clamp95 | 0.08407 | 0.0750 | 0.0455 |
| cap80_only | 0.08407 | 0.0753 | 0.0455 |
| overflow_soft | 0.08407 | 0.0751 | 0.0455 |

No production behavior changed by this audit.
