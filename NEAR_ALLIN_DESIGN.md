# Near-all-in sizing normalization design

## Observation

Read-only audit on seeds 6000-6007 (standard, 24 entries):

- aggressive postflop actions: 1,439
- actual all-in/clamped: 77
- non-all-in aggressive: 1,362
- non-all-in commit >=95%: 44
- of those 44, residual <=1BB: 30; <=2BB: 38; <=5BB: 44

The extreme tail is real, but a fixed threshold such as ">=95% -> shove" is not
adopted yet.

## Root cause found in code

`plan.act_with_plan` caps a computed bet/raise to the available stack before
returning it.  That exact all-in target then goes through `runner.shape_size`,
which applies archetype jitter / odd sizing.  A negative jitter can therefore
turn an intentional exact stack target into a non-all-in target that leaves a
small residual stack.

Example from the audit:

```
stack=49,900, pot=114,400, intent_size=.59
plan conversion: min(49,900, round(114,400*.59)) = 49,900  # exact stack
executed pre-clamp after shape_size: 49,700
residual: 200
```

This is not an ICM "leave chips behind" concept.  No such concept currently
exists in the bot.

## Locked first correction

Preserve only an **exact pre-shape all-in target**.

For a live postflop bet/raise:
- compute the maximum total target as current remaining stack + current-street
  contribution;
- if the decision-layer target is already at that maximum, do not pass it
  through `shape_size`;
- otherwise keep the existing `shape_size` behavior unchanged.

This is a semantic-preservation fix, not a new shove threshold.

## Explicitly not changed

- no >=80/85/90/95% auto-shove rule
- no residual-BB threshold
- no ICM leave-1BB concept
- no plan probabilities or sizing coefficients
- no preflop sizing change
- no replayed-action reshaping
- no Round.apply legality change

## Verification order

1. compile + frozen regression
2. rerun the same near-all-in audit seeds 6000-6007
3. compare:
   - actual all-in/clamped count
   - >=95% non-all-in tail
   - <=1/2/3/5BB residual counts
   - extreme examples
4. inspect the remaining tail before deciding whether any second-stage
   near-all-in normalization is justified.


## Regression note after first correction

After commit `931d793`, frozen regression reports only seed 3001 as changed while aggregate
VPIP/PFR/flop rates remain the same. Comparing the design-lock commit `492874c` to
`931d793` shows that the only production file changed is `session.py`, and the only
behavioral change is preserving an exact pre-shape all-in target instead of passing it
through `shape_size`.

Therefore this fingerprint change is expected in principle, but the frozen baseline is
not updated yet. The same near-all-in audit must be rerun first to confirm that the
changed behavior lands in the intended all-in tail rather than introducing an unrelated
side effect.
