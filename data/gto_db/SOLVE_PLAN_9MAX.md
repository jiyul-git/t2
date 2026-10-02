# 9-max MTT solver fill plan

Public/open data is collected first. Solver output fills the remaining canonical gaps.

## Main mid-stack order

1. **30 BB exact-uniform-ante pilot**
2. **25 BB**
3. 40 BB
4. 20 BB
5. 50 / 75 / 100 BB after mid-stack validation

Positions:
`UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN, SB, BB`

First validation pass:
- EP through BTN open: 2.0 BB
- no open limps outside the dedicated SB/BvB tree
- one non-jam 3-bet size per seat class
- jam available
- no rake / ChipEV
- expand to 4-bet/squeeze/cold branches only after the initial surface passes

## Exact T2 ante mechanics

The canonical ante is **uniform_total_1bb**, not BBA.

For `N = hand_start_players`, every dealt-in player posts `1/N BB`; total ante is exactly 1 BB and folds do not re-split it.

The GTO side now supports this exactly:
- full-hand configs use the per-seat `1/N` ante;
- continuation subgames keep already-folded antes as `dead_money`;
- `hand_start_players` remains part of the state even after folds;
- the 5–9 player reference/tree verifier passes.

For a 9-max 30 BB hand:
- per-player ante = **1/9 BB**;
- stack after ante before blinds = **30 - 1/9 = 29.88888888888889 BB**;
- total starting pot after SB/BB = **2.5 BB**.

Do not downgrade a new solve merely for an ante mismatch if it uses this exact configuration.

## Old 30 BB pilot

The earlier 30 BB pilot is **not promotable**:
- its ensemble file is `promotion_ready: false`;
- only 2 of 8 planned runs were received;
- the original public-RFI comparison had mean absolute aggregate difference **9.42 percentage points**.

It may be retained as experiment history, but its frequencies must not enter the canonical DB. The new 30 BB run starts from the exact uniform-total-ante configuration and current solver implementation.

## Small blind / BvB

SB first-in is separate from the no-limp EP–BTN validation surface.

Use a dedicated BvB tree with limp enabled and stack-appropriate raise sizing. Do not infer SB strategy from the no-limp main tree.

## Promotion gates

For each stack:
1. exact T2 mechanical state verified;
2. convergence metadata present and registered threshold passed;
3. non-blind RFI aggregate cross-check;
4. boundary-hand direction checks at EP / CO / BTN;
5. selected BB and SB defense checks;
6. no restricted-tree result labeled full-tree GTO;
7. no interpolation stored as exact.

Only after those gates pass are the 169-class action frequencies materialized into the operational DB.
