# 9-max MTT solver fill plan

Public search happens before every generated block. Solver output is a gap-filler, not the default source.

## Main mid-stack tree

Target depths, in order:
1. 30bb pilot
2. 40bb
3. 25bb
4. 20bb
5. 50/75/100bb after mid-stack validation

Positions:
`UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN, SB, BB`

For the first main-tree pass:
- EP through BTN open: 2.0bb
- no open limps
- one non-jam 3-bet size per seat class
- jam available
- restricted open+3bet tree for the first validation pass
- no rake / chip EV

Reason: validate the broad RFI and clean single-open defense surface before adding 4bet/squeeze complexity.

## Small blind is separate

Do not validate SB first-in from the no-limp main tree.

Public 9-max MTT references show materially different SB sizing and strategic mixing:
- 20bb primary raise size ~3bb
- 25/30bb ~3.5bb
- 40bb ~4bb
- limp strategy can be first-class at shallow/mid stacks

SB/BvB therefore gets a separate tree with limp enabled and stack-specific sizing after EP–BTN/clean-defense validation.

## T2 BBA mismatch

T2 posts 1BB dead money from the BB only.

Current GTOpen preflop config supports a uniform per-seat ante external to the common live-stack cap. A first approximation uses:
- 1/9bb dead ante per seat
- total dead money = 1bb

This matches the initial pot but not:
- BB-specific 1bb stack reduction,
- exact all-in cap for BB,
- side-pot/excess behavior caused by that one-BB asymmetry.

Generated outputs are therefore `near/limited`, not `exact`, until the solver can model the BBA stack asymmetry or an exact external source is available.

## Promotion gates

For each stack:
1. non-blind RFI aggregate MAE versus an independent public 9-max MTT reference,
2. boundary-hand direction check at EP / CO / BTN,
3. selected BB and SB defense checks from an independent reference,
4. solver convergence metadata present,
5. no restricted-tree result labeled full GTO,
6. all assumptions stored with the row.

If the 30bb pilot fails the aggregate gate, change the solver model/tree before solving other depths.
