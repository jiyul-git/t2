# P5 independent review — PR #18 Monte Carlo validity, 2026-10-10

## Immutable integrated source

- PR #18 2-parent merge: `69e55fc35a208679f06409754d4b43260f9f4fe4`.
- First parent `9d15c1dd70ef283f53a4f2a6bb2718b74917b90d` (P9 sample handling).
- Second parent `71c46aa20b9eac016709d7ee835597b890c8906b` (latest requested PR #16 P8 range/provenance changes).
- Production and PR #16 are **not** merged/activated by this review.
- PR #18 author's CI: https://github.com/jiyul-git/t2/actions/runs/38041673060 SUCCESS.
- P5 independent status-to-planner CI: https://github.com/jiyul-git/t2/actions/runs/38042173500 SUCCESS.
- P8 independent review CI initially failed from test-only wrong key `summary['chip_ev']` (correct contract key `call_chip_ev`), NOT a production failure; corrected review CI https://github.com/jiyul-git/t2/actions/runs/38042198809 SUCCESS.

## P5 exact contract

- `bot.equity_vs_pools` returns `None` when accepted=0, when partial accepted<requested, missing opponent pool or requested=0, with separate `reason` values. A genuinely observed zero returns numeric 0.0 and `complete=True` only when all draws were accepted. Solo-eligible pot is exact equity=1, not falsely marked as Monte Carlo with zero accepted.
- `session.layer_equities_by_pot_layer` always collects requested/valid/rejected samples and the per-layer reason. Missing conditional range metadata (including a NONEMPTY unsupported legacy fallback) prevents estimate. `_layer_call_summary` propagates `incomplete_reasons` with missing opponent details and valid counts, and uses no phantom EV.
- `plan.preflop_plan` chooses a legal fold on incomplete equity with `decision_quantity=unverified_missing_calloff_equity`, `equity_status=unavailable_not_negative_ev`, `mathematically_justified=False`, `strategy_consumer=False`, `legacy_evaluated=False`. This is NOT a mathematically justified fold. The engine may conservatively fold a +EV hand because computation failed: epistemic risk remains, so this is a fail-closed execution policy only. No AA/AK exceptions or probability floor.
- For a fully accepted numeric zero, a price-based negative-EV fold can be selected, yet the consumer still has `mathematically_justified=False` (range-model and Monte Carlo uncertainty unbounded). `complete=True` is sample acceptance, not strategy truth.
- `session._attach_p8_observer_evidence` preserves `missing_evidence` vs `model_unavailable` vs `legacy_fallback` in `pf_calloff_consumer.opponent_range_evidence` when conditional mode is enabled; the original action likelihoods and observer-perceived knowledge remain unchanged.
- Captured layer `seed`, `sampling.seed`, `requested`, `accepted`, `rejected`, `sample_variance`, `split_pot_draws` and conditional weighted range are preserved with unchanged global/shared RNG. Full-precision opponent weights and source SHA are serialized via `RP.replay_record` only with `T2_RANGE_REPLAY_CAPTURE=1`; default-OFF record/strategy unchanged. Capture cannot regenerate historic original B37 288-combo weights.
- P9 pooled empirical mean and sample variance are conditional on assumed opponent pool; **not a confidence proof**. All 800 valid draws do not make an inferred posterior exact.
- Existing P13 `award_pots` odd-chip tie and partial-call ICM tests passed. PR #19 general MTT full-field BF is separate and not included in SHA 69e55; do not claim it as tested/integrated.

## Actual completed CI

P9 official 38041673060: sampler and layered uncertainty tests PASS; P8 weighted posterior and adapter PASS; P5 calloff isolation + P13 terminal/partial-call PASS. Paired default-OFF source `54e8798` vs PR18 branch seed11: 725/725, seed12: 719/719 PF decisions with entire JSON state identical.

P5 independent 38042173500: injected model missing, unsupported, zero MC and partial MC through `session -> _layer_call_summary -> plan.preflop_plan -> pf_calloff_consumer`, valid numeric zero, pure calloff bypass and RNG, plus P9/P8 replay, P13 ICM PASS.

P8 independent 38042198809: weighted range/replay source and sample provenance, MC status checks, conditional range regression, P5/P13 checks and B37 per-layer proxy PASS. Earlier run 38042166634 failed only because test code used wrong `chip_ev` key.

**P5 review disposition:** Approve the narrowly scoped P9 MC-to-P5 sample-status contract at pinned SHA 69e55, with documented computational fallback risks. **NOT approve PR #18 for merging to production or default-ON**: original HAND130 288 weighted opponent posterior remains unarchived, independent full production regression and cross-department integration (including P13 PR19) incomplete. PR #18 remains draft pending other owners; no changes to actor strategy or solver constants in the review branch.
