# Money-open sizing behavioral counterfactual

Status: preregistered before behavioral counterfactual measurement.

The structural sizing check on seeds 92100..92119 passed.  Those seeds are not
used for the primary behavioral sample below.

## Question

For a natural-state near-ladder unopened preflop raise, what changes if the
same opener, in the same hand state and with the same RNG state up to the
decision, uses the already-defined money-sizing shadow target instead of the
baseline applied target?

This check is one-hand/off-policy.  The baseline tournament continues
unchanged; the counterfactual hand is discarded after measurement.  Therefore
later tournament states remain natural baseline states.

## Fixed sample

- entries: 100
- rounds: 260 maximum
- stop at remaining <= 8
- format: standard
- seeds: 92200 through 92219 inclusive
- population: near-ladder unopened preflop non-all-in baseline raises with an
  actual applied baseline size
- stage definition: identical to MONEY_SIZING_PROMOTION.md

Seeds 92100..92119 were already inspected in the structural check and are
excluded from this primary sample.

## Intervention

Immediately before each potentially qualifying baseline hand, the Hand object
is deep-copied.

The baseline hand runs normally.  If it contains a qualifying unopened raise,
the copy is replayed from the pre-hand state with the same cards, profiles,
reads, dynamics, and RNG state.

No decision is replayed and no strategy function is replaced.  The normal
preflop plan and normal shape_size call run in the counterfactual too, so RNG
consumption is identical up to the opener's raise application.

Only the first unopened raise target of the observed opener is replaced:

    cf_target_chips = round(max(2 * BB, base_target_chips * size_factor_shadow))

All later decisions are recalculated by the engine from the changed betting
state.  Baseline state is never overwritten by the counterfactual.

If the rounded target equals the baseline target, the row is recorded as a
zero intervention and is not replayed.

Limp remains shadow-only and is not changed.

## Hard harness checks

Any of these is a structural failure of the measurement:

1. before the intervention, the counterfactual preflop log prefix differs from
   the baseline prefix;
2. the normal counterfactual plan proposes a different opener action or
   different unmodified raise target before interception;
3. the sizing interception is not used exactly once on a changed row;
4. counterfactual target is below 2 BB or above the baseline target;
5. the target differs by more than one chip from the registered formula;
6. baseline or counterfactual table chips are not conserved;
7. an engine/counterfactual exception occurs.

These are harness checks, not poker-quality thresholds.

## Primary outcome

For the baseline opener:

    paired chip delta (BB)
      = counterfactual final-stack change
        - baseline final-stack change

The primary estimate is the mean paired chip delta across qualifying rows.
Because rows within one tournament seed are dependent, uncertainty is also
reported by seed: the tool bootstraps the 20 seed-level means with a fixed RNG
seed and reports a percentile 95% interval.

Interpretation is fixed before measurement:

- interval wholly below 0: evidence against promotion;
- interval wholly above 0: evidence supporting promotion;
- interval overlapping 0: chip-EV result is inconclusive.

This does not claim dollar-EV or ICM-EV equivalence.

## Secondary outcomes

Reported descriptively, with baseline and counterfactual values/differences:

- opponent call count after the open;
- whether a 3-bet/all-in raise occurs after the open;
- downstream preflop action-path change rate;
- flop-start pot in BB when a flop betting round exists;
- opener flop-start SPR when defined;
- showdown/fold result and winner-path change rate;
- paired chip-delta quantiles by stage and position.

No secondary cutoff will be invented after seeing the result.

## Promotion rule

Structural harness failure blocks promotion.

Otherwise the primary chip-EV interpretation above is reported together with
the secondary path changes.  A clearly negative primary interval blocks
promotion.  A clearly positive interval supports promotion.  An interval
overlapping zero is recorded as inconclusive rather than being converted into
a pass by a post-hoc tolerance.

The actual production sizing switch remains off during this measurement.
