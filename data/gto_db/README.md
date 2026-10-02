# T2 GTO Knowledge Database

This directory is T2's operational **9-max MTT strategy-value layer**.

Runtime rows answer: **for this poker state and hand class, what action frequency/value do we have?** They do not carry provider/source/chart provenance. Legal/license files and research audit material remain separate.

## Canonical tournament state

T2 uses `uniform_total_1bb`:
- `N = hand_start_players`;
- each dealt-in seat posts `1/N BB`;
- total ante = **1 BB**;
- folds do not re-split the ante;
- SB/BB live blinds are 0.5/1.0 BB in addition to the ante.

For 9-max, every seat posts **1/9 BB** ante.

## Current operational inventory

Master index: `index_9max_operational_v1.json`

### Full-tree-family external rows
`preflop_9max_fulltree_external_v1.jsonl`
- stacks: **5 / 10 / 20 / 40 / 100 BB**
- **269 action tables per stack**
- **1,345 action tables total**
- 169 hand classes per table
- **227,305 rows**
- families include open, limp, call-vs-open, 3bet, call-vs-3bet, 4bet, call-vs-4bet, 5bet, call-vs-5bet

### 1–25 BB first-in shove rows
`preflop_9max_pushfold_1to25_v1.jsonl`
- 9-max subset only
- 25 stack depths × 5 opening seats = **125 spots**
- **21,125 rows**
- no-ante shove/fold abstraction

### HoldemMath shove/call rows
`preflop_9max_pushfold_holdemmath_flat_v1.jsonl`
- 4/6/8/10/12/15/20 BB
- 616 spots × 169 hands
- **104,104 rows**
- first-in shove and call-vs-shove
- no-ante and 0.1 BB/player variants

### Total
**352,534 normalized 9-max hand-frequency rows.**

All three operational datasets are validated with:
- `table_players = 9`
- `format = MTT`
- `value_status = exact`
- frequency within [0,1]
- no runtime source/provider/chart/provenance fields

## Current canonical gaps

There is still no admitted **25 BB or 30 BB exact T2 full raise tree**.

The prior 30 BB solver pilot is experiment history only and is not promotion-ready. New 25/30 BB solves must use the exact `uniform_total_1bb` mechanics and pass the registered convergence/cross-check gates before their rows are added here.

## Matching rule

Match on actual poker state: hand-start player count, stack convention, ante/blinds, positions, complete action history/sizes, action and hand class.

Never silently:
- substitute 8-max for 9-max;
- substitute no-ante/per-player-0.1 data for exact T2 uniform-total mechanics;
- interpolate a missing stack/action node and call it exact;
- route a hand-frequency lookup through a chart representation.
