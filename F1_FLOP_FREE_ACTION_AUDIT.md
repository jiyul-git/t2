# Sequential audit — F1 flop, no wager yet

Status: CLEAR F1 SEMANTIC/DUPLICATE-GATE DEFECTS FIXED; multiway and emotion architecture remain open.

Reference model: judgment -> plan -> action.

## Situation

The flop is dealt and no one has bet yet when hero reaches a decision.

This includes distinct contexts:

1. hero was preflop aggressor and is first/OOP;
2. hero was preflop aggressor and action checks to hero IP;
3. hero was caller and acts before the preflop aggressor;
4. hero was caller and action checks to hero after the aggressor checks;
5. limped pot with no meaningful aggressor;
6. heads-up;
7. multiway with players still behind;
8. one or more opponents all-in while a live side-pot opponent remains.

## Judgment inputs

- exact hole cards / flop board;
- current made strength and draw structure;
- hero perceived range;
- each opponent perceived range;
- joint multiway equity;
- relative strength against relevant continuing ranges;
- nut advantage / range advantage;
- blocker/unblocker effects;
- board texture;
- position / players behind;
- preflop initiative and line;
- effective stacks / SPR;
- opponent reads;
- ICM/tournament context;
- stable skill limits.

Current emotion must not alter this judgment layer under the V2 architecture.

## Rational line-plan candidates

### Value
- value_3street;
- value_2street;
- thin/merged value;
- protection/equity denial;
- stack-off value.

### Control/showdown
- pot control;
- showdown/check;
- price-setting block only when a known aggressor/range relation makes the semantic label valid.

### Bluff/draw
- semibluff;
- pure bluff / multi-street bluff;
- giveup.

### Inducement
- trap / value induce;
- planned value check-raise.

The current-action plan then chooses:
- check;
- bet at a strategic size.

A later opponent bet is a new F3 judgment-plan-action event.

---

# What already matches the target reasonably well

## F1-K1 KEEP — line plan and current-action intent are already separate

`make_plan` creates the broader line plan.

`attach_intent -> decide_aggression -> decide_size` then creates a per-street intent.

That is close to the requested architecture:

```
judgment -> line plan -> current action plan -> execution
```

The intent stores `act / size / src`.

## F1-K2 KEEP — joint multiway equity now preserves opponent pools

The earlier multiway fix reaches `_eq_vs`, so hero equity can be evaluated against distinct
opponent range pools rather than one union duplicated N times.

This is closed and user-validated.

## F1-K3 KEEP — known-aggressor blockbet and no-aggressor lead are separated

A no-aggressor OOP lead is no longer mislabeled as blockbet/donk.

That semantic boundary remains valid.

---

# Fixed defects

## F1-1 FIXED — stochastic plan-permission gate ran twice

Before:

```
update_plan
 -> refresh
      -> _allowed(...)
 -> _allowed(...) again
```

For low/intermediate skill plans, `_allowed` is stochastic.

That means a plan could need to survive two independent permission rolls in one decision cycle,
silently multiplying the intended skill gate.

Fix:
`refresh` no longer calls `_allowed`.
The unique permission gate remains at the end of `update_plan`.

## F1-2 FIXED — flop thin-value decisions used turn thin-value skill

Old mapping:

`thin_value + flop -> thin_value_turn`.

So changing turn thin-value skill altered flop planning and flop value-bet execution.

The code already has `range_merge` specifically to represent flop/middle-strength merging.

Fix:

`thin_value + flop -> range_merge`

while turn and river keep their dedicated concepts.

No new concept was invented.

## F1-3 FIXED — checkraise_flop leaked into generic value betting

`persona.derive()['value']` sets:
- `xr` when `checkraise_flop` is high;
- `lead` for low aggression.

`decide_aggression` then changed generic value-bet probability based on that compatibility field.

So a flop check-raise skill could suppress generic value betting on later streets.

Fix:
live vector-profile value betting no longer consumes the derived `value` compatibility label.

Trap/induce is already selected explicitly at the line-plan layer.

## F1-4 FIXED — display label could alter blockbet planning

Vector profiles are supposed to be driven by concepts/temperament, while `type` is descriptive.

The blockbet path still applied a special fish multiplier from the display/archetype label.

Fix:
that archetype-label fallback is now legacy-only when no concept vector exists.

---

# Remaining architecture gaps

## F1-A MAJOR MULTIWAY GAP — rel/nut/range/blocker still use a union range

Joint equity is opponent-specific now.

But several other judgment inputs still consume the legacy union `opp_range`:

- `relative_strength`;
- `blocker_score / blocker_effect`;
- `nut_advantage`;
- `range_advantage`.

In multiway poker:

```
tight bettor range + loose caller range
```

is not generally equivalent to one union range.

Therefore the F1 judgment is only partially opponent-specific.

Do not fix this by averaging opponent ranges.
Each metric needs a defined multiway semantic.

## F1-B MAJOR MULTIWAY GAP — trap exploit uses one main opponent

Session selects one `_main` opponent for `opp_est`.

`trap_judgment` asks whether that opponent is likely to bet.

In multiway, the relevant event is closer to:
"what is the chance at least one appropriate opponent bets, and what free-card risk exists if all check?"

Using only the aggressor/deepest stack can miss the actual likely bettor.

## F1-C ARCH_MISMATCH — current tilt still changes judgment itself

`h.axes(seat)` still returns `tilted_view(base, tilt)`.

That modified profile changes:
- range reading;
- board-texture skill;
- blocker skill;
- SPR perception;
- calculated outs;
- other judgment inputs.

Under the locked user architecture:

```
stable-skill judgment
-> candidate plans
-> emotion biases plan choice
-> action
```

current emotion should not rewrite the judgment capability vector.

This remains a global refactor item and should not be patched piecemeal inside F1.

## F1-D ARCH_MISMATCH — execution can still reshape strategic size

`decide_size` selects strategic pot fraction, but session/runner `shape_size` can still alter
the final amount using player-style jitter.

Under V2, strategic style/randomness belongs before ACTION.

Execution should only perform:
- chip conversion;
- legal minimum;
- cap/rounding.

This is a global execution-boundary refactor.

## F1-E REVIEW — lead/donk/probe are not first-class action-mode provenance

The engine can usually infer the context from:
- initiative;
- OOP vs aggressor;
- previous street checks.

But the current intent generally says only `bet`.

For later story reasoning, it may be useful for current action plans to preserve form such as:
- cbet;
- lead/donk;
- no-aggressor lead;
- probe;
- value bet;
- semibluff bet.

Do not create separate persona skills merely for naming them.

## F1-F REVIEW — line plan labels still mix motive and execution form

`trap` is retained as a plan string for compatibility even though comments correctly state:

- goal = value extraction;
- mode = trap.

The newer `plan_goal / plan_mode` fields are the right direction.
Later refactor should make them primary rather than relying on the overloaded plan string.

---

# F1 decision

Local semantic defects above are fixed.

Do not calibrate frequencies yet.

Before F1 can be considered strategically complete, the larger architecture must still solve:

1. stable judgment profile vs emotion-biased plan selection;
2. opponent-specific multiway rel/nut/range/blocker semantics;
3. strategic sizing entirely before execution;
4. explicit action-form provenance.

Targeted verifier:
`tools/verify_f1_free_action.py`.
