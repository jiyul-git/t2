# P13/P15 audit — complete-field BF and parallel worker epoch lifetime

**Base:** P8 PR #26 `0ce4ecd1ecc1e7221ea5a6f00e734aa32100d889`, including approved PR #23 actor BF metadata transport and end-to-end replay tests. All of `session.py`, `range_posterior_v1.py`, `tools/verify_pr21_actor_bf_provenance.py`, `tools/verify_pr24_p8_epoch_evidence_endtoend.py`, `bot.py`, `plan.py`, and `preflop.py` are unchanged by this P13/P15 patch.

## The bug

A parallel mini worker in `live2._table_mini` has **only the worker-owned table's players**. It receives the full-field `_frozen_field` separately. Previously `Hand.bf_details` hashed only `owner.players` while calling it `observed_field_epoch_id`. A partial worker therefore falsely reported `observed_epoch_diverged=True`, even when no real field player had changed. A sequential coordinator could see other table hands' intermediate results and report divergence while a parallel worker could not. This created provenance log differences despite matching card actions and player stacks.

## Contract — six independently meaningful fields

| Field | Meaning |
|---|---|
| `field_snapshot_id` | SHA of the **captured** complete PID→chips map and snapshot hand/level. It identifies an historical reference, not its freshness. |
| `observed_field_epoch_id` | SHA of the **actually and completely observed current field roster** and the actual observer hand/level. **None** if roster is partial/unavailable or intentionally not read during a frozen simultaneous round. |
| `observed_epoch_diverged` | A three-valued comparison: `True` for two known and unequal IDs; `False` for two known and equal IDs; **None** when either epoch is unavailable. Never equate unknown with false. |
| `snapshot_epoch_exact` | True only when the underlying complete PID/chips historical snapshot is validated and used in exact-size (≤9) generic prize ICM — includes valid frozen round reference; does not imply *current* exact. |
| `snapshot_current` | True only when validated against a full, current field observation (or a mathematically complete single live table); always false for frozen-round reference, unobservable, stale, expired. |
| `is_exact` | True only for validated **decision-current generic field BF** (or full table). False for a valid historical frozen reference BF, empirical fallback and any unverified state. It NEVER claims spot-specific win/lose/tie call payout EV. |

New independent classification: `field_observation_status` distinguishes `verified_full_current_roster`, `incomplete_current_field_roster`, `frozen_reference_not_current`, `frozen_clock_mismatch`, `frozen_reference_released_or_replaced`, and `no_epoch_attestation`. `field_epoch_status` distinguishes `current_verified`, `stale_remote`, `stale_clock`, `unobservable_partial_field`, `frozen_epoch_reference`, `expired_frozen_epoch`.

### Frozen batch lifetime

`Field.step_others(simultaneous=True)` captures one complete `_frozen_field` then releases it in `finally`. Its **same object**, exact `epoch_id`, exact `hand_no`, and exact `level` must all match `Hand.bf_details`' saved reference and live owner hand/level. A stale retained reference crossing **hand 0→1** or **level 1→2**, or a released/replaced object, is `expired_frozen_epoch`. The numeric valuation then uses the unchanged existing empirical `field_bf()` curve with the reason `frozen_snapshot_lifecycle_expired`, not an invented "observed remote mismatch".

During a normal active frozen batch, **neither sequential coordinator nor parallel partial workers compute any observed-current field hash**: both use the same captured full PID/chips/hand/level reference for the same generic BF and **identical metadata**. The frozen method is `frozen_epoch_reference_icm` with `snapshot_epoch_exact=True`, but `is_exact=False` and `snapshot_current=False` for latest field ICM. If the frozen epoch is no longer active, *only* a complete observed roster may support new current exact status. Outside frozen scope, actual remote-only stack mutation remains `stale_remote` with empirical BF and observed unequal epoch IDs.

### Live2 HERO time vs synchronous finish

`live2.build_hand()` stamps HERO at the beginning of the HERO action. **Separately**, `live2.finish(defer_others=False)` first commits HERO outcome to `f.players`, then calls `f.step_others(settle=False, simultaneous=True)` to create a *new* frozen round-start reference for other tables. These two phases are **not proven to share a common epoch**. No semantic rewrite, RNG draw or scheduling reorder is made.

The result archive's new `field_epoch_timing` record (metadata only) includes `hero_hand_start_epoch_id`, `hero_hand_start_phase=before_hero_hand_action`, `other_tables_reference_epoch_id`, `other_tables_reference_phase=after_hero_hand_completed_before_other_table_work`, `common_start_epoch_verified=False`, `execution_path=synchronous_after_hero`. For deferred/vclock paths, an unobserved synchronous-other epoch is represented by **None** and a distinct phase marker, never fabricated.

The test `tools/verify_p13_parallel_epoch_lifetime.py` exercises actual `live2.finish(defer_others=False)`, captures the archived record without writing user files, and confirms the other-table frozen ID differs after controlled HERO chip changes.

### Approval gate

Required: `verify_parallel_table_processes.py 18 0 11` **and** `27 0 11` including byte-normalized bot-log and final state parity; hand 0→1 and level 1→2 with retained frozen object; live2 synchronous timing; complete/partial roster; PR #26 normal and incomplete MC `range_provenance`, empty-range replay and actor BF evaluation phase; P9 sample validity, P5 all-in, HAND130 tie/partial call, global RNG and paired ON/OFF actions.

**No merge** into PR #21/#24/#25/#26/test3/production until P15 and P8 independently approve this combined patch. Legacy `field_bf()` empirical constants, new BF floors, conditional range defaults, actor action policy and tournament execution order remain untouched.
