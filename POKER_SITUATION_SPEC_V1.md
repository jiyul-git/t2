# Poker situation specification v1 — theory first, code second

Status: **SPECIFICATION ONLY**.  This file defines the poker situations that the engine should
be able to reason about before we compare them with the current implementation.

The existing code is not the source of truth for this document.

---

# 0. Audit rules

## 0.0 Mandatory action cycle

Every voluntary action is specified as:

```
judgment -> plan -> action
```

and the cycle repeats whenever new information arrives.

A multi-street plan may survive across later nodes, but it never suppresses the next judgment.
At each new node the player judges the new state, then explicitly keeps/revises/replaces the plan,
then acts.

Emotion may bias only the plan choice/revision.


## 0.1 One sequential story

A hand is inspected in actual order:

```
tournament/table context
-> preflop
-> flop
-> turn
-> river
-> showdown / fold end
```

At every point we record:

1. what information is available now;
2. what rational plans are available;
3. what action choices can express those plans;
4. what new event causes a re-plan;
5. what story from earlier streets is still relevant.

We do **not** skip a street because its structure looks similar to another street.

## 0.2 Emotion acts only when a plan is selected or revised

Emotion is allowed to bias **planning**, never execution.

```
objective state / perceived state
        |
        v
rational candidate plans
        |
        +---- emotional bias at this decision point
        v
chosen plan / response-plan / intent
        |
        v
execution
        |
        +---- legal clamp / chip conversion only
```

Once an intent has been chosen, execution must not independently decide to become more
aggressive, scared, sticky, tilted, etc.

This rule applies to reactive decisions too.  Facing a new bet is a **new planning event**:

```
check
-> opponent bets
-> form a response-plan
-> execute fold/call/raise
```

The response is not "execution changing its mind"; it is a new decision event caused by new
information.

## 0.3 Separate motive, execution form, and perception

A composite line should usually be assembled from:

- **motive / strategic goal**: value, thin value, bluff, semibluff, pot control, trap...
- **execution form**: bet, check, check-raise, overbet, block bet, probe, 3-bet...
- **perception / calculation**: range, sizing, blockers, fold equity, pot odds, SPR, ICM...

Do not create a monolithic concept such as `river_bluff_checkraise` unless the decomposition
cannot represent the strategy.

## 0.4 Avoid combinatorial explosion

We explicitly enumerate the chronological decision nodes, but we do not duplicate every node
for every stack/position/board/opponent combination.

Those are orthogonal state axes applied to every node:

- position / action order;
- effective stack / SPR;
- heads-up vs multiway;
- initiative and previous aggressor;
- range advantage / nut advantage;
- board texture and runout;
- tournament pressure / ICM;
- opponent model and reliability of the read;
- hero's learned concepts / temperament;
- emotional state, **planning only**.

---

# 1. Before cards / hand context

Before preflop action, the player can form only broad strategic constraints, not a postflop
line for cards not yet seen.

Required state:

- position and table size;
- effective stacks against relevant opponents;
- blinds / ante / level;
- tournament stage, payouts, ICM / bubble factor;
- stack distribution at the table and field;
- opponent tendencies with confidence/sample size;
- hero skill/perception limits;
- current emotional state.

Possible broad plans:

- normal chip-EV play;
- ICM survival tightening;
- pressure/accumulation strategy;
- deliberate variance increase/decrease;
- target weak stacks / avoid covered confrontations;
- exploit specific preflop leaks.

Story check:

- broad tournament intent may alter thresholds, but must not predetermine a specific flop action.

---

# 2. PREFLOP — actual sequential nodes

## P0. Forced posts

Events:

- SB / BB / ante posted;
- a player may already be partially or fully all-in from forced posts.

Choices:

- none.

Checks:

- forced action must not be interpreted as voluntary aggression;
- effective stacks after posts must be correct before strategy.

## P1. Action arrives unopened

Information:

- hole cards;
- position;
- players behind;
- effective stacks;
- ante/blind structure;
- ICM;
- reads on players behind.

Rational plan families:

- fold;
- open-raise for value / range realization;
- steal;
- limp as a deliberate mixed strategy;
- trap-limp premium;
- short-stack open-shove;
- pressure open against over-folding players.

Action choices:

- fold;
- limp;
- raise;
- shove.

Sizing choices:

- normal open;
- exploitative smaller/larger open;
- all-in.

Re-plan triggers:

- someone calls;
- someone 3-bets;
- multiple callers;
- all-in behind.

Story carried forward:

- opener has initiative unless later action changes it;
- open size and position shape perceived range.

## P2. Action arrives after one or more limps, no raise

Information added:

- limper count;
- limper positions;
- inferred limp ranges;
- players behind.

Rational plans:

- overlimp;
- isolation raise for value;
- isolation bluff / dead-money attack;
- squeeze-like large iso against multiple limpers;
- trap behind with premium;
- fold;
- short-stack shove over limpers.

Choices:

- fold;
- call/limp behind;
- raise;
- shove.

Story checks:

- isolation motive must not be confused with an unopened steal;
- limpers' responses produce a new state, not a continuation of "unopened".

## P3. Facing a single open raise

Information added:

- opener position;
- open size;
- opener range/read;
- callers before hero, if any;
- effective stack vs opener and callers.

Rational plans:

- fold;
- flat for realization / pot control / trapping;
- value 3-bet;
- polarized bluff 3-bet;
- linear/merged 3-bet;
- squeeze if callers exist;
- reshove at appropriate depth;
- exploitative 3-bet against excessive open/fold tendencies.

Choices:

- fold;
- call;
- 3-bet;
- shove.

Story checks:

- 3-bet construction is not the same skill as postflop thin value;
- flatting premium is deliberate slowplay, not failure to value bet.

## P4. Facing a 3-bet after hero opened or cold-called

Information added:

- 3-bettor identity / position / size;
- whether hero is original raiser;
- cold callers / dead money;
- effective stack and resulting SPR.

Rational plans:

- fold;
- call to realize equity;
- value 4-bet;
- bluff 4-bet;
- 4-bet shove;
- trap-call with top range;
- exploit light 3-bettor;
- tighten vs value-heavy 3-bettor.

Choices:

- fold;
- call;
- 4-bet;
- shove.

## P5. Facing a 4-bet or higher re-raise

Rational plans:

- fold bluff/value boundary;
- call where stack geometry permits;
- value 5-bet / shove;
- rare bluff shove where strategically justified.

Choices:

- fold;
- call;
- raise/shove.

Checks:

- "reraise" must not flatten all 3-bet/4-bet/5-bet knowledge if the strategic requirements differ.

## P6. Facing an all-in preflop

Rational plans:

- fold;
- call-off;
- overcall multiway;
- reshove only if additional live players and legal/strategic reason exists.

Inputs:

- pot odds;
- opponent shove range;
- players behind;
- ICM;
- bounty/reentry if format has it;
- effective stack already committed.

Story ends preflop if no further action.

## P7. Preflop closes

Record for flop story:

- aggressor / initiative;
- caller structure;
- pot type: limp / single-raised / 3-bet / 4-bet+;
- positions;
- effective stacks;
- hero and perceived opponent ranges;
- whether action was exploitative or baseline.

---

# 3. FLOP — actual sequential nodes

New information:

- three-card board;
- made hand / draw / backdoors;
- range advantage;
- nut advantage;
- board texture;
- SPR;
- number of opponents;
- positions;
- preflop initiative.

## F1. Hero acts first / checks around to hero with no bet yet

Rational plan families:

### Value
- three-street value;
- two-street value;
- thin value;
- protection / equity denial;
- stack-off plan.

### Control
- pot control;
- showdown;
- block-like small bet only if the semantic conditions truly exist.

### Draw / bluff
- semibluff;
- pure bluff;
- range bluff / c-bet;
- delayed-bluff setup;
- give-up.

### Inducement
- value trap / planned check-raise;
- check to induce bluff;
- check to protect checking range.

Possible actions:

- check;
- bet normal;
- bet small;
- bet large;
- overbet only if strategy supports it.

If hero checks, story splits:

- action checks through -> F2;
- opponent bets -> F3.

If hero bets:

- everyone folds -> hand ends;
- one/more calls -> turn story;
- hero faces raise -> F4.

## F2. Flop checks through

Interpretations:

- nobody chose to bet;
- ranges may become capped/shifted;
- initiative can weaken without disappearing as historical information.

Carry to turn:

- missed c-bet opportunity;
- possible delayed c-bet;
- possible probe opportunity for the non-aggressor;
- protected checking range possibility.

## F3. Hero checked, then faces a flop bet

This is a **new response-plan event**.

Rational response plans:

- fold;
- bluff-catch / continue;
- draw call;
- value call / trap-call;
- value check-raise;
- semibluff check-raise;
- rare pure bluff check-raise.

Inputs:

- bet size and what hero can infer from it;
- bettor range and line;
- pot odds;
- hand equity / draw;
- blockers;
- fold equity against a raise;
- players behind;
- SPR.

Important distinction:

- a planned trap may explain the earlier check;
- a reactive bluff check-raise does **not** require that the initial check was planned as a bluff.

## F4. Hero bet and now faces a flop raise

New information:

- opponent chose an aggressive response to hero's range and sizing.

Rational plans:

- fold;
- call;
- value 3-bet;
- semibluff 3-bet;
- bluff 3-bet in rare polarized spots;
- stack off.

Checks:

- this is a bet/raise response, not a check-raise;
- checkraise skill should not govern it merely because the final action is a raise.

## F5. Flop closes after call(s)

Record for turn:

- who retained initiative;
- bet/check/raise sequence;
- actual sizing;
- number of remaining players;
- updated perceived ranges;
- plan and remaining betting budget;
- whether hero induced action or reacted to it.

---

# 4. TURN — enumerate again, do not inherit flop shortcuts

New information:

- turn card;
- whether it favors hero/opponent ranges;
- draws completed / new draws appeared;
- SPR and effective stacks after flop action;
- flop action story.

## T1. Hero has first opportunity to bet, no turn bet yet

Possible rational plans:

### Value
- continue value barrel;
- downgrade three-street to two-street;
- newly promote to value because turn improved hero;
- thin value turn;
- protection/equity denial.

### Control
- pot control;
- showdown/check;
- block strategy if semantic conditions are present.

### Bluff/draw
- second barrel bluff;
- semibluff;
- give up after failed flop bluff;
- delayed c-bet after flop check-through;
- probe after opponent checked back flop;
- new bluff created by favorable scare card.

### Induce
- value trap;
- planned turn check-raise.

Choices:

- check;
- bet with appropriate sizing/overbet only if justified.

If check then bet faced -> T3.
If hero bets and is raised -> T4.

## T2. Turn checks through

Carry to river:

- missed second barrel;
- showdown-heavy/capped interpretations;
- delayed opportunities now exhausted or transformed;
- possible river probe/value/bluff depending on river.

## T3. Hero checked, then faces a turn bet

New response-plan.

Rational plans:

- fold;
- bluff-catch;
- draw call;
- value call;
- value check-raise;
- semibluff check-raise;
- pure bluff check-raise where range/blocker/fold-equity supports it.

Critical turn-specific property:

- future-card equity still exists;
- semibluff check-raises are fundamentally possible.

This is strategically different from river check-raise.

## T4. Hero bet and faces turn raise

Rational plans:

- fold;
- call;
- value re-raise;
- semibluff re-raise;
- rare bluff re-raise;
- stack off.

Inputs:

- line strength;
- size;
- remaining SPR;
- range/nut interaction on turn card.

## T5. Turn closes

Record for river:

- complete action sequence;
- initiative;
- range updates;
- actual investment;
- remaining stack;
- whether current plan is still alive or must be revised;
- whether bluff/value story remains credible.

---

# 5. RIVER — enumerate independently

New information:

- final board;
- no future equity remains;
- every bet/raise is now value, bluff, or a sizing/control device around showdown value.

## R1. Hero has first opportunity to bet, no river bet yet

Rational plan families:

### Value
- strong value;
- thin value;
- polarized nut value;
- exploitative small value;
- overbet value.

### Showdown/control
- check/showdown;
- induce bluff with a bluff-catcher;
- block bet where hero genuinely sets the price against a known aggressor/range structure.

### Bluff
- missed-draw bluff;
- blocker bluff;
- scare-card bluff;
- exploitative bluff against over-folding range;
- overbet bluff if polarization/nut advantage supports it.

### Give-up
- check/fold candidate;
- check with no plan to bluff unless opponent's subsequent bet creates new information.

Choices:

- check;
- bet small/normal/large/overbet.

Important:

- `river_bluff` when hero bets first is a **proactive river bluff**.
- It is not the same event as a later bluff check-raise.

## R2. River checks through

Hand goes to showdown if eligible.

Check:

- do not retroactively change the plan because the result is now known.

## R3. Hero checked, then faces a river bet

This is a new response-plan created by the opponent's actual bet.

Candidate plans:

### Fold
- bluff-catcher too weak;
- size/range indicates value;
- blockers poor;
- multiway / ICM considerations.

### Call
- bluff-catch;
- value bluff-catch / under-repped strong hand;
- exploitative hero-call.

### Value check-raise
- opponent has enough worse hands that can call;
- hero's range/hand supports raising;
- sizing chosen for value.

### Reactive bluff check-raise
This is **not** assumed before the check.

Possible story:

```
hero checks / gives up / seeks showdown
-> opponent chooses a river bet
-> size + line imply a capped or thin-value-heavy region
-> hero has little/no showdown value
-> hero's blockers remove calls and/or preserve folds
-> hero estimates enough of that betting range can fold to a raise
-> choose the smallest/most profitable raise family that attacks that region
```

Required information:

- opponent bet size;
- perceived betting range;
- relative strength / showdown value;
- blocker/unblocker effects;
- opponent tendency to **bet then fold to a raise**, if enough data exists;
- raise size needed to achieve target folds;
- risk/reward and legal minimum.

This response must not use generic fold-to-bet as if it were automatically fold-to-raise.

### River call vs raise distinction

A hand can be:

- too weak to call but an excellent bluff-raise candidate;
- good enough to call but a bad bluff-raise candidate;
- strong enough to value-raise;
- strong enough only to call because worse hands will not continue.

These are separate plan comparisons.

## R4. Hero bet and faces river raise

Rational plans:

- value call;
- bluff-catch call;
- fold;
- value re-raise / jam;
- extremely rare bluff re-raise, only if coherent and legal.

No semibluff category exists on river.

## R5. River raise faces re-raise

Rational plans:

- fold;
- call;
- value jam/call-off;
- bluff continuation only in exceptional coherent range structures.

The engine must distinguish this from an initial river check-raise.

---

# 6. MULTIWAY overlays

At every postflop node explicitly check:

- number of live opponents;
- players still to act;
- whether bettor/raiser is closing action;
- side-pot/all-in constraints;
- relative ranges of more than one opponent;
- reduced bluff frequency and stronger value requirements where appropriate.

A heads-up strategy must not be reused merely with a constant multiplier if the semantic
decision changes.

---

# 7. ALL-IN / EFFECTIVE-STACK overlays

At every bet/raise decision:

- actor maximum legal target;
- opponent effective cap;
- whether a nominal raise is effectively all-in;
- whether further betting decisions can still exist;
- pot/side-pot eligibility.

Strategic choice is made before execution converts an effective-all-in intent into legal chips.

---

# 8. PLAN CONTINUITY / STORY checks

For every transition flop -> turn -> river, compare the story.

Examples that must be representable:

- value remains value but sizing budget changes;
- value downgrades to pot control;
- draw completes -> value;
- draw misses -> give up;
- draw misses -> proactive river bluff;
- bluff improves to showdown/value;
- flop check-back -> delayed turn c-bet;
- opponent checks back -> turn probe;
- planned trap gets no action -> direct value later;
- planned trap gets bet -> value check-raise/call;
- initial give-up check -> opponent's new sizing creates a reactive bluff-raise opportunity;
- thin value bet gets raised -> call/fold/re-raise depending on new range;
- bluff gets raised -> abandon or continue according to range/blockers, not because "bluff plan" is immutable.

A plan is persistent context, not a command that forbids re-planning after new information.

---

# 9. EMOTION overlay — plan only

Emotion may alter **which candidate plan wins** at a planning/re-planning node.

Examples:

- tilt can overweight aggressive candidate plans;
- fear can overweight folds/control;
- sticky state can overweight continue/call plans;
- frustration can overweight variance-seeking lines;
- confidence/overconfidence, if later modeled, can alter plan ranking.

Emotion must not:

- change chip amount after an intent was chosen;
- turn a stored call intent into a raise in the execution layer;
- make legal sizing jitter carry strategic meaning;
- independently alter fold/call/raise after the response-plan has been selected.

Current-code audit requirement:

- any use of a tilted profile inside pure execution/sizing/response execution must be classified;
- if response selection is retained as a planning function, name and boundaries should make that explicit.

---

# 10. CODE-MAPPING pass — columns to fill next

For every node above, the implementation audit will record:

| Field | Meaning |
|---|---|
| Situation ID | P1, F3, T4, R3... |
| Rational plan candidates | expected poker plans |
| Final action owner | exactly one function should own the choice |
| Motive concepts | value/bluff/etc. |
| Execution-form concepts | cbet/checkraise/overbet/etc. |
| Perception inputs | range/sizing/blocker/fold etc. |
| Emotion input | plan selection only |
| Current producer(s) | actual code |
| Current consumer(s) | actual code |
| Observation source | actual stats/book |
| Status | KEEP/SPLIT/ADD/REROUTE/LEAK/DUP/MISS |
| Story invariant | what must remain true across streets |

No strategic code changes are accepted until this mapping is completed.
