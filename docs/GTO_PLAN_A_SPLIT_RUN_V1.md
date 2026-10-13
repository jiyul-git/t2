# Plan A split run — second session (T2 side) runs p60_utg_vs_btn_b40 and p60_hj_vs_bb_b40

Split (user, 2026-10-13, revised): the original session runs p60_co_vs_sb_b40 and p60_utg1_vs_sb_b40 only
(`PLAN_A_IDS="p60_co_vs_sb_b40 p60_utg1_vs_sb_b40"`); the T2-side session runs p60_utg_vs_btn_b40 and p60_hj_vs_bb_b40.
A separate GPT session owns p60_btn_vs_bb_b40 only (`PLAN_A_IDS="p60_btn_vs_bb_b40"`) and returns results on
`chatgpt/plan-a-btn-bb-20261013`, based on 8c6e4d3366d222b45a7ca777961334c39bf54f34.
The original session must remove BTN-vs-BB from its chain; if already started, stop that spot and report its progress.
All returned results require SHA256SUMS and gate checks before integration. This ownership note does not itself stop another session.

## Setup (branch chatgpt/terminal-census-v2-20260930, the commit that adds this file)
1. `python3 -m pip install numpy`
2. `cd vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel` (the spot loop calls
   vendor/gtopen/target/release/examples/t2_cont_panel; the subgame solver itself is Python)
3. `sh tools/gto_spot/plan_a_install_inputs.sh` — unpacks the parent dump and the equity table to the container-local paths the specs
   name (/home/user/gto_ckpt/plan_a/p60_b40/dump.jsonl, /home/user/gto_ckpt/plan_a/eq_table_202_1200.json) and checks SHA256SUMS:
   | file | sha256 |
   |---|---|
   | p60_b40 dump.jsonl (400 it, reach >= 1e-6) | fdc51aca49d23fddd89a7c5b1cf89856f2dec9260c5bb8ace06f0bfedab21171 |
   | eq_table_202_1200.json | f29a53e2be9974c11a02094fb3c9c2b3b364fe06112cf1e689d6ebab0999ad7f |
   | transfer/p60_b40_dump.jsonl.gz | d469735254c0b441fd9ac6e65db83acb5ba7fb0410c46265dcf055c7e6d14e5e |
   | transfer/eq_table_202_1200.json.gz | 7ee7b84c227a6657ca1c0b6a50d36110ee08d252e863963e976690126cbd836d |
   Everything else the chain reads is in the repo: specs (data/gto_spot/plan_a/specs/), parent config and gap
   (cfg_p60_b40.json, parent_p60_b40_convergence.json), panels and menu (data/gto_hu_continuation/).

## Reproduction check before the run (step 0, terminal 0, board AcKc6c)
`python3 tools/gto_spot/plan_a_repro_step0.py data/gto_spot/plan_a/specs/<id>.json 0 AcKc6c /tmp/repro_<id>` prints the terminal
JSON sha256 and tools/gto_spot/flop_digest.py of the flop (deterministic content; excludes timings and the build commit).
| spot | terminal 0 line | term0.json sha256 | flop AcKc6c digest |
|---|---|---|---|
| p60_utg_vs_btn_b40 | UTG raise 2, BTN 3-bet 6, UTG call | 9401909dee63413ef7cead8f7f670a838fc56106d1f5c310822667ab655a1fb6 | 8797aeb1cfa68fd280c0655c4fc8ab25bdd4a272c43af870d3c30bd7c67d8d73 |
| p60_hj_vs_bb_b40 | HJ raise 2, BB 3-bet 8, HJ call | bea884cf697390c5cd54f8c54163da250b45eaaae2f1d5842c4054401b5c25d5 | 8588eeebb8ee2ec8857158928ac7e7edbc70cdb331ac84684c01d1dd7a8ef822 |
| p60_co_vs_sb_b40 (control: equals this session's chain artifact) | CO raise 2, SB 3-bet 8, CO call | addd06e97e9bcfea36027fae7c21d71071cb5d77964ff15ca7aab9e3bf7a3e01 | a035dc0cc8ae5a15cdedbf31af63b06030021597b43485f087e9b0f0e9326466 |
A mismatch stops the split: report it before running anything else.

## Run (resumable; relaunch after the 2 h background limit)
`PLAN_A_IDS="p60_utg_vs_btn_b40 p60_hj_vs_bb_b40" SPOT_PANEL_WORKERS=4 sh tools/gto_spot/run_plan_a.sh 60`
Per spot: rule-v3 loop -> grade -> P144 -> grade (PRECISION=144) -> sensitivity. Log: /home/user/gto_ckpt/plan_a/spots.log.

## Return (separate branch; this session checks sha256 and gates before merging)
- data/gto_spot/records/<id>.json, <id>_p144.json; data/gto_spot/plan_a/sensitivity/<id>_p144.json
- per spot from /home/user/gto_ckpt/spots/<id>/: state.json and step*/report.json, step*_p144/report.json -> data/gto_spot/plan_a/remote_runs/<id>/
- /home/user/gto_ckpt/plan_a/spots.log -> data/gto_spot/plan_a/remote_runs/spots.log
- a SHA256SUMS of all returned files

## Status
- 2026-10-13: the T2-side session reproduced all three references bit for bit (term0 sha256 and flop digest; utg_vs_btn checked on
  the artifact its chain produced) on 79cef4a6 (computation identical to e6ba28b3). Its chain runs utg_vs_btn then hj_vs_bb; results
  return on branch ccr-9a10123b-0lyye0 (same paths + SHA256SUMS).
