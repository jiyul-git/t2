# Poker decision model V2 — judgment -> plan -> action

Status: DESIGN SPECIFICATION.  The existing code is not the source of truth.

## 1. Core invariant

Every voluntary action must come from exactly one cycle:

```
new information
-> JUDGMENT
-> PLAN
-> ACTION
-> new information
-> JUDGMENT
-> PLAN
-> ACTION
-> ...
```

There is no strategic action without a judgment and a plan.

### JUDGMENT

Interpret only information available at that moment:

- hole cards / current board;
- perceived hero and opponent ranges;
- made strength, equity, blockers and draws;
- position and players still to act;
- pot, effective stacks and SPR;
- previous action story and initiative;
- heads-up / multiway / side-pot state;
- opponent model and confidence;
- tournament/ICM context;
- the player's non-emotional knowledge and calculation limits.

Judgment answers **what is happening now?**  It does not choose the action.

### PLAN

Choose what the player is trying to accomplish from the judged state.

A plan has two nested scopes.

1. **Line plan / horizon**
   - examples: value_3street, value_2street, pot_control, bluff_2street,
     semibluff line, trap/induce, showdown/giveup;
   - may survive for more than one street;
   - is context for the next decision, never a command that skips later judgment.

2. **Current action plan**
   - the plan for the action that will now be executed;
   - examples: check this node, bet 65% pot for value, call as bluff-catcher,
     raise for value, raise as bluff, fold, shove;
   - includes the **strategic size/form** of bet or raise.

The next card or opponent action starts a fresh judgment.  The line plan is then explicitly
**kept / revised / replaced**, and a new current action plan is selected.

### ACTION

Execute the current action plan.

Execution may do only:

- poker-rule legality;
- chip-unit rounding/conversion;
- cap to legal/effective stack;
- deterministic UI/representation work.

Execution must not invent a new strategic action, motive or strategic size.

## 2. Emotion rule

Current emotion/tilt affects **PLAN selection/revision only**.

It does not alter JUDGMENT and it does not alter ACTION after the plan is chosen.

Examples:

- the same judged state can lead a tilted player to choose an over-aggressive plan;
- a fearful player can over-select control/fold plans;
- a sticky player can over-select continue/call plans;
- once "call" is selected, execution cannot turn it into a raise because of tilt;
- once "bet 70% pot" is selected, execution cannot strategically resize it because of tilt.

Stable personality/skill is different from current emotion.  A weak range reader may judge the
state poorly even while calm.  That belongs in JUDGMENT.  Current tilt does not temporarily erase
range-reading or pot-odds knowledge under this architecture; tilt changes which plan is chosen
from the judged state.

## 3. Planning horizon examples

### Nut-strength flop hand

```
flop judgment
-> line plan: extract value across 3 streets
-> current plan: bet 60%
-> action

turn card + call observed
-> new judgment
-> keep/revise 3-street value plan
-> current plan: bet/check/induce with a new size
-> action

river card + opponent action
-> new judgment
-> keep/revise/replace
-> current plan
-> action
```

"3-street value" never means "autobet three times without re-judging."

### River check then opponent small bet

```
judgment before first river action
-> plan may be showdown/giveup/control
-> current plan: check
-> action: check

opponent bets small  [new information]
-> new judgment: reinterpret range + sizing
-> choose response plan:
     fold / bluff-catch / value raise / reactive bluff raise
-> action
```

A reactive bluff check-raise need not have been intended before the check.

## 4. Exhaustive strategic motive families

These are runtime motives, not necessarily one-to-one persona skills.

### Value / realization
- strong value extraction;
- thin value;
- stack-off/value commitment;
- protection/equity denial;
- realization by call/check;
- under-representation / induce.

### Control / showdown
- pot control;
- showdown/check-back;
- bluff-catch;
- block/price-setting where semantically valid.

### Bluff
- pure bluff;
- semibluff;
- continuation/barrel bluff;
- delayed bluff;
- probe;
- blocker bluff;
- scare-card bluff;
- reactive bluff raise/check-raise;
- squeeze/steal/isolation bluff preflop.

### Inducement / deception
- slowplay;
- trap;
- planned value check-raise;
- trap-call / under-rep;
- range protection/mixing where needed.

### Abandon / risk control
- give up;
- fold;
- line downgrade;
- ICM-driven survival.

## 5. Execution-form families

These are **how** a motive is expressed, not why:

- check;
- call;
- bet;
- raise;
- check-raise;
- re-raise;
- overbet;
- block bet;
- limp;
- open raise;
- isolation raise;
- 3-bet / 4-bet / higher;
- shove / call-off.

A compound line should normally be motive + execution form + perception inputs.

## 6. Sequential situation coverage

### Preflop
P0 forced posts
P1 unopened action
P2 limpers, no raise
P3 facing open (with/without callers)
P4 facing 3-bet
P5 facing 4-bet+
P6 facing all-in
P7 action closes / carry story to flop

Every node requires judgment -> plan -> action.

### Flop
F1 no bet yet, hero decision
F2 hero checks and action checks through
F3 hero checks then faces bet
F4 hero bets then faces raise
F5 raise faces re-raise
F6 street closes / carry story to turn

### Turn
T1 no bet yet, hero decision
T2 hero checks and action checks through
T3 hero checks then faces bet
T4 hero bets then faces raise
T5 raise faces re-raise
T6 street closes / carry story to river

### River
R1 no bet yet, hero decision
R2 hero checks and action checks through
R3 hero checks then faces bet
R4 hero bets then faces raise
R5 raise faces re-raise
R6 showdown/fold end

River-specific rule: no semibluff remains because no future card exists.

### Overlays at every applicable node
- heads-up vs multiway;
- players behind / closing action;
- effective-all-in / side-pot state;
- position relative to the aggressor;
- range/nut advantage;
- board/runout class;
- tournament/ICM context;
- opponent model and confidence.

## 7. Story continuity

Every new judgment must receive the previous story:

- previous line plan and whether it succeeded;
- actual prior actions and sizes;
- initiative/aggressor changes;
- range updates;
- cards that changed strength/range distribution;
- remaining effective stack and plan budget;
- opponent response to earlier actions.

Required transitions include:

- value -> value;
- value -> thinner value / pot control / fold;
- draw -> value;
- draw -> giveup;
- draw -> proactive river bluff;
- bluff -> value/showdown after improvement;
- bluff -> giveup;
- flop check-back -> delayed c-bet;
- opponent check-back -> probe;
- trap -> value after no bite;
- trap -> value response after opponent bets;
- check/giveup -> reactive bluff raise after opponent creates new information.

## 8. Audit consequence

For every voluntary action in the current engine, the code audit must identify:

1. judgment producer;
2. line-plan producer/reviser;
3. current-action-plan producer;
4. sole action executor;
5. motive concepts;
6. execution-form concepts;
7. perception/calculation concepts;
8. emotion input — plan step only;
9. observation source;
10. duplicate or bypass path.

Statuses:
`KEEP / SPLIT / ADD / REROUTE / REMOVE_COMPAT / ADD_OBSERVATION / ARCH_MISMATCH`.

No strategic coefficient calibration is accepted until this mapping is complete.
