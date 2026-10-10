# Department 8 — PR21 observed-actor BF provenance propagation

**Parent integrated production SHA:** `0a45af4ce79faf13d78824448f2e1b8943b4518e` (PR #21; draft).  
**Independent blocker report:** `da6764d2e3d7199525973386cb89fb5eef5f4edc` (audit PR #22).  
**Scope:** ONLY observed-actor BF source/provenance. This does **not** resolve P13's separate all-tables snapshot freshness/epoch issue. Do not merge or deploy until that review concludes.

## Defect and fix

Before: `session.HandRun._preflop_perceived_range` provided the BF number using `h.bf(target)`, then logged `observer_model_inputs.bubble_factor` only. The full-field ICM vs empirical distinction (P13 `Hand.bf_details(target)`) was not attached to the opponent posterior. The existing `pf_bf_provenance` belonged to the **deciding hero seat**, not the reconstructed actor `target`.

After: the optional, default-OFF `T2_RANGE_CONDITIONAL_V1=1` path calls **`h.bf_details(target)` once** at the observer's preflop reconstruction decision. `_ctx['bubble_factor']` receives exactly `_actor_bf['value']`. It attaches the full unrounded details to `actor_bf_provenance`, and copies it into `observer_model_inputs.actor_bf_provenance`. The metadata explicitly identifies `actor_bf_evidence_source=Hand.bf_details(target)`, `actor_bf_evaluation_phase=observer_reconstruction`, and `actor_action_epoch_bf_verified=False`. It distinguishes `actor_bf_likelihood_direct_input=True` for first-in shove/ordinary open from `False` for 3bet/unsupported legacy fallback.

The evidence payload retains **every field returned by P13** (including future timestamp, field-wide sequence/freshness tokens) without renaming or deriving their meaning. For early unavailable/not-applicable P13 methods that omit certain keys, only the required unobserved keys are filled with `None`; the original method/value/is_exact/reason remains unchanged. Standard fields include `value`, `method`, `is_exact`, `reason`, `field_completeness`, `snapshot_alive`, `snapshot_current`, `bf_kind` and `price_specific`. This is not certification that an observer's current reconstructed actor BF is historically equal to the actor's BF at the time of the original public action.

The full `actor_bf_provenance` survives:

1. Supported conditional posterior: `_new_meta.actor_bf_provenance` and `observer_model_inputs.actor_bf_provenance` even if the posterior returns `complete=False` / no combos.
2. Unsupported public action: `source=legacy_fallback`, `failure_kind=model_unavailable`, `complete=False`, with the actor BF evidence kept and no false conditional-model confidence.
3. Pot layers: `range_provenance` for the opponent in every eligible layer, including **complete sampled equities**. Existing `missing_range_details` still holds failed model evidence; `_layer_investment_summary.incomplete_reasons` carries `range_provenance` when failure prevents EV.
4. Replay: original per-combo `weights`, `support`, `mass`, SHA256 and `source_metadata` unchanged; new top-level `range_metadata` also records *missing/no-pool* actor evidence, which the legacy `opponents` map could not represent. Each layer's `range_provenance` is recorded in `layer_sampling`.
5. Final P5 seed: `pf_opp_range_meta`, `pf_calloff_consumer.opponent_range_evidence`, and `pf_call_ev_shadow.range_model_evidence` already carry full metadata through the previously working P8 path. `pf_bf_provenance` remains separately owned by the deciding seat; it is **never replaced by the opponent's BF**.

## Invariants and test authority

The new `tools/verify_pr21_actor_bf_provenance.py` tests:

- P13 real complete 8-person PID snapshot vs existing missing-full-field empirical source, including exactness and `price_specific=False`.
- Numeric BF value used by the model **equals** BF provenance value; the old `h.bf(target)` call is prohibited inside the ON path.
- Equal BF numerical value but different method/reason/snapshot info yields **bitwise-equal** weighted combo dict, signature, mass and support. These synthetic same-number cases are intentionally **not claimed to be physically identical ICM states**.
- Changing BF value on the same first-in public shove at 18BB/21BB changes the existing actor-policy weighted posterior. Reconstructed 3bet-shove, same public event + perceived profile, does **not** depend directly on numeric BF; its evidence still records the actor BF snapshot provenance as context only.
- All poster weights, full-precision JSON replay, MC seed/counts/variance/tie info remain intact; complete and failed pot layers carry actor BF source to P5. Unavailable 0/partial sample contracts remain unchanged.
- `call_allin` legacy fallback and `missing_evidence` paths preserve the source but remain incomplete. P5 hero's own BF source remains distinct.
- Default OFF never calls observed-actor `bf_details` through this range path; global RNG unchanged. Historical HAND130 original 288 weighted combos **not reconstructed**.

The CI workflow also runs P8/P5/P9 prior contracts, P13 odd-chip/partial-call terminal ICM, independent exact/incomplete BF regressions, and paired default-OFF seed-11/12 full-hand JSON fingerprints. P5, P9, P13 code blobs (`bot.py,icm.py,preflop.py,play.py,plan.py,fieldsim.py,context.py`) are deliberately **unchanged** from PR21 parent.

## Integration contract with P13 snapshot epoch update

1. Keep this P8 patch on its isolated branch; PR21 stays DRAFT/OFF. P13 independently implements its field-wide snapshot epoch/freshness evidence and defines the *valuation* epoch for every table in simultaneous play.
2. On the P13-integrated HEAD, **apply the selective P8 hunks** in `session.py` (`h.bf_details(target)` source, `actor_bf_provenance` posteriors, complete/incomplete layer propagation), plus `range_posterior_v1.replay_record` all-range metadata and regression tests. Do **not** overwrite P13's new `icm.py`, `fieldsim.py`, `context.py`, `play.py`, or snapshot logic.
3. Because `actor_bf_provenance` copies P13's returned `bf_details` dict rather than reconstructing labels, new epoch/freshness fields should pass through **unchanged** into range metadata/replay/P5 logs. Extend the regression to verify same snapshot epoch at the observer's likelihood computation and ensure remote stale/unverified snapshots are *not* labeled `is_exact=True`. Do not silently infer actor action-time BF from a later observer-time value.
4. Rerun all P8/P9/P13/P5 CI on the **new combined immutable SHA**, with independent review. Default feature flag stays OFF and no PR16/test3 merge or operational release.

No new experience constants, probability floors, minimum defense ranges, AA-special cases, solver imports, or changes to production payout/ICM rules.
