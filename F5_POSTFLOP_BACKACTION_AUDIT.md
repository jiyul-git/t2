# Sequential audit — F5 hero aggressed, then faces a raise/re-raise

Status: CLEAR BACK-ACTION COORDINATE/READ-CLASSIFICATION DEFECTS FIXED; strategy model remains incomplete.

Reference model: judgment -> response plan -> action.

## Situation

Hero has already bet or raised on the current postflop street, then a later opponent raises and
action returns to hero.

Canonical cases:

1. hero bet -> opponent raise -> hero;
2. hero bet -> call -> later raise -> hero;
3. hero raise -> opponent re-raise -> hero;
4. hero bet/raise -> incomplete all-in raise -> hero;
5. hero bet/raise -> all-in full raise -> hero;
6. multiway hero bet -> one caller -> another raise -> hero;
7. side-pot/live-stack variants.

This is distinct from:

- F4: hero had not previously aggressed and faces a wager;
- F3: hero checked, then faces a bet and may check-raise;
- POST-E: hero previously called and a later raise reopens action.

## Rational judgment inputs

- hero's earlier aggressive action and strategic motive;
- exact amount hero already contributed this street;
- exact new call price;
- exact raise size and pot before that raise;
- raiser's perceived range;
- other live opponents and their ranges;
- whether raise rights remain open;
- current pot / effective stacks / side pots;
- hero's made/draw strength and joint equity;
- stack-off commitment plan;
- opponent fold-to-raise / re-raise behavior when enough evidence exists;
- ICM;
- stable skill/perception limits.

## Response-plan candidates

- fold;
- call / bluff-catch / draw continue;
- value re-raise;
- semibluff re-raise on flop/turn;
- bluff re-raise where coherent;
- shove / effective-all-in where legal.

The response plan must be expressed in the same chip-coordinate system that Round.apply expects.

---

# Fixed defects

## F5-1 FIXED — re-raise target forgot hero's already-invested contribution

`act_with_plan` returns a postflop raise amount that session passes to `Round.apply` as a
**street total-contribution target**.

Old formula:

```
target = (pot + 2 * tocall) * multiplier
```

works only when hero has contributed zero this street.

Example:

```
start pot 100
hero bets 50
villain raises to 150
hero contribution = 50
pot_live = 300
hero tocall = 100
```

A pot-size re-raise target is:

```
50 + 300 + 2*100 = 550
```

Old code returned 500, silently losing hero's existing 50-chip coordinate offset.

Fix:

```
target = hero_contrib + response_raise_base
```

The first-action case remains unchanged because `hero_contrib=0`.

## F5-2 FIXED — raise cap used remaining stack instead of total reachable target

Old:

`min(remaining_stack, target)`.

But `Round.apply` expects a total street target.

If hero already has 50 in and 300 behind, maximum legal target is 350, not 300.

Fix:

`max_target = hero_contrib + remaining_stack`.

## F5-3 FIXED — "is this only a call?" comparison mixed coordinates

Old code compared:

`raise_target <= tocall`.

For back-action:
- raise target is a total street contribution;
- `tocall` is only the incremental amount.

Those are different coordinate systems.

Fix:

`call_target = hero_contrib + tocall`.

A planned target at or below that point is converted to a call before execution.

## F5-4 FIXED — fold-to-bet was contaminated by fold-to-raise

Old postflop observation passed `facing_bet=True` once any wager had appeared on the street.

Thus:

```
hero bets
opponent raises
hero folds
```

could increment `fold_to_bet`.

That statistic is used to model ordinary response to a bet and must not include response to a raise.

Fix:
postflop observation now classifies the exact event before every action as:

- no wager;
- facing bet;
- facing raise.

Separate shadow counters now track:
- `facing_raise / fold_to_raise`;
- street-specific flop/turn/river versions.

No population prior or exploit coefficient was invented.
The new fold-to-raise channel is SHADOW until enough strategic design/calibration exists.

## F5-5 FIXED — postflop re-decision class was not preserved

The live response calculation knew only `tocall > 0`.

It did not preserve whether the current event was:
- first bet faced;
- cold raise faced;
- hero check -> bet;
- hero bet/raise -> re-raise;
- hero call -> later raise.

Fix:
session now records `response_kind` from public current-street action history:

- `free_action`;
- `face_bet`;
- `check_then_face_bet`;
- `cold_facing_raise`;
- `aggressor_backaction`;
- `caller_backaction`.

For F5, hero bet/raise -> opponent raise is `aggressor_backaction`.

The kind is passed into `act_with_plan`, response trace, and intent/execution provenance.

---

# What remains structurally sound

## F5-K1 KEEP — legal raise rights are already passed before response selection

Incomplete all-in raise rights are handled through `Round.can_raise`.

If re-raising is illegal, raise candidates are removed before action execution.

## F5-K2 KEEP — exact facing-wager fraction is already preserved

F4 fixed the raiser's current action size as:

`new chips on that action / pot immediately before the action`.

That remains valid for F5.

## F5-K3 KEEP — current opponent action already narrows perceived range before response

Session includes current-street action history in each opponent's perceived range before the hero
response.

---

# Remaining strategic gaps

## F5-A MAJOR MISS — raise-range inference still treats bet and raise similarly

`ranges.narrow_by_actions` receives the literal action name, but its current aggressive branch
sends:

- bet;
- raise;
- all-in raise

through the same `_bet_range` machinery.

A raise after hero bets is not strategically equivalent to a first bet.

Do not fix this by simply multiplying range strength by an arbitrary constant.
A future response model should define:
- value-raise region;
- semibluff/bluff-raise region;
- stack/size dependence;
- opponent raise tendency.

## F5-B MAJOR MISS — fold-to-raise read is collected but not yet consumed

This is deliberate.

F3 previously borrowed fold-to-bet, which was semantically wrong.
F5 now creates the correct observation channel.

Later bluff re-raise / check-raise exploit logic may consume fold-to-raise only after:
- sample confidence;
- street semantics;
- raise-size context;
- prior population model

are explicitly defined.

## F5-C ARCH_MISMATCH — generic response still shares one action selector across first bet and re-raise

`response_kind` is now preserved, but `decide_response` does not yet branch explicitly on it.

For example, one-pair value against a first bet and the same hand after hero bet -> raise should
not necessarily use the same raise/call thresholds.

This belongs in the future explicit response-plan object.

## F5-D MULTIWAY GAP — raiser and prior callers are not jointly represented in exploit logic

Joint equity sees separate range pools.

But response quality still uses one primary aggressor read plus aggregate/union information in
several places.

In:

```
hero bet -> A call -> B raise -> hero
```

hero needs to reason separately about:
- B's raise range;
- A's capped/continuing range;
- A's possible re-action;
- stacks and side-pot eligibility.

## F5-E GLOBAL — emotion and execution sizing boundary remain open

As in F1-F4:
- current tilt still mutates judgment inputs through `tilted_view`;
- `shape_size` can still alter strategic sizing after the plan is chosen.

These are global V2 refactors.

---

# Verification target

`tools/verify_f5_backaction.py` checks:

1. re-raise target includes hero's existing contribution;
2. raise cap uses total reachable contribution;
3. call-target comparison uses the same coordinate system;
4. bet-facing and raise-facing fold reads are separated;
5. current-street facing sequence is classified correctly;
6. hero bet/raise -> opponent raise is preserved as `aggressor_backaction`.
