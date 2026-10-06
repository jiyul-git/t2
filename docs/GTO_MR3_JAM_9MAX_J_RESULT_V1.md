# 9-max 30bb plan J (max_raises 3, 4-bet = jam only) — result v1

Pre-registration: `GTO_MAX_RAISES_AUDIT_9MAX_V1.md` section 5 (bcef3e0). Gate A (action-line re-key) passed exactly (01bbb58).
J = 100 iterations, same seeds, same 33 tables re-keyed by line. Data: `data/gto_validation/pilot9/step3/j_compare.json`,
`j_coverage.json`; J exports + whole-tree dump under `/home/user/gto_ckpt/step3/j/`.

## Tooling added on the way (all gated exact)
- Multi-path export mode (one load + one gaps_and_evs): 5 exports bit-identical to the single-path T exports (3dfd5b9).
- Whole-tree dump (`t2_tree_dump`, one average-strategy traversal per seat): strategies and action EVs identical (difference 0) to
  t2_action_values on 144 T path nodes and to 279 J path nodes; J tree 16,958 nodes in 12 min vs ~5 min per path export.
- Coverage from the dump + a 0-iteration census structure: reproduces the T census to 4 decimals (the full census on the mr3 tree did
  not finish in 1 h 50 min).

## Pre-registered comparison (M4, 166 shared elements)
- D4 = max |M4(J) - M4(T2)| = 19.3 pp (n51 SB 3-bettor call 28.6 -> 47.9%) > R = 4.33 pp; 38 elements above R.
  Decision rule: missing 4-bet is a structural effect larger than the last HU outer-loop change.
- RFI T2 -> J: UTG 11.1 -> 15.3, UTG+1 13.6 -> 17.5, UTG+2 16.3 -> 20.3, LJ 18.2 -> 22.1, HJ 22.4 -> 26.7, CO 29.1 -> 32.7,
  BTN 50.2 -> 45.3, SB 68.9 -> 75.3.
- 3-bettors raise (non-jam 3-bet) roughly half as often (e.g. BTN vs CO 22.9 -> 10.4%) and cold-call more (SB vs BTN 28.6 -> 47.9%).
- New action: openers 4-bet jam 0-6.1% of their range (mostly premium classes, 0-7 classes > 50%); 3-bettors fold 16-48% to the jam.
  Openers still fold only 0-20% to 3-bets.
- gap_total 0.042 bb at 100 iterations (T: 0.012): the larger tree is less converged at the same iteration count.

## Coverage at J (shares of flop reach 0.735)
| | T | J |
|---|---|---|
| HU SRP | 24.0% | 23.3% |
| HU 3-bet | 31.9% | 24.1% |
| 3-way+ SRP | 27.2% | **52.0%** |
| 3-way+ 3-bet | 16.9% | 0.6% |
| solved (33 tables) | 50.5% | 46.8% |

## Reading and decision
- J is adopted as the 30 bb tree (G1): the 4-bet changes the 3-bet / flat structure far beyond the outer-loop residual and is played.
- The tables are stale at J (computed at state-2 / T ranges; 3-bet ranges narrowed sharply), which is the likely reason openers still
  almost never fold to 3-bets. A J-tree outer step is needed before any J frequency is used.
- With fewer 3-bets the flatting lines grew, and they end in static multiway pots (pure showdown equity, no realization, no position):
  the same over-valuation of passive continues that the HU work removed now sits in the multiway model, at 52% of flop reach.
- Consequence for the verified standard (G4): spots whose continuation is heads-up (single open folded to the BB, BB vs SB, opener vs
  3-bet after the others fold) can be verified with HU methods; spots upstream of flats (RFI, SB / cold-call decisions) stay
  `static_dependent` until multiway continuation values exist.
- Next (efficiency): an exact heads-up spot solver (two-player zero-sum subgame from a node with the arriving ranges, solved
  continuation tables, exact all-ins) with measured exploitability — it verifies the HU-continuation spot families, serves as G6(a),
  and is the extractor's fast on-demand fallback.
