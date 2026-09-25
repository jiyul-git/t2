# Sequential audit — F3 checked, then faces a bet

Status: CLEAR CHECKRAISE/RESPONSE-ROUTING DEFECTS FIXED; broader response architecture remains open.

Reference model: new information -> judgment -> plan -> action.

## Situation

Hero has already checked on the current street. A later opponent bets and action returns to hero.

Canonical forms:

1. hero checks -> one opponent bets -> hero;
2. hero checks -> bet -> caller(s) -> hero;
3. hero checks -> bet all-in -> hero;
4. hero checks -> short incomplete all-in raise changes the price -> hero;
5. multiway check -> bet -> raise before hero returns;
6. trap/induce line receives the expected bet;
7. semibluff/checkraise candidate receives a bet;
8. prior giveup/showdown plan receives new information and must re-judge.

This is a **new decision event**. The earlier check is not permission for execution to improvise later.

## Rational judgment inputs

- updated opponent-specific ranges after the current bet/calls/raises;
- hero joint equity;
- exact pot odds;
- current made/draw strength;
- prior line plan and current refreshed plan;
- bettor identity / estimated range;
- players still behind;
- legal raise right;
- opponent response-to-raise read when available;
- effective stacks / SPR;
- ICM.

## Rational response plans

- fold;
- call / bluff-catch;
- value check-raise;
- semibluff check-raise;
- bluff check-raise;
- check-raise shove where stack geometry warrants it.

A raise after checking must be produced by the **check-raise response planner**, not by a generic
raise path that bypasses check-raise skill.

---

# Fixed defects

## F3-1 FIXED — two independent check-raise producers

Old path:

```
act_with_plan
 -> decide_response
      -> generic value/reraise/bluff/semibluff raise can already happen
 -> session
      -> only if generic returned call/fold:
           checkraise_decision
           -> maybe overwrite action to raise
```

Consequences:

- generic raises could bypass `checkraise_flop/checkraise_late`;
- the same decision event had two separate strategic producers;
- session changed the action after the response planner had already returned.

Fix:

```
act_with_plan
 -> if checked_before and raise legal:
      checkraise_decision is the only raise producer
 -> if gate declines:
      decide_response(... allow_raise=False)
 -> session executes the returned response only
```

Session no longer performs a post-hoc checkraise override.

## F3-2 FIXED — incomplete-all-in raise rights reach postflop response planning

The same invariant already fixed preflop now applies here.

If `Round.can_raise(seat)` is false:

- checkraise gate is not called;
- generic response raises are disabled;
- response plan is fold/call only.

Execution no longer has to discover an illegal strategic raise and replace it.

## F3-3 FIXED — river bluff-catch skill leaked into flop/turn behavioral bias

`persona.bias('bluff_fear')` and `persona.bias('hero_call')` always read
`bluffcatch_river`.

Therefore changing river bluff-catch skill changed flop and turn call/fold behavior.

Fix:

- flop/turn use `bluffcatch_early`;
- river uses `bluffcatch_river`;
- `call_bias` and the final response bias both pass the current street.

## F3-4 FIXED — display label could change vector-profile line-read trust

`calldown_need` reduced read trust for an archetype-family `fish` based on `profile['type']`.

For modern vector profiles, `type` is descriptive and must not change strategy independently.

Fix:
the archetype-family modifier is legacy-only when no concept vector exists.

## F3-5 FIXED — fold-to-bet was used as fold-to-checkraise evidence

`checkraise_decision` used `street_gap`, which is based on fold-to-bet.

Those are different events:

- fold-to-bet: opponent checks/faces a bet and folds;
- fold-to-raise: opponent bets first, then faces a raise and folds.

Using one as the other creates false exploit information.

Fix:
the incorrect fold-to-bet adjustment was removed.

No arbitrary replacement coefficient was invented.

---

# Remaining strategic gaps

## F3-A MISS — dedicated postflop fold-to-raise observation is still absent

A strong exploitative checkraise system should learn:

```
opponent bets
-> faces raise/checkraise
-> fold/call/reraise
```

by street and with sample confidence.

Until that exists, checkraise fold-equity should stay neutral rather than borrowing fold-to-bet.

## F3-B ARCH_MISMATCH — response plan is traced but not yet a first-class intent object

Free-action decisions already use `intent[street]`.

Facing-bet responses are still returned as an action tuple with trace/provenance.

The final V2 architecture should preserve a current response-plan object such as:

- `call_bluffcatch`;
- `call_draw_realize`;
- `value_checkraise`;
- `semibluff_checkraise`;
- `bluff_checkraise`;
- `fold`.

## F3-C MULTIWAY GAP — players behind are mostly represented by a count

`to_act_behind` increases call requirements, but separate behind-player:

- ranges;
- raise propensity;
- stacks;
- side-pot status

are not first-class response inputs.

## F3-D MULTIWAY GAP — several plan-state strength metrics still use union range semantics

Joint equity is opponent-specific, but relative/nut/range/blocker semantics remain partially union-based.

That affects the plan state that checkraise consumes.

## F3-E ARCH_MISMATCH — response sizing still crosses the execution boundary

`checkraise_size` makes a strategic sizing decision, after which session can still apply
`shape_size`.

Under V2, all strategic sizing/style randomness should be finished before ACTION.
Execution should only legalize/convert/round.

## F3-F GLOBAL — emotion still contaminates judgment

The response receives the tilted profile today.
That global violation remains unchanged from F1/F2.

---

# F3 decision

The duplicate checkraise producer and street/domain leaks are fixed.

Do not calibrate checkraise frequencies yet.

Before exploitative checkraise can be called complete, add a dedicated fold-to-raise observation
channel and include it in the later opponent-read architecture.

Targeted verifier:
`tools/verify_f3_checkraise_response.py`.
