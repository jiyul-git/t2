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
