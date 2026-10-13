# Plan A split run — second session (T2 side) runs p60_utg_vs_btn_b40 and p60_hj_vs_bb_b40

Split (user, 2026-10-13): this session runs p60_co_vs_sb_b40, p60_utg1_vs_sb_b40, p60_btn_vs_bb_b40; the T2-side session (same
machine class: 4 cores, 15 GB, cargo) runs p60_utg_vs_btn_b40 and p60_hj_vs_bb_b40 on the same commit, build, scripts and config.

## Setup (branch chatgpt/terminal-census-v2-20260930, the commit that adds this file)
1. Use **Python 3.11** for every Python command, including subprocesses in `run_plan_a.sh`.
   Reference sessions reproduced the control terminal with Python 3.11.15 / NumPy 2.4.6. Python 3.12 changes floating-point
   `sum()` behavior: the control pot becomes 18.0 instead of 17.999999999999996 and the terminal hash becomes
   ff623d3d9135086cb92c0060c3853ec5aaa6c369c8e5260b330cf7fb743c5752. Do not accept that hash as the reference.
   Example: `uv venv -p 3.11 .venv311 && uv pip install -p .venv311/bin/python numpy==2.4.6`, then
   `export PATH="$PWD/.venv311/bin:$PATH"` from the repository root. Confirm `python3 --version` reports 3.11 and run both
   reference checks below; matching the version alone does not replace the hash gates.
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
- 2026-10-13 (user): p60_btn_vs_bb_b40 moves to a separate GPT session (branch chatgpt/plan-a-btn-bb-20261013, head 2585fca7; its
  control term0 addd06e9... and flop digest a035dc0c... matched after switching to Python 3.11.17 — Python 3.12's compensated
  float sum() changes the control pot to 18.0). Current split:
  | session | spots | result branch |
  |---|---|---|
  | this session | p60_co_vs_sb_b40, p60_utg1_vs_sb_b40 (+ the p60 v2b parent) | chatgpt/terminal-census-v2-20260930 |
  | T2 session | p60_utg_vs_btn_b40, p60_hj_vs_bb_b40 | ccr-9a10123b-0lyye0 |
  | GPT session | p60_btn_vs_bb_b40 | chatgpt/plan-a-btn-bb-20261013 |
  Every returned set is merged only after its SHA256SUMS and the gates are checked here.
- 2026-10-13 (user): queue after the B40 spots — the 9 v2b subgames (p60v2b_co_vs_sb_3b35, _3b40, p60v2b_utg1_vs_sb_3b35, _3b40,
  p60v2b_utg_vs_btn, p60v2b_btn_vs_bb_3b35, _3b40, p60v2b_hj_vs_bb_3b35, _3b40), taken in this order by whichever session frees up
  first; claim a spot by pushing a one-line note to its result branch before starting it. Inputs: the v2b dump is in the transfer
  set (p60_v2b_dump.jsonl.gz; SHA256SUMS updated; plan_a_install_inputs.sh installs it). Python 3.11 as above.
- v2b reproduction reference (Python 3.11, step 0, terminal 0, board AcKc6c; v2b dump installed and checked first):
  | spot | terminal 0 line | term0.json sha256 | flop AcKc6c digest |
  |---|---|---|---|
  | p60v2b_co_vs_sb_3b40 | CO raise 2, SB 3-bet 8, CO call | d221ccbed8f7a395434b7f6bf0a1b0ba93b6b82bc60dfca0e6475d987ea81236 | e73299315861596844dea56152413dd3252bd2230f137b71de234948ebffabc6 |
  Command: `python3 tools/gto_spot/plan_a_repro_step0.py data/gto_spot/plan_a/specs/p60v2b_co_vs_sb_3b40.json 0 AcKc6c /tmp/repro_v2b`
- 2026-10-13 (standard amendment 6): spot loop rule v4 = v3 with damped matrices (0.5 old + 0.5 new from step 1), up to 12 steps;
  all Plan A specs now carry rule "v4" (step 0 is identical, so every reproduction reference above stays valid). Sessions running
  a spot under v3: pull, and if the spot has not converged by step 5 (v3 would end without a stop decision and the grader would fail),
  re-run `run_plan_a.sh` on the pulled spec: the loop resumes from the saved state under v4. Reason: p60_co_vs_sb_b40 cycled with
  period 2 under v3 (CO 4-bet 0% <-> ~10% between steps).
- 2026-10-13 (user, Plan A amendment A7): B40 spots stopped everywhere. Claims: T2 session p60v2b_utg_vs_btn, p60v2b_hj_vs_bb_3b40,
  p60v2b_hj_vs_bb_3b35; this session p60v2b_co_vs_sb_3b40, p60v2b_utg1_vs_sb_3b40. Open: p60v2b_co_vs_sb_3b35,
  p60v2b_utg1_vs_sb_3b35, p60v2b_btn_vs_bb_3b40, p60v2b_btn_vs_bb_3b35. v2b reproduction reference: commit 44113004 (table above).
- 2026-10-13 (user, supersedes the claims above): v2b split, three spots per session, 4.0x spots first in every session:
  | session | order | result branch |
  |---|---|---|
  | this session | p60v2b_co_vs_sb_3b40 -> p60v2b_utg1_vs_sb_3b40 -> p60v2b_utg1_vs_sb_3b35 | chatgpt/terminal-census-v2-20260930 |
  | T2 session | p60v2b_utg_vs_btn -> p60v2b_hj_vs_bb_3b40 -> p60v2b_hj_vs_bb_3b35 | ccr-9a10123b-0lyye0 |
  | new Claude session | p60v2b_btn_vs_bb_3b40 -> p60v2b_btn_vs_bb_3b35 -> p60v2b_co_vs_sb_3b35 | claude/p60-btn-vs-bb-b40-20261013 |
  Sessions may stop at their usage limit: commit / back up after every finished step so another session can resume a spot.
