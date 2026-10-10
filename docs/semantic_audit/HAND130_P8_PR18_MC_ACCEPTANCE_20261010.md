# Department 8 independent acceptance review: PR #18 / P9 Monte Carlo provenance

**Audited immutable integrated PR18 SHA:** `69e55fc35a208679f06409754d4b43260f9f4fe4`  
**Parent PR16 HEAD:** `71c46aa20b9eac016709d7ee835597b890c8906b`  
**P9 native successful GitHub Actions:** [#38041673060](https://github.com/jiyul-git/t2/actions/runs/38041673060).  
**P8 independent tests:** `tools/review_p9_p8_weighted_mc_contract.py`; audit workflow `p8-review-p9-mc-contract.yml`, successful run [#38042198809](https://github.com/jiyul-git/t2/actions/runs/38042198809) on test commit `67427cc36188a08f6a856cd0c04fc4c7c1f66d2b`.

## P8 conclusions, scope and disposition

**P8 observer-weight / MC-validity interface: APPROVED for continued isolated PR16 integration review.** This approval is narrowly about the P9 data contract and its observed behavior on the integrated PR18 commit, *not* a release or GTO/strategy approval. **Do not deploy, merge into test3 or activate the optional observer range by default.** Independent signoff from P5 and P13/P17 on the combined current branch, plus separate P13 BF work (PR19), remains required.

The new producer `bot.equity_vs_pools` uses a local RNG and accepts either the original ordered/uniform pools or weighted dicts, without flattening the conditional posterior. `equity_vs_combos` retains the exact support and positive weights after dead-card filtering. It records:

- requested / accepted / rejected attempts
- actual trial seed
- pot-share sum and square sum, unbiased variance for at least two valid draws
- split-pot draw count (0 < showdown share < 1)
- reason, complete flag, and observed sample mean

When accepted=0, the estimate is `None` with `reason=no_valid_mc_samples`, not 0.0. A partly accepted batch returns `None` for decision use but retains the observed mean for **diagnostics only**; `reason=insufficient_valid_samples`. The independent P9 sample fixture proves an actual valid 0% share remains exactly 0.0 with `complete=True` when all requested draws are accepted; it does not conflate observation with population truth. Empty opponent pool uses exact sole-eligible equity 1.0, not a 0-draw opponent showdown.

`session.layer_equities_by_pot_layer` now invokes an audited sampler **even when `capture_sampling=False`**. The inexpensive per-layer record includes `seed`, `requested_samples`, `valid_samples`, `rejected_samples`, `sample_variance`, `split_pot_draws`, `reason`. With replay capture, it additionally includes the full `sampling` dictionary; P8 `range_posterior_v1.replay_record` preserves per-combo weights and source metadata plus each layer's audit, allowing complete evidence reconstruction for *new* events. The layer and `_layer_call_summary` reject partially/fully missing estimates and preserve per-layer `incomplete_reasons` (including `missing_range_details`).

A conditional posterior with `complete=False`, including `call_allin` / `legacy_fallback` marked `model_unavailable`, is explicitly excluded from decision-grade layer equity even if a legacy numeric combo pool exists. `plan.preflop_plan` routes missing equity to a **legal fallback fold** with `equity_status=unavailable_not_negative_ev`, `strategy_consumer=False`, `mathematically_justified=False`, and detailed `incomplete_reasons`. An actual valid zero-equity estimate is handled separately.

The independent P8 ON-mode test reconstructed a **synthetic current-policy** BB-versus-LJ all-in posterior: 845 weighted combos, mass 142.02665121791807, and tested a 120-request, 120-accepted pairwise sampling with seed 383335961, variance 0.22043067226890753 and 9 split-pot draws. Recording the full weights, provenance, SHA-256 and layer sampling survived JSON losslessly. Global RNG state and shadow sampling ON/OFF point estimates remained equal. This is **NOT** the archived HAND130 288-combo observer distribution: its exact weights / actor Book / original 800 valid-sample trace remain unavailable.

## CI and regression evidence

The independent P8 workflow [#38042198809](https://github.com/jiyul-git/t2/actions/runs/38042198809) passed:

- P8 synthetic weighted observer → audited sampler → replay JSON → P5 fail-closed consumer
- P9 zero/partial/all-valid/true-zero/tie/seed/variance invariants
- prior P8 range serialization, conditioned posterior, missing-evidence provenance
- P5 calloff isolation, original terminal ICM and P13 odd-chip/partial-call regression
- four fixed-seed per-layer proxy B37 comparison

The first P8 CI attempt #38042166634 failed due to a **P8 test-only field-key error** (`summary['chip_ev']` instead of `summary['call_chip_ev']`), corrected in `67427cc`. It did not expose a producer failure. The final audit workflow passed at that SHA.

PR18's [#38041673060](https://github.com/jiyul-git/t2/actions/runs/38041673060) also passed default-OFF seed 11/12 full JSON parity against prior PR16, totaling 160 hands and 1,444 preflop decisions with zero engine errors. No default policy behavior or shared RNG change was observed in these tested configurations. Complete Monte Carlo samples **do not certify the opponent's model**, solved GTO, or optimal call/fold; P5 carries `estimate_status=point_estimate_sampling_and_range_error_unbounded` and never labels the missing-input fallback a proven negative-EV fold.

**Integration constraints:** PR19 P13 global-field BF uses a different branch and must be independently reconciled before combined release review. Preserve `pf_bf_provenance` when combining P9 + P13. No new empirical constants, AA-specific paths, solver range imports, or equity floors were introduced in P8 review.
