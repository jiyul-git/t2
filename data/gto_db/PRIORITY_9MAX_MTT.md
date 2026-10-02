# 9-max MTT GTO DB priority

Canonical target for T2 is **9-max NLHE tournament play**. 8-max material is auxiliary validation only and must not define the 9-max knowledge DB.

## Target tournament mechanics

T2's canonical ante model is **uniform_total_1bb**.

For a hand that starts with `N = hand_start_players`:
- every dealt-in player posts exactly `1/N BB` dead ante;
- total ante is exactly **1 BB**;
- SB additionally posts **0.5 BB** live;
- BB additionally posts **1.0 BB** live;
- folds do **not** re-split or recalculate the ante;
- the initial pot is therefore **2.5 BB** whenever all N players can post in full.

For 9-max this is **1/9 BB per player**. A hand-start stack `S` becomes `S - 1/9` after the ante before live blinds; SB and BB then post their live blinds on top.

A reference row must preserve the mechanical condition that affects strategy: hand-start player count, stack convention, ante model, blinds, action history and sizes. Operational rows do **not** carry provider/source/chart provenance.

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
3. non-all-in open vs jam/3-bet,
4. blind-vs-blind.

Push/fold-only solutions must never substitute for a normal raise tree.

### Tier 3 — deeper common stacks
**50 / 75 / 100 BB**

Same node order as Tier 1.

### Tier 4 — ultra-deep / review-driven
**150 BB+**

Generate only after Tiers 1–3 or when a live T2 hand requires the spot.

## Data priority

Preferred order:
1. exact 9-max MTT `uniform_total_1bb` data with matching stack/action tree;
2. exact 9-max MTT data with a documented different ante model;
3. our own 9-max solver output using the exact T2 ante mechanics and a validated tree;
4. nearby 9-max reference used only for cross-checking;
5. 8-max / cash / HU evidence only as auxiliary evidence.

The runtime DB stores strategy values, not provenance. Legal/license material and research notes stay outside the runtime row schema.

## Current short-stack material

### HoldemMath push/fold
- 9-max.
- 4/6/8/10/12/15/20 BB.
- no-ante and 0.1 BB-per-player variants.
- first-in shove and call-vs-shove ranges.
- multiway solution uses a single-caller approximation.
- no ICM, no rake, no limps.

At 9-max, the 0.1 BB/player variant contributes **0.9 BB total ante**, so it is close to but not identical to T2's **1.0 BB total / 1/9 BB per player** target.

## Solver promotion requirements

Operational frequency rows contain the poker state, action, hand, frequency and exact/derived status. Solver diagnostics live in separate solve artifacts.

Before a generated block is admitted as canonical:
- table size and `hand_start_players` must match;
- `uniform_total_1bb` must be represented exactly;
- stack convention, blinds and action sizes must match;
- convergence/best-response diagnostics must pass the registered gate;
- restricted-tree output must not be labeled full-tree GTO;
- aggregate and boundary-hand behavior must be checked against independent 9-max evidence.

A solver result is never promoted merely because it exists.
