# P8 independent review — PR #21 P9 MC + P13 full-field BF integration

**Immutable production-code SHA examined:** `0a45af4ce79faf13d78824448f2e1b8943b4518e` (PR #21).  
**Source PR parents:** PR #18 P9 `69e55fc35a208679f06409754d4b43260f9f4fe4` and PR #19 P13 `791ab4e771d7e239b915594f3ba65594957348d0`.  
**Integrated source CI:** [#38042964484](https://github.com/jiyul-git/t2/actions/runs/38042964484), SUCCESS.  
**P8 independent tests:** `tools/review_pr21_p8_bf_mc_integration.py`, previously audited `tools/review_p9_p8_weighted_mc_contract.py` reused unchanged, and dedicated audit-only workflow. **Zero production changes; no PR16/test3 merge.**

## Verdict: **BLOCK PR21 release/integration pending provenance/freshness resolution**

The P9 sample and conditional weighted posterior contracts remain internally sound; the combined PR21 has two distinct BF *evidence* limitations that are not covered by its green CI, so it must remain draft and OFF:

1. **Target-actor BF provenance is missing in the P8 estimated-range record.** In `session.HandRun._preflop_perceived_range`, `_ctx['bubble_factor'] = h.bf(target)` saves the **scalar only**, and `observer_model_inputs.bubble_factor` likewise saves only the numeric value. The actual basis `h.bf_details(target)`—exact full-field ICM vs existing `field_bf_empirical_approximation`, `is_exact`, snapshot status and fallback `reason`—does **not** survive in the source/metadata for the target's conditional weighted range. `pf_bf_provenance` is recorded separately **for the deciding seat**, not this *opponent* target. Therefore one cannot diagnose whether a changed opponent posterior was computed using complete-field ICM or the empirical approximation. This is an *audit/source contract problem*, not proof that the current BF scalar or sampler is wrong. Required fix: record `actor_bf_provenance` for the BF **actually passed** to the observer likelihood, preserving method, exactness, reason and snapshot evidence, without changing the input number. Ensure it propagates to replay `source_metadata`, per-layer incomplete evidence and P5 calloff logs. On complete and fallback cases prove method-only updates with same value leave weights identical.
2. **No independently verifiable remote-field snapshot epoch/freshness signal.** For split tables, `play.Hand.bf_details` calculates `snapshot_is_current` by comparing **only this table's** stacks against `_start_stacks`; `icm.table_bf` verifies full-field PID mapping and chip multisets but does not receive a field-epoch ID or a newer remote-stack snapshot. Independent negative witness creates a valid eight-survivor snapshot, then changes **only another table's** player chip stack in a separately known later state while leaving local stacks unchanged. `bf_details` still returns `method=exact_full_field_icm, is_exact=True` because the newer remote-only event is not represented in the old evidence. The API cannot detect an externally stale snapshot when that change is not passed in. This is a **possible false exactness claim when a snapshot is reused past its epoch**, not evidence of a specific stale production decision. Required resolution: P13 must document and mechanically guarantee that frozen field snapshot epoch is the proper common simultaneous valuation epoch for every hand, or attach a verified field-wide freshness/epoch identity and mark unreconciled epochs `is_exact=False` instead of claiming decision-current prize ICM.

The first blocker directly concerns P8 provenance; the second concerns P13 snapshot correctness. No new BF constants, AA exceptions, solver priors, combo floors or strategy changes are proposed.

## Independently measured BF/likelihood behavior

Using the same **public first-in shove** and neutral `reads.range_profile(None)` with no private opponent persona, changing *only the BF number* from incorrect five-seat generic BF `3.0391747926446793` to validated full-field BF `3.4653251545473682`:

| Actor stack (BB) | Old posterior mass | New posterior mass | Support old/new | Weights changed? |
|---:|---:|---:|---:|---|
| 9 | 345.5 | 345.5 | 362 / 362 | No |
| 12 | 305.7272727273 | 305.7272727273 | 336 / 336 | No |
| 15 | 275.3181818182 | 275.3181818182 | 325 / 325 | No |
| 18 | 218.1354545455 | **214.4604545455** | 336 / 336 | **Yes** |
| 21 | 126.1125 | **122.6475** | 308 / 308 | **Yes** |
| 25 | 75.6545454545 | 75.6545454545 | 325 / 325 | No |

This is a deterministic *existing actor-policy model sensitivity*; neither old incorrect BF nor newly valid BF certifies that the estimated opponent's real behavior follows this policy. Note the P13 existing single 9BB test had 0 changed likelihoods; it is not a universal zero-derivative claim.

At a **fixed scalar BF**, merely changing a description of exact/empirical provenance leaves the model's per-combo likelihoods, support, mass and signature identical: no provenance field enters `range_posterior_v1.conditioned_preflop_range`. The absence of BF provenance in the model metadata makes the *why* of differences unreproducible later.

For a fixed public **threebet_shove** context and perceived opponent profile, changing just BF 3.039→3.465 produces exactly the **same** 845 weighted combos, mass `142.02665121791807`; `_threebet_likelihood` uses `defend_action_likelihoods` and `raise_form`, neither receiving `bubble_factor`. Different **observed behavior** in future simulated hands could still indirectly result from actor policy or action histories changing; this isolated equality is conditional on the *same* event/profile.

## P9 MC and P5/P13 contracts

- `bot.equity_vs_pools`: rejects impossible draws without inventing valid 0% equity; zero/partial accepted samples yield `None`, `complete=False` and reason `no_valid_mc_samples` or `insufficient_valid_samples`. Fully valid real-zero yields `0.0`, `complete=True`. Local RNG preserves global/shared state.
- `session.layer_equities_by_pot_layer` preserves per-pot requested, valid, rejected, seed, variance, split-pot draws and incomplete reason; never flattens weighted dict to equal support; `_layer_call_summary` passes missing reasons to P5.
- `plan.preflop_plan` legal fallback `fold` on unavailable evidence has `equity_status=unavailable_not_negative_ev` and `mathematically_justified=False`, not a claimed -EV fold.
- Full-combo weights, prior/posterior support/mass, SHA-256, event source and per-layer MC audit remain replayable for **new** events, not archived HAND130 288 combos. Even `complete=True` only says requested valid samples were accounted for, not opponent model truth, solvers, confidence interval or strategy optimality.
- Original B37 terminal odd-chip tie is still **B37 231422**, BB **86884**, prize share **18.515842285449054%**; P13 partial-call/regression passes.
- Local stale/partial/missing/mismatched PID snapshots explicitly return empirical `field_bf` with `is_exact=False`. The negative witness is specifically **remote-only evolution invisible to the BF API**.
- PR21 CI paired OFF (2 seeds × 40 hands: 359 + 361 decisions, 0 changes) and ON (2 seeds × 20 hands: 180 + 181 decisions, 0 changes) against PR18; no default activation or production branch merge. These are behavioral smoke tests, not proof that split-table rare cases are complete.

## Approval scope

**P8 weighted posterior / P9 MC data-contract preservation: PASS.**  
**PR21 as combined full-field-BF/provenance release artifact: BLOCK** pending target-actor BF source logging and verified snapshot-epoch semantics from P13/P8. P5 and P17 approval remains independent. Keep the PR DRAFT, conditional range default OFF, no `test3` merge and no deployment. Documentation only: do not retune `field_bf` coefficients, add minimum ranges or force a value for missing MC equity.
