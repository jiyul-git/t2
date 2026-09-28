# RFI-only runtime attribution — 2026-09-28

Comparison is direct A/B between:
- baseline tree: `e17be45f0e9a8462c55fd0d0b28a04430c72f465`
- same tree with only the rounded RFI base/depth/ante candidate applied

Regression population: seeds 3000–3005, 30 hands/seed, 180 hands total, 9-max, 150bb start.

## Main correction

The earlier comparison against `tools/baseline_9max_post_f8.json` made the RFI candidate appear to move:
- VPIP 20.7% -> 23.0%
- flop 47.2% -> 56.1%

That was **not** the RFI-only effect. The frozen `current` baseline is at rev `0962cb2`, while the actual pre-candidate tree `e17be45` had already moved.

Direct runtime A/B:

| metric | pre-candidate e17be45 | RFI-only candidate | delta |
|---|---:|---:|---:|
| VPIP count / decision count | 315 / 1379 = 22.84% | 317 / 1380 = 22.97% | +0.13%p |
| PFR count / decision count | 167 / 1379 = 12.11% | 167 / 1380 = 12.10% | ~0 |
| flop reached | 100 / 180 = 55.56% | 101 / 180 = 56.11% | +0.56%p |

Action totals:
- raise: 167 -> 165 (-2)
- all-in: 1 -> 3 (+2)
- call: 155 -> 157 (+2)
- fold: 1273 -> 1271 (-2)

Thus the aggressive-event count is conserved: two raises became all-ins, leaving PFR unchanged. Net VPIP rises only by two voluntary calls/entries.

## Scope of behavioral change

- 12 / 180 hands have any actual preflop-log difference.
- 5 / 180 hands change whether a flop is reached.
- seed 3002 has no actual-action divergence in the 30-hand window despite threshold-value differences.

Representative first actual divergences:
- seed 3000 hand 24: raise -> all-in; no flop in either arm.
- seed 3001 hand 11: fold -> raise, later player raise -> call; candidate reaches flop.
- seed 3003 hand 15: limp/call -> fold; candidate no longer reaches flop.
- seed 3004 hand 25: early raise -> fold, later seat becomes raiser and receives a call; flop status unchanged.
- seed 3005 hand 14: fold -> raise; candidate ends preflop, while baseline limp/check reaches flop. Later hands contain compensating path changes.

## Interpretation

The large VPIP/flop gap previously reported came mainly from comparing against an older frozen baseline, not from the RFI coefficient candidate.

The RFI candidate itself causes a small runtime perturbation in this 150bb 9-max fixture. The fixture is also outside the directly calibrated public-data envelope (8-max, <=100bb), so it should be treated as a side-effect / extrapolation check, not as direct calibration evidence.

No production decision should be made from the stale-baseline delta. Use direct parent-vs-candidate A/B for attribution.
