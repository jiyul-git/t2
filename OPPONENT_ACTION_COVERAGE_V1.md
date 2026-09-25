# Opponent-action coverage V1

Basis: `POKER_DECISION_MODEL_V2.md`.

Goal: cover **every strategic event class** that can create, close, or re-open a hero decision.
Chip amounts are continuous inputs, so they are not enumerated one-by-one.  They are represented
by strategically distinct size classes: small / normal / large / overbet / all-in, plus legal
minimum and effective-stack constraints.

The exhaustive unit is not a full hand permutation.  A betting round is a state machine:
the same event grammar can repeat after every full raise until stacks or action rights end it.

---

# 1. Universal betting-round state

At every hero decision the following state is sufficient to identify the strategic event class:

- street: preflop / flop / turn / river;
- hero has acted this street? if yes: check / call / bet / raise;
- current wager exists? yes/no;
- amount to call and size class;
- number of live opponents;
- players still to act behind hero;
- current aggressor;
- hero initiative from previous action story;
- raise depth this street;
- hero raise rights open/closed;
- full raise vs incomplete all-in;
- effective stacks / side-pot eligibility;
- prior line plan;
- observed opponent actions and sizes on this street;
- earlier-street story.

Every new opponent action updates this state and may create a new
`JUDGMENT -> PLAN -> ACTION` cycle.

---

# 2. Opponent action alphabet

An opponent can produce only these strategic event classes:

## When no wager exists
- check;
- bet small;
- bet normal;
- bet large;
- overbet;
- all-in bet.

## When a wager exists
- fold;
- call;
- all-in call;
- full raise small/normal/large;
- overbet raise;
- all-in raise;
- incomplete all-in raise.

Important:
- an incomplete all-in may increase the amount to call without reopening raise rights;
- a full raise reopens action for eligible players;
- if every other live player is all-in, a covering player cannot make a dead extra raise;
- a fold/call may change multiway composition even if it does not immediately return action to hero.

---

# 3. Preflop: exhaustive strategic event classes

## PF-A. Hero has not acted and no voluntary raise exists

Opponent history before hero can be:

1. everyone before hero folded;
2. one limper;
3. multiple limpers;
4. limp(s) plus short all-in below a full raise, where legal semantics matter;
5. action reaches BB after limp-around, giving BB option to check or raise.

Hero judgment -> plan candidates:
- fold where legal/relevant;
- check in BB option;
- overlimp;
- isolation raise;
- isolation bluff;
- trap limp;
- open/iso shove.

Opponent responses after hero raises:
- all fold -> hand/round may close;
- one call;
- multiple calls;
- one full 3-bet;
- cold 3-bet after one/more calls;
- all-in 3-bet;
- incomplete all-in that may or may not reopen action.

Each raise event creates a new hero cycle if action returns.

## PF-B. Hero faces first full raise

Possible history:
- open only;
- open + one caller;
- open + multiple callers;
- open + short all-in caller;
- opener already all-in.

Hero response plans:
- fold;
- flat;
- value 3-bet;
- linear/merged 3-bet;
- polarized bluff 3-bet;
- squeeze;
- reshove;
- call-off if raise is effectively/all-in.

Opponent response to hero 3-bet:
- fold(s);
- call(s);
- original opener 4-bet;
- caller cold 4-bet/backraise;
- all-in 4-bet;
- incomplete all-in.

Action returning to hero creates PF-C/PF-D style re-plan.

## PF-C. Hero previously opened and now faces 3-bet

Possible intervening events:
- all others fold, one 3-bet;
- one/more calls then squeeze 3-bet;
- short-stack shove;
- full raise plus cold caller(s).

Plans:
- fold;
- call;
- value 4-bet;
- bluff 4-bet;
- 4-bet shove;
- trap-call.

If 4-bet receives 5-bet, repeat generic re-raise cycle.

## PF-D. Hero previously called and action reopens

This is distinct and must not be lost.

Examples:
- hero calls open -> later player squeezes;
- hero limps -> later raise -> action returns;
- hero calls 3-bet -> another player jams where legal.

Plans:
- fold;
- call additional amount;
- backraise/squeeze value;
- backraise bluff where coherent;
- shove.

## PF-E. Hero previously raised and faces re-raise

Generic recursive state for 3-bet / 4-bet / 5-bet+.

Plans:
- fold;
- call where legal/strategically meaningful;
- value re-raise;
- bluff re-raise where coherent;
- shove/call-off.

The recursion ends when:
- everyone but one folds;
- all remaining players call/are all-in and action closes;
- no legal raise remains;
- stacks are exhausted.

---

# 4. Postflop: exhaustive strategic event classes per street

The same graph applies on flop, turn, and river, with street-specific plan candidates.
River removes semibluff/future-equity plans.

## POST-A. Hero has not acted, no bet before hero

Opponent actions before hero:
- zero or more checks;
- in multiway, a player before hero may bet after earlier checks.

If no bet reaches hero:
JUDGMENT -> proactive PLAN -> ACTION:
- check;
- value bet;
- thin value bet;
- protection/equity-denial bet;
- semibluff bet (flop/turn);
- pure bluff;
- block/price-setting if semantics fit;
- probe/delayed c-bet if story fits;
- trap/induce check;
- giveup/showdown check;
- overbet as an execution form where justified.

If an opponent bets before hero, move to POST-B.

## POST-B. Hero has not acted this street and faces a bet

This is a lead/donk/probe/value/bluff from the opponent depending story; hero need not know the
true motive, only infer a range.

Plans:
- fold;
- call for value/realization;
- bluff-catch;
- draw call;
- value raise;
- semibluff raise (flop/turn);
- pure bluff raise;
- shove/stack-off.

After hero calls:
- later players may fold/call/raise;
- a later raise reopens hero action -> POST-E.

After hero raises:
- opponents may fold/call/re-raise -> POST-D.

## POST-C. Hero checked, then faces a bet

This is the **check-then-face-bet** family.

Earlier check motive may have been:
- trap/induce;
- showdown/control;
- giveup;
- range protection/mix;
- failed opportunity to bet.

The opponent bet is new information.  Hero now judges again.

Plans:
- fold;
- call / bluff-catch;
- draw call (flop/turn);
- value check-raise;
- semibluff check-raise (flop/turn);
- reactive pure bluff check-raise;
- shove.

A reactive bluff XR does not require a pre-planned bluff check.

After hero check-raises:
- folds -> hand may end;
- calls -> street closes when all others settle;
- re-raise -> POST-D recursive response.

## POST-D. Hero bet/raised and now faces a raise/re-raise

Possible history:
- hero bet -> opponent raise;
- hero raise -> opponent 3-bet;
- hero check-raise -> opponent re-raise;
- multiway cold raise after call(s);
- short all-in raise;
- full raise.

Plans:
- fold;
- call;
- value re-raise;
- semibluff re-raise (flop/turn);
- rare coherent bluff re-raise;
- shove/stack-off.

If another full raise comes back, repeat POST-D.
River has no semibluff branch.

## POST-E. Hero called, then a later opponent raises

Multiway back-action state.

Examples:
- bet -> hero call -> player behind raises;
- hero check-call -> later player check-raises/cold raises;
- hero calls raise -> another opponent re-raises.

Plans:
- fold;
- call additional amount;
- value backraise;
- semibluff backraise (flop/turn);
- rare bluff backraise;
- shove.

This state is strategically different from the first call because:
- price changed;
- raising range is stronger/different;
- players remaining changed;
- side-pot/effective-stack geometry may change.

## POST-F. Hero action receives no raise

After hero bet/raise:

Opponent aggregate outcomes:
1. all fold -> hand ends;
2. exactly one call -> carry HU story;
3. multiple calls -> carry multiway story;
4. call(s) plus all-in call(s) -> carry side-pot/effective-stack story;
5. fold(s) + call(s) -> same with narrower field;
6. raise occurs -> POST-D, regardless of earlier folds/calls.

After hero check:
1. all remaining check -> street closes;
2. later opponent bets -> POST-C when action returns;
3. in multiway, bet gets called/raised before returning to hero -> hero judges the **full observed sequence**, not just the original bet.

---

# 5. Multiway sequences that must be explicitly preserved

The following cannot be reduced to simple heads-up "opponent bet" labels:

- bet -> call -> hero decision;
- bet -> raise -> hero decision;
- check -> bet -> call -> hero decision;
- check -> bet -> raise -> hero decision;
- hero bet -> call -> raise -> hero decision;
- hero call -> later raise -> hero decision;
- hero raise -> cold call(s) -> re-raise -> hero decision;
- short all-in -> call(s) -> hero decision;
- main-pot all-in plus live side-pot opponent(s);
- all opponents all-in, so no further raise is legal.

The hero judgment must know who performed each action, size, position/order, and whether action
is closing.

---

# 6. Size classes are information, not separate actions

For every bet/raise event retain:

- exact amount;
- fraction of relevant pot;
- legal min raise;
- fraction of effective stack committed;
- post-action SPR;
- all-in / effective-all-in flag.

Strategic interpretation may categorize size as:

- tiny/block-like;
- small;
- medium;
- large;
- pot/overbet;
- all-in.

Do not throw away the exact size after classification.

---

# 7. Street-specific differences

## Flop
- future cards: two;
- backdoors and semibluffs matter;
- range advantage often broad;
- multiway caution strongest.

## Turn
- one future card;
- barrel / delayed / probe stories become important;
- semibluff remains but with different equity;
- turn card can radically change range/nut advantage.

## River
- no future cards;
- no semibluff;
- every raise is value/bluff/merging error/control only;
- thin-value and bluff-catching boundaries are central;
- reactive bluff raise can be created by opponent sizing/range information;
- bet-then-fold-to-raise tendency is distinct from fold-to-bet.

---

# 8. All-in / incomplete-raise branches

Every node must distinguish:

1. normal non-all-in action;
2. full all-in raise that reopens action;
3. all-in call;
4. incomplete all-in raise that changes price but does **not** reopen raise rights for players
   whose action is already closed;
5. only all-in opponents remain -> no dead raise;
6. unequal all-ins -> side pots / contestable contributions.

These are legality overlays; they also change judgment because the future action tree changes.

---

# 9. Closure conditions

A street/hand stops generating decisions when one of these occurs:

- only one live player remains;
- every non-folded player has matched the current wager and no action remains;
- all remaining players are all-in;
- river action closes -> showdown;
- a legal full raise reopens action, in which case the cycle continues rather than closing.

---

# 10. Audit mapping requirement

For each canonical state above, current code must identify:

- what opponent sequence is visible to judgment;
- whether exact sizes and actor identities survive;
- whether range narrowing uses the whole sequence;
- which function creates the plan;
- which function alone creates the action;
- whether a later raise correctly causes a fresh judgment/plan;
- whether multiway and incomplete-all-in state are preserved;
- whether emotion enters only at plan selection.

Any missing event class is `MISS`.
Any action produced by two paths is `DUP`.
Any new opponent event that does not cause a fresh plan is `ARCH_MISMATCH`.
