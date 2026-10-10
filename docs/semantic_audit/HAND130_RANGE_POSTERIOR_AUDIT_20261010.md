# HAND130 B37 / Department 8 — action-conditional opponent range audit

**Scope:** read-only source audit, deterministic routing verifier, ICM sensitivity.  
**Parent source SHA (Department 5):** `874aa76eacec319cd0d6c52b694f841c85dd42ef`.  
**Historical HAND130 fixture:** `docs/handoff/T2_T3_HANDOFF_20261010.md`, Appendix F, hash `6e1ba98ab1a0`.  
**Department 8 strategy changes:** **NONE**. Do not merge strategy or shared-producer edits without Department 5 and Department 2 review.

## 1. Exact action taxonomy and call graph

* **First-in shove**: no previous full raise; `session.HandRun._pf_range_action` maps `pf_act='shove', pf_role='open'` to `action='open'`; public metadata likewise maps first raised action to `open`. `_preflop_story_range -> ranges.preflop_range(action='open') -> preflop._open` is an RFI prior, not P(shove | hand, stack, position, entrants behind).
* **3bet shove over a 2BB LJ open**: the B37 BB attacker had `pf_role='defend', pf_act='shove'`; this maps to `action='3bet'`. Archived reconstruction metadata: `opener_pos='LJ'`, `open_bb=2.0`, `raise_level=1`, `stack_bb=6.3442`, source `standard_preflop_range`. `ranges.preflop_range(...,'3bet')` has **no `allin` parameter, no shove/raise-form conditional likelihood and no final 7.3442BB wager input**. Ordinary 3bets and 3bet shoves can therefore receive identical ranges at identical remaining-stack inputs.
* **All-in call** is not an aggressive 3bet. `session._pf_range_action` labels `pf_act='call'` as `call`, but `ranges._defend_likelihood_range` currently obtains P(call | hand) from `defend_action_likelihoods(..., opener_allin=False, can_raise=True)`. For a true calloff, this is the wrong action opportunity set; premium hands may be assigned too little call mass. See `docs/semantic_audit/r2/CALLOFF_PATH_AUDIT.md` P7.
* **Opener's later 4bet** has a separate `_preflop_story_range` path: preserve their earlier RFI prior and reweight by `preflop_reraise_posterior`. It must not be mistaken for a cold 3bet, and a shove form must not silently discard that prior.
* **Iso over a lone prior shove** has explicit special handling in `_pf_range_action` and public metadata and is not automatically an ordinary 3bet.

**HAND130 is a 3bet-shove reconstruction defect, not the first-in-shove path itself.** Both paths remain model-incomplete, but they are not the same event.

## 2. What can be recovered about the archived 288 combos

The archived actor observer trace states:

| Field | Archived value |
|---|---|
| BB seat | 9 |
| `pf_opp_ranges_n['9']` | 288 |
| `pf_opp_ranges_mass['9']` | 288.0 |
| `pf_opp_ranges_sig['9']` | `469eeda4009881f0` |
| `pf_opp_range_meta['9']` | `standard_preflop_range / 3bet / raise_level=1 / LJ / 2.0BB / 6.3442BB` |
| `first_in_allin_read_as_open` | false |
| Hero dead cards | Ac, Kh |
| Stored equity | 0.631820; 800 requested Monte Carlo draws |

**The individual combos, per-combo weights, opponent Book observations, reconstructed `perceived_profile`, `tb_polar`, and draw trace are absent from Appendix F.** The signature alone is not reversible into them. Replaying the original conditional distribution from the actor profile would leak information unavailable to the observer.

Actual generation logic:

1. Observer `reads.perceived_profile` -> `reads.range_profile`; never actual opponent persona.
2. `persona.read_opponent` -> `tb_polar` from observed `pf_3bet`, observation count and line-reading competence, then `session` supplies `polar = tb_polar * w`.
3. `ranges.preflop_range` gets attack threshold `tp` from shared `preflop.defend_thresholds`.
4. With `polar <= .02`, `_defend_likelihood_range` calls `preflop.defend_action_likelihoods` per hand class. It emits a weighted dict with action likelihood >= `_LIK_MIN=.01`, **but assumes `opener_allin=False, can_raise=True`**.
5. With `polar > .02`, the code skips the class likelihood and creates an **unweighted list** with the legacy hand-order bands `v<=hi*(1-.55*polar)` or `min(.90, hi+.10+.25*polar)<v<=min(.95, blf_lo+(hi-val_hi)*2.2)`. Here `hi=tp`. Each selected combo has legacy mass 1.
6. When the class likelihood function returns `None` or an empty pool, the function also falls through to an unweighted hard-band range.

An archived count of 288 and total mass exactly 288.0 is compatible with the unweighted polar or fallback path; it is **not sufficient evidence to choose between those paths**. In particular, it does not validate P(3bet-shove | hand) or show 288 probability-normalized combos. Do not claim the 288 prior is calibrated or identify its individual weights.

## 3. Shared producer and likelihood exposure

Call dependencies:

```text
preflop.defend_thresholds  -> preflop.defend_action_likelihoods -> preflop.defend_decision  [actor]
                         \-> ranges._def_thresholds -> preflop_range             [observer]
                         \-> ranges._defend_likelihood_range -> defend_action_likelihoods [observer]
                         \-> preflop.calloff_cap                     [legacy calloff]
```

Changing `gto.defend_pct`, `defend_thresholds`, `LEVEL_TIGHTEN`, or its context signature would change (a) actual actor continuing/aggression weights, (b) the opponent observer's posterior support/mass, (c) hypothetical multiway/side-pot equity and (d) legacy fallback behavior. In the polar branch it can change *which* combos exist (discontinuous boundary); in the non-polar branch it can change both support and weights. This is **not** a local Department 5 calloff-only fix.

`ranges._LIK_CACHE` keys on inferred profile, role, bb, previous open and related context, **not** on a version of `defend_thresholds`. Cache invalidation is required in counterfactual in-process producer swaps to avoid stale likelihood output. No counterfactual coefficient or default range floor is proposed.

## 4. Equity and action sensitivity: distinguish uncertainty sources

Archived observed input: `e=0.631820`, `cost=53442`, `contestable=161884`.

* Chip-EV threshold `53442/161884 = 0.330125...`.
* Historical global BF threshold `~0.630692` compared the wrong risk amount for this terminal spot. Department 5's exact 8-player terminal ICM path derives `e_req=(ICM_fold-ICM_lose)/(ICM_win-ICM_lose)=0.3715371093145927` **under no ties**.
* Exact prize shares (from `HAND130_EXACT_TERMINAL_ICM_20261010.md`) are fold 0.17700552609563854, loss 0.15461616393763215, win 0.21487760646031855, tie 0.18733849424660832.
* For equity share `e=P(win)+P(tie)/2`, with unknown tie frequency `q`, prize-share EV difference from folding is exactly

  `D(e,q) = (ICM_lose-ICM_fold) + e*(ICM_win-ICM_lose) + q*(ICM_tie-(ICM_win+ICM_lose)/2)`.

  Feasible `0<=q<=2*min(e,1-e)`. At the **fixed archived equity estimate**, D ranges from `+0.01568502245667733` to `+0.01759337969499232` of the payout pool, **before** equity estimation and opponent-range errors.
* Keeping this exact payoff geometry fixed, **a reduction of 0.260282890685407 in inferred equity** (0.63182 down to 0.371537109314593) is needed to make the *no-tie* prize advantage zero. This is a break-even sensitivity bound, **not evidence that the true opponent range has that equity**.
* The entire fixed-posterior equity MC consumes 800 requested iterations. With 800 independent, valid observations bounded in [0,1], a distribution-free 95% Hoeffding half-width is `sqrt(log(40)/1600)=0.04801614`. This is conditional on a **fixed, correct range**, independent draws and 800 accepted observations. The original accepted count and draw values were not archived. MC error and **model uncertainty** must not be conflated.
* Posterior misspecification is not bounded by that MC interval. Neither the magnitude nor the sign of the effect of changing the 288-combo support/weights is measurable without the actual posterior or a defensible shove-conditional prior. Thus a mathematically sound ICM call from the **input** is not a validated assertion that this **input distribution** is right.

Diagnostic sensitivity examples **(hypothetical equity inputs, not estimates of HAND130's opponent)**, fixed ICM geometry:

| e | D min (no ties), payout percentage points | D max, payout percentage points |
|---:|---:|---:|
| 0.30 | -0.43109 | -0.27560 |
| 0.35 | -0.12979 | +0.05163 |
| 0.40 | +0.17152 | +0.37885 |
| 0.45 | +0.47283 | +0.70607 |
| 0.631820 | +1.56850 | +1.75934 |

The tie EV range `D(e,q)` can straddle zero below the no-tie threshold; do not convert equity share into a win rate.

## 5. Existing external comparator, with scope limit

`docs/semantic_audit/r2/CALLOFF_PATH_AUDIT.md` recorded 63 9-max push/fold reference spots: using DB first-in jam range in a call-equity rule yielded ~0.940 average match; using T2-observer RFI-derived jam range yielded ~0.771. It contrasts model quantities, **not B37's 3bet-shove**. DB format (push/fold 0.1bb per player antes, chip EV) differs from T2's opening/3bet choices, BB ante and bubble ICM. This evidence supports investigating event-conditional priors, not importing DB jam percentages into B37.

## 6. Acceptance conditions / Department 5 & 2 handoff

* Record **event class** (first-in shove / open+3bet shove / nonshove 3bet / call vs shove / cold 4bet or iso), actor role, first/open wager, final bet, effective stack, previous action history, observer snapshot hash and timing. Do not use hidden actor cards/profile to make the live observer posterior.
* Log **prior support+mass, likelihood model/version and relevant conditioning flags, after-action support+mass, a reversible per-combo weight artifact or content-addressed blob, post-card-blocking mass, sample seed, requested and accepted draws, sample variance and tie count**. A hash+count is not a replayable distribution.
* Conditional posterior contract: `P(combo | observed shove action, public context, observer evidence) proportional to P(observed shove action | combo, public context, observer evidence) * P(combo | previous public history, observer evidence)`. Do not treat unconditional RFI or 3bet as a shove-specific likelihood.
* After a defensible conditional model is available, use **paired, common-random-number** equity comparisons versus the archived 288 model on B37 *and multiple diverse hands*, including blocker effects, `first-in` and `3bet` separately. Report actionable changes by opponent prior, estimation error and ICM, not just a changed decision.
* Any `defend_thresholds` revision requires Department 2 calculation provenance and Department 5 actor/fallback contract review before implementation. Run `tools/verify_f7b_defend_likelihood.py`, `tools/verify_f7b_defend_rewire.py`, `tools/verify_hand130_b37_replay.py`, `tools/verify_hand130_exact_icm.py`, range posterior invariant checks and field fixed-seed regression. **No shared producer was modified here.**

## Verification

`python3 tools/verify_hand130_range_posterior.py` exercises native current repo functions and archived metadata, and explicitly declares `archived_posterior_recomputed=false` and `archived_mc_recomputed=false`. See GitHub Actions run logs for actual runner execution. The numerical ICM sensitivity above was independently recomputed from the four archived prize shares. No claim of an independent HAND130 288-combo equity rerun.
