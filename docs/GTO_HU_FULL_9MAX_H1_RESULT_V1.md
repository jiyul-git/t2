# 9-max 30bb H1 (full HU SRP set) — result v1

States (100 it, same config / seeds / tree): O static; S = 4 solved tables (BTN / CO / HJ / UTG -> BB, at O ranges);
H = S + 4 new solved tables (SB 11 / LJ 795 / UTG+2 2548 / UTG+1 7997 -> BB, panel_v1, at S ranges). Data:
`data/gto_validation/pilot9/h1/h1_analysis.json`; tables report `/home/user/gto_ckpt/h1/tables_report.json` (96/96 flops <= 0.30% pot,
max 0.298). Checkpoint restores verified: S-state and O-state UTG+1 path exports are identical to the original exports.
Comparisons with references are near-reference only.

## H - S (new nodes; all expected directions hold)
| opener | RFI S -> H | jam share of opens | BB fold | BB call | terminal reach |
|---|---|---|---|---|---|
| SB (11) | 59.3 -> 84.7% | 38.9 -> 3.5% | 0.0 -> 8.7% | 63.0 -> 52.2% (BB 3-bet 22.0 -> 29.6%) | +68% |
| LJ (795) | 16.8 -> 20.6% | ~0 | 0.0 -> 34.0% | 91.8 -> 52.0% | -43% |
| UTG+2 (2548) | 14.7 -> 17.5% | ~0 | 0.0 -> 36.1% | 92.4 -> 54.1% | -37% |
| UTG+1 (7997) | 12.6 -> 14.9% | ~0 | 0.1 -> 39.1% | 93.1 -> 55.7% | -44% |

- Old 4 nodes: RFI and BB responses within 0.7 pp of S (interaction small).
- Hands (opener node, fold / raise / jam, S -> H): SB 98s and T8s jam -> raise, SB 22 stays jam; LJ 98s / 22 / T8s fold -> raise;
  UTG+2 A5s / 98s / 22 / T8s fold -> raise; UTG+1 A5s fold -> raise 0.73, K9s 0.38 -> 0.94 raise, T8s fold -> raise, 98s 0.35 raise.
- SB responses to non-SB opens did not move (they lead mostly to 3-way terminals, still static): SB flats 15% vs BTN, 34% vs CO,
  52% vs UTG (8-max near-reference EP-vs-SB 13.7%).

## Reading
- RFI H vs near-references (PreflopRanges 9-max): UTG 13.4 / 16.5, UTG+1 14.9 / 18.6, UTG+2 17.5 / 21.7, LJ 20.6 / 25.7, HJ 24.2 / 29.9,
  CO 30.8 / 37.5, BTN 43.0 / 48.7. SB 84.7% (raise-or-fold tree; PreflopRanges 89.4%, Matthiola's limp tree 29.4% raise is not comparable).
- BB vs early / middle openers now folds 34-41% (8-max near-references EP-vs-BB 24.3%, MP-vs-BB 16.6%); BB vs SB 8.7% (SB-vs-BB 25.6%).
  The early-position tables were solved at tight opener ranges (O / S); whether the overfold shrinks as openers widen is what the
  outer loop (OL) measures. No coefficient is changed to close the gap.
- Still static: 3-bet pots (35.7% of O flop reach), 3-way+ SRPs (26.8%), every SB flat line.
