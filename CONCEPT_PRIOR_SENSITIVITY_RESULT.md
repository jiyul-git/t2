# Concept prior local sensitivity — result

Sample:
- field quality 0.78
- 3,000 profiles per arm
- deterministic per-pid RNG
- base perturbation ±0.25
- spread perturbation ±0.15
- no production parameter persisted

## Main result

The realized generator is locally well behaved.

For almost every concept, a ±0.25 nominal base perturbation moves the realized median by
about 0.2-0.3 points.  The response is nearly symmetric; typical asymmetry is only 0.1.

Therefore base calibration can be treated approximately as a monotone local control of
the realized median.  There is no evidence of severe rejection-filter discontinuity in
the neighborhood currently tested.

Spread behaves similarly: ±0.15 typically moves q90-q10 width by roughly 0.2-0.4 points.
The main exceptions are concepts already near the 0/10 clamps.

## Clamp-sensitive concepts

The strongest issue remains `stack_decay`:
- baseline floor around 10%
- spread+ floor around 11.3%
- increasing spread adds clamp saturation more readily than useful interior width

Other concepts requiring care before spread increases:
- `pf_range`: spread+ ceiling 9.7%
- `range_merge`: spread+ floor 6.7%
- `blocker`: spread+ floor 5.6%
- `overbet`: spread+ floor 5.6%
- `pf_defend`: spread+ ceiling 4.9%
- `checkraise_late`: spread+ floor 4.8%

## Interpretation

The prior mechanics are sufficiently regular that future realized-median / realized-width
targets can be solved with small iterative base/spread changes rather than redesigning the
generator.

However, no calibration should be applied yet.

The current concept taxonomy still contains street aggregation that must be resolved first,
because calibrating a shared concept and later splitting it would invalidate the population
work.  In particular:
- `checkraise_late` currently represents turn + river;
- `bluffcatch_early` currently represents flop + turn;
- `thin_value_turn` is also used as the flop fallback in `street_concept`.

Therefore the next step is a street-concept granularity audit.  LOADING/SPREAD remain
unchanged until that taxonomy is either accepted or split.

## Closure

Sensitivity mechanics audit accepted.
No production behavior, generator prior, or frozen regression baseline changed.
