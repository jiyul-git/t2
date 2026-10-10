# P5 independent review — PR #16, 2026-10-10

**Reviewed immutable head:** `54e879863d7d1ef08a14079289f0822e6995b1e2`, parent P5 `6f0d912d7a6c6f62c2f82a38746ca588953544e8`. Draft, OFF by default; no merge or production enable.

## Evidence verified

- P8 CI 38040101358 success: conditional model, paired B37 estimated ranges, default-OFF identical vs P5 seed11/12 (725 + 719 preflop decisions), P13 odd-chip/partial-call ICM, weighted MC adapter, sampling and P5 caller isolation.
- Independent P5 review CI `38040658140` **contract/paired succeeded**. `tools/review_pr16_p5_contract.py` probes actual `HandRun._preflop_perceived_range` (not only a direct fake range fed to the P5 planner), preserves weighted 3bet-shove combos and complete model provenance on a supported event. Exact P13 tests re-run.
- Separate paired ON/OFF field-run at 6-hand cap per table, 60 total hands per seed, seed 11 and seed 12: **537/537 and 537/537 actions identical**, 0 errors, all end-hand records identical; real-world sampling coverage is limited. No observed field action differences to attribute in this sample.
- B37 proxy same-seed 4 x 800 equities (legacy vs conditional):
  `1617746575`: 0.604375 → 0.598750, Δ−0.005625, call→call;
  `392948249`: 0.581875 → 0.574375, Δ−0.007500, call→call;
  `2388835235`: 0.564375 → 0.562500, Δ−0.001875, call→call;
  `4184181557`: 0.571250 → 0.610000, Δ+0.038750, call→call.
  Mean Δ+0.0059375; conditional support 845 vs 677. Differences come from action-form posterior/weighting rather than ICM, which is held fixed in the paired actor comparison; the MC draws are paired by seed but change sampling choices as posterior changes. This is *not* observed original 288-combo equity or proof of optimality.
- PR diff contains no new AA/AK-specific override, forced range floor, or poker-calibration experience coefficient. Preflop defense and persona producers remain untouched, and existing ICMBF/potodds and pf_defend gate semantics unchanged.

## Three reproducible release blockers

1. **Missing P8 evidence provenance is dropped in session.** `_preflop_perceived_range` correctly returns `({}, {source:MODEL,complete:false,missing:[...]})` for a supported event without requisite evidence. But `HandRun._run` saves `_pf_opp_range_meta[seat]` only within `if _rr:`. Consequently the decision seed never sees the missing reason. An all-in call with no usable opponent range takes P5's `mathematically_justified=False` execution fallback fold; it is not a computed -EV fold. Action policy for insufficient_evidence must be decided explicitly, not silently relabeled accurate defense.

2. **Unsupported roles silently fall back to legacy range on the enabled flag.** With `kind='call_allin'`, `conditioned_preflop_range` correctly refuses v1 model. But `_preflop_perceived_range` ignores that status and resumes `_preflop_story_range`; the downstream EV can appear complete under a generic, structurally wrong observer range. This is a methodological blocker; either preserve `model_unavailable` with fallback provenance and prevent it from being called an action-conditioned EV, or supply validated conditional likelihood.

3. **Zero accepted MC simulations become false numeric equity zero.** `bot.equity_vs_pools` returns `share/max(1,run)`, so `run=0` produces 0.0. With capture auditing `accepted:0`, `session.layer_equities_by_pot_layer` nevertheless labels row `complete=True,equity=0`, `_layer_call_summary` then returns `complete=True` and planner may fold as though the zero is an observed loss rate. Independent reproduction used a stubbed sampling failure, not a naturally occurring HAND130 board. Stop/fail the estimator at accepted=0, explicitly mark layer incomplete with reason, preserve cause through shadow and plan. No invented equity 0 or rank cap.

## Contract/operational recommendations

- P8: preserve per-seat range_status + meta regardless of `rr` truthiness; distinguish **unsupported model** from **missing required public input**, zero posterior, and a genuinely verified empty posterior; avoid legacy substitution disguised as v1 success. Ensure original opponent Book and conditional weights are captured if available, without hidden cards.
- P5/P9: require `accepted>0` for equity; propagate requested/accepted/variance/seed and missing reasons; if evidence incomplete, mark `insufficient_evidence`. A legal fold in this state is an execution fallback, not mathematically proven fold. Do not introduce AA/AK overrides or a new probability floor.
- P13: retain current `award_pots` SB odd-chip parity and partial-call spot BF. Existing fixed B37 no-tie break-even 0.3715371093145927 persists only for the archived geometry. General MTT missing cross-table stacks or terminal HU inapplicable still uses an explicitly approximate scalar BF; obtain independent P13 signoff before release.
- P8/P17: expand the ON field comparisons to representative actual shoved spots with per-spot action difference attribution and scenario-level missing-data census. In present seed 11/12 field samples no behavior changed; do not infer the feature is accurate or universally inert.
- Do not merge PR #16 or set `T2_RANGE_CONDITIONAL_V1=1` by default before blockers and independent owner signoff.

**Review branch only:** `chatgpt/hand130-p5-pr16-review-20261010`. This is a test/report branch based on immutable P8 PR commit; no strategy files changed.
