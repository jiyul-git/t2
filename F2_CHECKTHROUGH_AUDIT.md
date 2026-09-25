# Sequential audit — F2 flop checks through / turn continuation context

Status: CLEAR CHECK-THROUGH / DELAYED-CBET / PROBE FLOW DEFECTS FIXED; broader multiway/emotion architecture remains open.

Reference model: judgment -> plan -> action -> new information -> judgment -> plan -> action.

## Situation

The flop ends without a bet and the hand reaches the turn.

Canonical cases:

1. preflop aggressor checks flop OOP, opponent checks back;
2. action checks to preflop aggressor IP, aggressor checks back;
3. multiway flop checks through;
4. trap/induce plan checks and nobody bites;
5. caller checks through with aggressor, creating a later probe opportunity;
6. limped pot checks through with no meaningful aggressor.

The turn is a **new judgment event**.  The flop plan can inform it, but cannot suppress re-judgment.

## Rational turn distinctions

### Delayed cbet
The preflop aggressor skipped the flop and now gets a turn betting opportunity.

### Probe
A non-aggressor attacks after the prior aggressor declined to bet on the previous street.

### Trap no-bite
Hero intentionally checked a value/trap line, nobody bet, so the concealment mode failed and the
value goal may need to switch to direct extraction.

### Ordinary check-through
No special initiative story exists, especially in limped/no-aggressor pots.

These must not all be labeled as ordinary barrel continuation.

---

# Fixed defects

## F2-1 FIXED — probe context was written after the current action intent was already frozen

Old order:

```
update_plan
  -> attach_intent
session sets opp_checked_prev
act_with_plan executes old intent
```

So the probe flag could exist in state but was too late to affect that turn action.

Fix:
session computes the previous-aggressor check-through context before `update_plan` and passes it
into the plan pipeline.

`update_plan` stores it before `attach_intent` runs.

## F2-2 FIXED — delayed-cbet state used intended flop action instead of actual executed action

Old `refresh` inferred `flop_checked` from:

`plan_state['intents']['flop']`.

That is wrong when:
- forced replay changes the action;
- sizing legality causes a fallback;
- another execution deviation occurs.

Fix:
actual executed actions are now stored per street in `executed_actions`.

Turn refresh uses actual flop execution first and only falls back to intent for legacy states.

## F2-3 FIXED — executed action history could disappear on plan replacement

Board-change revision and update-plan state carryover previously preserved:
- intents;
- deviations;
- bet streets;
- plan_since;
- signatures.

But not actual executed action history.

Fix:
`executed_actions` is now preserved through both:
- `runner.revise_plan`;
- `plan.update_plan`.

## F2-4 FIXED — delayed cbet was counted as an ordinary barrel

Old postflop observation logic labeled any turn action by `street_aggr` as a barrel opportunity.

After a flop check-through, the preflop aggressor remains the line aggressor, so:

```
PFR checks flop
turn arrives
PFR bets
```

was recorded as a barrel despite no flop cbet.

Fix:
- barrel opportunity requires that the same aggressor actually bet the previous street;
- turn-after-flop-check-through is observed separately as delayed cbet.

New delayed-cbet read channel is SHADOW only for now:
- `delayed_cbet_opp`;
- `delayed_cbet`;
- perceived delayed-cbet rate/count.

No strategy coefficient was invented from it yet.

## F2-5 FIXED — delayed-cbet skill was bypassed in the representative giveup/showdown line

`decide_aggression` previously returned from the giveup/showdown cbet branch **before**
`delayed_cbet` skill was calculated.

So the dedicated delayed-cbet concept did not affect one of the most natural delayed-cbet spots.

Fix:
the delayed-cbet context/skill factor is computed before that branch.

## F2-6 FIXED — delayed-cbet skill affected bluff lines but not delayed value

A delayed-cbet range must contain value and bluffs.

Old code boosted delayed aggression for bluff/semibluff lines only.

Fix:
the same existing delayed-cbet skill factor now also affects turn value betting after an actual
flop check-through.

This does not add a new coefficient; it applies the already-existing delayed-cbet multiplier to
both halves of the delayed betting range.

---

# What already worked

## F2-K1 KEEP — trap no-bite state exists

When a street ends without any bet, trap plans receive `mark_no_bite`.

On the next refresh, a trap that received no action can switch from concealment mode back to
direct value extraction.

The goal/mode comments already reflect the correct architecture:
value extraction is the goal; trap is an execution mode.

## F2-K2 KEEP — preflop/line aggressor remains available after a check-through

If nobody bets the flop, the preflop aggressor remains the relevant range-initiative reference.

That is useful for:
- delayed cbet;
- probe semantics.

It should not be confused with "last player who bet this street"; those are different concepts.

---

# Remaining gaps

## F2-A MAJOR MULTIWAY GAP — probe context is still centered on one aggressor

In multiway pots, "the aggressor checked" is not the whole story.

Turn probe judgment may depend on:
- each opponent's capped/uncapped range;
- which players checked before hero;
- players still behind;
- whether one caller can still protect the aggressor's range.

The current scalar `opp_checked_prev` is therefore only a partial context representation.

## F2-B READ GAP — delayed-cbet observation is not yet consumed by exploit strategy

The engine now learns delayed-cbet frequency separately from barrel frequency.

But `opp_bet_prob` still uses generic:
- cbet on flop;
- barrel on turn/river.

So a turn trap decision after flop check-through cannot yet ask:
"does this opponent actually delayed-cbet often?"

Do not wire the new statistic with an arbitrary coefficient.
The turn judgment interface should first know whether the opponent is in a barrel or delayed-cbet
opportunity.

## F2-C ARCH_MISMATCH — action form is still not explicit provenance

The current intent usually records only:
`bet` or `check`.

A turn bet after flop check-through should eventually preserve action form such as:
- delayed_cbet;
- probe;
- ordinary value bet;
- semibluff.

That is story/provenance, not necessarily a new skill axis.

## F2-D GLOBAL — current emotion still contaminates judgment

Same unresolved V2 mismatch as F1:
`h.axes -> tilted_view` changes calculation/reading ability before plan selection.

## F2-E GLOBAL — execution-side strategic size shaping remains

Same unresolved V2 sizing-boundary problem as F1.

---

# Verification target

`tools/verify_f2_checkthrough.py` checks:

1. probe context enters the plan before intent creation;
2. delayed-cbet skill affects giveup/showdown turn aggression;
3. delayed-cbet skill also affects delayed value range;
4. delayed-cbet observation does not increment barrel counters;
5. actual execution provenance is wired and preserved across plan revision.
