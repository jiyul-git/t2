# Worker instructions: recompute 30 bb SB open vs BB (`p30_flat_sb_vs_bb`) - user approval 2026-10-26 ("워커 하나 띄워서 재계산 ㄱㄱ")
Why: step 1 stopped because flop KcTd9h (3-bet 10.5 bb call terminal) did not converge: DCFR 4.16 % pot, CFR+ at the same budget (1000 it) 0.675 %, target 0.3 %. Recompute = redo that flop with CFR+ at 3x the budget
(3000 it), then let the rule-v4 loop continue (max 3 steps, quick grade: converged -> final step, else mean of the last 2 steps with `stopped_at_step_cap`; amendments 7 / 11 as before; no P144).
If the flop still does not converge, the loop stops again with the same verdict: then report the numbers (do not try other methods; the coordinator and the user decide).

## Setup (once per container; Python 3.11, `python3 -m pip install numpy==2.4.6`)
```sh
cd /home/user/t2
git fetch origin chatgpt/terminal-census-v2-20260930 && git checkout -B work origin/chatgpt/terminal-census-v2-20260930
(cd vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel)
sh tools/gto_spot/plan_a_install_inputs.sh      # equity table (sha256 checked); may report missing 60 bb files, ignore
sh tools/gto_spot/plan_a_install_p30.sh         # 30 bb parent dump (sha256 f8cc8ea5...)
mkdir -p /home/user/gto_ckpt/spots && tar -C /home/user/gto_ckpt/spots -xzf gto_split_backup/p30_sb_recompute/p30_flat_sb_vs_bb.tgz
sha256sum gto_split_backup/p30_sb_recompute/p30_flat_sb_vs_bb.tgz        # expect 659559737ec9ccbf0c8144ca8150686e143f42ba3f3be233ed084060704077d9
git mv data/gto_spot/quick/p30_flat_sb_vs_bb.json data/gto_spot/quick/p30_flat_sb_vs_bb_stopped_step1.json   # run_quick.sh skips ids that already have a quick record
```
The tarball holds the spot state: steps 0-1 with all flop artifacts; `step1/term1_flops/KcTd9h.json` is the CFR+ 1000-it result, `first_attempt/` holds the DCFR artifact.

## Run (TRACKED background task, timeout 7200000; killed after 2 h: relaunch the SAME command, it resumes; a killed retry restarts at 3000 it)
```sh
cd /home/user/t2 && RETRY_ITER_MULT=3 RETRY_THREADS=4 SPOT_PANEL_WORKERS=4 PLAN_A_IDS="p30_flat_sb_vs_bb" sh tools/gto_spot/run_quick.sh
```
`RETRY_ITER_MULT` / `RETRY_THREADS` are implemented in `tools/gto_spot/spot_loop.py` `retry_flops` (default unchanged). Log: /home/user/gto_ckpt/plan_a/quick.log; retry log: /home/user/gto_ckpt/spots/p30_flat_sb_vs_bb/step1/term1_flops/logs/KcTd9h.retry.log.
Never two copies at once (`ps -eo args | grep spot_loop`). Back up at every relaunch and at every finished step: `sh tools/gto_spot/plan_a_backup_progress.sh p30_flat_sb_vs_bb`,
then `git add data/gto_spot/quick data/gto_spot/plan_a/progress && git commit && git push -u origin HEAD:claude/p30_sb_recompute_20261026` (YOUR branch only; never the census branch or test3; no force push; no model name in commit messages).
If the redone flop is the last long job (a few hours at 4 threads) also push the flop artifact: `tar -czf gto_split_backup/p30_sb_recompute/p30_flat_sb_vs_bb_resume.tgz -C /home/user/gto_ckpt/spots p30_flat_sb_vs_bb` if < 100 MB.

## Report (Korean, short) when the flop finishes and when the quick record exists
KcTd9h exploitability and iterations after 3000 it (converged? target 0.3 %), loop decision per step (D/U table), root mix of the SB (fold / call / 3-bet / jam) and of the BB, `stopped_at_step_cap`, branch + commit.
The result is `data/gto_spot/quick/p30_flat_sb_vs_bb.json`. Do not edit docs, CLAIM or other tools. DB promotion forbidden; connecting to T2 needs the user's approval.
