# Effective-all-in v1 design

Branch: `chatgpt/effective-allin-v1-20260925`

## Context locked before implementation

The near-all-in audit has already separated two different meanings of
"effective":

- **actor-effective**: the acting player is the limiting stack and can actually lose
  the rest of its stack to at least one opponent;
- **opponent-effective**: an opponent is shorter, so the actor may still retain a large
  stack even though the opponent is effectively all-in.

Only **actor-effective** rows are eligible for deciding whether the actor should be
normalized to a physical shove.

The 6000-6007 actor-effective non-all-in sample contained:

```
commit       postSPR<=.02  <=.03  <=.05  <=.10
>=85%                  4       5      6      16
>=90%                  4       5      6      11
>=95%                  4       4      4       4
```

The six rows at `commit>=90% AND postSPR<=0.05` are:

- 99.2%, postSPR 0.00
- 98.3%, 0.01
- 98.0%, 0.01
- 97.5%, 0.02
- 93.8%, 0.03
- 93.1%, 0.05

At `postSPR<=0.10` the >=90% population jumps from 6 to 11 and starts admitting
materially larger residual stacks.  Therefore v1 deliberately uses the tighter elbow.

## v1 classifier

Evaluate **after** personality shaping and legal minimum-raise flooring, because the
question is whether the final legal wager leaves a strategically negligible actor stack.

A non-replay bet/raise is classified as actor effective-all-in when all are true:

1. `actor_cap <= opp_cap_max`
2. final legal target / actor_cap >= 0.90
3. actor residual / pot-after-action <= 0.05

Where:

- actor_cap = current-street contribution already made + remaining stack
- final legal target is capped to actor_cap
- pot-after-action = the actor-visible contestable pot before action + new chips put in
- actor residual = actor_cap - final legal target

## Execution layering

Classification and execution are separate.

```
final legal target
    -> effective-all-in classifier
        -> false: keep target
        -> true : execution mode
                    -> shove          (v1 implemented mode)
                    -> leave-behind   (reserved future mode)
```

This is intentional: effective-all-in and leaving ~1BB behind are not opposites.
A future ICM/money-jump concept may classify the wager as effective-all-in and then choose
an explicit leave-behind amount.  That behavior must be logged as an intentional mode,
not produced accidentally by sizing jitter.

v1 has no leave-behind policy.  A classified action defaults to physical shove.

## Exclusions

v1 does not:

- classify opponent-effective rows as actor shoves;
- alter preflop;
- alter calls/folds/checks;
- invent an ICM threshold;
- add a 1BB leave-behind rule;
- change plan probabilities or sizing coefficients;
- re-normalize replayed actions.

## Validation

First run targeted unit-style verification of the classifier, then frozen regression.
After that run the same 6000-6007 audit plus an out-of-sample 6100-6107 audit.

The in-sample expectation is not a fixed hand count because normalizing one action can
change later tournament trajectories.  The invariants are:

- no engine errors;
- classified actor-effective near-all-ins execute as full actor-cap shoves;
- opponent-effective cases are not promoted merely because they cover the opponent;
- replayed actions stay unchanged;
- no accidental leave-behind semantics are introduced.
