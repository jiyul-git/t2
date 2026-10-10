# P13 — Complete surviving-field BF guard (PR #16 baseline)

**Base:** `54e879863d7d1ef08a14079289f0822e6995b1e2` (PR #16); branch `chatgpt/p13-complete-field-bf-20261010`. **No merge or production activation implied.**

## Why the previous result was mathematically invalid

Prior `icm.table_bf(stacks, seat_idx, remaining,...)` used exact payout ICM whenever `remaining <= 9`, but `stacks` contained only the active seats at the local table. A five-player table in an eight-survivor field incorrectly became a five-way ICM problem using an eight-place prize table. The wrong result depends on table assignment even though the tournament's surviving-stack set has not changed.

For the archived HAND130 starting stacks, a synthetic partition with table seats `[1,3,5,8,9]`, seat 3 as B37 and three survivors on another table gives **3.0391747926446717** for the erroneous local-only exact BF, compared with **3.465325154547401** when all eight stacks are included (same risk rule and same payouts). This is a classification error, not an invitation to adjust a constant.

## New exactness contract

`table_bf(..., field_stacks=None, return_details=False)` retains the numeric BF default interface. `Hand.bf(s)` remains a float for every existing P5/other consumer; `Hand.bf_details(s)` and `return_details=True` expose evidence and source.

- `method=exact_full_field_icm` and `is_exact=True` ONLY if `remaining == live_table_count` (entire field seated here) OR `remaining == len(field_stacks)` AND each full-field snapshot stack is finite and positive AND the multiset of table stacks is contained in the multiset of field stacks.
- Duplicate stack values count with multiplicity and are mathematically exchangeable in payout ICM. Exact payout ICM uses the field-stacks vector and the matched hero stack index.
- `fieldsim.FieldSim.field_snapshot()` already records all positive stacks at the hand-start snapshot; `stamp()` already provides `field_stacks` through `context.SPEC`. No invented external-table stacks are inferred.
- If no complete, matching field snapshot is available with another table still alive, `method=field_bf_empirical_approximation`, `is_exact=False`. Keep the existing `field_bf()` curve using the actual `remaining`, `itm`, `field_avg_stack`, `payout_flat` inputs. If even the whole-field average is unavailable, the method explicitly tags `field_average_source=local_table_fallback_not_field_average`; this is weaker evidence.
- `remaining > 9` always uses the pre-existing empirical curve even if all stacks are known, since this exact engine's 9-player limit is a computational boundary.
- During a hand, local stacks can move after the hand-start field snapshot (blind, bet, pot allocation); then the multiset contract fails and reverts explicitly to approximation rather than pretending this is a contemporaneous exact ICM. Future work would need a full field/player-ID snapshot at the same decision boundary for exact postflop valuation.
- Missing `remaining`/`itm` was already a `Hand.bf()==1` legacy no-tournament-context early return, now separately tagged `method=unavailable_tournament_context`; **this fix does not add a BF=1 fallback for split tournament fields**.

### Heuristic `field_bf()` is not validated exact ICM

Existing constants `_SIGMA_STAGE=.55`, `_SIGMA_HI=.63`, `_SIGMA_LO=.89`, `_LADDER_W=.95`, `_LADDER_P=1.60`, `_K=1.50`, `_FLAT_GAIN=.95` construct smooth stage/stack/flatness signals. The comments explain intended qualitative behavior (bubble peaks, larger stacks different pressure, satellite payout flatness), **not a dataset-calibrated or outcome-equivalent BF derivation**. Their clipping to `[1,4]` and dependence only on field average, remaining count and payout flatness cannot capture exact ladder jumps, individual opponent stacks, or a spot-specific call price. No constant has been added or retuned here. The approximate result is an explicit unresolved model limitation, not a mathematically proven call/fold threshold.

## Interaction with department 5

- No edits to `plan.py`, `preflop.py`, `persona.py`, or `icm.required_equity()`; scalar BF decision interface remains the same.
- `session.HandRun._run` records read-only `pf_bf_provenance` on the plan seed and passes the same BF numeric value to the existing plan parameter. Changes in objective BF from correcting field membership can still legitimately change generic nonterminal decisions; 5번 must review these decision differences.
- In HAND130 all eight survivors are on the table, so objective BF remains **3.465325154547401** and spot-specific terminal HU ICM remains **37.15371093145927%** no-tie price (equivalent spot BF ~1.1996025358246731). Saved opponent posterior and finite-MC uncertainty remain outside this change.
- P8 optional conditional opponent posterior may use `h.bf(target)` as a prior-policy input. Full-field completeness changes this context in split endgame tournaments; 8번 review should verify its behavior on identical public information.
- The previous general-BF approximation remains mathematically approximate outside verified terminal HU outcome-specific ICM. Do NOT convert this into an AA or skill override.

## Reproduction and approval gate

`python3 tools/verify_p13_complete_field_bf.py` checks old 5-seat BF versus full 8, complete and missing snapshots, invalid snapshot membership/length, duplicate stacks, >9 curve, Hand integration, and a *derived midpoint* synthetic equity in the actual P5 price consumer (to show a possible justified call-to-fold change, not a reported HAND130 action). Run the existing `verify_hand130_exact_icm.py` and `verify_hand130_partial_call_icm.py` to demonstrate B37 spot-price and odd-chip regression preservation. Fixed-seed paired field actions vs original PR #16 SHA and results should be attached from CI rather than claimed without execution.

**Review requested:** department 5 for numeric BF behavioral changes and audit-only plan seed field, department 8 for observer posterior BF input on split-table endgames, and department 17 for release CI. Do not merge into PR #16, test3, or production without that review and complete regression evidence.


## 2026-10-10 P9/P8 preview-only integration (NOT upstream approval)

**Preview parent:** PR #18 `69e55fc35a208679f06409754d4b43260f9f4fe4`, which itself descends from P8 PR #16 head `71c46aa20b9eac016709d7ee835597b890c8906b`. GitHub PR #18 remains unapproved/unmerged at preview creation; do not substitute this branch for its requested upstream approval/merge.

### Strengthened time/identity contract

Previous proof by matching stack *counts* was incomplete: different players can own identical stack values and a hand-start snapshot may be stale at a later decision. The preview therefore adds:
- `fieldsim.Field.field_snapshot()` captures `remaining`, `stacks`, and **pid→stack** in one synchronous read. `context.SPEC` carries `field_pid_stacks` and `Field.stamp()` applies the same `_frozen_field` frame to the hand.
- `Hand.bf_details()` maps each current local seat to its same-period player pid and compares its stacks with immutable `_start_stacks`. If the current-table chips changed since the field snapshot, exact full-field BF is **not** asserted; an empirical method and `stale_field_snapshot` reason are logged.
- `icm.table_bf()` accepts optional `field_pid_stacks`, `table_pids`, `snapshot_is_current`; exact split-table BF needs all positive surviving PIDs and chips plus exact local PID membership. A coincidentally matching chips-only multiset does not prove that all survivors were represented.
- In complete **single-table** cases, the current table itself is the full field, so the separate frozen snapshot is unnecessary and `remaining == live_table_count` still enables generic exact-field BF.
- `bf_kind=generic_default_risk_not_spot_call_prize_ev` and `price_specific=False` are mandatory provenance distinctions even when `is_exact=True` for the underlying generic payout-ICM BF. Only the separate terminal HU payout-state calculation yields call-price-specific win/lose/tie EV.

### Preserving P8/P9/P5

The preview begins with PR #18's **entire** code tree. `session.py` only inserts the BF provenance acquisition/seed log and replaces the single planner BF float source. P8 range `source,missing,complete,model_unavailable,legacy_fallback`, P9 `valid_samples,requested_samples,incomplete_reasons,observed_sample_mean`, and P5 `unavailable_not_negative_ev` are unchanged. In particular, no `bot.py`, `plan.py`, `range_posterior_v1.py`, or `tools/compare_hand130_range_v1.py` change is introduced by P13.

Additional P13 observer sensitivity test uses existing synthetic *neutral perceived* observer profile for first-in shove; the P8 OFF legacy range does not consume `h.bf(target)`, while the ON first-in policy `_first_in_likelihood` consumes `bubble_factor` through the pre-existing depth and variance functions. A general 3bet shove's likelihood has no direct `bubble_factor` argument. This test does not reconstruct the original HAND130 opponent Book.

**Release:** hold draft P13 code until departments 5 and 8 explicitly approve PR #18 and the approved P9 code has actually been integrated into PR #16; only then re-integrate and validate against its true latest commit. No production deployment.


## PR #22 blocker resolution — field epoch/freshness and actor provenance

**Base PR #21:** `0a45af4ce79faf13d78824448f2e1b8943b4518e`.  
**P8 audit:** PR #22 `da6764d2e3d7199525973386cb89fb5eef5f4edc`.

### Three distinct meanings that must not be collapsed

1. **Snapshot epoch:** `fieldsim.Field.field_snapshot()` captures `pid_stacks`, `stacks`, `remaining`, `hand_no`, `level` and `epoch_id` (deterministic SHA-256 over player identities, chip amounts and tournament hand/level). `_frozen_field` can designate this snapshot as the common logical beginning of a simultaneous multi-table batch; it does *not* mean all other-table hands are still incomplete at a later decision.
2. **Actual locally observed latest field:** `Hand.bf_details()` compares that epoch identity to the complete **live field roster** via a transient `Field` owner reference on *every consumption*. A change exclusively on another table is detected even when all current-table stacks stay constant. This attestation does not modify the roster, event order or RNG.
3. **Price-specific outcome ICM:** `icm.table_bf()` is a default-risk whole-field BF, not an exact win/lose/tie payout EV at a particular call price. The terminal HU call ICM code remains separate.

### Method/exactness mapping

| Source/evidence | BF computation | `is_exact` for decision-current field | Reason |
|---|---|---:|---|
| All survivors in live table, internally consistent count | Existing generic field ICM | true | `complete_table` |
| Split table, PID+chip+epoch attested live | Existing generic field ICM | true | `current_verified` |
| Split table, certified `_frozen_field` common-round epoch | Same generic BF **of the frozen reference epoch** | **false** | `frozen_common_round_epoch_not_decision_current`; `snapshot_epoch_exact=true` |
| Split table, stale remote-only changes outside valid batch | Existing `field_bf()` empirical curve | false | `remote_field_changed_after_snapshot` |
| Snapshot missing/unknown/released or local chips changed | Existing `field_bf()` empirical curve | false | Exact rejection reason in metadata |

A frozen batch is *deliberately* not revalued at later workers' decision times. It remains the simultaneous round-start policy reference. Its BF value is kept to avoid making strategy depend on sequential versus parallel worker execution order. However, `is_exact=false` and `snapshot_current=false` expressly deny that it is **latest field exact ICM**. We cannot detect unmerged remote worker changes that exist only in another process; that uncertainty is why even the first worker in a frozen batch does not claim current-field exactness. The `live2.build_hand()` HERO path uses the same conservative frozen-round labeling when other tables are alive and pending. No hand scheduler ordering, effective stacks, time banks, seed sequence, or card/actor policy has been changed.

Full snapshots with no live owner/epoch attestation never prove a split-table current exact calculation, even if PID+stack counts match. A **new** confirmed field snapshot can reestablish an exact generic BF. Entire-field chip movements below the hand-start boundary of a single hand remain outside this generic BF and must be handled by the separate spot-specific outcome model.

### P8 actor-BF provenance

`session.HandRun._preflop_perceived_range` now gets `h.bf_details(target)`, uses its **unchanged numeric `value`** as `bubble_factor`, and retains the actor's complete BF method, `is_exact`, fallback reason, snapshot identity, scope and observed epoch in `actor_bf_provenance` and `observer_model_inputs.actor_bf_provenance`. This is different from `pf_bf_provenance`, which belongs to the deciding seat. Existing P9 `incomplete_reasons` and original conditional range metadata remain unchanged and are replayed as source metadata. For legacy scalar-only Hand fixtures, method explicitly becomes `legacy_scalar_without_epoch_evidence` and `is_exact=false`; no invented provenance is claimed.

### Required cross-department confirmation

**P15 (simultaneous tournament scheduler):** confirm `_frozen_field` is the common logical round-start valuation reference and never a claim of contemporaneous global stacks; work queues and commit ordering remain unchanged. **P8:** confirm actor BF provenance survives conditional posterior/replay and no numerical likelihood changes from metadata alone. **P5:** confirm generic frozen reference vs terminal spot payout ICM distinction and unchanged calloff contract. **P17:** inspect isolated CI, paired OFF/ON and real parallel worker parity before integration. This fix remains on a separate review branch and is NOT approval to merge PR #21, `test3` or production.
