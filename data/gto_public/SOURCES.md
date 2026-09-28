# Public GTO data sources

## Vendored / normalized

### matthiola0/poker-hand-review
- Commit: `9ef33a4d70b48c4ec8aea6093562e38ef46feb24`
- License: MIT
- Data: 8-max MTT preflop charts, 202 nodes, 34,138 hand-node rows after normalization.
- Stacks: 3, 5, 8, 10, 12, 15, 17, 20, 22, 26, 30, 35, 40, 50, 70, 100bb.
- Local file: `8max_mtt_matthiola.jsonl`

### amaster97/poker_solver
- Commit: `f78f1b2bc338dd8cbb5226ecb8398bbdb3635676`
- License: MIT
- Data: 27 precomputed HUNL preflop blueprint shards.
- Stacks: 20, 30, 40, 60, 80, 100, 150, 175, 200bb.
- Antes: 0, 0.5, 1.0bb.
- 169 hand classes, 25,000 DCFR iterations per cell.
- Local directory: `amaster_hu_blueprints/`
- Use only as auxiliary stack-depth / deep-stack reference because the game is heads-up.

## Indexed only, not copied

### mpcaren/preflop-range-trainer
- Commit: `6606aefc2f6b7fcb6ffff8b1d772c142102113b1`
- Repository has no detected license.
- Contains 100bb 8-max RFI / facing-open / facing-3bet / facing-4bet frequency text files.
- We keep only the path index in `mpcaren_100bb_8max.reference.json` and do not redistribute the source files.
