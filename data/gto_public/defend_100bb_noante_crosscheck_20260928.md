# Defense 100bb no-ante cross-check

MTT-derived fitted coefficients are evaluated against a separate public 100bb no-rake GTO Wizard extraction. Source files are queried only, not vendored.

- supported spots: 22
- baseline defend MAE: 0.0550
- fitted defend MAE: 0.1569
- baseline 3bet MAE: 0.0278
- fitted 3bet MAE: 0.0612

Only CO/BTN/SB/BB defenders are included in the fitted-coefficient score because those are the positions supported by the MTT direct-defense source.
