# Public 8-max MTT vs-open width audit

- charts: 60
- baseline defend MAE: 0.0502
- candidate defend MAE: 0.0480
- baseline 3bet MAE: 0.0331
- candidate 3bet MAE: 0.0347
- holdout fitted defend MAE: 0.0426
- holdout fitted 3bet MAE: 0.0353

Primary sizing assumption: 2.5bb open, SB 3bb. Source does not encode exact sizing, so treat as near/reference rather than exact.

| node | target defend | base | candidate | target 3bet | base 3bet | cand 3bet |
|---|---:|---:|---:|---:|---:|---:|
| EP-vs-MP | 0.162 | 0.160 | 0.162 | 0.089 | 0.088 | 0.089 |
| EP-vs-BTN | 0.200 | 0.208 | 0.211 | 0.091 | 0.104 | 0.105 |
| EP-vs-SB | 0.229 | 0.244 | 0.248 | 0.113 | 0.159 | 0.161 |
| EP-vs-BB | 0.719 | 0.698 | 0.708 | 0.093 | 0.137 | 0.139 |
| MP-vs-BTN | 0.232 | 0.219 | 0.221 | 0.124 | 0.109 | 0.110 |
| MP-vs-SB | 0.263 | 0.257 | 0.260 | 0.170 | 0.167 | 0.169 |
| MP-vs-BB | 0.745 | 0.734 | 0.743 | 0.144 | 0.144 | 0.145 |
| BTN-vs-SB | 0.292 | 0.276 | 0.278 | 0.226 | 0.180 | 0.181 |
| BTN-vs-BB | 0.782 | 0.788 | 0.794 | 0.183 | 0.154 | 0.155 |
| SB-vs-BB | 0.724 | 0.724 | 0.724 | 0.162 | 0.142 | 0.142 |
