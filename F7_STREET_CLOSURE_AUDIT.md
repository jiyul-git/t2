# Sequential audit — F7 postflop street closure / carry-forward

Status: CLEAR ACTION-STORY CARRY DEFECTS FIXED IN BRANCH; strategy architecture remains open.

Reference model: judgment -> plan -> action -> observed result -> next judgment.

## Situation

Hero or an opponent has acted, no further raise occurs, and the betting round closes.

This is POST-F from `OPPONENT_ACTION_COVERAGE_V1.md`.

Canonical outcomes after the last aggressive action:

1. everyone folds;
2. exactly one call;
3. multiple calls;
4. one all-in call;
5. calls plus one/more all-in calls;
6. no wager at all -> check-through;
7. a prior main-pot all-in exists while live players close a side-pot street.

The next street must start from the exact public action story that actually happened.

---

# Rational carry-forward state

The next judgment needs:

- who made the last aggressive action;
- who called it;
- which calls exhausted stacks;
- exact action-time size of every bet/raise/call;
- full vs incomplete raise semantics;
- each opponent's narrowed range after those actions;
- previous line plan and response plans;
- initiative;
- remaining live stacks;
- main-pot/side-pot eligibility;
- board transition.

A final action string alone is not enough.

---

# Fixed defects

## F7-1 FIXED — completed-street range narrowing used the wrong size coordinate

Current-street narrowing had already been improved to reconstruct action-time pot size.

But once the street closed, `_acts_of` fell back to `full_log` and calculated:

`recorded target / street-start pot`.

That is wrong for raises.

Example:

```
start pot 100
A bets 50          -> pot 150
B raises to 150    -> B newly puts 150
```

The strategically meaningful raise size is:

`150 / 150 = 1.00 pot`

not:

`150 / 100 = 1.50 pot`.

Because `ranges.narrow_by_actions` consumes size fraction, the same public hand could be read
differently on the current street and again on the next street.

Fix:
completed streets now use `full_action_meta.increment` and reconstruct the pot immediately before
each action.

## F7-2 FIXED — all-in call became an aggressive range action after carry-forward

Raw log spelling uses `allin` for both:

- all-in call;
- all-in bet/raise.

`ranges.narrow_by_actions` treats raw `allin` as aggression.

So an opponent who merely called off could be remembered on the next street as if they had
bet/raised.

Fix:
both current and completed street range stories now normalize through
`_observed_postflop_action`:

- all-in call -> `call`;
- price-increasing all-in -> `raise`.

## F7-3 FIXED — POST-F aggregate outcome was only reconstructible, not explicit

The raw action history remains the source of truth, but the engine had no explicit street-closure
provenance saying whether the last aggression received:

- zero calls;
- one call;
- multiple calls;
- all-in call(s);
- or no wager existed.

Fix:
`_postflop_street_outcome` stores a per-street summary in `h.street_outcomes`.

This is provenance only for now; it does not add a strategy multiplier.

Kinds:

- `checkthrough`;
- `all_fold`;
- `one_call`;
- `one_allin_call`;
- `multi_call`;
- `multi_call_with_allin`.

## F7-4 FIXED — postflop showdown aggressor semantics still trusted raw `allin`

The normal showdown reveal order looks for the last aggressor.

Using raw `allin` could classify an all-in caller as the last aggressor.

Showdown aggression observation also missed postflop all-in raises because it only accepted
`bet/raise` strings.

Fix:
when postflop action metadata exists:

- last aggressor = last live actor with `raised=True`;
- aggressive showdown actor = any postflop actor with `raised=True`.

Preflop-only legacy fallback remains unchanged.

---

# What remains sound

## F7-K1 KEEP — initiative carries from the actual last aggressor

Postflop human and bot branches now update aggressor from rule-event `raised`, not raw
`allin` spelling.

A call-off therefore does not steal initiative.

## F7-K2 KEEP — opponent pools are re-narrowed from the complete public story

At the next decision, each opponent gets its own perceived range pool and historical/current actions
are applied before equity is computed.

The F7 fixes make those historical actions semantically consistent with current-street actions.

---

# Remaining strategic gaps

## F7-A MAJOR SIDE-POT GAP — closure provenance is not side-pot EV decomposition

If one player is already all-in and two deep players continue, a later call/fold decision can involve:

- locked main-pot equity;
- marginal side-pot equity;
- different opponent sets for each pot.

`street_outcomes` does not solve that.  It only preserves the event class.

This remains a dedicated next architecture problem.

## F7-B MULTIWAY GAP — range/nut/blocker semantics still use union consumers

Opponent-specific equity pools are preserved, but several other metrics still consume the union
range.  Carry-forward is now exact; interpretation is not yet fully multiway-native.

## F7-C GLOBAL — emotion still alters judgment

Current `tilted_view` remains upstream of judgment.

Under V2, emotion must bias plan selection only.

## F7-D GLOBAL — execution still reshapes strategic size

`shape_size` remains after the strategic size decision.

That boundary will be refactored globally rather than patched per street.

---

# Verification target

`tools/verify_f7_street_closure.py` checks:

1. completed-street raise size uses action-time pot, not street-start pot;
2. completed all-in call is remembered as call;
3. current-street all-in call is also normalized as call;
4. POST-F closure classes distinguish normal/all-in/multi callers;
5. postflop showdown aggression uses rule-event metadata.
