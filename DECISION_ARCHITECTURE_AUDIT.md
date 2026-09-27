# Decision architecture audit — working map

This document is the authoritative structural map for the current audit.
It is intentionally separated from prior calibration work.

## 1. Current decision pipeline

### Preflop

```
preflop_plan
  -> open_decision / iso_decision / defend_decision
  -> action + size + pf_seed
```

`pf_seed` is carried into postflop state.

### Postflop, not facing a bet

```
update_plan
  -> make_plan or revise_plan
  -> refresh
  -> river_fix
  -> _allowed
  -> attach_intent
       -> decide_aggression
       -> decide_size
  -> act_with_plan executes the stored intent
```

This path is intended to have one strategic owner for bet/check and one owner for size.

### Postflop, facing a bet

```
act_with_plan
  -> calldown_need
  -> decide_response
       -> fold / call / raise
```

After this generic response, session currently runs a second check-raise layer **only when
the generic response returned call/fold and the player checked earlier on this street**:

```
decide_response -> call/fold
  + already_checked
  -> checkraise_decision
  -> optional raise
```

Therefore a real check-raise can currently be produced in two different places.

## 2. Confirmed architecture defects / hazards

### A. Check-raise has duplicate action producers

`decide_response` can return raise before `checkraise_decision` is reached.
That generic raise can use `reraise`, `bluff`, `semibluff`, `stackoff`, etc.

Consequence: a player can execute a check-raise without the declared `checkraise_*`
skill governing the action.

Status: DUP / requires rerouting design.

### B. Street resolution is inconsistent

Current aliases:

- checkraise: flop / late(turn+river)
- bluffcatch: early(flop+turn) / river
- thin_value: turn alias also used on flop / river

Status: SHARED. Split decision must be semantic, not automatic.

### C. Preflop reads postflop thin-value skill

`preflop.defend_decision()` reads generic `thin_value`.
The alias resolves to `thin_value_turn`.

Consequence: a postflop turn thin-value skill changes preflop 3-bet/call composition.

Status: LEAK.

### D. Trap permission can use the wrong street skill

`_allowed(plan='trap')` requires generic `checkraise`.
The alias resolves to `checkraise_flop`, regardless of current street.

Consequence: a turn/river trap can be allowed/blocked by flop XR skill.

Status: LEAK.

### E. Derived `value='xr'` is anchored to flop XR but used later

`persona.derive()` sets `value='xr'` from `checkraise_flop >= 6.5`.
Later this field changes trap taste and general value-bet frequency.

Consequence: a flop XR trait leaks into later-street value execution.

Status: LEAK / compatibility field review.

### F. River bluff-catch skill leaks into earlier-street biases

`bluff_fear` and `hero_call` always read `bluffcatch_river`.
Those biases are then used by generic call decisions on earlier streets.

Status: LEAK / bias model review.

### G. Reactive river bluff check-raise lacks the observation it really needs

Current opponent book has:

- street-specific fold-to-bet;
- bet sizing mean/variance;
- aggression/passivity;
- showdown evidence.

It does **not** separately track:

```
opponent bets -> faces raise -> folds
```

That is strategically different from fold-to-bet.

Consequence: a model for "small river value bet looks capped, raise only enough to fold
that thin-value region" cannot directly estimate the opponent's fold-to-raise tendency
from current observations.

Status: MISS in perception data, if reactive bluff XR is adopted.

### H. Current `river_bluff` is a proactive line, not the same as reactive bluff XR

`river_fix` creates `river_bluff` after a missed draw using:

- bluff;
- barrel_river;
- blocker effect.

That state then feeds proactive river betting.

This should not be conflated with:

```
check -> observe opponent river bet -> reinterpret range/size -> bluff check-raise
```

They are different decision events.

Status: semantic separation required.

## 3. Current concept layers

### Motive / strategic goal

Examples:

- bluff
- semibluff
- thin value
- pot control
- trap
- range merge
- stack-off/value extraction

### Execution form

Examples:

- c-bet / barrel
- check-raise
- block bet
- probe
- delayed c-bet
- overbet
- reraise
- open / 3-bet forms

### Perception / calculation

Examples:

- range_read
- sizing_tell
- blocker
- fold_equity
- board_texture
- outs
- potodds
- spr
- icm

Target rule: composite actions should combine layers instead of introducing a single
monolithic skill whenever possible.

## 4. Inspection grid to finish before any code redesign

Every strategic row must answer:

1. What event creates the decision opportunity?
2. Is this proactive, reactive, or deliberately induced?
3. Which function owns the final action?
4. Which concept(s) determine motive?
5. Which concept determines execution form?
6. Which perception/calculation inputs are available?
7. Is any input coming through a generic alias or derived compatibility field?
8. Can another function create the same final action first?
9. Does the required opponent statistic actually exist?
10. Is street sharing intentional and semantically defensible?

Only after this grid is complete should a row be marked:

`KEEP / SPLIT / ADD / REROUTE / REMOVE_COMPAT / ADD_OBSERVATION`.

## 5. Work order

1. finish complete decision/concept/observation matrix;
2. lock taxonomy;
3. lock one-owner routing for each final action;
4. add missing observation channels only where required;
5. implement concept splits/additions;
6. targeted counterfactual tests;
7. frozen regression;
8. regenerate realized prior distribution;
9. only then calibrate LOADING/SPREAD.

No production strategic coefficients are changed by this audit.


## 6. Emotion boundary — newly locked rule

User design decision:

> Emotional state may influence **plan / re-plan selection only**.  Once a plan or response-plan
> is chosen, execution must follow it except for legality/chip conversion.

The current strategy does **not** yet activate this boundary, but the pre-logic
plumbing now exposes it explicitly.

`play.Hand` now has `base_profile`, `planning_profile`, `execution_profile`, and
`profile_views`.  For exact behavior preservation, production `axes()` is deliberately
pinned to `planning_profile()`, which is the same `PS.tilted_view(base, t)` behavior as before.
No current action consumer has been switched to `execution_profile()` yet.  Therefore tilt can
still alter concept/temper values broadly; changing those consumers is F7-C **logic activation**,
not plumbing.

Target architecture:

```
base_profile
   |
   +--> planning_view(base_profile, emotion_state)
   |       -> choose/revise plan or response-plan
   |
   +--> execution_view(base_profile)
           -> execute stored intent; legality/chip conversion only
```

A reactive event (for example, check -> opponent river bet) is itself a new planning event.
Emotion may bias the newly selected response-plan there, but may not subsequently rewrite the
selected fold/call/raise or strategic size during execution.

Status: PRE-LOGIC BOUNDARY SCAFFOLDED / STRATEGY ACTIVATION DEFERRED.
`tools/verify_prelogic_profile_boundary.py` proves the new views preserve historical
`axes()` behavior before activation.


## 7. Locked decision-cycle invariant

Every voluntary poker action must be produced by the same conceptual cycle:

```
JUDGMENT
-> PLAN
-> ACTION
-> new information/event
-> JUDGMENT
-> PLAN
-> ACTION
-> ...
```

Definitions:

- **Judgment** = interpret the currently available state: hand/range strength, board, position,
  stack geometry, opponent model, tournament context, previous action story, and perception limits.
- **Plan** = choose the strategic intention for the next decision horizon.  The horizon may be
  multi-street (for example value_3street / bluff_2street / trap) or immediate/reactive
  (for example bluff-catch call, value raise, river bluff check-raise).
- **Action** = execute the already chosen plan as fold/check/call/bet/raise/shove with its strategic
  size.  Execution may apply only legality/chip conversion; it must not invent a new strategy.

A long-horizon plan is context, not an instruction that skips later judgment.  New information
(board card, opponent bet/raise/check, player elimination/ICM change, stack change, etc.) creates
a new judgment event, which may preserve, revise, or replace the prior plan.

Emotion/tilt belongs only in the **PLAN selection/revision step**.  It may bias which candidate
plan wins, but it does not independently mutate ACTION after the plan has been selected.

### Current-code mismatch against this invariant

The current engine only partially follows this cycle:

- proactive postflop play has a plan state and stored street intent;
- facing-bet responses are selected separately inside `act_with_plan -> decide_response` rather
  than being represented as a new explicit response-plan;
- same-street stored intent is not re-created merely because an opponent later bet/raised;
- check-raise can be produced by both the generic response path and a later checkraise-specific gate;
- preflop decisions return actions directly rather than a uniform explicit plan object;
- the tilted profile is passed broadly, so emotion is not currently confined to plan selection.

These are architecture findings, not yet behavior changes.

### Pre-logic execution boundary scaffold

F7-D now records the execution transformation chain without changing it:

`calculated_target -> execution_input_target -> shaped_target -> legal_target
-> final_target -> applied_target`.

The same intent record also identifies replay vs fresh judgment, whether expression shaping was
called/changed the target, whether minimum-raise clamping occurred, and whether
`effective_allin_v1` promoted the legal target to actor-cap shove.

This is provenance only.  `plan.act_with_plan` still owns strategic action/size judgment;
`session.HandRun` still performs the existing expression/legal conversion.  Moving or removing
those conversions is F7-D logic/refactor activation and is deliberately deferred.

Gate: `tools/verify_prelogic_execution_boundary.py` plus the frozen production fingerprint.
