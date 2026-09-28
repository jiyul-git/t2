# Defense nested-policy shadow

- current train Brier: 0.09245
- current holdout Brier: 0.07568
- winner use_hot: False
- winner params: {"attack_floor": 0.003, "attack_rel_tp": 0.5, "continue_floor": 0.04, "continue_rel_gap": 0.4}
- winner train Brier: 0.09373
- winner holdout Brier: 0.08290
- winner holdout attack MAE: 0.12243
- winner holdout continue MAE: 0.16034

Train stacks: 10/20/50bb. Holdout stacks: 15/30/100bb. No production code changed.
