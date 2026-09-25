# Strategy -> code cross-check V1

Basis: `POKER_DECISION_MODEL_V2.md`.

This is a structural audit, not balance calibration.

| Node | Current judgment | Current plan | Current action owner | Status | Main issue |
|---|---|---|---|---|---|
| P1 unopened | open thresholds / reads / ICM in preflop | implicit inside open_decision | open_decision returns action directly | ARCH_MISMATCH | no explicit action-plan object |
| P2 limpers | iso thresholds / limper reads | implicit inside iso_decision | iso_decision | ARCH_MISMATCH | no explicit plan; iso motive and action fused |
| P3 facing open | defend thresholds / reads / stack | implicit inside defend_decision | defend_decision | ARCH_MISMATCH + LEAK | no explicit response-plan; generic thin_value alias leaks from postflop |
| P4 facing 3bet | same defend pipeline, raise_level | implicit | defend_decision | REVIEW | 3bet/4bet strategic knowledge flattened into one pipeline |
| P5 facing 4bet+ | same defend pipeline | implicit | defend_decision/calloff | REVIEW | higher re-raise semantics need explicit audit |
| P6 facing all-in | calloff calculations | implicit | calloff_decision | ARCH_MISMATCH | plan and execution returned together |
| F1/T1/R1 no bet | make/revise/refresh judgment | line plan + attach_intent | act_with_plan executes stored intent | CLOSEST TO TARGET | proactive path already resembles target cycle |
| F3/T3/R3 check then face bet | calldown_need + perceived range/size | no explicit response-plan object | decide_response, then possible checkraise_decision | DUP + ARCH_MISMATCH | two raise producers; response plan not represented |
| F4/T4/R4 bet then face raise | calldown_need / response judgment | no explicit response-plan | decide_response | ARCH_MISMATCH | prior line plan exists but new response plan is implicit |
| F5/T5/R5 raise then face re-raise | same generic response path | implicit | decide_response | REVIEW | repeated aggression levels not explicitly represented |
| any proactive bet size | decide_size after line plan | current intent stores size | execution converts to chips | PARTIAL KEEP | strategic size is chosen before execution, good boundary |
| check-raise size | checkraise_size after second gate | not stored as a unified response-plan | session applies | DUP | separate sizing/action owner from generic response |
| emotion/tilt | h.axes() creates tilted_view before judgment | also direct tilt inputs in planning | tilted profile flows into later decisions | ARCH_MISMATCH | current tilt changes judgment skills, not only plan choice |

## Confirmed semantic leaks

1. `preflop.defend_decision` reads generic `thin_value` -> aliases to `thin_value_turn`.
2. `_allowed(trap)` reads generic `checkraise` -> aliases to `checkraise_flop`.
3. `persona.derive()['value']=='xr'` is derived from flop XR but affects later-street behavior.
4. `bluff_fear` / `hero_call` always read `bluffcatch_river`, then affect earlier-street calls.
5. real check-raises can be created before the checkraise-specific gate.
6. opponent model has fold-to-bet, but not bet-then-fold-to-raise.

## Important correction about emotion

Current `play.Hand.axes()` returns `PS.tilted_view(base, t)`.

`tilted_view`:
- decays the concept vector;
- changes aggression/looseness/discipline;
- re-derives compatibility fields.

Because this modified profile is used in range reading, calculation and response functions,
current tilt can change **JUDGMENT itself**.

Under V2 this is not allowed.  Stable skill can cause imperfect judgment; current emotion may
only bias the plan selected from that judgment.

There is also a second direct tilt path into `make_plan -> trap_judgment`, so trap selection can
receive emotion through both the tilted profile and the explicit tilt argument.

## Refactor target, not yet implemented

```
base profile
   |
   +--> judgment_view      # stable skill/perception limits, no current emotion
   |      -> judged state
   |
   +--> plan_selector(judged state, previous plan, emotion)
   |      -> line plan + current action plan
   |
   +--> action_executor(current action plan)
          -> legal chips/action only
```

Facing a new bet/raise is a new planning event, not an execution override.

No production strategic behavior changed by this document.


# Opponent-action pass

Compared against `OPPONENT_ACTION_COVERAGE_V1.md`.

## What the current engine already preserves well

### Legal betting-round recursion: KEEP

`runner.Round` already represents the legal action loop rather than assuming one action per street.

It preserves:

- repeated full raises;
- minimum raise amount;
- action reopening after a full raise;
- incomplete all-in raises that do not reopen closed raise rights;
- all-in calls;
- no dead raise when every other live player is all-in;
- action order;
- uncalled excess return;
- contestable contribution for unequal stacks/side pots.

This is a strong execution foundation.  The strategic layer does not need to recreate poker legality.

### Per-actor public action history exists: KEEP

`session.HandRun._acts_of(seat)` can recover each opponent's observed postflop sequence
with street/action/size.  `ranges.perceived_range` receives that per-actor history before the
ranges are combined.

So the raw public story is not absent.

## Structural losses after the story is observed

### MULTIWAY-1: opponent-specific ranges are flattened before core plan/equity

In `session`, each live opponent is first assigned and narrowed an individual range, but the
combos are then appended into one `opp_r` union.

`plan._eq_vs(hero, board, opp_range, n_opp)` explicitly treats `opp_range` as
**one opponent's range** and duplicates that same pool `n_opp` times.

Therefore a spot such as:

```
tight player bets
loose player calls
hero acts
```

does not remain as two distinct opponent pools inside the core plan equity calculation.
It becomes one combined pool copied for both opponents.

Status: ARCH_MISMATCH / multiway information collapse.

Required target:
`opp_ranges = {pid/seat -> perceived range}` or an ordered list of distinct pools, preserved
through judgment/equity instead of flattening to one union.

### MULTIWAY-2: one "main opponent" drives several exploit inputs

For planning, `session` chooses one `_main` opponent:

- current aggressor if available;
- otherwise the deepest remaining opponent.

`opp_est` and `opp_stack_bb` are then mainly taken from this one player.

That is insufficient for multiway stories where:

- bettor is loose but caller is very strong;
- one opponent is short all-in while another has a live side-pot stack;
- a player behind can still raise;
- different opponents have opposite fold/call tendencies.

Status: ARCH_MISMATCH / single-opponent reduction.

### MULTIWAY-3: facing-bet equity applies bettor update to an aggregated pool

Inside `act_with_plan`, when facing a bet:

`bet_r = perceived_range(opp_range, [(street,'bet',sz)], profile)`

is applied to the already aggregated `opp_range`, then equity uses:

`[bet_r] + [opp_range] * (n_opp-1)`.

This distinguishes "one bettor + other opponents" only syntactically; the underlying pools are
not tied to the actual bettor/callers' separate ranges.

Status: ARCH_MISMATCH.

### MULTIWAY-4: observed call/raise sequence is not yet a first-class response-plan input

The full per-seat history exists, but `calldown_need/decide_response` mostly receives:

- one aggregated opponent range;
- one main opponent estimate;
- number of opponents / players behind;
- current to-call and line bluff prior.

Thus strategic distinctions such as:

- bet -> call -> hero;
- bet -> raise -> hero;
- check -> bet -> call -> hero;
- hero call -> later raise -> hero;

are not represented as explicit **sequence classes** in the response-plan object because there is
no explicit response-plan object yet.

Status: ARCH_MISMATCH / target for response-plan redesign.

## Opponent actions and fresh re-planning

There is an important partial success:

- every time action returns to a bot, `session` recomputes current perceived opponent ranges;
- `update_plan` runs again;
- if the opponent-range signature moved, `refresh` can update range-dependent state;
- if facing a wager, `act_with_plan -> calldown_need -> decide_response` makes a fresh response.

So later opponent bets/raises are not simply ignored.

However, under the V2 invariant the fresh response should be represented explicitly as:

```
new opponent event
-> judgment
-> response-plan
-> action
```

rather than judgment and action being fused inside `decide_response`.

## Opponent-action audit result

Canonical strategic event classes can be covered without enumerating every literal hand
permutation.  Full raises are recursive; multiway folds/calls/raises are state updates.

The current engine's largest gap is **not legal action coverage**.  `Round` is already strong.
The gap is preservation of opponent-specific strategic information from the public action story
into judgment and response planning.


# Per-opponent range preservation fix — CLOSED (user-validated)

Implemented on this audit branch:

- current-street `r2.log` actions are now included when narrowing each opponent's range;
- ranges are preserved as `opp_ranges[seat]` instead of only being unioned;
- multiway equity uses distinct opponent pools through `bot.equity_vs_combos`;
- `make_plan`, `refresh`, board-change replan, and facing-bet equity can receive those pools;
- per-opponent signatures detect redistribution even when the union of combos is unchanged;
- legacy union `opp_range` remains temporarily for consumers not yet redesigned.

Important remaining scope:

- several exploit/plan consumers still intentionally use one `_main` opponent estimate;
- blocker/nut/range-advantage formulas still use the legacy union where their correct multiway
  aggregation semantics have not yet been specified;
- side-pot-specific strategic weighting is not solved by this patch.

Those are **not** silently marked fixed.  The patch fixes the information-loss boundary first so
later strategy work can consume opponent-specific state without reconstructing it.

Targeted verifier: `tools/verify_multiway_range_preservation.py`.

User validation (Termux, 2026-09-26): compile succeeded and verifier reported `3/3 structural checks passed`.
