# Decision architecture audit - current implementation map

Status: CURRENT IMPLEMENTATION
Branch: `chatgpt/logic-tuning-20260927`
Updated: 2026-09-28

This file describes what the current code actually does.
Target architecture remains in `POKER_DECISION_MODEL_V2.md`.

---

## 1. Runtime ownership

### External entry
`ui/server/ui_server.py`
-> receives UI/API actions
-> calls `live2.step()`
-> streams state/bot actions to the browser

### Tournament/session shell
`live2.py`
-> owns saved tournament state
-> builds the hero hand/table
-> starts or resumes `session.HandRun`
-> advances other tournament tables
-> archives completed hands
-> emits telemetry

### Hand state
`play.Hand`
-> cards / seats / stacks / profiles / reads / tilt / plan state
-> exposes `base_profile`, `planning_profile`, `execution_profile`
-> production `axes()` still returns the tilted planning profile

### Betting rules
`runner.Round`
-> legal betting-round state machine
-> contribution / current bet / min-raise / raise rights
-> full raise / incomplete all-in raise / all-in call
-> action order / folds / all-ins / uncalled excess
-> raw `action_meta` is the rule-level source of truth

---

## 2. Canonical public action story

### Raw facts
`runner.Round.apply()` records:
- actor and input action
- contribution before/after
- increment
- current bet before/after
- min-raise before
- full vs incomplete raise
- all-in call vs all-in raise
- actor stack before/after
- raise right before the action
- cumulative full-raise count

### Semantic event conversion
`action_events.py` converts raw metadata into one canonical postflop event stream.

Each event preserves:
- street / actor
- check / call / bet / raise / fold
- wager faced
- full-raise depth and any-raise depth
- full vs incomplete raise
- all-in state
- action size and actual price faced
- previous action by the same actor
- response class:
  - free_action
  - face_bet
  - check_then_face_bet
  - cold_facing_raise
  - caller_backaction
  - aggressor_backaction

Raise depth is recursive. Higher re-raises do not need separate hard-coded branches.

### Consumers
The same canonical event model now feeds:
- opponent range narrowing
- response classification
- aggression/barrel summaries
- postflop observation book
- sizing context
- street outcome summaries
- audits

`session.py` keeps compatibility aliases, but semantic reconstruction belongs to `action_events.py`.

---

## 3. Opponent model and range flow

### Persistent reads
`reads.Book` stores observer -> target public observations:
- VPIP/PFR/limp
- 3-bet / 4-bet / backraise
- c-bet / barrel / delayed c-bet
- facing bet / facing raise
- fold to bet / fold to raise
- sizing statistics
- showdown evidence

`reads.perceived_profile()` converts the book into the observer's current estimate of that opponent.

### Starting range
`session.HandRun` reconstructs each opponent's preflop perceived range from:
- position
- observed preflop action
- stack depth
- open size / callers / raise level
- observer's perceived opponent profile

### Postflop line update
`session.HandRun._acts_of()`
-> returns that opponent's accumulated postflop story

`ranges.perceived_range()`
-> `ranges.narrow_by_actions()`
-> updates the range event by event

Current interpretation:
- bet: select a betting range
- raise: first survive the price faced, then select a raising range
- re-raise: repeat the same conditional update
- call: call/continue range depending on raise rights and all-in state
- check: checking range

Same-street re-raises are not counted as new barrels.
Barrel count means aggression across distinct postflop streets.

Call/continue narrowing uses the actual incremental price faced.
The continue model also uses a price-based minimum-defense floor.

### Multiway
Per-opponent pools are preserved as `opp_ranges[seat]`.
Core equity can use distinct pools through `bot.equity_vs_combos()`.

Legacy union `opp_range` still exists for several consumers.
Some exploit inputs still use one selected main opponent.

---

## 4. Decision flow

### Preflop
`session.HandRun`
-> `plan.preflop_plan()`
-> open / iso / defend / call-off logic in `preflop.py`
-> returns action + size + `pf_seed`
-> `runner.Round.apply()`

The preflop path still does not use the same explicit plan-object structure as postflop.

### Postflop - no wager faced
For every bot decision:
`session.HandRun`
-> rebuild current perceived opponent ranges
-> `plan.update_plan()`

`update_plan()` is the single plan-update entry point:
1. create or revise line plan
2. refresh if board/range state changed
3. river-specific reclassification
4. concept permission check
5. create current street intent if missing

Current intent:
`attach_intent()`
-> `decide_aggression()`
-> `decide_size()`
-> stored in `plan_state['intents'][street]`

Execution:
`act_with_plan(tocall == 0)`
-> reads stored intent
-> returns check/bet and strategic target
-> session performs chip conversion / expression shaping / legality
-> `runner.Round.apply()`

### Postflop - wager faced
`session.HandRun`
-> canonical `response_context`
-> current opponent ranges
-> pot/side-pot geometry
-> `plan.act_with_plan(tocall > 0)`

Inside:
1. compute current equity against current perceived pools
2. compute call threshold
3. classify check-raise spot vs ordinary response
4. choose response
5. store explicit response-plan record
6. return fold / call / raise target

Response records are stored by `record_response_plan()` under
`plan_state['response_plans'][street]`.

### Check-raise ownership
Current implementation no longer has two competing raise producers for the same check-raise spot.

If the response class is `check_then_face_bet`:
- `checkraise_decision()` owns the raise opportunity
- generic `decide_response()` is called with direct raising disabled

If the player bet/raised and later faces another raise:
- response class becomes `aggressor_backaction`
- it does not re-enter the check-raise gate

---

## 5. Response logic now separated by purpose

### Call vs value re-raise
A hand being good enough to call no longer automatically qualifies it as a value re-raise.

Value re-raise requires a separate value condition, including equity against the opponent range expected to continue to the new raise.

### Bluff / semibluff re-raises
Non-value raises use a shared optimistic EV veto before frequency/personality selection.

The same structural veto is used for:
- bluff re-raise
- semibluff re-raise
- give-up deviation raise
- non-value check-raise

### Made-hand bluff conversion
A made one-pair hand is no longer converted into a pure bluff plan simply because relative strength is low.

### River-started bluff
A bluff that first starts on the river uses the `river_bluff` plan, not `bluff_2street`.

---

## 6. Relative strength and equity

`plan.relative_strength()` / `joint_relative_strength()`
compare the hero hand against the **current perceived opponent range(s)**.

Therefore rel/equity do not read the betting story directly.
The story first changes the opponent range; rel/equity are then computed against that updated range.

This is the intended current data flow:

public action story
-> canonical events
-> perceived opponent ranges
-> rel / equity / range advantage / blocker judgment
-> plan or response selection

---

## 7. Profile / emotion boundary

Current plumbing exists:
- `base_profile()`: emotion-free
- `planning_profile()`: tilted
- `execution_profile()`: emotion-free
- `profile_views()`: exposes all views

But production `Hand.axes()` still returns the tilted planning view.

Therefore current tilt can still affect:
- range reading
- calculations
- plan selection
- response selection

This does not yet satisfy the target rule "emotion changes plan selection only".

Status: OPEN ARCHITECTURE MISMATCH.

---

## 8. Execution boundary

Strategic postflop bet size is selected in `plan.py`.
The session then converts it to actual chips.

Production still calls `runner.shape_size()`, which can add persona sizing jitter / odd sizing before legality clamps.

Therefore execution is not yet a perfectly pure legality-only layer.

Status: OPEN ARCHITECTURE MISMATCH.

The manual pure-logic audit disables this sizing-expression layer so strategy can be inspected without presentation noise.

---

## 9. Current remaining structural mismatches

1. Preflop still returns action/size directly instead of using the same explicit plan object as postflop.
2. Tilted planning profile still flows into judgment/calculation instead of plan selection only.
3. Production expression shaping can still change strategic size after plan selection.
4. Some multiway exploit/blocker/range-advantage consumers still use legacy union range or one main opponent even though distinct opponent pools now exist.
5. Legacy compatibility paths remain for callers that do not provide full canonical event metadata.

These are the current architecture gaps.
The following older findings are CLOSED in the current branch:
- duplicate check-raise producer
- stale checked-before rerouting into check-raise after re-raise
- loss of arbitrary raise depth
- bet/raise treated identically in postflop range inference
- same-street re-raise counted as another barrel
- loss of all-in-call vs all-in-raise semantics
- complete collapse of multiway opponent ranges before core equity
- absence of fold-to-raise observation
