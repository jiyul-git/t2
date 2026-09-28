# POST_RANGE soft-boundary shadow — 2026-09-28

Production unchanged. A single global logistic boundary width is fitted on training stacks while preserving each chart's current calibrated aggregate RFI rate exactly.

## Result

- selected tau: **0.0400**
- train Brier: hard 0.05623 -> soft 0.03848
- holdout Brier: hard 0.04844 -> soft 0.03279
- holdout conditional TV: hard 0.11427 -> soft 0.14469
- holdout board range_adv MAE: hard 0.09215 -> soft 0.06849
- holdout board nut_adv MAE: hard 0.04138 -> soft 0.03398
- range_adv sign flips: hard 2 -> soft 1
- nut_adv sign flips: hard 3 -> soft 0

Holdout stacks are 15/30/100bb; pair metrics use the public BB call range unchanged, isolating opener POST_RANGE representation.
