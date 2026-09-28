# POST_RANGE RFI source audit — 2026-09-28

Neutral GTO baseline only: production POST_RANGE hard-cutoff representation is compared with public 8-max MTT hand-frequency charts. SB is excluded. For board metrics, the public BB call range is held fixed so only the opener-RFI range changes.

## Aggregate

| metric | old e17be45 | new ca418d2 | delta |
|---|---:|---:|---:|
| RFI Brier | 0.06202 | 0.05477 | -0.00725 |
| mean abs open-rate error | 0.03515 | 0.00986 | -0.02528 |
| conditional range TV | 0.18665 | 0.12675 | -0.05990 |
| board range_adv MAE | 0.10294 | 0.09448 | -0.00846 |
| board nut_adv MAE | 0.05714 | 0.04192 | -0.01522 |
| range_adv sign flips vs source | 4 | 5 | +1 |
| nut_adv sign flips vs source | 5 | 6 | +1 |

## Pair spots

| stack | source node | opener | Δ range_adv MAE | Δ nut_adv MAE | old TV | new TV |
|---:|---|---|---:|---:|---:|---:|
| 10 | BTN-vs-BB | BTN | +0.0020 | +0.0016 | 0.0739 | 0.0940 |
| 10 | EP-vs-BB | LJ | +0.0089 | -0.0138 | 0.1975 | 0.1708 |
| 10 | MP-vs-BB | CO | +0.0119 | -0.0319 | 0.2024 | 0.1451 |
| 15 | BTN-vs-BB | BTN | -0.0284 | -0.0016 | 0.1528 | 0.0823 |
| 15 | EP-vs-BB | LJ | +0.0189 | -0.0057 | 0.1934 | 0.1487 |
| 15 | MP-vs-BB | CO | -0.0091 | +0.0003 | 0.1281 | 0.1181 |
| 20 | BTN-vs-BB | BTN | -0.0062 | -0.0080 | 0.1716 | 0.0834 |
| 20 | EP-vs-BB | LJ | -0.0091 | -0.0353 | 0.2247 | 0.1023 |
| 20 | MP-vs-BB | CO | +0.0029 | +0.0076 | 0.0820 | 0.0863 |
| 30 | BTN-vs-BB | BTN | -0.0034 | -0.0015 | 0.0850 | 0.0628 |
| 30 | EP-vs-BB | LJ | -0.0019 | -0.0339 | 0.2370 | 0.0897 |
| 30 | MP-vs-BB | CO | -0.0130 | -0.0162 | 0.1584 | 0.0715 |
| 50 | BTN-vs-BB | BTN | -0.0024 | -0.0173 | 0.1536 | 0.0810 |
| 50 | EP-vs-BB | LJ | -0.0308 | -0.0312 | 0.1898 | 0.0924 |
| 50 | MP-vs-BB | CO | -0.0270 | -0.0230 | 0.1711 | 0.0907 |
| 100 | BTN-vs-BB | BTN | -0.0076 | -0.0254 | 0.2428 | 0.0866 |
| 100 | EP-vs-BB | LJ | -0.0452 | -0.0201 | 0.2862 | 0.0991 |
| 100 | MP-vs-BB | CO | -0.0129 | -0.0186 | 0.2534 | 0.1176 |

Negative delta is improvement. This audit does not validate persona deviations or the defense model; it isolates the RFI/open-range component that POST_RANGE consumes.
