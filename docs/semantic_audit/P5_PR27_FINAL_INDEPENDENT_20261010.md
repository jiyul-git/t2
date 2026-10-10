# P5 final independent review — PR #27 at immutable SHA 3c434b2 (2026-10-10)

## Scope and GitHub provenance

- Production target PR #27: `3c434b28046643ba54c04447951ad148ae6f9c1c` (Draft, no merge).
- P13 production CI: `https://github.com/jiyul-git/t2/actions/runs/38049054671` — SUCCESS.
- P15 audit `d839a09a17bf39e76f505402ed1de5d9b3c556c4` directly descends from 3c434b2, with no production modifications reported; P15 is an independent tournament/parallel reviewer, not an assertion of P5 strategy correctness.
- P5 separate audit branch `chatgpt/p5-pr27-final-independent-20261010`. Source-pinning job uses `git diff --exit-code 3c434b2 HEAD` on `plan.py, preflop.py, session.py, bot.py, icm.py, play.py, live2.py, range_posterior_v1.py, fieldsim.py`: **identical production sources**.
- P5 initial full independent workflow `https://github.com/jiyul-git/t2/actions/runs/38050408200`: SUCCESS, three jobs covering calloff, 27 players/3 tables, ON/OFF paired.
- Additional actual 27-player HandRun BF-to-final-log inspection `tools/review_p5_pr27_real_27_field.py` and decision/epoch test `tools/review_p5_pr27_final.py` on the same PR27 production source.
- Additional audit-only test-file history: first real-27 run expected supported-likelihood observer_model_inputs in unsupported legacy_fallback metadata, but fallback intentionally has only top-level actor provenance. Audit harness corrected to test those two contracts separately; **not a production bug**.

## Independent finding: MC no evidence != zero equity

Independent `tools/review_p5_pr27_final.py` plus actual PR27 inherited `tools/verify_hand130_mc_contract.py`, `tools/verify_hand130_calloff_isolation.py` and P8 provenance tests were run by CI.

- Accepted zero Monte Carlo samples: layer `equity=None,complete=False,reason=no_valid_mc_samples`, with requested/accepted/rejected information.
- Partially accepted samples: `equity=None,complete=False,reason=insufficient_valid_samples`; `observed_sample_mean` is diagnostic-only, not a decision EV.
- Supported model missing a public input: `missing_opponent_range`; unsupported action `unsupported_opponent_model` or explicitly marked `legacy_fallback / model_unavailable`, never certified as an action-conditioned opponent posterior.
- Numerically valid zero-equity estimate `0.0` is kept distinct from `None`; `complete=True` only certifies sampling contract, NOT truth of opponent posterior, GTO strategy or finite-error bounds.
- If equity cannot be computed, actual P5 pure-calloff returns legal executable Fold with `equity_status=unavailable_not_negative_ev`, `strategy_consumer=False`, `mathematically_justified=False`, `legacy_evaluated=False`; `incomplete_reasons` and opponent's BF range metadata remain in `pf_calloff_consumer`. An execution fallback may still forgo +EV and is NOT a validated -EV verdict.

## Independent finding: whole-field BF methods under epoch controls

P5 directly creates P13 Field, stamp, frozen coordinator, partial worker and remote-only drift, then calls actual `Hand.bf_details` and feeds its full-precision scalar to actual `plan.preflop_plan`.

| Status | `method` | `is_exact` decision-current | `observed_epoch_diverged` | Generic BF (8-survivor fixture) |
|---|---|---|---|---|
| Current verified whole field | `exact_full_field_icm` | true | false | 3.4653251545473682 |
| Active frozen reference | `frozen_epoch_reference_icm` | false; `snapshot_epoch_exact=true` | None | same 3.4653251545473682 |
| Partial worker without current full roster | `field_bf_empirical_approximation` | false | None | 1.7580606985767642 |
| Frozen worker owning only local roster | `frozen_epoch_reference_icm` | false | None | same as full coordinator frozen |
| Frozen hand/level advanced or reference released | `field_bf_empirical_approximation` | false | None | existing heuristic, not invented exact value |
| Remote-only movement with verifiable complete roster | `field_bf_empirical_approximation`, stale_remote | false | true | old approximation, no fabricated exactness |

All BF evidence includes `bf_kind=generic_default_risk_not_spot_call_prize_ev` and `price_specific=False`. No unverifiable remote current epoch ID appears in a frozen or partial worker. `False` and `None` are never interchanged. The generic BF uses the old empirical curve for incomplete evidence; no BF floor or new experiential coefficient is introduced.

A **derived synthetic midpoint equity** of 0.5474509122487927 (same cards/price/seeds) yields Fold under current full-field BF, Fold under valid frozen BF, Call under partial-roster empirical BF. This demonstrates caller consumes the correct *numeric* BF; it is not a HAND130 equity reconstruction, strategic optimality result or new hand exception.

## Actual 27-player / 3-table HandRun evidence

Independent `tools/review_p5_pr27_real_27_field.py` uses a real Field with 27 players and three tables under a single frozen snapshot and intercepts only `PL.preflop_plan` to inspect actual `kwargs['bf']`, `h.bf_details` and saved `h.pf_seed`.

- Model OFF: 30 actual P5 plan decisions, all `pf_bf_provenance` exactly equal to producer details and numeric input, 0 fabricated remote epoch, 0 engine errors.
- Model ON: 30 actual P5 decisions, **28 actor BF provenance entries** persisted in the `pf_opp_range_meta` and relevant `pf_calloff_consumer.opponent_range_evidence`; 0 fabricated observed remote epoch, 0 engine errors.
- Both modes: all 30 P5 decisions carry `field_epoch_status=frozen_epoch_reference`, current exactness false, method empirical since 27 survivors exceeds exact <=9 engine capacity, observed remote epoch ID and divergence both None.
- Supported P8 classes carry `observer_model_inputs.actor_bf_provenance` and numeric likelihood BF equal to actor producer BF. Unsupported classes have explicit top-level actor BF and `legacy_fallback`, with `actor_bf_likelihood_direct_input=False`; no fake supported likelihood assertion.
- Frozen reference in 8-survivor complete-field case remains the snapshot-epoch generic exact BF, not decision-current exact.
- Separate independent `verify_parallel_table_processes.py 27 0 11` passed sequential/parallel equivalence.

## BF vs exact price-specific prize EV

The source of a generic BF and source of an exact *particular call* payout EV remain different:
- B37 objective generic whole-field BF 3.4653251545474 (all eight survivors).
- Terminal HU result-specific win/lose/tie chip settlement yields no-tie equity requirement 0.3715371093145927, derived price-equivalent BF 1.1996025358246731; the P5 strategy consumer chooses the spot-specific BF **only when the exact terminal HU gate is satisfied**, logs `icm_pricing_basis=terminal_hu_exact_outcome_prices`, and retains objective generic BF separately.
- Real odd-chip tie stacks B37=231422, BB=86884 and two-layer chip conservation match `award_pots`. P13 opponent-uncalled-excess partial call 40.2587519026% rather than erroneous 45.7216940% is preserved.
- For nonterminal, multiway, >9 players or incomplete field context, generic BF is explicitly `generic_bf_approximation_not_spot_validated` and cannot be relabeled a price-specific prize EV.

## RNG, ON/OFF and existing strategy

P5 independent run `38050408200` completed 3/3 jobs SUCCESS. Real 9-max R2 same-seed short-run ON/OFF comparison: seed 11 180/180 action/size equal and identical final hand records; seed 12 181/181 equal, no errors. The subsequent actual 27-player logs also preserve BF/P8 provenance without changing strategy code. Global and plan-shared RNG state remain unchanged for scoped tests. These short tests do not certify all uncommon late-tournament actions; no ungrounded claim of solver optimality.

**Status: P5 technical sign-off for PR27 SHA 3c434b2, confined to BF/provenance/MC/incremental-calloff data and tested behavior. No newly discovered production-code blocker in that scope. Production merge, PR #27 approval from all departments, test3 integration and deployment remain BLOCKED pending P8/P17 integrated review and all release gates.** Historic 288-combo posterior not independently reproduced, and empirical incomplete-field BF and legal fallback-fold uncertainty remain openly labeled.
