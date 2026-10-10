# P5 independent combined-code review: PR #21 (2026-10-10)

## Immutable target, isolation, release status

- PR #21 DRAFT: `https://github.com/jiyul-git/t2/pull/21`
- Inspected PR head: `0a45af4ce79faf13d78824448f2e1b8943b4518e`.
- Merge ancestor: `f6b2578b4068aa571f632ce1bedf3f47bf32f56b` with first parent P9 PR #18 `69e55fc35a208679f06409754d4b43260f9f4fe4` and second parent P13 PR #19 `791ab4e771d7e239b915594f3ba65594957348d0`.
- Official combined CI `https://github.com/jiyul-git/t2/actions/runs/38042964484`: SUCCESS, checks full integration and source preservation.
- **Independent** review branch: `chatgpt/p5-pr21-combined-review-20261010`. Production code is inherited unchanged from PR #21; only new tests, independent CI and this document were added. Independent tested commit `913f5168043b0c79280c0d76d06cf41001debce4`, full successful CI `https://github.com/jiyul-git/t2/actions/runs/38043724807` with both jobs green.
- No merge, default flag enablement or deployment was performed.

## Joint P9 MC -> P5 final action and provenance

`tools/review_pr21_combined_mc_p5.py` and `tools/review_pr21_combined_bf_p5.py` use actual `session.layer_equities_by_pot_layer`, `_layer_call_summary`, `plan.preflop_plan`, `session._attach_p8_observer_evidence`, and `_merge_pf_seed`.

- No valid MC draws: `equity=None`, `complete=False`, `reason=no_valid_mc_samples`. Zero requested draws are separately `no_requested_samples`.
- Some valid but fewer than requested: `equity=None`, `complete=False`, `reason=insufficient_valid_samples`; `observed_sample_mean` only for diagnostics. No chip/payout EV from that incomplete layer.
- Truly observed zero with all requested samples accepted: numeric `equity=0.0`, `complete=True`. `complete` is not accuracy or optimal-play certification.
- Model unsupported vs missing range: respectively `unsupported_opponent_model` and `missing_opponent_range`; `incomplete_reasons`, conditional model `missing` status, and `opponent_range_evidence` survive in the final `pf_calloff_consumer`. Legacy fallback is explicitly marked and cannot be silently treated as complete supported conditional equity.
- Actual legal fold when evidence is incomplete: `equity_status=unavailable_not_negative_ev`, `mathematically_justified=False`, `strategy_consumer=False`, `legacy_evaluated=False`, `decision_quantity=unverified_missing_calloff_equity`. This can MISS an actual +EV call; it is a safety/execution behavior, **not** a proven negative-EV decision.
- P9 requested/accepted/rejected draws, per-layer seeds, variance and tie counts, P8 weighted range source/signature and optional exact double-precision replay provenance intact. Shared RNG unchanged in comparisons.
- No new AA hand-specific forced action, empirical strategy coefficient or arbitrary equity lower bound introduced.

## P13 BF completeness and actual P5 behavior

P13 `Hand.bf_details` outputs `value` plus `method,is_exact,reason,field_completeness,bf_kind,price_specific`. `Hand.bf()` supplies the exact same `value` numeric contract to P5. Actual `HandRun` with conditional range ON/OFF also logs `pf_bf_provenance` without overwriting P8/P9 cause metadata.

Synthetic 5-table-seat / 8-total-survivor B37-stack fixture at a fixed call price `C=53442`, `pot_before=108442`:
- Complete 8-field PID+stack snapshot: generic BF `3.4653251545473682`, `is_exact=True`, `method=exact_full_field_icm`.
- Missing other-table stack snapshot: old empirical BF `1.7580606985767642`, `is_exact=False`, `reason=missing_full_field_stacks`. No invented BF=1.
- Local stack changed since frozen snapshot: empirical BF `1.7580666484135543`, `reason=table_stacks_changed_after_field_snapshot`.
- Other-table PID P2 chip count changed while frozen aggregate chips remained old: **must not** certify exactness; observed `field_bf_empirical_approximation`, `reason=missing_or_mismatched_player_id_snapshot`.
- Algebraic midpoint between the old empirical and new complete-field price thresholds, equity `0.5474509122487927`: actual P5 planner chooses **Fold** with complete-field BF vs **Call** with missing-field empirical BF. Synthetic sensitivity case, NOT actual HAND130 equity or a newly fitted constant. All other card/pot/call costs and random seeds are held equal. Full BF precision preserved in planner (`objective_unconditional_bf`) and the logged generic provenance.
- Even with completely verified field BF, injecting zero/partial/unsupported/missing MC equity cannot create a mathematically justified fold. New combo constraints are orthogonal to BF exactness.

## Generic whole-field BF != price-specific payout ICM EV

All `Hand.bf_details` reports explicitly tag:
`bf_kind=generic_default_risk_not_spot_call_prize_ev`;
`price_specific=False`. Even `is_exact=True` certifies the **generic** BF's field inputs, not win/loss/tie EV for a particular action.
- HAND130 B37 all 8 field players at same table: generic BF approx `3.4653251545474`, remains unchanged.
- Actual fold/win/lose/tie payout ICM for B37 facing B14 allin uses actual chip-unit odd-chip settlement and `_terminal_hu_call_icm`: no-tie break-even `0.3715371093145927` and derived spot-equivalent BF `1.1996025358246731`.
- For B37 tie, B37 ends `231422` and BB ends `86884` chips, matching live `award_pots`.
- P13 partial matched all-in scenario gives correct `0.402587519026` vs erroneous `0.457216940363`.
- The planner's `objective_unconditional_bf` still records generic BF, while `objective_spot_bf` and `icm_pricing_basis=terminal_hu_exact_outcome_prices` use the **spot** equivalent when the exact terminal HU conditions are satisfied. For all other structures `icm_pricing_basis=generic_bf_approximation_not_spot_validated` and an explicit risk label remain.

## Real independent CI evidence

P5 independent `38043724807`, both jobs SUCCESS:
- `independent`: independent BF completeness/MC 0/partial/status to final P5, real HandRun BF scalar and final provenance ON/OFF, P9+P8 inherited contract, P13 odd chips and partial call, RNG, no new strategy errors.
- `on-off-smoke`: same-seed within combined PR21 HEAD:
  - seed 11: OFF=180, ON=180 PF decisions, action/size differences=0, hand record equal, 20 hands.
  - seed 12: OFF=181, ON=181 PF decisions, differences=0, hand record equal, 20 hands.
  - Total 361 paired decisions, no observed action changes. Tiny sample does not cover every unusual tournament stage.
- Official PR21 `38042964484` additionally ran before/after P9 parent:
  - OFF seed 11 359/359, seed 12 361/361 action identity, no errors.
  - ON seed 11 180/180, seed 12 181/181 action identity and hand-state identity.

**Test-harness issue fixed without production change:** initial independent CI `38043564516` expected planner input BF rounded to 6 decimals; P5 correctly preserves full-precision BF. Assertion corrected at `6927a7e`; subsequent CI passed. Not a PR #21 bug.

## Disposition and unresolved uncertainties

**P5 independent APPROVAL for the scoped combined MC/BF decision-data contract at PR21 SHA 0a45af4.** No new production-code defect detected by these tests. This is NOT approval to merge, deploy, or enable the optional range flag. Require separate P8, P13 and P17 release signoffs and a full production-endgame regression. The actual historical HAND130 288 opponent weighted combos are unavailable, MC estimates have unquantified range/model error, and the existing empirical `field_bf()` curve is not an exact payout-I CM model. Missing-equity execution folds can still sacrifice true +EV and must never be represented as proven negative EV.
