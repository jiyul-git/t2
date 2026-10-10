# HAND130 B37 — P5 → P8/P13 review contract (NOT approved by departments)

Scope: feature branch `chatgpt/hand130-calloff-audit-20261010`.
The user directed inter-department review; this file is a concrete
handoff REQUEST. No independent acknowledgement or approval from P8/P13
has been received. Never present this document as signoff.

## P5 verified runtime routing, ownership

- `plan.preflop_plan` takes the direct pure-calloff path when the previous
  aggressor is all-in, no further raise is legal, and call cost is positive.
- It never calls `defend_decision`, `calloff_cap`,
  `defend_thresholds` or `gto.defend_pct` for this actor decision.
  Guarded tests monkeypatch those producers to raise if called.
- If projected per-layer equity is complete, select by incremental price
  and opponent range equity. The separately seeded pot-odds calculation noise
  and perceived ICM remain; the pf_defend gate draw is **audit only**.
  Incomplete evidence gives an explicitly `mathematically_justified=False`
  legal fold, not a claimed -EV fold. Correct fallback knowledge unavailable.
- `pf_defend` is not mapped to a new action frequency or a hand-class override;
  without a validated memorized call-vs-shove chart it can only be logged here.
  The surviving **individual** differences are observer-range reading,
  `icm_bf` and `calc_noise('potodds')`. This is a deliberate limitation,
  not a claim every low-skill bot calculates like a solver.
- The unrelated first-open, nonterminal 3bet/4bet and P4 near-allin choices
  retain their legacy policies pending separately validated multi-branch EV.

## P13 review requested: payout ICM

- Verify use of actual incremental call `C=53442`, contestable pot
  `P+C=161884`, folded blinds, ante, original eight stacks and payout vector
  `[32.573,20.195,14.332,11.075,8.795,7.166,5.863]`.
- Program's original `h.bf(s)=3.465325` is a generic risk measure and
  generates a break-even `0.630692` in `icm.required_equity`:
  not an exact outcome-specific ICM call price.
- The terminal-heads-up simulator enumerates payout ICMEV for
  fold, call-win, call-lose, and call-tie, with chip conservation per outcome.
  With the *archived* rounded payout percentages, in order:
  17.700552609563854, 21.487760646031855,
  15.461616393763215, 18.515842285449054 (corrected award_pots live SB-unit/button odd-chip tie).
  Win/lose no-tie break-even equity 0.3715371093145927.
- It makes no assumption on the tie frequency. For an observed equity-share
  point estimate (win probability + half tie probability) bounds are computed
  from the feasible tie-frequency interval. Error in the 800 Monte Carlo
  draws and observer range is **not** included. The point estimate is not
  mathematically certified to cross any threshold.
- Validate prize percentages with source tournament payout scaling and payout
  rounding; check odd-chip split conventions and short/side-pot cases.
- The exact-price `equivalent_bubble_factor` 1.1996025358246731 is
  algebraically DERIVED from ICM win/loss gains and real call price. It is
  *not* a new calibrated parameter. It is used only for terminal complete
  field heads-up, not generalized to 10+ field players or multiway.
- Confirm if the actor `PS.icm_bf` distortion should be applied to a
  price-specific BF or directly to payout state EV. Current contract uses
  existing perception function and separately seeded calculation error.

## P8 review requested: observer and weighted range

- The actor-only route changes `plan.py`; shared
  `preflop.defend_thresholds` / `ranges._defend_likelihood_range`
  functions are untouched and direct nonterminal callers still use them.
- `ranges.preflop_range('call')` still uses generic
  `defend_action_likelihoods`, which may reconstruct all-in callers as if
  they faced an ordinary open with a raise option. Fix requires a public
  caller allin/price/context contract and observation-conditioned likelihood.
- `session._preflop_story_range` sees the publicly recorded '3bet'
  or 'open' story. First-in shove incorrectly reused open range in prior R2
  audit; P6 and P7 are unresolved independently of the actor calculation.
- HAND130 original observer range: 288 combinations, no archived individual
  combo weights. Direct T2 reconstruction with neutral TAG BB-vs-LJ
  `3bet` proxy gives 298 combinations. These are NOT interchangeable.
- Need source profile/read-book posterior, known action-line metadata,
  blocked-card conditioning, B14 stack (6.3442BB after ante), original
  action likelihood and exact weighted keys for independent replay.
- Before any producer change, run actor/observer conditional action
  probability consistency, range mass, posterior support and cold/multiway
  tests on fixed seeds. Do not force observer to know opponent's private cards.

## P5 reproducibility and known gaps

- `tools/verify_hand130_part2.py` is imported from test3's Part 2 audit.
  It validates original static source and unmodified wrong-quantity cap.
  The W5 arithmetic discrepancy is resolved: correct in-place tp value gives 0.016657816839054443; original runtime SHA and tilt remain unknown;
  actual planning profile/tilt/env SHA not archived. This historical check
  must not be relabeled as the changed behavior.
- `tools/verify_hand130_b37_replay.py`: archived B37 profile, decision
  seed 3365551903, gate roll 0.664054, pre/post selected action (fold/call).
- `tools/verify_hand130_calloff_isolation.py`: P1 complete/missing cannot
  call the legacy producer and preserves shared RNG; normal 3bet still can.
- `tools/verify_hand130_mc_sensitivity.py`: six independently seeded 800
  sample runs across six existing T2 range-model counterfactual contexts.
  **Not** the archived 288-combo true replay, cannot certify game-theoretic
  optimality. Original two-layer conservative Hoeffding halfwidth 0.0412725
  exceeds original objective BF point margin 0.001128.
- Existing `tools/verify_preflop_closure.py` has an unrelated failing
  weak-limp test on unmodified pre-change code; do not suppress it or
  claim green integration.
- No deployment or merging to master/test/test3 until P8/P13 review
  and production regression gates pass.

## P13 corrections pending independent signoff

Tie scenario now reproduces actual award_pots SB-unit/button odd-chip distribution (25,000: 10,000/15,000; 136,884: 65,000/71,884), resulting stacks B37=231422, BB=86884. Exact P13 partial-call synthetic regression derives 40.2587519026% rather than 45.7216940363% by using hero-eligible contestable_before_call in spot-BF conversion. No-tie HAND130 37.1537109315% unchanged.

Part2 followup contract confirms correct W5=0.016657816839054443 and no source code repair. General MTT must include all surviving stacks and payout structure before claiming exact ICM, otherwise a logged approximate BF remains uncertain. Original opponent posterior and full source SHA remain unavailable. Independent P13 and P8 approval is still required.
