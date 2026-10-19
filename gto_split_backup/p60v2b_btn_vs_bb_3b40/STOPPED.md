# p60v2b_btn_vs_bb_3b40 — paused (user request "잠시 중단", 2026-10-19)

State at the pause:
- 24-board v4 loop: converged at step 3 (stop decision; `converged` true, `converged_strict` false, amendment-8 exemption used:
  BB at the 4-bet-call terminal, BTN arriving < 1 combo; `amendment8_unsupported_nodes` = path [0,0,0,0,0,0,1,0,3,2]).
  Backups step0.tgz .. step3.tgz.
- 24-board record regraded on 9abf2bd (amendment 9): G6(a) fail (BTN root mean EV loss 0.01293 bb > 0.010), G6(b) pass;
  status provisional (P144 not graded). Record not committed yet (written at the end of the chain).
- P144 (precision_pass.py) in progress: term0 144/144 boards, term1 131/144 boards solved.
  Backups: step3_p144_partial.tgz, step3_p144_term0_partial.tgz, step3_p144_term1_partial.tgz (to 2026-10-14 19:29Z, 248 boards),
  then step3_p144_part1.tgz (files changed after that). Restore: extract step3.tgz, then the three *_partial.tgz, then part1.
- Code: result branch merged with chatgpt/terminal-census-v2-20260930 at 9abf2bd (amendments 9-11); v2b repro matched on it.

Resume (same machine layout, /home/user/t2, /home/user/gto_ckpt, Python 3.11 venv first in PATH):
  restore /home/user/gto_ckpt/spots/p60v2b_btn_vs_bb_3b40 from the archives above (and state.json), then
  PLAN_A_IDS="p60v2b_btn_vs_bb_3b40 p60v2b_btn_vs_bb_3b35 p60v2b_co_vs_sb_3b35" SPOT_PANEL_WORKERS=4 sh tools/gto_spot/run_plan_a.sh 60
  (solved boards are reused; P144 resumes at term1, then amendment-10 loop if inconsistent, grade, sensitivity).
