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

## 40 bb (tree p40 v1 = the 60 bb v2b tree at stack 39.89: ante 1/9, opens 2.0 (SB 3.0, limp allowed), 3-bet 3.0x / blinds 3.5x-4.0x, 4-bet jam only, open jam excluded)
| file | content | method |
|---|---|---|
| chart_40bb_parent.json / chart_40bb_rfi.png | parent full-tree chart (RFI 8, vs open 37, vs 3-bet 51 nodes) | parent exact gap 0.00858 bb at 150 iterations, static realization |
| p40_flat_<opener>_vs_bb.json, p40_flat_sb_limp_vs_bb.json | HU subgame BB vs a single open (or SB limp): flat call, 3-bet call (two blind 3-bet sizes) and jam pots with the corrected flop terminals | 24-board loop (rule v4, max 8 steps) -> quick (converged: final step, else mean of last 4 steps); written when each spot finishes |
Flat-call spots: one spot covers the BB flat call (priority 1) and the 3-bet-call terminals (priority 3); nodes after the 4-bet / jam are research.
Tools: tools/gto_spot/plan_a_flat_specs.py, run_quick.sh.

## s60 record for the T2 builder (2026-10-19, requested by the T2 session)
data/gto_spot/records/s60.json (pushfold_record_v1, same format as 011TJ's s30 / s40: per node aggressor_action_combos, actor_arriving_combos,
class_strategy / class_ev_bb, unsupported_low_reach) built from the 60 bb parent dump with tools/gto_spot/pushfold_record.py (011TJ's builder + env
overrides PF_W / PF_CFG / PF_STD): stack_bb 60, status quick, symmetric_stack_assumption, static_continuation_for_flop_pots, gap 0.009568 bb at 200 iterations.
Check: the same builder on this session's 40 bb dump reproduces 011TJ's s40.json exactly (all keys and nodes equal).
Correction (2026-10-19): chart_*_parent*.json `combos` / `mix` / `reach_combos` were first weighted by class combos twice (RFI play % looked ~3-5 pp too
narrow, e.g. 60 bb UTG 11.1 % -> 14.1 %); per-class frequencies and EVs were not affected. Fixed and regenerated (60 / 40 bb charts and PNGs).

Resume manual: docs/GTO_RESUME_40BB.md (commands, restore, 100 bb parent, rules).
