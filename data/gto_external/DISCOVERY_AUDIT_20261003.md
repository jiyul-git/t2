# 9-max MTT external GTO discovery audit — 2026-10-03

## Goal

Collect external **scenario × position × stack × 169-hand** preflop action-frequency / EV evidence for T2 without filling gaps with hand-authored or extrapolated pseudo-GTO. Canonical target remains **9-max NLHE MTT, 1 BB big-blind ante (BBA)**.

## Already imported and redistributable

### jensbaagaard/poker-practice
- 9-max MTT raw source, MIT.
- Nominal stack packs: **5 / 10 / 20 / 40 / 100 BB**.
- Each stack file has **271 top-level keys**, of which **269 are action tables** and 2 are utility ranges (`EmptyRange`, `WideRange`). Across 5 stacks this is **1,345 action tables**.
- Operational normalization expands every action table to the full **169 hand classes** (missing sparse entries are explicit 0.0), giving **227,305 hand-frequency rows**.
- Local locator:
  - branch: `chatgpt/gto-external-harvest-20261003`
  - raw: `data/gto_external/jensbaagaard_9max_mtt/MTT_*_GTO.json`
  - normalized/UI charts: `data/gto_external/jensbaagaard_9max_mtt/charts/MTT_*_GTO.charts.json`
  - index: `data/gto_external/jensbaagaard_9max_mtt/charts/INDEX_9MAX.json`
- **No 30 BB pack exists in this source.** 20/40 BB may be used for stack-sensitivity cross-checking, but not as an exact 30 BB hand-level reference.
- Families include RFI, limp, call-vs-open, 3bet, call-vs-3bet, 4bet, call-vs-4bet, 5bet, call-vs-5bet.
- Keep its original assumptions; do not silently reinterpret it as arbitrary asymmetric stacks or exact T2 BBA.

### RangeMyHand push/fold
- 9-max + 6-max, **1–25 BB**, CC BY 4.0.
- The raw file has **225 spots across 6-max + 9-max**. The **9-max subset is 125 seat×stack spots** (25 stack depths × 5 opening seats), giving **21,125 hand-frequency rows**.
- Chip-EV Nash, no ante, shove-or-fold abstraction.

## Newly found high-value crosschecks

### PreFlop Camp
Status: **crosscheck only; do not bulk vendor**.

Useful target-aligned nodes:
- 9-max jam/fold: **4 / 5 / 6 / 7 / 8 / 10 / 12 / 15 / 20 BB**.
- 9-max BB call-off vs jam: **10 / 15 / 20 BB**.
- 9-max reshove / 3-bet jam: **15 / 20 / 25 BB with BB ante**.
- Publishes per-hand EV and measured exploitability for its solved Nash families.

Important model limits:
- Simplified no-overcall / class-level model.
- Not table-exact.
- The site's ordinary MTT open/defense ranges are curated approximations, not solver-exact.
- Reshove assumes the opener uses the site's reference open range; at 20 BB the 25 BB reference range stands in.

Rights:
- Terms of Use prohibit redistributing the app's generated data as your own.
- Therefore store source metadata and small validation checkpoints only, not 169×node copies.

Sources:
- https://pre-flop.ai-speeds.com/
- https://pre-flop.ai-speeds.com/privacy.html

### Daily Poker Spot push/fold
Status: **crosscheck only until redistribution permission is established**.

Coverage:
- 9-max / 6-max.
- **3 / 4 / 5 / 6 / 7 / 8 / 9 / 10 / 12 / 15 BB**.
- Ante selectors include **1 BB BBA**.
- Chip-EV Nash open-shove, equal stacks, folded to hero.

Limits:
- First-in shove only.
- No prior limpers/raises.
- No ICM / bounty / satellite.

Source:
- https://www.dailypokerspot.com/tools/push-fold-charts

### PreflopRanges.app
Status: **manual/public crosscheck only**.

Coverage visibly includes 9-max MTT:
- stack depths **10 / 15 / 20 / 25 / 30 / 40 BB**
- RFI, 3bet, squeeze, cold 4bet and response nodes
- per-hand mixed frequencies in the viewer.

Do not systematically extract or redistribute the full corpus; retain only small published aggregate checks.

Source:
- https://preflopranges.app/

### PokerData
Status: **provider/API crosscheck; currently not a 9-max MTT import source**.

Current documented tournament REST API:
- **8-max NLHE MTT**
- **1 BB BBA**
- **10 / 15 / 20 / 30 / 40 / 50 / 75 / 100 / 200 / 300 BB**
- 169-class mixed frequencies, chip-EV
- action-path range/node/spots endpoints.

Do not substitute this 8-max tree for 9-max truth. The provider has 9-max material elsewhere, but no documented `nlmtt9` endpoint was verified in this audit.

Source:
- https://pokerdata.io/api

## Rejected as canonical GTO truth

### b5501123/MttDoc
Reject. Files that look attractive (9-max BBA 25/30/40 BB RFI/BB-defend/rejam) are generated from hand-written training baselines. Project docs explicitly describe them as a baseline rather than solver-precise GTO.

### jayj1990/gto-today
Reject for 9-max canonical use. The 9-max decision tree is derived from a solver-backed 6-max tree by seat mapping, with heuristic depth adjustments at shallower stacks.

### ho0527/pokertrace
Reject. Its deep RFI generator explicitly labels the output as teaching-reference extrapolation rather than solver-precise values.

### badtreebear/felt
Keep only as auxiliary unverified reference. It has useful 9-max 100 BB RFI / vs-RFI / vs-3bet categories, but not precise mixed frequencies and the underlying chart provenance is insufficiently established for promotion.

### Braininhood/Portfolio Poker AI
Useful solver implementation reference, not target data. Its default preflop abstraction is 100 BB, ante=0, 2.5 BB raise and max_raises=1; that is not T2's 1 BB-BBA MTT target.

### zwarag/gto-open
Watch only. The repository currently describes a planned open GTO database, but no solved v0 preflop corpus was found.

## Discovery/search rule

Before writing "no hand-level reference exists", search both the operational DB and harvested external-data branches. Current provenance-free operational materialization contains **248,430 9-max rows**: 227,305 full-tree-family rows plus 21,125 1–25 BB open-shove rows.

For 30 BB, distinguish:
- **hand-level reference exists in neighboring stacks**: yes, 20/40 BB in the Jens pack;
- **exact 30 BB hand-level pack from that source**: no;
- **exact 30 BB public-viewer crosscheck**: potentially available in non-vendored sources such as PreflopRanges.app, subject to the existing no-bulk-extraction rule.

## Remaining canonical gaps

Highest-priority missing **redistributable, exact-or-near-exact 9-max 1 BB-BBA** evidence:

1. **25 BB full tree** — RFI, BB/SB vs open, non-blind vs open, opener vs 3bet, squeeze/cold-3bet/cold-4bet, BvB.
2. **30 BB full tree** — same families.
3. **50 BB** — same families.
4. **Asymmetric effective stacks** rather than one symmetric stack bucket.
5. **SB limp / limp-reraise trees** at tournament depths.
6. Per-hand **EV as well as action frequency** at non-push/fold nodes.
7. 4bet+ branches under the exact BBA configuration.

## Data-quality rule going forward

A source may look like GTO because it has a 13×13 grid. That is not enough. Before promoting data to canonical T2 knowledge, record:
- player count
- exact ante/blind structure
- nominal/effective stack definition
- action sizes
- solver/model and convergence evidence
- whether frequencies are solved or hand-authored/extrapolated
- whether the node is a full tree or a reduced shove/fold abstraction

Source/licensing notes may remain in separate research/legal files when required, but they are **not fields in the operational frequency rows or runtime lookup key**. Anything with unresolved model assumptions stays **crosscheck / auxiliary / rejected**, never silently merged into truth.
