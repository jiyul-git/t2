# 9-max 30bb continuation-model pilot (Option S) — result v1

States (100 iterations each, same config / seeds / tree): **O** original dynamic static payoff; **F** C1b static payoff frozen as
tables at nodes 24 / 73 / 242 / 24726 (BTN / CO / HJ / UTG open -> BB call); **S** C3 solved continuation tables (panel_v1, 24 boards,
outer step 1 at O's endpoint ranges) at the same nodes. Every other terminal keeps the static payoff in all three states.
Data: `data/gto_validation/pilot9/` (c1/c1a_identity.json, c2/, s_analysis.json). Numbers are near-reference comparisons, not errors
against exact GTO.

## Integrity
- C1a: injection reproduces the static payoff bit for bit at the fixed 100-iteration profile (4 nodes + control path).
- C2: 96/96 flops converged (max exploitability 0.293-0.299% pot). Solved minus static gross, class mean: opener +0.70 to +0.78 bb,
  BB +0.03 (BTN node) to -0.24 bb (UTG node) — the static payoff undervalued the opener and overvalued the BB caller.
- F - O (table freezing): RFI within +-0.08 pp, terminal reach within 1%, BB responses within 0.15 pp except BB vs UTG (fold -1.1 pp).

## Main estimate S - F (per node; all expected directions hold)
| opener node | opener RFI | opener jam share of opens | BB fold | BB call | BB 3-bet |
|---|---|---|---|---|---|
| BTN (24) | 36.5 -> 42.9% (+6.4 pp) | 17.3 -> 0.1% | 0.0 -> 12.0% | 80.6 -> 60.1% | 9.6 -> 18.6% |
| CO (73) | 26.9 -> 30.8% (+3.9 pp) | 6.0 -> 0.1% | 0.0 -> 17.6% | 86.2 -> 66.5% | 8.0 -> 10.5% |
| HJ (242) | 21.9 -> 24.3% (+2.4 pp) | 0.3 -> 0.0% | 0.0 -> 23.3% | 88.1 -> 63.0% | 8.6 -> 9.2% |
| UTG (24726) | 11.4 -> 13.4% (+2.0 pp) | 0.1 -> 0.0% | 1.2 -> 40.5% | 93.7 -> 54.5% | 3.3 -> 5.0% |
(values shown O -> S; F is within 0.1 pp of O except the BB-vs-UTG fold noted above)

- Specificity: positions and lines whose terminals were not replaced did not move (UTG+1 / UTG+2 / LJ RFI +-0.04 pp; control path
  UTG+1 -> BB: BB fold +0.06 pp).
- Playability / jam structure (opener node, F -> S frequencies fold / raise / jam): BTN 98s 0 / 0 / 1.00 -> 0 / 0.99 / 0.01, BTN 22
  0 / 0.26 / 0.74 -> 0 / 1.00 / 0, BTN KQo and AKo jam -> raise, CO 98s fold 0.96 -> raise 0.999, HJ 98s fold 1.00 -> raise 0.999,
  HJ 22 fold 0.24 -> raise; UTG K9s fold 1.00 -> raise 0.51; UTG A5s / 98s / 22 still fold.
- SB responses moved little (the SB still flats 15-52% of opens; its 3-way terminals stay static); BTN cold-calling stays ~0.

## Reading
- The mechanism is confirmed in 9-max: replacing the static flop-terminal value at four HU SRP terminals makes the BB fold, removes the
  opener's jam dependence, turns playability hands from fold / jam into raises, and loosens exactly the openers whose terminals were
  replaced. This is a causal estimate (S - F), not a fit to a reference.
- Remaining gap to the near-references (PreflopRanges 9-max / Matthiola 8-max): BTN 48.7 vs 42.9, CO 37.5 vs 30.8, HJ 29.9 vs 24.3,
  UTG 16.5-18.5 vs 13.4 — about 30-50% of the gap closed at these positions with 19% of flop reach replaced.
- Not settled: BB vs UTG fold 40.5% is above the 8-max near-reference EP-vs-BB 24.3%; this is outer step 1 at O's tight UTG range
  with a 24-board panel, so it is not a calibrated value. Still static: SB opens, 3-way SRPs (~4% of flop reach each), 3-bet pots
  (36% of flop reach), non-selected HU openers.

## Stop point
No outer step 2 and no expansion were started. Next decisions for the user: expand to the full HU set (+ SB), outer loop with the E1
raw-residual rule, and a plan for 3-way and 3-bet terminals.
