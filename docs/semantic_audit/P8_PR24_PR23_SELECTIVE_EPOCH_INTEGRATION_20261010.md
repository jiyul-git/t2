# P8 selective integration — PR24 field epoch and PR23 observed actor BF evidence

**Exact integration base:** PR #24 `75c6ee2db50a06a0f3141835f063695c26c6ebc7` (P13 field epoch, includes PR21 P9/ICM).  
**Selective source:** PR #23 `4dff6388ede3fe716d19741280193c96000915fe` (P8 actor BF evidence).  
**Original combined PR21:** `0a45af4ce79faf13d78824448f2e1b8943b4518e`.  
**Release gate:** draft only; conditional range `T2_RANGE_CONDITIONAL_V1` default OFF. No PR16/test3 merge or operating deployment.

## Merge discipline

This is NOT an automatic branch merge and **session.py was not replaced** with the PR23 version. The branch starts from the immutable PR24 HEAD, with narrow `session.py` additions for evidence **after** PR24's already-correct `h.bf_details(target)` call. `play.py`, `icm.py`, `fieldsim.py`, `context.py`, `bot.py`, `preflop.py` and `plan.py` remain bit-for-bit PR24. PR24's full-field `field_snapshot_id`, remote-owner epoch verification, `field_epoch_status`, `snapshot_epoch_exact`, `snapshot_current`, observed epoch identity and frozen reference semantics remain P13-owned.

## Data contract

`session.HandRun._preflop_perceived_range()` already uses P13 `h.bf_details(target)` exactly once and sends `value` to the actor-policy likelihood. P8 preserves its original returned dict as `actor_bf_provenance` without changing values or applying new gates:

- `actor_bf_evaluation_phase='observer_reconstruction'` identifies when BF was evaluated.
- `actor_action_epoch_bf_verified=False` states that the observer's reconstructed actor BF is **not** independently verified to equal that actor's BF when the earlier public action happened.
- `actor_bf_evidence_source='Hand.bf_details(target)'` (or `legacy_scalar_without_epoch_evidence` on PR24's legacy adapter) identifies actual evidence.
- `actor_bf_likelihood_direct_input` is true for supported first-in/open action-policy likelihood and false for threebet/unsupported legacy fallback.

The same fields persist on complete conditional posterior, incomplete `missing_evidence`, and `model_unavailable`/unvalidated `legacy_fallback`. The original `source`, `missing`, `complete`, reason and full `observer_model_inputs.actor_bf_provenance` stay unchanged.

`session.layer_equities_by_pot_layer()` adds `range_provenance` **for complete MC layers and for incomplete/missing opponent ranges**; it never alters their weights, sample seed, counts, variance, tie records or completion decisions. `_layer_investment_summary()` includes the same evidence in `incomplete_reasons[idx].range_provenance` if a pot's equity is incomplete. The existing final `pf_opp_range_meta`, `pf_call_ev_shadow.range_model_evidence`, and `pf_calloff_consumer.opponent_range_evidence` carry it into P5 logs. The decider's `pf_bf_provenance` stays **separate**.

`range_posterior_v1.replay_record()` retains its current per-combo `weights`, `support`, `mass`, SHA-256 and `source_metadata` unchanged, and **adds top-level `range_metadata`** for all reported seats, including a failed opponent whose combo pool was correctly rejected and thus does not appear under `opponents`. No false numeric equity is invented.

## P13 snapshot states (must not be conflated)

- `field_epoch_status=current_verified`: a PID/field epoch verified current can use complete-field ICM; `snapshot_current=True`, `snapshot_epoch_exact=True`, `is_exact=True` if all separate conditions pass.
- `stale_remote`: another table's stack change invalidates the original snapshot for decision-current claims; P13's existing empirical fallback returns `is_exact=False`.
- `frozen_epoch_reference`: frozen common-round ICM is exact **as a reference epoch** (`snapshot_epoch_exact=True`) but **not the live decision-current field** (`is_exact=False`, `snapshot_current=False`). Its numeric BF remains unchanged by later remote changes in that batch.
- `live2` common-round provenance is validated by P13's existing regression; P8 does not implement or reinterpret field ownership/epoch logic.

The new `tools/verify_pr24_p8_epoch_evidence_endtoend.py` uses real P13 Field/Hand attestations for current, remote-stale and frozen-reference cases, then passes the exact original four epoch fields all the way through a **successful** weighted MC pot, an artificially incomplete pot with a rejected nonempty candidate, the final P5 `opponent_range_evidence` and the **empty-combo** replay record. It asserts `actor_action_epoch_bf_verified=False` and keeps hero `pf_bf_provenance` separate.

Also run unchanged `tools/verify_pr21_actor_bf_provenance.py` from PR23 at the new combined code, to assert provenance-only changes don't affect combo weights, BF-value changes can affect first-in shove, fixed-profile threebet shove is BF-independent, weighted 845 support/mass, replay/layers/final P5, missing/legacy and RNG. This is not reconstruction of the missing original HAND130 288-combo posterior.

## Re-test and signoff boundary

CI requires PR24 P13 remote-only/frozen/live2 validation; parallel/sequential worker replay; P9 accepted/rejected MC and valid-zero vs None; P8 ON/OFF, weights and legacy failure provenance; P5 calloff and HAND130 odd-chip/tie/partial-call; and paired OFF and ON seed-11/12 full fingerprints **against unchanged PR24**. Exact results and full workflow URL are supplied in PR details after CI.

**Required remaining reviews:** P13 must independently reconfirm epoch correctness on this final SHA; P5/P17 verify combined consumer and release gates. **Passing P8 CI is not P13 approval or authorization to merge/deploy.** No new empirical constants, forced minimum ranges, AA-specific exceptions, equity floors, actor private-data inference or policy formulas are introduced.
