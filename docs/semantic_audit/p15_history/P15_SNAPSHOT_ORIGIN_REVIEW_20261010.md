# P15 — snapshot origin follow-up (2026-10-10 KST)

Base: PR24 `75c6ee2db50a06a0f3141835f063695c26c6ebc7`.
Branch: `chatgpt/p15-snapshot-origin-audit-20261010`.
This change records existing valuation origins; it does not unify them or change policy, settlement, table ordering, seeds, time-bank rules or worker ownership.

## Actual producer and consumption times

| Path | Snapshot creation | Consumption | Classification / new `field_snapshot_phase` |
|---|---|---|---|
| `live2.step` -> `build_hand` (split HERO) | Saved `st.field` after new-hand number/level setup and before HERO actions | Rebuilt HERO HandRun; unmerged remote results are unavailable | `hero_hand_start_observed_field` |
| `build_hand` (one table) | `stamp()` reads currently loaded complete table field | Current HERO HandRun | `field_observation`; no split-table frozen marker |
| `finish(defer_others=False)` | HERO final stacks copied to `Field`, button advanced, then `step_others(simultaneous=True)` captures a NEW baseline | Other tables only, until batch release | `post_hero_settlement`; NOT the HERO start epoch |
| `Field.step_others(simultaneous=True)` direct | After plan/seed allocation, immediately before scheduled table play | All hands in that other-table batch; released in `finally` | `other_tables_batch_start`; no claim that caller included HERO in this baseline |
| `Field.step_others(simultaneous=False)` | Fresh `stamp()` per bot hand, after earlier completed tables | Individual bot hand | `field_observation`; sequential observation, no common frozen baseline |
| `compute_others(field_dump)` direct | Loads supplied input, then freezes other-table batch | Other-table batch; collect/balance after it | `legacy_input_field`; helper cannot infer the input's external chronology |
| Legacy `resume_others` / missing `others_base` recovery -> `compute_others` | Saved post-HERO field passed to helper | Other-table recovery batch | `legacy_post_hero_input` |
| `compute_others_parallel(round_base)` | Loads retained round-start dump, then freezes other-table batch | Sequential simultaneous runner or per-table process tasks | `round_start_other_tables`; same input epoch as deferred HERO |
| `finish(defer_others=True)` / `_resume_parallel_others` | NO new valuation snapshot at merge | Ownership overlay of ready results, then collect/balance | Merge preserves original sources; rejects wrong base key / ownership |
| `compute_vclock_ahead` | Full observed field at precompute call | Independent per-table tasks, possibly multiple speculative hands | `vclock_precompute_batch_start`; its `clock` is batch input clock, NOT event end time |
| `_vclock_table_task` / coarse task | Receives that frozen baseline | Own table clock and level evolve; stops at elimination/H4H barriers | Same precompute baseline, not a new global snapshot per event |
| `apply_vclock_events` | NO valuation snapshot | Completed events only, ordered by `(end, tid, index)` at publication boundary | Event `end` is completion time; separate from baseline clock |
| Next HERO after publish / movement | Reconstructs field from committed state | New HERO HandRun | New observed-start epoch; does not retroactively alter active HERO |

`epoch_id` remains PID/chips + hand/level. A phase tag is explanatory provenance, not extra RNG input or a different mathematical ICM identity. Two producer phases can have the same ID if their state truly matches; equality is tested, never presumed.

## Logging contract

- Context -> Hand -> `pf_bf_provenance` carries `field_snapshot_phase` and `field_snapshot_clock`.
- HERO archive `field_context` carries baseline ID, phase, hand, level, clock.
- Bot summary and detailed logs carry `field_snapshot` with those five fields (also for preflop-only hands).
- Frozen BF reason is `frozen_reference_epoch_not_decision_current`, removing the unsupported universal common-round wording.
- No `is_exact=True` or current-field claim is added for a frozen reference. The observed-roster/lifetime defects belong to P13 and remain visible in the required gates.

## Reproduction environment

Local: Linux 6.18.44 x86_64 / glibc 2.39, Python 3.12.14.
The paired verifier starts fresh subprocesses/state namespaces, fixes `PYTHONHASHSEED=0`, `T2_TABLE_WORKERS=1`, and separately tests `T2_TIMING_V1=off` and `on`.
Without fixed hash seed, packed read-history ordering differs between subprocesses; this is an environment control, not a strategy repair. Only newly added provenance and nondeterministic `telemetry_session_id` are excluded from paired comparisons. Cards, chip results, action logs, RNG states, field book, clocks, banks, ranks, busted order and seats remain compared.

```bash
python3 tools/verify_p15_snapshot_origins.py
python3 tools/verify_parallel_table_processes.py 18 0 11
python3 tools/verify_parallel_table_processes.py 27 0 11
python3 tools/verify_p15_frozen_lifetime.py
python3 tools/verify_p13_field_epoch_freshness.py
python3 tools/verify_parallel_tables.py
PYTHONPATH="$PWD" python3 ui/tools/verify_vclock_finish_ownership.py
PYTHONPATH="$PWD" python3 ui/tools/verify_async_refill.py
```

The two UI test launchers need the target repository on PYTHONPATH: the current setup shell omits `range_posterior_v1.py`. This audit did not repair that separate packaging issue and does not claim a standalone installation PASS.

## Initial local results on PR24 (historical, before P13 lifetime fix)

- Origin + paired behavior gate: PASS. 27 players / 3 tables / seed817, 3 rounds each in default, deferred and vclock modes, both timing OFF/ON. Game states, action logs and field/hand RNG match unmodified PR24. Rank/order/seats/banks are included; the fixture does not prove that every possible multiway elimination tie is exercised.
- Default HERO/bot epochs differ as witnessed; deferred HERO/other epochs match; vclock reports its independent precompute origin.
- 18-player worker parity: PASS, but only one non-HERO table, hence insufficient.
- REQUIRED 27-player worker parity: FAIL. Players/tables/tilt/book/notes match; BF observed-epoch provenance differs because process mini-fields contain only local players. The gate retains exact log comparison; no metadata suppression/xfail is used.
- Lifetime boundary gate: release PASS; hand-number and level transitions FAIL (`frozen_epoch_reference` survives).
- Existing P13 epoch contract, ownership merge, vclock finish ownership and async refill/break/H4H/bust/movement gates: PASS.
- Evidence: `evidence/P15_SNAPSHOT_ORIGINS_20261010.json`, `evidence/P15_FROZEN_LIFETIME_20261010.json`.

## CI and remaining approval

PR24's original CI run38045277420 is SUCCESS on75c6ee2d, but runs only the 18-player parity case. This is not evidence that the 27-player or lifetime gates passed.
The local P13 workflow change requires 27-player parity and frozen-lifetime gates on this audit branch. The branch upload was rejected by automatic approval review as an external upload/remote mutation beyond the verification request; therefore these additions have NOT run on GitHub CI. The lifetime gate uses `!cancelled()` so the provenance failure does not skip it. Neither gate is allowed to fail silently.

At the initial follow-up check, PR24 still pointed to75c6ee2d and P13/P8 integration pointed tob3e8e9ca; P13's requested lifetime/partial-roster fix was not yet published. After its exact SHA is available, apply this metadata-only change in an isolated integration and rerun the SAME scripts, recording the integration SHA and actual CI result. No approval is inferred from older CI or from an unpublished fix.

P15 does not mandate replacing the legacy chronology with the deferred chronology: that would change the available decision information. This follow-up preserves existing semantics and labels them accurately. Common-start unification requires a separate paired behavior study across eliminated players/ranking/table movement/banks/RNG, rather than silently reordering finish.

No merge or production deployment is performed.


## Follow-up after published P13 lifetime fix — completed

The final read discovered P13 original fix `e82f5e978fc4da5c229b01f0cf164a058b15562d` and its PR26/P8-integrated revision `263564edaec23f0fd76c950ec8e5c096e2089b74`. An isolated LOCAL worktree `chatgpt/p15-snapshot-origin-lifetime-20261010` was created from263564ed and the two P15 commits were applied there. The one test conflict was resolved preserving P13's UNKNOWN observation assertions (`None`), with P15's generic frozen-reference reason. No GitHub PR was merged.

Runtime tested checkpoint: `b9097dad` (263564ed + P15 origin logging). Subsequent changes only document evidence and enable the future CI branch.

| Same gate | Original PR24 / P15 origin-only patch | After P13 fix + P15 isolated integration |
|---|---|---|
| 27 players / 3 tables, worker1 vs worker8, seed11 | FAIL: observed-epoch log difference | PASS: final states and full normalized bot logs identical |
| Frozen release | PASS (old path could relabel unchanged field current) | PASS (`expired_frozen_epoch`) |
| Hand0→1 with retained frozen object | FAIL | PASS (`expired_frozen_epoch`) |
| Level1→2 with retained frozen object | FAIL | PASS (`expired_frozen_epoch`) |
| HERO post-result vs start reference logged separately | PASS after P15 metadata | PASS also in P13 `field_epoch_timing` archive |
| 27-player, seed817, 3 modes ×3 rounds × timingOFF/ON vs75c6ee2d | PASS | PASS: actual action logs, cards/chips/state/banks/ranks/seats and RNG preserved |
| 18-player parity, P13 freshness, ownership merge | PASS | PASS |
| Vclock finish ownership and async refill/break/H4H/bust/movement | PASS with explicit PYTHONPATH | PASS with explicit PYTHONPATH |

Also ran `python3 tools/verify_p13_parallel_epoch_lifetime.py`: PASS including partial-vs-complete roster provenance, clock expiry and actual synchronous-finish archive. Unknown remote current epoch is `None`, not a fabricated equal/different comparison. Existing nonfrozen full-roster remote-change detection remains intact.

Evidence is separately retained in `P15_SNAPSHOT_ORIGINS_AFTER_P13_20261010.json` and `P15_FROZEN_LIFETIME_AFTER_P13_20261010.json`; original FAIL evidence was not overwritten.

**CI distinction:** P13 revision263564ed's remote workflow run38048997098 (P13 P15 Full-Field Epoch and PR26 Provenance Contract) is SUCCESS and includes the mandatory27-player case. This was independently retrieved from GitHub, not inferred from local PASS. P15 additions / isolated local integration are NOT uploaded and have NO remote CI result because upload was rejected by automatic approval review. Do not label that as CI failure or CI success.

P15 approval: published263564ed's lifecycle/partial-roster/synchronous-origin correction passes the independently rerun scope. The added origin tags and scripts pass LOCAL review; their final remote integration still needs its own head-specific CI. This is not an overall P5/P8/project merge authorization. Merge and deployment remain on hold. No new constants, timing rules, RNG draw or scheduling reorder was introduced.
