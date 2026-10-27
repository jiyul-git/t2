# Worker instructions: 60 bb / 100 bb parents with open 2.5 bb (written 2026-10-26 by session 01BLRH...)

User decision 2026-10-26: from 60 bb up the opens are sized >= 2.3 bb, first run 2.5 bb (2.0 open invites too many calls and multiway pots). T2 formats: standard starts at 150 bb, turbo at 100 bb.
The existing 100 bb parent (`cfg_p100_v1`) and the 60 bb parents (`cfg_p60_v2b`) use open 2.0. New configs, identical except `open_raises_by_seat` = 2.5 for UTG..BTN (SB 3.0, BB 3.5 unchanged) and `open_raises` [2.5]:
`data/gto_spot/plan_a/cfg_p100_o25.json` (arm `o25`, stack 99.89), `data/gto_spot/plan_a/cfg_p60_o25.json` (stack 59.89). You get ONE of them (your task text says which). Do not run the other.

## Setup (once per container; Python 3.11 required; `python3 -m pip install numpy==2.4.6`)
```sh
cd /home/user/t2                                  # repo root of this session
git fetch origin chatgpt/terminal-census-v2-20260930 && git checkout -B work origin/chatgpt/terminal-census-v2-20260930
mkdir -p /home/user/gto_ckpt/plan_a
(cd vendor/gtopen && CARGO_TARGET_DIR=/home/user/gto_ckpt/target_exp cargo build --release -p solver --features t2-cont --example t2_cont_terminal)
ls /home/user/gto_ckpt/target_exp/release/examples/t2_cont_terminal     # must exist (the script calls it)
```
If `/home/user/t2` is not the repo path, `ln -s <repo> /home/user/t2` first.

## Run (TRACKED background task, timeout 7200000; killed after 2 h; relaunch the same command, it resumes from `ck.gtop`)
```sh
cd /home/user/t2 && sh tools/gto_spot/plan_a_parent_run.sh <60|100> o25      # log lines go to stdout; state in /home/user/gto_ckpt/plan_a/p<S>_o25/
```
~30 min per 25 iterations at 100 bb alone on 4 cores (first chunk 60 min); stop at exact gap <= 0.010 bb or 400 iterations (the script does it). Memory: 100 bb tree ~2.6 M nodes, 3.5 GB arena (15 GB RAM machine: run NOTHING else heavy).
Never run two copies (`ps -eo args | grep t2_cont_terminal`). The checkpoint `ck.gtop` is NOT in the repo: if the container is replaced the solve restarts at iteration 0, so push `convergence.json` copies at every relaunch.
Do not rely on the 2 h limit message: relaunching the same resumable command is the intended procedure of this task (user: continue across 2 h chunks).

## Finish (when `final_n` and `dump.jsonl` exist in the work dir)
```sh
python3 tools/gto_spot/export_parent_chart.py /home/user/gto_ckpt/plan_a/p<S>_o25/dump.jsonl data/gto_spot/plan_a/cfg_p<S>_o25.json <S>bb_o25 <gap_exact> data/gto_spot/quick/chart_<S>bb_open25_parent.json
python3 tools/gto_spot/plot_rfi.py data/gto_spot/quick/chart_<S>bb_open25_parent.json data/gto_spot/quick/chart_<S>bb_open25_rfi.png "<S>bb 9-max RFI, open 2.5 (parent gap <gap_exact>)"
gzip -c /home/user/gto_ckpt/plan_a/p<S>_o25/dump.jsonl > data/gto_spot/plan_a/transfer/p<S>_o25_dump.jsonl.gz && (cd data/gto_spot/plan_a/transfer && sha256sum p<S>_o25_dump.jsonl.gz >> SHA256SUMS)
cp /home/user/gto_ckpt/plan_a/p<S>_o25/convergence.json data/gto_spot/plan_a/parent_p<S>_o25_convergence.json
PF_W=/home/user/gto_ckpt/plan_a/p<S>_o25 PF_CFG=data/gto_spot/plan_a/cfg_p<S>_o25.json PF_STD="Plan A parent p<S> o25" python3 tools/gto_spot/pushfold_record.py <S> s     # -> data/gto_spot/records/s<S>.json: RENAME it s<S>_open25.json (do not overwrite the 2.0 record)
git add -A data/gto_spot && git commit -m "p<S>_o25 parent: <iterations>, exact gap <gap>" && git push -u origin HEAD:claude/p<S>_o25_20261026
```
Push only to YOUR branch `claude/p<S>_o25_20261026`; never to the census branch or test3; no force push. Do not edit tools / docs / CLAIM. Report in Korean, short: iterations, exact gap, RFI play% per seat (from the chart), branch + commit. DB promotion forbidden; connecting to T2 needs the user's approval.
