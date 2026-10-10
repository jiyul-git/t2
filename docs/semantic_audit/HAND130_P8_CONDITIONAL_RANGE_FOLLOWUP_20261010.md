# HAND130 P8 — action-conditioned opponent range follow-up (isolated)

**Branch:** `chatgpt/hand130-range-conditional-v1-20261010`  
**Implementation parent (P5):** `6f0d912d7a6c6f62c2f82a38746ca588953544e8`  
**Older P8 audit:** `a96afb55dc7c1852180ebd951b505eafa4512d3b`, PR #14.  
**P5 latest checked separately:** `6f0d912d7a6c6f62c2f82a38746ca588953544e8`.  
**Integrated atop latest P5 `6f0d912`: retains P13 split-pot/odd-chip fixes in `session.py`. No `test3` merge.**  
**Status:** feature-gated prototype, not approved production range knowledge.

## Event classification and dependency contract

`range_posterior_v1.classify_public_action()` consumes public `action_meta` and distinguishes:

* `first_in_shove`: all-in as first aggressive action; not the general RFI prior.
* `open_raise`: first ordinary raise (only when no earlier limper).
* `threebet_shove`: full raise over one previous full raise with actor all-in.
* `threebet_raise`: full raise over one previous full raise without all-in.
* `call_allin`, `iso_after_limp`, `iso_over_shove`, `other`: explicitly unsupported by v1; no fabricated range.
* Deep or replayed multiple-action 4bets: unsupported; legacy 4bet story is NOT reused as a generic 3bet.

For each event, store role, prior raises, per-action history, `pre_current`, `post_current`, posted contribution, actor stack remaining at action, known effective stack, observer dead cards, `seats`, antes, inferred opener position and caller count. The observed all-in target must equal posted contribution + pre-action remaining stack, so synthetic/invalid amounts fail closed. For a first-in action, historical behind-seat stacks are derived from their later recorded `pre_stack` before their first response or current unacted stack; unavailable data fails closed.

The mathematical producer is:

```
posterior(combo) = prior_mass(combo) * P(observed action/form | combo, public context, observer-perceived profile)
```

The likelihood reuses **existing** `preflop.open_entry_threshold`, `open_form`, `limp_p`, `defend_action_likelihoods`, `raise_form`, and their mixed/hot-zone choice logic, without editing any threshold or adding guessed coefficients. The call of an existing actor policy is deterministic and uses a symbolic Bernoulli capture, **not** private actor RNG or cards. No `polar > 0.02` uniform-weight exception remains in this opt-in path: observed action likelihood weighs each combo, and any existing polarization signal is not injected as an unverified independent coefficient.

**Source of uncertainty:** This is the observer's **model of actual actor behavior**, not GTO. Actual opponent Book, tilt, exploit, full size-density of non-all-in bets, future opponent action states and original B37 288 combo weights are not reconstructed. Normal raise sizes are recorded but only raise-vs-shove `form` is modeled, not a validated conditional density for each distinct normal bet amount. Missing required evidence returns `(None, meta.complete=False)` for supported event types. Unsupported roles use the old model only outside the experimental routing (and must not be claimed as v1 posterior).

## Isolation and reproducibility

* `T2_RANGE_CONDITIONAL_V1=1`: test-only observer routing in `session._preflop_perceived_range`. Default unset = production behavior remains unchanged.
* `T2_RANGE_REPLAY_CAPTURE=1`: separate opt-in full-precision per-combo `weights`, SHA-256, event source metadata, layer seed, MC accepted/rejected/requested, sample variance and split-pot draw count. Optional audit does **not** consume extra RNG or change computed equity.
* `bot.equity_vs_pools`/`equity_vs_combos` accept an optional `audit` dictionary. The default path is unchanged.
* Every conditional route is traced with `source=observer_actor_policy_conditional_v1`, support, mass, and explicit missing fields.
* No modification to `preflop.defend_thresholds`, `gto.defend_pct`, or `ranges._LIK_CACHE`.

## Existing verified numerical comparison (NOT the archived 288 range)

Native Python verifier at GitHub Actions run #38039527871 passed all relevant stages:

| Model / dataset | Support | Mass | Mean equity (4 x 800) |
|---|---:|---:|---:|
| Synthetic default PERCEIVED BB vs LJ general 3bet | 677 | 141.0831080646762 | 0.58046875 |
| Synthetic default PERCEIVED BB vs LJ conditioned 3bet shove | 845 | 142.02665121791807 | 0.58640625 |
| **Delta** | | | **+0.0059375** |

With both reconstructions, P5's fixed HAND130 objective 8-player terminal ICM and actor response produced four calls from four seeds. The conditional model is **not** the actual archived 288-combo posterior, and the archived equity `0.631820` has not been re-simulated from its original weights. It would be false to claim the conditional proxy has proven an optimal AKo call.

A native invariant check also confirmed `P(3bet shove | H,C)+P(non-shove 3bet | H,C)=P(attack | H,C)` for a qualifying hand/context. At 6.3442BB the production `raise_form` is forced shove, so its nonshove 3bet likelihood is **zero**, which must not be replaced with minimum probability or a generic range.

The P5-parent vs P8 **default-OFF** match for seeds 11 & 12 over 80 hands per seed gave *identical entire JSON records*: 725 and 719 preflop decisions respectively, 0 engine errors. Enabled-P8 smoke (seed 11, 40 hands) completed with 0 engine errors. MC weighted adapter, sampling, action-likelihood and P5 ICM/calloff isolation tests passed.

The unpaired `tools/regress.py check --baseline current` run failed against `baseline_9max_post_f8.json` (VPIP 20.7% vs 20.4%, PFR 12.1% vs 11.4%, flop 47.2% vs 52.2%) but that file predates current P5. A more appropriate fixed-parent direct comparison was run and passed; **do not conceal or misattribute** the old-baseline failure.

## Latest P5 code comparison

P5 branch HEAD `6f0d912` adds changes after original parent, including `session._terminal_hu_call_icm` exact tie pot chip-allocation work, terminal payoffs and partial-call ICMEV tests, plus later `plan.py` provenance changes. The first P8 experiment used older P5 `0786d970`, but this integration branch was rebuilt starting from new P5 `6f0d912`, applying only explicit P8 hunks to current `session.py`. Full P5 exact-ICM/partial-call regression and new field-run evidence must still pass. The 8 department's standalone model and sampling diagnostics can be reviewed independently, but integration/rebase awaits P5 and P13 acceptance. The latest `test3` is not merged.

## Outstanding before production

1. Replay original HAND130 with the original `Book`, `perceived_profile`, observed public `action_meta`, exact weights, accepted MC trace; original 288 were archived as count/signature only and cannot be inverted.
2. Validate the first-in and 3bet-shove conditional model against real actor likelihoods over stack/position/raise-size and history cohorts; test only representative syntax/wiring at present.
3. For normal 3bet amount conditioning, obtain a validated size-likelihood producer rather than guessing bet-size buckets or coefficients.
4. Check v1 conditional mode complete versus incomplete evidence behavior and field-longrun statistics across profiles; 40-hand smoke shows execution, not optimality.
5. Latest P5 source has been selectively integrated without deleting P13 split-pot logic; obtain P2/P5/P13 review and pass exact-ICM/partial-call regression before enabling flag in production.

## Integration branch source lineage

This document also appears on `chatgpt/hand130-range-conditional-integrate-20261010` created from actual P5 HEAD `6f0d912`. It preserves all subsequent P5 session/plan updates and adds P8 source changes as independent insertions. The older prototype PR #15 is superseded for integration review; it should remain a nonmergeable archive of the initial experiment. Final actual Actions result must be taken from the integration-branch run, not inferred from the older base.

## PR #16 P5/P13 blocking-review correction (2026-10-10)

**Reference:** P5 independent review commit `3f17b6633c2bf26df3a56bebaab3c0e4b409b126`, original witness `tools/review_pr16_p5_contract.py`. This addendum **supersedes the old B37 single-equity comparison** above; do not quote its +0.0059375 equity delta as the corrected result.

### P13 actual chip-ICM geometry

`tools/compare_hand130_range_v1.py` previously invoked `session._terminal_hu_call_icm(...)` without tournament `unit` and `odd_order`, silently using `unit=1, odd_order=None`. Correct inputs are `unit=5000` and `odd_order=[8,9,1,2,3,4,5,7]`, which split a tie across **both** layers under the actual small-blind unit and BTN-left payout priority. Correct final B37/B.B. stacks: **231422 and 86884 chips**; correct B37 tied prize share **18.515842285449054%**. The corrected comparison asserts these outputs for every modeled equity and leaves all P13 production split logic unchanged.

The prior comparison called `bot.equity_vs_combos` once then replaced `shadow['effective_equity']`, `gross_return` and `call_chip_ev` without replacing the archived `layer_equities`. This mixed incompatible numeric sources. The corrected comparison instead invokes production `session.layer_equities_by_pot_layer` for **both layers and each model/seed**, generates `session._layer_call_summary`, replaces **all** dependent fields and recorded layer equities consistently, then invokes actual P5 calloff with exact ICM. It asserts all MC accepted draws >0 and verifies unchanged shared RNG.

Corrected **four paired seeds, 800 requested draws per layer** (neutral perceived observer proxy, NOT the original archived 288-combo distribution):

| model | original single-pool mean (obsolete methodology) | corrected layered mean | P5 action | objective ICM | fixed-input ICM EV min-max across seeds (prize points) |
|---|---:|---:|---|---|---|
| general 3bet | 0.58046875 | **0.60225550** | call 4/4 | call 4/4 | lower 1.30580–1.49237; upper 1.33969–1.52372 |
| conditional 3bet-shove | 0.58640625 | **0.59638625** | call 4/4 | call 4/4 | lower 1.22921–1.48157; upper 1.26414–1.51306 |

New difference **conditional minus general = -0.00586925**; obsolete difference **+0.0059375**. Because the sampling object changed from one unconditional pool-equity estimate to two per-layer estimates with new derived seeds and rounding, the difference in means is **not** attributable solely to correcting odd-chip settlement. These are P5 *conditional input* responses; no certification that the opponent 288 combo posterior is correct.

### P5 independent blocker / evidence status

Previously `HandRun._run` saved range metadata inside `if _rr`, so `complete=False`, `source`, `missing` and its failure reason disappeared whenever the conditional range was empty. Now `session._record_preflop_observer_range` keeps metadata regardless of support, and only keeps the pool if it exists. For supported but incomplete contexts, status is `missing_evidence`, `failure_kind=missing_evidence` and `range_available=False`. The observer range stays empty—no guessed opponent pool, and the calloff missing-evidence fallback remains explicitly unverified.

Previously `call_allin` / unsupported event forms silently used legacy `ranges.preflop_range` without any conditional-model failure marker. Now unsupported forms explicitly return `source=legacy_fallback`, `conditional_source=observer_actor_policy_conditional_v1`, `failure_kind=model_unavailable`, `complete=False`, `missing=['action_class_not_supported']`, `model_calibrated=False`, `equity_model_status=unvalidated_legacy_proxy` and `legacy_source` from the real fallback. The legacy pool is intentionally unchanged for supported old action routes; numeric equity derived from that pool is **not** labeled a verified conditional-model estimate.

`session._attach_p8_observer_evidence` puts the full per-seat source/missing/status into `pf_opp_range_meta` and (when present) `pf_calloff_consumer.opponent_range_evidence` on the **experimental ON** path. The consumer explicitly marks estimate status unvalidated and `mathematically_justified=False`. OFF behavior intentionally retains the old exact fingerprint.

Native regression `tools/verify_pr16_p5_provenance.py` derives cases from P5's independent witness, asserting ON supported weight preservation, ON missing evidence retention through final seed and consumer, `call_allin` fallback and conditional model unavailability, and OFF unchanged legacy support.

### Unresolved: P9 acceptance-zero sample gate

P5's original reviewer also reproduced `bot.equity_vs_combos` returning numeric 0.0 with `accepted=0`, which `session.layer_equities_by_pot_layer` may currently mark `complete=True`. It is **not** a mathematically established 0% equity. This is a separate shared-sampling producer issue requiring Department 9 approval and regression. **GitHub issue [#17](https://github.com/jiyul-git/t2/issues/17)** requests a fail-closed contract; P8 has not invented a fallback probability or changed the P9 sampler. PR #16 must remain non-release / draft pending P9's decision.

Neither production `_split_pot_winnings` / `_terminal_hu_call_icm` nor `preflop.defend_thresholds` is modified by this correction. No `test3` merge, feature flag remains off by default.
