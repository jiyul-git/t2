# 9-max GTO research/source registry

This file is **research/legal inventory only**. Runtime GTO rows do not carry source/provider/chart provenance.

| Material | 9-max | Stack coverage | Ante | Runtime use |
|---|---:|---|---|---|
| HoldemMath push/fold | yes | 4/6/8/10/12/15/20 BB | none + 0.1 BB/player | flattened to per-hand shove/call rows |
| Jens Baagaard MTT tables | yes | 5/10/20/40/100 BB | upstream assumptions | 269 action tables/stack, normalized to 169 hands |
| RangeMyHand push/fold | yes | 1–25 BB | none | 125 9-max spots, normalized to 169 hands |
| PreflopRanges public viewer | yes | 10/15/20/25/30/40 BB | viewer-specific | manual cross-check only |
| GTO Academy / commercial libraries | yes | broad | product-specific | cross-check/index only |
| T2/GTOpen solver | configurable | configurable | **exact uniform_total supported** | canonical gap filling after validation |
| Matthiola | 8-max | broad | source-specific | auxiliary only |
| haowenzheng-art poker-gto-trainer | nominal 9-max | deep | unclear | rejected; sampled JSON is `solver:fallback`, `accuracy:0.0` |

## T2 target

Canonical ante mechanics are **uniform_total_1bb**:
- N is the number dealt in at hand start;
- every seat posts `1/N BB`;
- total ante is 1 BB;
- folds do not change N or redistribute the ante.

For 9-max, the exact target is **1/9 BB/player**.

GTOpen now represents folded-seat antes in continuation subgames through `dead_money`, so new T2 solves can match these mechanics exactly.

## Retrieval / solve rule

1. Use already normalized 9-max rows when the mechanical state matches.
2. Search for additional open exact values.
3. If the exact state is missing, solve it with the current exact T2 mechanical config.
4. Keep convergence/model diagnostics outside runtime rows.
5. Admit frequencies only after validation; never promote heuristic/fallback charts as canonical values.

## Correct current inventory

- Jens: **269 action tables/stack × 5 = 1,345 tables**, **227,305 rows**.
- RangeMyHand 9-max only: **125 spots**, **21,125 rows**.
- HoldemMath flattened: **616 spots**, **104,104 rows**.
- Operational total: **352,534 rows**.

There is no admitted exact 25/30 BB full-tree corpus yet.
