# 9-max 30bb OL (outer loop on the 8 HU SRP tables) — result v1

Rules: `GTO_HU_FULL_OUTER_9MAX_DESIGN_V1.md` (value-space raw residual D vs panel error U, alpha 0.5 on tables, max 3 steps, minimum
one update). Start state H (H1). Data: `data/gto_validation/pilot9/ol/` (step0-2 reports, state1/2 frequencies, ol_final.json).
576/576 flop solves at <= 0.30% pot (step 2 max 0.298). Comparisons with references are near-reference only.

## Stop decision
| step | max D/U | node-seats passing | max D / U_paired | decision |
|---|---|---|---|---|
| 0 (at H) | 2.57 (SB opener) | 7/16 | 6.51 | continue (minimum one update) |
| 1 (at state 1) | 1.05 (UTG opener) | 15/16 | 4.80 | continue |
| 2 (at state 2) | 0.51 | 16/16 | 5.32 | **stop: converged at panel_v1 resolution (value space); state 2 accepted** |

- Not a fixed-point proof: D / U_paired stays 1.2-5.3, and the signed change is negative at every opener seat in every step
  (opener values drift down monotonically; largest opener change 0.57 -> 0.22 -> 0.11 bb). The loop still moves, by less than panel_v1's own error.
- The criterion is value-space; E1's seat-swap loss was not computed (60 replicate preflop solves per step are not affordable in 9-max).

## Accepted state 2 vs O / H
| | UTG | UTG+1 | UTG+2 | LJ | HJ | CO | BTN | SB |
|---|---|---|---|---|---|---|---|---|
| RFI O | 11.4 | 12.6 | 14.7 | 16.8 | 21.9 | 26.9 | 36.5 | 59.2 |
| RFI H | 13.4 | 14.9 | 17.5 | 20.6 | 24.2 | 30.8 | 43.0 | 84.7 |
| RFI state 2 | 12.6 | 13.8 | 16.0 | 19.1 | 22.7 | 28.1 | 38.4 | 62.6 |
| PreflopRanges 9-max | 16.5 | 18.6 | 21.7 | 25.7 | 29.9 | 37.5 | 48.7 | 89.4 |
| jam share of opens, state 2 | 0 | 0 | 0 | 0 | 0 | 2.1 | 6.9 | 28.7 |

BB vs opener, state 2 (fold / call / raise / jam, %): BTN 12.2 / 64.1 / 13.2 / 10.4 (8-max BTN-vs-BB 10.4 / 71.6 / 9.3 / 8.6);
HJ 22.3 / 64.3 / 8.7 / 4.7 (MP-vs-BB 16.6 / 69.7 / 8.8 / 4.9); UTG 37.9 / 56.8 / 5.3 / 0 (EP-vs-BB 24.3 / 66.3 / 8.7 / 0.7);
SB 6.7 / 62.5 / 18.0 / 12.8 (SB-vs-BB 25.6 / 62.6 / 7.8 / 4.0).

## Reading
- H overshot: one undamped-at-O-ranges step (S / H1) loosened openers and made the BB fold too much; the self-consistent state sits between
  O and H for every position. Net O -> state 2: RFI +0.8 to +3.4 pp, BB fold vs openers 0-1% -> 7-38%.
- Jam dependence partly returned at BTN / SB (BTN 98s / AKo jam 0.98-0.99, SB 98s / 22 / KQo / AKo jam). Correction to an earlier
  note: called all-ins are valued exactly (SPR 0 -> pot x equity, no realization factor), so jam is not a static-payoff artefact. What
  changed is the raise branch: its HU SRP continuation is now solved (and fell step by step), while its 3-bet-pot and 3-way branches are
  still static. Whether that mix biases raise vs jam is the step-3 question.
- BB overfolds vs early positions (34-38% vs ~24% near-reference) persist after self-consistency; early-position openers stay tight
  (UTG A5s / K9s / 98s / T8s fold).
- Remaining static share: 3-bet pots (35.7% of O flop reach) and 3-way+ SRPs (26.8%), incl. every SB-flat line (SB flats 51% vs UTG).
