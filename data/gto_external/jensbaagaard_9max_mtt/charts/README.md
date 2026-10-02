# Generated chart packs

Source: jensbaagaard/poker-practice @ 449993f78d995c77b72d0bcac418a8507dd6f783
Generator: scripts/build-ranges.mjs
License: MIT

These are the upstream UI-ready chart arrays generated from the raw MTT GTO tables.
They preserve scenario, stack, hero/villain seat, and mixed-frequency range notation.
Use only entries applicable to 9-max when building T2's 9-max reference layer.

Stacks: 5 / 10 / 20 / 40 / 100bb.
Scenarios include open, vs raise, vs 3bet, vs 4bet, and vs 5bet where the source tree contains the node.


## T2 inventory / lookup note

This directory is the redistributable **9-max MTT hand-level frequency reference** collected for T2.

- stack packs: **5 / 10 / 20 / 40 / 100bb**
- scenario tables: **271 per stack**
- total scenario tables: **1,355**
- hand granularity: **169 classes per table**
- frequencies: mixed action frequencies from the upstream generated chart data

Useful files:
- `INDEX_9MAX.json` — inventory/index
- `MTT_20_GTO.charts.json` and `MTT_40_GTO.charts.json` — neighboring-stack references for current 30bb solver validation

There is **no exact 30bb file in this pack**. Do not interpolate 20bb and 40bb and label the result as source truth. If an exact 30bb comparison is required, first search the other harvested/public crosscheck sources and preserve their redistribution restrictions.

When another workstream needs these files, record both the branch and path. Searching only `chatgpt/gto-reference-20260928` will miss this dataset.
