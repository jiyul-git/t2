# Session 011TJw... status for docs/GTO_SESSIONS_BOARD.md (2026-10-19 ~12:00Z)

Text to merge into the shared board (branch chatgpt/terminal-census-v2-20260930) by its maintainer; this session could not push there.

Stack-split row: | btn session 011TJw... | 10 / 15 / 20 / 25 bb push/fold and 30 / 40 bb parent trees: DONE 2026-10-19 (see below) |

## Session 011TJw... status (branch claude/pushfold-10-25-20261019)
Pre-registered before solving: docs/GTO_PUSHFOLD_10_25_V1.md, docs/GTO_STACK_30_40_V1.md. All records `quick`, symmetric stacks,
chip EV, 9-max, ante 1 bb, vendored preflop DCFR (seeds 202, 1200 samples), stop at exact gap <= 0.010 bb.
| bucket | menu | iterations | exact gap (bb) | record |
|---|---|---|---|---|
| pf10 | jam / fold | 25 | 0.00663 | data/gto_spot/records/pf10.json |
| pf15 / pf20 / pf25 | fold / open 2.0 (SB 3.0) / jam; vs open fold / call / 3-bet jam | 75 / 100 / 75 | 0.00751 / 0.00539 / 0.00736 | pf15/20/25.json |
| s30 / s40 | Plan A v2b parent menu (cfg_p60_v2b with stack S - 1/9) | 150 / 150 | 0.00913 / 0.00858 | s30.json / s40.json |
Run files (exact gaps, logs, dump.jsonl.gz + SHA256SUMS): data/gto_spot/pushfold/runs/pf*/, data/gto_spot/stack3040/runs/s{30,40}/.
- 40 bb parent: data/gto_spot/stack3040/cfg_s40.json is IDENTICAL to data/gto_spot/plan_a/cfg_p40_v1.json (board branch 1453d25) and is
  already solved (150 iterations, exact gap 0.00858 bb; dump.jsonl sha256 a092af6d5eb989aa11c622ad829c3b4083bf3d69b0bdaaddff94705e61af1589;
  30 bb dump f8cc8ea5bbb8140bdd949b959119a7e75d84d313ce23323aa12b702b157e3671). The 01BLRH 40 bb parent solve started ~10:00Z repeats it;
  it can be stopped and the dump taken from this branch (gunzip data/gto_spot/stack3040/runs/s40/dump.jsonl.gz).
- Same finding as the board's 30 / 40 bb flat-call request: BB flat-call defence vs a 2.0 open ~100 % at 15-40 bb under the static continuation.
- 30 / 40 bb flat-call pot split: 011TJ is willing to take 30 bb (s30 parent ready); waiting for the user's go in session 011TJ.
- 60 bb claims of 011TJ (btn_vs_bb_3b35, co_vs_sb_3b35) withdrawn, never started; btn_vs_bb_3b40 left to the 60 bb quick summary.
