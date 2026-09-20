# Money-open sizing promotion check

Status: preregistered before the new multi-seed measurement.

Baseline engine behavior is the integrated UI v49 + money-jump branch after
`f325a2d`. The files added by this check are measurement-only and do not change
poker decisions.

## Scope

Only unopened preflop raises with an actual legal applied raise size are used.
The observation must already contain:

- `applied_open_size_bb`
- `size_factor_shadow`
- `applied_money_size_bb_shadow`

Near-ladder stages are reported separately:

- approach: remaining / ITM <= 1.5 and > 1.2
- bubble: remaining / ITM <= 1.2 and > 1.0
- ITM: remaining <= ITM
- final9: remaining <= 9

The final9 rule is applied first, matching the existing form checker.

## Fixed new sample

The already-inspected seed 92020 is not reused as the new validation sample.

- entries: 100
- rounds: 260 maximum
- stop at remaining <= 8
- format: standard
- seeds: 92100 through 92119 inclusive

## Structural pass/fail checks

These are mechanics/invariant checks, not poker-optimality claims.

For every included row:

1. shadow legal size must never be below 2.0 BB;
2. shadow size must never exceed the actually applied baseline size;
3. logged shadow size must equal
   `max(2.0, applied_open_size_bb * size_factor_shadow)`
   after the existing 3-decimal logging convention;
4. holding the observed state fixed, changing only `open_size_skill` from 1 to
   9 must never make the shadow raise larger.

Any violation stops sizing promotion.

## Descriptive output only

The tool reports, without inventing a pass/fail cutoff:

- sample size by seed, stage, and position;
- changed-rate;
- exact-2BB rate;
- baseline and shadow size quantiles;
- shrink amount quantiles;
- same-state skill-1 versus skill-9 shadow comparison.

A high 2BB concentration is reported, not automatically labeled good or bad.
This measurement does not claim EV improvement and does not promote sizing by
itself.

Limp remains shadow-only and is outside this check.
