# 9-max MTT GTO DB priority

Canonical target for T2 is **9-max NLHE tournament play**. 8-max material under `data/gto_public/` is auxiliary cross-validation only and must not define the canonical player-knowledge database.

## Target tournament mechanics

T2's ante phase uses a **1 BB big-blind ante (BBA)**:
- SB posts 0.5 BB.
- BB posts 1 BB live blind.
- BB additionally posts 1 BB dead ante.
- The dead ante goes into the pot and does not reduce the amount other players must call.
- Because the BB alone pays the dead ante, its live stack is one BB shorter than an equal pre-hand stack held by the other seats.

A source/solver row must therefore record whether it is exact BBA, per-player ante, no-ante, or an approximation. Equal-total-pot ante is not silently labeled exact BBA.

## Stack priority

### Tier 1 — common mid-stack tournament play
**20 / 25 / 30 / 40 BB**

Build these first:
1. RFI for all first-in positions.
2. BB vs open — BTN, CO, HJ first, then earlier positions.
3. SB vs open — BTN, CO, HJ first.
4. BTN / CO / HJ vs earlier open.
5. Original opener facing a 3-bet.
6. Blind-vs-blind, including SB limp/raise where supported.
7. Squeeze / cold 3-bet / cold 4-bet.

### Tier 2 — short stack
**8 / 10 / 12 / 15 / 20 BB**

Priority:
1. first-in jam/open decision,
2. call vs shove,
3. non-all-in open vs jam/3-bet where the source/tree supports it,
4. blind-vs-blind.

Licensed push/fold data may seed this tier, but push/fold-only solutions must not be substituted for normal raise trees.

### Tier 3 — deeper common stacks
**50 / 75 / 100 BB**

Same node order as Tier 1. Use exact public 9-max material when redistribution is allowed; otherwise solve and cross-check manually.

### Tier 4 — ultra-deep / review-driven
**150 BB+**

Generate only after Tiers 1–3 or when a live T2 hand requires the spot.

## Source policy

Preferred order:
1. exact 9-max MTT BBA source with redistributable frequencies,
2. exact 9-max MTT source with a clearly documented ante model,
3. our own 9-max solver output with full tree/solver metadata,
4. nearby public reference used only for manual cross-check,
5. 8-max / cash / HU material only as auxiliary evidence.

Do not bulk-extract websites whose terms prohibit scraping or redistribution. Such sources may be used for a small number of manual validation points and must be recorded as external references, not vendored data.

## Current usable sources

### HoldemMath push/fold
- 9-max.
- 4/6/8/10/12/15/20 BB.
- no-ante and 0.1 BB-per-player ante variants.
- first-in shove and call-vs-shove ranges.
- data license: CC BY 4.0.
- multiway solution uses a single-caller approximation.
- no ICM, no rake, no limps.

Use: Tier-2 reference / short-stack knowledge.
Status vs T2 BBA: **near**, not exact.

### Existing 8-max MTT dataset
Use only for:
- source-shape sanity checks,
- hand-frequency methodology,
- 8-vs-9-max sensitivity studies.

It is not the canonical 9-max target.

## Solver output requirements

Every generated spot must store:
- table size = 9,
- positions and action history,
- pre-hand/effective stack convention,
- blind structure,
- ante model,
- action menu and sizes,
- limp availability,
- solve algorithm,
- iteration count,
- convergence/best-response gap,
- continuation/equity abstraction,
- hand-class action frequencies,
- provenance commit,
- quality status: `exact / near / limited / rejected`.

A solver result is never promoted merely because it exists. Compare a small set of aggregate and boundary-hand frequencies against an independent 9-max reference before marking it usable for learned GTO memory.
