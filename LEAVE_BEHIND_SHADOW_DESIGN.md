# Intentional leave-behind shadow design

Status: **locked before out-of-sample seeds 6200-6215 are observed.**

This design was chosen after exploratory seeds 6100-6107.  Therefore 6100-6107 is
the selection sample and must not be used as confirmatory evidence for this selector.

No production action is changed by this design.

## 1. Population

Only actions that satisfy all of the following are eligible:

1. postflop effective-all-in v1 classifies the action `effective=True`;
2. v1 would actually promote a non-all-in target:
   `pre_effective_target < actor_cap`;
3. decision kind is `facing_bet`.

Already-exact all-ins are not leave-behind candidates.

Free-action promotions are excluded from this first version.  The exploratory sample
showed no comparable positive survival-option cluster there, and free-action does not
share the same upstream BF semantics as facing-bet.

## 2. Survival signal without BF double-counting

The existing objective self-preservation signal contains both BF and a ladder component.
Facing-bet response logic already consumes BF upstream, so the execution selector must
not simply reuse the whole BF-including objective as its leave-behind reason.

Define the BF-free ladder component from existing signals:

```
ladder_component_objective
    = payout_importance
      * ladder_buffer
      * shorter_severity
      * waiting_feasibility
```

The same personality awareness already used by perceived self-preservation is recovered
without adding a new axis:

```
awareness
    = self_preservation / self_preservation_objective
```

when the objective denominator is positive, clamped to [0,1].

Then:

```
ladder_option_perceived
    = ladder_component_objective * awareness
```

This keeps the ladder option personality-sensitive while avoiding a second BF term.

## 3. Shadow candidate rule

A promoted facing-bet action is a shadow leave-behind candidate iff:

```
ladder_option_perceived > perceived_urgency
```

No numeric cutoff is added.

The rule means: preserve the non-all-in option only when the player's perceived payout/
ladder value of staying alive exceeds the perceived cost of waiting.

## 4. Execution amount if later enabled

Do **not** invent a one-BB residue.

If the selector is eventually enabled, v1 execution becomes:

```
effective_allin = True
  selector = shove
      -> actor_cap
  selector = leave_behind
      -> pre_effective_target
```

Therefore:

```
leave_amount = actor_cap - pre_effective_target
```

The leave amount is the already legal, personality/plan-shaped target that existed before
v1 normalization.  This avoids inventing a new bet size and preserves the planner's
original sizing coordinate.

## 5. Field-order safeguard

The exploratory strong candidate (seed 6107 H120) had:

- cycle remaining drift = 0
- cycle shorter-stack drift = 0
- action players-to-jump = cycle-start players-to-jump

Across all 15 exploratory promotions, cycle remaining drift was zero.  Shorter-stack
count drift was at most one.

The OOS audit must still report these values.  If a candidate depends on material
within-cycle drift, do not enable the selector until field-context timing is resolved.

## 6. OOS test — seeds 6200-6215

Before seeing these seeds, lock the following checks:

- engine errors = 0;
- money-observation join missing = 0;
- report total effective-all-in promotions;
- report shadow candidates and their decision class;
- every candidate must be a non-exact `facing_bet` promotion;
- report candidate ladder_option_perceived, urgency, residual BB, BF, jump distance,
  shorter stacks, and cycle drift;
- do not tune the rule from OOS rows.

No minimum or target candidate count is required.  Zero candidates is a valid result and
would mean the strategy is naturally rare under this field sample.

## 7. Non-goals

This shadow design does not:

- change production actions;
- change effective-all-in v1;
- add one-BB residue logic;
- alter BF/ICM formulas;
- add a personality axis;
- use target pressure as actor survival;
- change the frozen regression baseline.
