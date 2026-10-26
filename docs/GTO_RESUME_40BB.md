# GTO resume manual — 40 bb flat-call spots, 100 bb parent, 60 bb quick (written 2026-10-21 by session 01BLRH...)

> **STATUS 2026-10-26 (read this first).** This manual's section 2 chain was STOPPED on 2026-10-21 21:37Z (this session's container idled, then restarted) and is NOT to be
> relaunched: other sessions finished the work in the meantime. Current facts, from the remote branches on 2026-10-26:
> - 40 bb flat-call tail (UTG, UTG+1, UTG+2, SB limp) was finished by the coordinator session (012qfUk9...): branches `claude/p40_flat_tail_20261021`, `claude/p40_flat_utg2_20261024`,
>   `claude/p40_sblimp_cfrplus_20261023` (SB limp redone with CFR+ in the amendment-11(a) retry, user delegated the approval to the coordinator on 2026-10-23). This session's records
>   BTN / CO / SB / HJ / LJ (data/gto_spot/quick/ on this branch) are the ones in use. All nine 40 bb flat-call records, s30, s40, s100 are copied into test3 `data/gto_records/*.json.gz` (MANIFEST.tsv).
> - 30 bb flat-call and 3-bet-call spots, the 100 bb parent (400-iteration cap, exact gap 0.01689 bb, branch `claude/p100_parent_20261024`), the open-size 2.0 / 2.5 parents (`claude/open_sizes_20261024`) and the 2.5 bb flat-call
>   defence (`claude/flat_open25_20261025`) were done or are running on other branches. 17 finished calculation branches are archived in `claude/archive-gto-runs-20261024` (ARCHIVE.md).
> - Connection to the T2 bot and the open decisions (ICM push/fold, open size 2.0 vs 2.5, 3-bet size choice) are tracked in `docs/T2_HANDOFF.md` section 8 (branch `claude/connect_open25_co40_20261025`).
> - Section 4 below (100 bb parent: resume from checkpoint) is obsolete; sections 0, 1, 6 and 7 (rules, setup, limit pattern, file map) still hold for any new calculation.
> - If you need to compute more here, first check the branches above so nothing is duplicated; the local progress backups under `data/gto_spot/plan_a/progress/` for utg2 / lj are stale.


For whoever continues this work after the session or its container is gone (weekly limit warning, reset 2026-10-26 02:00Z). Read this file,
then `docs/GTO_SESSIONS_BOARD.md` (status + user decisions) and `data/gto_spot/quick/README.md` (file map). The T2-side connection manual is
`docs/T2_HANDOFF.md` on branch `test3` (commit 6cac54c5); T2 connects GTO values, this side computes them.
Everything below is what exists **on branch `chatgpt/terminal-census-v2-20260930`**. `/home/user/gto_ckpt/...` is container-local and disappears.

## 0. Rules that do not change (user decisions)
- Game rules + standard solver sizes only; T2 bot behaviour is never a reference for pass / fail. 9-max, chip EV (no ICM), ante 1 bb, no rake.
- Symmetric stacks per bucket (10/15/20/25/30/40/60/100 bb); T2 looks up by effective stack. Records say `symmetric_stack_assumption`.
- Status `quick` = fill fast first: 24-board loop converged -> that state; capped / cycling -> mean of the last steps. No P144 (144-board pass) now;
  it is a later, partial refinement where T2 bots and GTO differ most.
- `db_promotion: forbidden`. Connecting GTO data to the T2 runtime needs the user's approval (T2 session does the connecting). Never call 3-way results GTO.
  No force push. No PRs unless asked. Do not modify T2 human-model code.
- Commit + push every step with the trailers `Co-Authored-By: <model> <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_<id>`.
- Respond to the user in Korean, short; visuals as PNG (never SVG / ASCII).
- Standards: `docs/GTO_VERIFIED_FREQUENCY_STANDARD_V1.md`. Relevant here: amendment 8 (opponent arrives < 1 combo at a terminal -> exempt), 10 (144-board
  continuation), 11 (one flop retry at 3x iterations; still unconverged at an exempt terminal -> recorded, run continues), 12 (nodes the opponent reaches with
  < 1 combo are `unsupported`, never used by T2). `quick` records are outside the verified ladder (research < provisional < conditional_verified < verified).

## 1. Fresh container setup (about 20 min + build)
```sh
git clone <repo> && cd t2 && git checkout chatgpt/terminal-census-v2-20260930
# Python 3.11 is REQUIRED (3.12 changes float sum(): different hashes). numpy 2.4.6. Check: python3 --version
cd vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel && cd ../..   # the loop calls vendor/gtopen/target/release/examples/t2_cont_panel
sh tools/gto_spot/plan_a_install_inputs.sh      # equity table + 60 bb dumps (sha256 checked)
sh tools/gto_spot/plan_a_install_p40.sh         # 40 bb parent dump -> /home/user/gto_ckpt/plan_a/p40_v1/dump.jsonl (sha256 a092af6d...)
```
Reference check (optional, as in docs/GTO_PLAN_A_SPLIT_RUN_V1.md): `python3 tools/gto_spot/plan_a_repro_step0.py <spec> 0 AcKc6c /tmp/repro`.
The 40 bb parent was solved independently by two sessions with identical dump (sha256 `a092af6d5eb989aa11c622ad829c3b4083bf3d69b0bdaaddff94705e61af1589`),
so a corrupted install is detectable. Machine class: 4 cores, 15 GB RAM; a tracked background task dies after 2 h (relaunch, see section 6).

## 2. 40 bb flat-call spots (the running job)
Spot = BB facing a single open (or the SB limp): live seats opener + BB; below the root the parent tree (call / 3-bet / jam; 4-bet jam only). One spot covers the
flat-call terminal (priority 1) and the 3-bet-call terminals (priority 3); after the 4-bet is research. Specs: `data/gto_spot/plan_a/specs/p40_flat_<opener>_vs_bb.json`
(generated by `python3 tools/gto_spot/plan_a_flat_specs.py 40 v1`; parent = `data/gto_spot/plan_a/cfg_p40_v1.json`, exact gap 0.00858 bb at 150 iterations).

| spot id | max_steps | status (2026-10-21) | record |
|---|---|---|---|
| p40_flat_btn_vs_bb | 8 | DONE, converged at step 4 | data/gto_spot/quick/p40_flat_btn_vs_bb.json |
| p40_flat_co_vs_bb | 8 | DONE, converged at step 2 | ..._co_vs_bb.json |
| p40_flat_sb_vs_bb (SB opens 3.0) | 3 | DONE, step cap, mean of steps 1-2 | ..._sb_vs_bb.json |
| p40_flat_hj_vs_bb | 3 | DONE, step cap, mean of steps 1-2 | ..._hj_vs_bb.json |
| p40_flat_lj_vs_bb | 3 | DONE, step cap, mean of steps 1-2 | ..._lj_vs_bb.json |
| p40_flat_utg2_vs_bb | 3 | RUNNING (started 2026-10-21 20:41Z) | - |
| p40_flat_utg1_vs_bb | 3 | queued | - |
| p40_flat_utg_vs_bb | 3 | queued | - |
| p40_flat_sb_limp_vs_bb | 3 | queued (last) | - |
User rule (2026-10-20): BTN and CO run to convergence; the other 7 stop at 3 steps (step index 0..2): converged earlier -> stop; not converged at the cap -> quick =
mean of the last 2 steps with `stopped_at_step_cap: true` and a `status_note`. A step takes about 3 h (3 terminals x 24 boards, 4 workers), a capped spot about 9 h.

**Start / resume (idempotent; skips spots whose `data/gto_spot/quick/<id>.json` exists; a loop continues at `state.json`'s step; finished flops are reused):**
```sh
# after a container loss first restore the in-progress spot(s), then run the chain:
sh tools/gto_spot/plan_a_restore_progress.sh p40_flat_utg2_vs_bb        # state.json + step reports + step inputs from data/gto_spot/plan_a/progress/
PLAN_A_IDS="p40_flat_btn_vs_bb p40_flat_co_vs_bb p40_flat_sb_vs_bb p40_flat_hj_vs_bb p40_flat_lj_vs_bb p40_flat_utg2_vs_bb p40_flat_utg1_vs_bb p40_flat_utg_vs_bb p40_flat_sb_limp_vs_bb" \
  SPOT_PANEL_WORKERS=4 sh tools/gto_spot/run_quick.sh        # run as a TRACKED background task, timeout 7200000; log: /home/user/gto_ckpt/plan_a/quick.log
```
After the restore the step's flops are recomputed (they are never backed up); a restore loses at most the running step (about 3 h). If a spot's earlier steps are missing
(`step<k>/tables_used.json` etc.) the quick mean cannot be built: restore from `progress/` (the backup script keeps them for in-progress spots) or rerun the spot.
`run_quick.sh` = `spot_loop.py <spec>` (rule v4, damped matrices) then `quick_spot.py <id> /home/user/gto_ckpt/spots/<id>` -> `data/gto_spot/quick/<id>.json`.
Read progress: `/home/user/gto_ckpt/spots/<id>/step<k>/report.json` (`terminals.<line>.seats.<pos>`: `D` = value change vs the previous step, `U` = panel error, `pass` = D <= U),
`state.json`. Reading a step report by hand:
`python3 - <<'EOF' ... json.load(open('.../stepK/report.json')) ...` (see how the status lines were built; D/U per terminal-seat).
**After every finished spot (and at every relaunch): back up and commit**
```sh
sh tools/gto_spot/plan_a_backup_progress.sh <id>      # state.json + step reports + small step inputs into data/gto_spot/plan_a/progress/<id>/ (never flops)
git add data/gto_spot/quick data/gto_spot/plan_a/progress && git commit -m "..." && git push origin chatgpt/terminal-census-v2-20260930
```
Then update `docs/GTO_SESSIONS_BOARD.md` (status line) and this file's table. Report to the user in Korean (see the style of earlier messages: per-terminal D/U table, BB defence mix vs the static parent,
folds / unstable classes).

Results so far (BB frequencies, corrected vs static parent chart): BTN open: fold 8.9 / call 76.9 / 3-bet 7 5.5 / 3-bet 8 2.2 / jam 6.4 (parent 0 / 85.5 / 0.6 / 2.9 / 11.0);
CO open: 12.7 / 77.2 / 0.7 / 6.9 / 2.5 (parent 0 / 89.3 / 1.5 / 2.7 / 6.6); SB 3.0 open: 23.9 / 69.6 / 4.7 / 0.0 / 1.8 (parent 0 / 86.8 / 2.6 / 4.0 / 6.6); HJ open: 14.7 / 76.7 / 3.2 / 4.1 / 1.4; LJ open: 19.8 / 73.9 / 4.1 / 1.7 / 0.4.
The static continuation lets the BB defend 100 %; the corrected values fold the weakest offsuit hands. Flat-call terminals converge by step 1-2; the 3-bet-call terminals of the BB are the slow ones.

## 3. 30 bb flat-call spots
Owned by session 011TJ (branch `claude/pushfold-10-25-20261019`, same tools `plan_a_flat_specs.py` / `run_quick.sh`; parent cfg `data/gto_spot/stack3040/cfg_s30.json`, dump gz on that branch).
Check the board for their status; do not duplicate.

## 4. 100 bb parent (paused; needed after the 40 bb flat spots, user order: 30/40 bb before 100 bb)
Config `data/gto_spot/plan_a/cfg_p100_v1.json` (stack 99.89, same sizes as v2b, max_raises 3, 4-bet 2.25x or jam, no parent 5-bet; 2.58 M nodes, 3.5 GB arena; the max_raises 4 tree is
43 M nodes / 59 GB and does not fit). Solve = `sh tools/gto_spot/plan_a_parent_run.sh 100 v1` (resumable from `/home/user/gto_ckpt/plan_a/p100_v1/ck.gtop`, a 3.5 GB checkpoint that is **not in the repo**; a new container
starts from iteration 0). Exact gap vs iterations (solve gap, skip off at the end): 25: 0.8255, 50: 0.3019, 75: 0.1284, 100: 0.0765 (exact 0.0765), 125: 0.0519, 150: 0.0392, 175: 0.0315, 200: 0.0272. ~30 min per 25 iterations
(first chunk 60 min). Stop at exact gap <= 0.010 bb or 400 iterations (the script does this; the last value is used with its gap stated). It checks the exact gap every 100 iterations (extra ~20 min).
When `final_n` and `dump.jsonl` exist: build the records exactly as for 60 / 40 bb:
```sh
python3 tools/gto_spot/export_parent_chart.py /home/user/gto_ckpt/plan_a/p100_v1/dump.jsonl data/gto_spot/plan_a/cfg_p100_v1.json 100bb <gap_exact> data/gto_spot/quick/chart_100bb_parent.json
python3 tools/gto_spot/plot_rfi.py data/gto_spot/quick/chart_100bb_parent.json data/gto_spot/quick/chart_100bb_rfi.png "100bb 9-max RFI (...)"
PF_W=/home/user/gto_ckpt/plan_a/p100_v1 PF_CFG=data/gto_spot/plan_a/cfg_p100_v1.json PF_STD="docs/GTO_PLAN_A_60BB_V1.md (Plan A parent p100 v1)" python3 tools/gto_spot/pushfold_record.py 100 s   # -> data/gto_spot/records/s100.json for the T2 builder
```
(`pushfold_record.py` is 011TJ's builder with env overrides; checked: on the 40 bb dump it reproduces their `s40.json` exactly.) Gzip the dump into `data/gto_spot/plan_a/transfer/` (and add sha256 to SHA256SUMS) so the next session need not resolve it.
100 bb flat-call spots after that (same recipe as section 2: `plan_a_flat_specs.py 100 v1`; the 100 bb tree has the 4-bet 2.25x menu, so check the spec's tree label) are the last priority.

## 5. 60 bb (final for now, user 2026-10-20)
Quick summary is final: `data/gto_spot/quick/` (README maps files): parent chart (RFI / vs open / vs 3-bet), six HU 3-bet spot records, `data/gto_spot/records/s60.json` (T2 builder format).
The stopped runs of other sessions (co_vs_sb_3b40 144-board loop, hj_vs_bb_3b35, btn_vs_bb_3b40 P144) are NOT resumed. 60 bb flat-call spots are not planned.

## 6. The 2-hour limit and container restarts
A tracked background task is killed after 2 h; an idle container can be reclaimed and restarted (disk usually survives a restart, not a deletion). Pattern that worked: on every "task killed" or "container restarted"
notice, check `ps -eo args | grep spot_loop`, read the newest `step<k>/report.json`, relaunch the same command (section 2) as a tracked task, and commit the backup. Detached `nohup` launches die with the container; tracked tasks are the only
survivable form. Never start a second copy of the chain; check `ps` first. Disk: 15 GB RAM, ~250 GB disk, ~10 GB free at times: old parent checkpoints (`ck.gtop`, 1-3.5 GB) of finished parents can be deleted.

## 7. Where things are
- `tools/gto_spot/`: `spot_loop.py` (v4 loop), `hu_spot.py` (HU subgame solver), `quick_spot.py` (quick records), `plan_a_flat_specs.py`, `run_quick.sh`, `plan_a_parent_run.sh`, `export_parent_chart.py`, `plot_rfi.py`,
  `pushfold_record.py`, `grade_spot.py` (labels; `--relabel` applies amendment 12), `precision_pass.py` (P144), backup / restore / install scripts.
- `data/gto_spot/plan_a/`: configs (`cfg_p40_v1`, `cfg_p100_v1`, `cfg_p60_v2b`, ...), specs, `progress/` (resume state), `transfer/` (dumps + equity table + SHA256SUMS).
- `data/gto_spot/quick/`: results (README = map). `data/gto_spot/records/`: graded records and `s60.json`.
- Other branches: `claude/pushfold-10-25-20261019` (011TJ: 10-25 bb push/fold, 30 / 40 bb parents, `s30.json`, `s40.json`); `test3` (T2 side: connection code, `docs/T2_HANDOFF.md`).
