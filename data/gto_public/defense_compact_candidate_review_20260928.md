# Defense compact-candidate cross-review — 2026-09-28

Source experiment branch: `tmp/preflop-policy-shape-20260928@d3c0f4da2571b137865dfaababba0486102ce7b5`.

## What improved

Public-data holdout from the compact semantic experiment:
- current holdout Brier: 0.07568
- 10-bin + semantic holdout Brier: 0.05993
- current attack MAE: 0.10051
- 10-bin + semantic attack MAE: 0.09928

8-max runtime comparison against current `test@1a23123`, seeds 3100–3105, 180 hands:
- test: n=1223, VPIP=368, PFR=190, flop=107
- candidate: n=1224, VPIP=369, PFR=198, flop=103
- delta: VPIP +1 event, PFR +8 events, flop -4 hands
- candidate policy hit 121 times
- five of six seed fingerprints changed.

Same-state replay over those 121 candidate-hit states:
- mean absolute attack delta: 0.05089
- mean absolute call delta: 0.09034
- mean absolute fold delta: 0.05334
- mean attack delta: +0.03566
- mean continue delta: +0.02085
- argmax changes: 16 / 121
- largest directional changes occur especially in BB/SB and some BTN states.

## Semantic rejection example

The compact model is not ready for promotion despite the average fit improvement.

Example from same-state replay:
- BB, 82o vs UTG+1, stack ~77bb
- current: attack 0.000, call 0.1993, fold 0.8007
- compact candidate: attack 0.000, call 0.5537, fold 0.4463

Direct source check in `matthiola0/poker-hand-review`:
- 50bb `EP-vs-BB`: 82o fold 1.0
- 50bb `MP-vs-BB`: 82o fold 1.0
- 100bb `EP-vs-BB`: 82o fold 1.0
- 100bb `MP-vs-BB`: 82o fold 1.0

So the compact binning can improve aggregate/holdout loss while smoothing semantically distinct hand classes together.

## Better next direction

The same experiment branch already measured defender-specific hand residuals:
- holdout Brier: 0.05854
- holdout attack MAE: 0.08668
- 70% of top-50 attack residual hands keep the same residual sign across 10/20/50bb.

This is a stronger next candidate than promoting the pure 10-bin semantic model.

Recommended next experiment:
1. retain the compact semantic base for broad policy shape;
2. add shrinkage-controlled defender-specific hand residual correction;
3. enforce direct-source guards on obvious pure-fold / pure-continue hand classes;
4. evaluate on held-out stacks and identical runtime states;
5. only then consider promotion to `test`.

No production change is recommended from the compact candidate as currently implemented.
