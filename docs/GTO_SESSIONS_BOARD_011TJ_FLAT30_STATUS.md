# Session 011TJw... status: 30 bb flat-call pots (2026-10-20, branch claude/p30-flat-20261019)

For docs/GTO_SESSIONS_BOARD.md (maintainer merges; this session cannot push to the census branch).
Method: census d1b670b tools (plan_a_flat_specs.py, run_quick.sh, quick_spot.py), parent s30 (cfg_p30_v1 = stack 29.89, exact gap 0.009128 bb, dump sha256
f8cc8ea5bbb8140bdd949b959119a7e75d84d313ce23323aa12b702b157e3671), Plan A loop (HU subgame + 24-board panel, rule v4), no P144, 4-bet and later out of scope.
Reproduction before the run (Python 3.11.17, numpy 2.4.6, census d1b670b): v2b co_vs_sb_3b40 step 0 terminal 0 d221ccbe..., flop AcKc6c e7329931... = table value.
SPOT_PANEL_WORKERS = 4 (4 cores / 15 GB). Each spot = 3 flop terminals per step (flat call, BB 3-bet 7 + call, BB 3-bet 8 + call), ~2.3 h per step.

| spot | steps | decision | converged / strict / exempt used | quick record |
|---|---|---|---|---|
| p30_flat_btn_vs_bb | 4 (0-3) | stop: converged at step 3 | true / true / false | data/gto_spot/quick/p30_flat_btn_vs_bb.json |
| p30_flat_co_vs_bb | 4 (0-3) | stop: converged at step 3 | true / true / false | data/gto_spot/quick/p30_flat_co_vs_bb.json |
Backups per step (step0-3.tgz, state.json, SHA256SUMS): gto_split_backup/p30_flat_{btn,co}_vs_bb/. Not run: SB, HJ, LJ, UTG+2, UTG+1, UTG opens and the SB limp pot.

BB root (facing the open), corrected vs the parent's static continuation:
| opener | source | fold | call | 3-bet 7 | 3-bet 8 | jam |
|---|---|---|---|---|---|---|
| BTN | parent static (s30) | 0.0 | 84.8 | 0.0 | 0.1 | 15.1 |
| BTN | loop, converged | 9.8 | 76.9 | 4.6 | 0.0 | 8.8 |
| CO | parent static (s30) | 0.0 | 89.4 | 0.1 | 0.2 | 10.2 |
| CO | loop, converged | 12.7 | 78.0 | 4.9 | 0.0 | 4.5 |
Step cost: 4 steps x ~2.3 h = ~10 h per spot; the 7 remaining spots would take ~70 h at 4 workers. Decision for the user: which of the remaining spots
(SB open, SB limp, HJ ... UTG) to run, or to extrapolate; frequencies for those stay the parent's static values (flat call / limp NOT connected).
