# Resume manual: 30 bb flat-call pot loop (session 011TJw..., branch claude/p30-flat-20261019)

Written 2026-10-26 04:10Z so another session (or this one after a token reset) can continue without the chat. Update the status table
(section 3) at the end of every big step. Companion docs: docs/GTO_STACK_30_40_V1.md (30 / 40 bb parent trees), docs/GTO_PUSHFOLD_10_25_V1.md,
docs/GTO_SESSIONS_BOARD.md (on chatgpt/terminal-census-v2-20260930), docs/GTO_SESSIONS_BOARD_011TJ_FLAT30_STATUS.md (board text, same branch as this file).

## 1. What is being computed and why
User decision (2026-10-19 / 20, relayed by the T2 sessions and confirmed in the 011TJ chat): the 30 bb parent tree (`s30`, symmetric stacks) keeps the
*static continuation* for flat calls, so BB defence vs an open (and the SB limp pot) is wrong (BB fold ~0 %). Fix = run the Plan A loop (HU subgame +
24-board flop panel, rule v4, damping 0.5) on the pots that reach the flop. One spot = one opener (or the SB limp) vs the BB; below the root the parent
tree (fold / call / 3-bet / jam), three flop terminals per step: flat call, BB 3-bet 7 + call, BB 3-bet 8 + call. 4-bet-and-later is out of scope.
Grade `quick`: converged -> that step; else mean of the last 2 steps (BTN and CO ran to convergence; the other spots have a **3-step cap**, user decision 2026-10-20).
No P144. Records are never verified; T2 runtime connection needs user approval (T2 sessions connect, not this one).

## 2. Environment (if the container is new)
Everything below lives under /home/user (scripts hard-code /home/user/t2 and /home/user/gto_ckpt).
1. `mkdir -p /home/user && git clone --branch claude/p30-flat-20261019 https://github.com/jiyul-git/t2 /home/user/t2` (large repo, allow 10 min).
2. **Python 3.11 only** (3.12+ breaks bit reproducibility): `uv venv -p 3.11 /home/user/py311 && uv pip install -p /home/user/py311/bin/python numpy==2.4.6 matplotlib`;
   every command: `export PATH=/home/user/py311/bin:$PATH`.
3. Build the panel solver: `cd /home/user/t2/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel` (~2 min).
4. Inputs: `cd /home/user/t2 && sh tools/gto_spot/plan_a_install_inputs.sh` (equity table + v2b dump; must end with `PLAN_A_INPUTS_OK`).
5. The 30 bb parent dump is NOT in this branch (59 MB). Restore it from the push/fold branch and check the hash:
   `mkdir -p /home/user/gto_ckpt/plan_a/p30_v1 && git fetch origin claude/pushfold-10-25-20261019 && git show origin/claude/pushfold-10-25-20261019:data/gto_spot/stack3040/runs/s30/dump.jsonl.gz | gunzip > /home/user/gto_ckpt/plan_a/p30_v1/dump.jsonl`
   `sha256sum /home/user/gto_ckpt/plan_a/p30_v1/dump.jsonl` must be `f8cc8ea5bbb8140bdd949b959119a7e75d84d313ce23323aa12b702b157e3671`.
6. Reproduction check before any compute (each ~6 min): `python3 tools/gto_spot/plan_a_repro_step0.py data/gto_spot/plan_a/specs/p60v2b_co_vs_sb_3b40.json 0 AcKc6c /home/user/gto_ckpt/repro/v2b`
   -> term0 `d221ccbed8f7a395434b7f6bf0a1b0ba93b6b82bc60dfca0e6475d987ea81236`, flop `e73299315861596844dea56152413dd3252bd2230f137b71de234948ebffabc6`. Mismatch -> stop and report.
7. Helper scripts (not tracked elsewhere): `mkdir -p /home/user/gto_ckpt/watch && cp tools/gto_spot/resume30/*.sh /home/user/gto_ckpt/watch/ && chmod +x /home/user/gto_ckpt/watch/*.sh`.
   Machine used: 4 cores, 15 GB; one flop process ~2.2 GB, single thread. Workers = min(cores, (GB-1)/2); the chains below use 2 + 2.

## 3. Status snapshot (2026-10-26 04:10Z)
| spot (BB defends vs) | state | quick record (data/gto_spot/quick/) | BB root fold / call / 3-bet / jam |
|---|---|---|---|
| p30_flat_btn_vs_bb | DONE, converged step 3 (strict, no exemption) | yes, usable | 9.8 / 76.9 / 4.5 / 8.8 |
| p30_flat_co_vs_bb | DONE, converged step 3 (strict) | yes, usable | 12.7 / 78.0 / 4.9 / 4.5 |
| p30_flat_hj_vs_bb | DONE, step cap (3 steps), not converged: flat terminal passes at steps 1-2, BB fails at the 3-bet-8 call terminal | mean of steps 1-2, usable for the flat-call node only | 19.3 / 72.8 / 4.7 / 3.3 |
| p30_flat_lj_vs_bb | DONE, step cap, flat terminal passes at step 2, BB fails at the 3-bet-call terminals | mean of steps 1-2, flat-call node only | 22.5 / 70.1 / 4.9 / 2.5 |
| p30_flat_sb_vs_bb | STOPPED at step 1: flop KcTd9h unconverged at the 3x retry (4.16 % pot) in the 3-bet-call terminal (amendment 7) | step 1 only, `usable_for_t2_connection: false` | fold 33.4 / call 63.4 / 3-bet 1.4 / jam 1.8 (steps 0-1 mean was 16.7 / 74.8: not converged) |
| p30_flat_sb_limp_vs_bb | STOPPED at step 0: flop KcJhJd unconverged at the 3x retry (0.736 % pot vs 0.3) at the flat terminal | step 0 only (undamped), `usable_for_t2_connection: false` | check 64.5 / raise 3.5 35.5 (= parent static) |
| p30_flat_utg2_vs_bb | RUNNING: step 0 done; step 1 terminals 0-1 done, terminal 2 (BB 3-bet 8 call) just restarted | no | - |
| p30_flat_utg1_vs_bb | RUNNING: step 0 done, step 1 starting | no | - |
| p30_flat_utg_vs_bb | NOT STARTED (last in chain A) | no | - |
Cost: ~2.3 h per terminal at 4 workers, ~7 h per step with 2 workers (3 terminals), up to 3 steps per spot -> UTG+2 needs ~9 h (step 1 terminal 2 + step 2), UTG+1 ~14 h (steps 1-2), in parallel,
UTG ~21 h after UTG+2. Stop earlier if a spot converges (loop decision `stop: converged`).
Parent numbers for comparison (s30 static continuation): BB vs BTN fold 0.0 / call 84.8 / 3-bet 0.1 / jam 15.1; vs CO 0.0 / 89.4 / 0.3 / 10.2.

## 4. Run / resume (exact commands)
Two detached chains (A: sb_limp, hj, utg2, utg; B: sb, lj, utg1) with 2 workers each and one backup watcher per spot:
```
export PATH=/home/user/py311/bin:$PATH
/home/user/gto_ckpt/watch/go30b.sh      # refuses to start if any run_quick.sh is already running; skips spots whose quick record exists
/home/user/gto_ckpt/watch/status30.sh   # one line per spot: step dirs + flops solved in the newest terminal
/home/user/gto_ckpt/watch/wait30.sh     # waits up to ~10 min, exits 3 ("CHAIN NOT RUNNING") if the chains died
```
What happens: `tools/gto_spot/run_quick.sh` (PLAN_A_IDS = the chain list, SPOT_PANEL_WORKERS=2) runs for each id `spot_loop.py <spec>` then `quick_spot.py <id> <spot dir>`.
It is resumable: solved flops (`/home/user/gto_ckpt/spots/<id>/stepK/termJ_flops/*.json`) and `state.json` are reused. Specs: data/gto_spot/plan_a/specs/p30_flat_*.json
(`max_steps` 3 for the seven spots run after BTN/CO; BTN/CO used 8). Log: /home/user/gto_ckpt/plan_a/quick.log (`DONE <id>` when a quick record exists).
Single chain by hand: `PLAN_A_IDS="p30_flat_utg_vs_bb" SPOT_PANEL_WORKERS=4 sh tools/gto_spot/run_quick.sh`.
Rules of thumb:
- Processes die when the container restarts (and when a tracked background task passes its 2 h limit). Detached `setsid nohup` (what go30b.sh does) is not subject to the 2 h limit but still dies with the container. After any restart: `ps -eo args | grep run_quick`; if none, run `go30b.sh` again (never run it while chains are running).
- Check `status30.sh` every ~10 min while you work; a stalled count with `mem used 0` means the chain is dead.
- One flop can take hours (hard boards, e.g. KcJhJd, KcTd9h, Qc9d7d): a flop that ends unconverged at 1000 iterations is retried once at 3000 (amendment 11, ~3-4 h); if it is still unconverged and the terminal is judged (not exempt) the loop stops (amendment 7) -> that is how the two SB spots stopped. If a retry is killed mid-run, my reading of spot_loop.retry_flops (untested): the first attempt was already moved to `first_attempt/<board>.json`, so on resume the board is re-solved at the normal budget and the retry is then skipped ("already retried once"), which can turn a recoverable flop into an amendment-7 stop; so do not kill a running retry unless you accept losing it.
- Never skip or disable a test/flop to get green; never push to the census branch; no force push.

## 5. Backup, restore, publish
- The watchers (`backup_watch.sh`, copies in tools/gto_spot/resume30/) write `gto_split_backup/<id>/stepK.tgz` when `stepK/report.json` exists, `stepK_partial.tgz` + `state.json` every ~30 min while a step runs, and `SHA256SUMS`; they commit and push to claude/p30-flat-20261019 (git lock: /home/user/gto_ckpt/watch/git.lock).
- Quick records and status notes are committed by hand (`git add data/gto_spot/quick/<id>.json`).
- Restore a spot on a new machine: `mkdir -p /home/user/gto_ckpt/spots/<id> && tar xzf gto_split_backup/<id>/stepK.tgz -C /home/user/gto_ckpt/spots/<id>` for every finished step, the newest `stepK_partial.tgz` the same way (it contains the step dir and state.json), and `cp gto_split_backup/<id>/state.json /home/user/gto_ckpt/spots/<id>/state.json`; then run the chain.
- `sha256sum -c SHA256SUMS` inside the backup folder checks the archives.

## 6. Quick record semantics (tools/gto_spot/quick_spot.py)
`python3 tools/gto_spot/quick_spot.py <id> /home/user/gto_ckpt/spots/<id> [k1,k2,...]` -> data/gto_spot/quick/<id>.json. Without the step list the tool uses the final step if
converged, else the mean of the last 4 steps (it would include the undamped step 0 when only 3 steps exist) - for step-capped spots **always pass the last two steps** (`1,2`) and add
`stopped_by`, `caveat`, `usable_for_t2_connection` fields as in the HJ / LJ records. A record whose loop stopped on a flop failure (SB spots) is flagged `usable_for_t2_connection: false`.
Earlier versions of the rebuilt records are kept in /home/user/gto_ckpt/*_quick_mean*.json (not in git).

## 7. Open items needing a decision / recompute
1. **p30_flat_sb_limp_vs_bb** (no corrected value yet; T2 reverted the SB limp): the flat terminal flop KcJhJd does not converge (0.736 % pot at 3000 its, target 0.3 %).
   Options: (a) more budget for that flop - untested recipe: set `iterations` in data/gto_spot/plan_a/specs/p30_flat_sb_limp_vs_bb.json to 6000 (first attempt 6000, retry 18000: ~10-20 h for one board),
   delete /home/user/gto_ckpt/spots/p30_flat_sb_limp_vs_bb/step0/term0_flops/KcJhJd.json and its `first_attempt/KcJhJd.json`, delete step0/report.json and state.json, delete data/gto_spot/quick/p30_flat_sb_limp_vs_bb.json, rerun the chain;
   (b) user decision to treat that board as an exemption / accept the flop at 0.736 %; (c) keep the parent static value.
2. **p30_flat_sb_vs_bb**: same pattern in step 1 (flop KcTd9h in the 3-bet-call terminal 4.16 % pot). The T2 session connected the SB value from step 1 and marked it for recompute: the recompute = (a) above for KcTd9h (step 1, terminal 1), resuming from step 1.
3. HJ / LJ / (later UTG+2, UTG+1, UTG) are step-capped records: more steps (raise `max_steps`, rerun; state.json resumes) would converge the 3-bet-call terminals; the flat-call node is already stable.
4. After the chains finish: update section 3, docs/GTO_SESSIONS_BOARD_011TJ_FLAT30_STATUS.md, and tell the T2 session which records changed (BB root values above are what they use).
5. 40 bb flat-call pots are Gto제작 (01BLRH...) territory (p40_flat_*), not this branch.

## 8. User decisions that apply (do not re-litigate)
Quick-fill direction (2026-10-19), symmetric stacks, no P144, 4-bet-and-later out of scope, 3-step cap for the seven spots (2026-10-20), BTN and CO to convergence, force push forbidden,
connecting GTO data to the T2 runtime needs user approval, ICM out of scope. Standard amendments 7-12 (docs/GTO_VERIFIED_FREQUENCY_STANDARD_V1.md) apply to the loop.

## 9. Update log
- 2026-10-26 04:10Z: manual written; chains relaunched after a container restart (UTG+2 at step 1 terminal 2, UTG+1 at step 1 terminal 0).
