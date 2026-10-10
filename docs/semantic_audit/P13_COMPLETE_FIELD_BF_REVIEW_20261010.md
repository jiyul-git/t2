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
