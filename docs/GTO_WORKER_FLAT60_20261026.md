# Worker instructions: 60 bb BB defence vs a 2.5 bb open (`p60_flat_btn_vs_bb_o25`, then `p60_flat_co_vs_bb_o25`) - user 2026-10-26 ("다른 것도 ㄱㄱ")
Same recipe as the 40 bb / 30 bb flat-call spots (docs/GTO_RESUME_40BB.md section 2): root = BB facing a single 2.5 open; below it the parent tree (call / 3-bet / jam); rule v4 24-board loop, max 3 steps, quick grade
(converged -> final step, else mean of the last 2 steps, `stopped_at_step_cap`), CFR+ retry of unconverged flops (amendment 11(a) variant), no P144. Parent = `p60_o25` (200 it, exact gap 0.00976). About 9+ h per spot; 60 bb flops are heavier than 40 bb.

## Setup (once per container; Python 3.11, `python3 -m pip install numpy==2.4.6`)
```sh
cd /home/user/t2
git fetch origin chatgpt/terminal-census-v2-20260930 && git checkout -B work origin/chatgpt/terminal-census-v2-20260930
(cd vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel)
sh tools/gto_spot/plan_a_install_inputs.sh      # equity table (sha256 checked); other missing files may be reported, ignore
mkdir -p /home/user/gto_ckpt/plan_a/p60_o25 && gunzip -c data/gto_spot/plan_a/transfer/p60_o25_dump.jsonl.gz > /home/user/gto_ckpt/plan_a/p60_o25/dump.jsonl
(cd data/gto_spot/plan_a/transfer && sha256sum -c SHA256SUMS 2>&1 | grep p60_o25)      # must say OK
```
## Run (TRACKED background task, timeout 7200000; killed after 2 h: relaunch the SAME command, finished flops / steps are reused; this relaunch is the intended procedure)
```sh
cd /home/user/t2 && SPOT_PANEL_WORKERS=4 PLAN_A_IDS="p60_flat_btn_vs_bb_o25 p60_flat_co_vs_bb_o25" sh tools/gto_spot/run_quick.sh
```
Log /home/user/gto_ckpt/plan_a/quick.log; progress /home/user/gto_ckpt/spots/<id>/step<k>/report.json. Never two copies at once. A flop that plateaus above 0.3 % after the retry stops the loop: report the numbers and stop (do not try other methods).
## Save (at every relaunch and when a spot ends)
```sh
sh tools/gto_spot/plan_a_backup_progress.sh <id>; git add data/gto_spot/quick data/gto_spot/plan_a/progress && git commit -m "<id>: <what>" && git push -u origin HEAD:claude/p60_flat_o25_20261026
```
Own branch only; never the census branch or test3; no force push; no model name in commit messages. Report in Korean, short, per finished spot: root mix of the BB (fold / call / 3-bet / jam), steps, `stopped_at_step_cap`, branch + commit. DB promotion forbidden; connecting to T2 needs the user's approval.
