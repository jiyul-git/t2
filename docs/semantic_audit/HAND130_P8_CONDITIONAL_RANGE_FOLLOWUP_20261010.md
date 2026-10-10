# HAND130 P8 — action-conditioned opponent range follow-up (isolated)

**Branch:** `chatgpt/hand130-range-conditional-v1-20261010`  
**Implementation parent (P5):** `0786d970c769198d2649c75fc520d447ab9b6e9a`  
**Older P8 audit:** `a96afb55dc7c1852180ebd951b505eafa4512d3b`, PR #14.  
**P5 latest checked separately:** `6f0d912d7a6c6f62c2f82a38746ca588953544e8`.  
**Never merge current `test3` or overwrite subsequent P5 chip/ICM fixes.**  
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

P5 branch HEAD `6f0d912` adds changes after original parent, including `session._terminal_hu_call_icm` exact tie pot chip-allocation work, terminal payoffs and partial-call ICMEV tests, plus later `plan.py` provenance changes. The P8 experiment was based on earlier P5 `0786d970`; as such, **do not merge P8 session.py over the updated P5 session.py** without preserving all P5 changes and re-running its new exact-ICM/partial-call regressions. The 8 department's standalone model and sampling diagnostics can be reviewed independently, but integration/rebase awaits P5 and P13 acceptance. The latest `test3` is not merged.

## Outstanding before production

1. Replay original HAND130 with the original `Book`, `perceived_profile`, observed public `action_meta`, exact weights, accepted MC trace; original 288 were archived as count/signature only and cannot be inverted.
2. Validate the first-in and 3bet-shove conditional model against real actor likelihoods over stack/position/raise-size and history cohorts; test only representative syntax/wiring at present.
3. For normal 3bet amount conditioning, obtain a validated size-likelihood producer rather than guessing bet-size buckets or coefficients.
4. Check v1 conditional mode complete versus incomplete evidence behavior and field-longrun statistics across profiles; 40-hand smoke shows execution, not optimality.
5. Rebase selectively onto P5 latest, preserve P13 split-pot handling, and obtain P2/P5 review prior to enabling flag in production.
