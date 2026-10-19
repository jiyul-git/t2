# quick grade (user decision 2026-10-19: fill fast first, refine later)

Never GTO-verified; `db_promotion: forbidden`; symmetric-stack assumption (all seats at the bucket stack, lookup by effective stack);
connecting to the T2 runtime needs user approval. Refinement targets later (P144 etc.) where T2 bots differ most.

## 60 bb (tree p60 v2b: ante 1/9, opens 2.0 (SB 3.0, limp allowed), 3-bet 3.0x / blinds 3.5x-4.0x, 4-bet jam only in the parent, open jam excluded)
| file | content | method |
|---|---|---|
| chart_60bb_parent_v2b.json | parent full-tree average strategy + action EVs per class: RFI (8), vs open incl. BB defence / cold 3-bet (37), opener vs 3-bet (51) | parent exact gap 0.0096 bb, static realization (no HU re-solve) |
| chart_60bb_rfi.png | RFI grids of the chart above | |
| p60v2b_co_vs_sb_3b40.json | HU subgame CO vs SB 3-bet 8 | 24-board loop converged, step 2 |
| p60v2b_utg1_vs_sb_3b40.json | UTG+1 vs SB 3-bet 8 | converged, step 3 |
| p60v2b_btn_vs_bb_3b40.json | BTN vs BB 3-bet 8 | converged, step 3 (P144 not used) |
| p60v2b_hj_vs_bb_3b40.json | HJ vs BB 3-bet 8 | not converged -> mean of steps 2-5 |
| p60v2b_utg_vs_btn.json | UTG vs BTN 3-bet 6 | not converged after 12 steps -> mean of steps 8-11 |
| p60v2b_hj_vs_bb_3b35.json | HJ vs BB 3-bet 7 | in progress (T2 side) -> mean of steps 3-6 for now |

HU spot files take precedence over the chart's vs_3bet node of the same pair. In a spot file only the root node (3-bet response) is
for connection; `deep` nodes (after the 4-bet / jam) are research; `off_path` nodes (opponent arrives < 1 combo) are not meaningful;
`unstable_across_steps` marks classes that moved > 10 pp between averaged steps.
Tools: tools/gto_spot/quick_spot.py, tools/gto_spot/export_parent_chart.py, tools/gto_spot/plot_rfi.py.
