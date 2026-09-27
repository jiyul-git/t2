# DECISION SYSTEM — target model + implementation audit

이 문서는 기존의 decision model, situation specification, opponent-action coverage, P1-P7/F1-F8 순차 감사, architecture audit를 통합한 현재 기준이다.

## 1. Core invariant

모든 자발적 액션은 정확히 한 번의 순환을 거친다.

```
new information
-> JUDGMENT
-> PLAN
-> ACTION
-> new information
-> ...
```

### JUDGMENT

현재 시점에 이용 가능한 사실/추정을 해석한다:
- hole cards / current board
- hero/opponent perceived ranges
- made strength, equity, blockers, draws
- position, players behind
- pot, effective stacks, SPR
- action story / initiative
- heads-up / multiway / side-pot
- opponent model + confidence
- tournament/ICM state
- 비감정적 계산/인지 능력

JUDGMENT는 “현재 무엇이 일어나고 있는가”를 답하며 액션을 직접 선택하지 않는다.

### PLAN

판단된 상태에서 목적을 선택한다.

두 층:
1. line plan: value_3street, value_2street, pot_control, bluff line, semibluff, trap, showdown/giveup 등.
2. current action plan: 지금 실행할 fold/check/call/bet/raise/shove와 전략적 size/form.

새 카드나 상대 액션은 새 judgment를 만든다. 기존 line plan은 keep/revise/replace 된다.

### ACTION

집행은 다음만 허용:
- poker legality
- chip unit conversion/rounding
- legal/effective cap
- deterministic UI/representation

집행 단계가 새로운 motive, aggression, fear, tilt, strategic sizing을 발명하면 구조 위반이다.

## 2. Emotion rule

현재 tilt/emotion은 PLAN 선택/수정에만 들어간다.

- 안정적 skill/personality가 판단 정확도를 바꾸는 것은 허용.
- 일시적 tilt가 factual judgment를 바꾸는 것은 금지.
- plan이 정해진 뒤 execution이 tilt 때문에 call을 raise로 바꾸거나 size를 다시 전략적으로 바꾸는 것은 금지.

현재 코드는 base/planning/execution profile view를 갖지만 production consumer 전환은 아직 F7-C logic barrier다.

## 3. Sequential situation coverage

### Preflop

- P0 forced posts
- P1 unopened
- P2 limpers, no raise
- P3 first open을 처음 대면
- P4 opener가 3bet을 다시 대면
- P5 prior caller/back-action
- P6 all-in / call-off / overcall / side-pot
- P7 cold-facing a re-raise

각 node는 position, size, live players, effective stacks, ICM, full public story를 유지해야 한다.

### Postflop

핵심 event classes:
- no wager yet / free action
- check-through
- check then face bet
- bet then face raise
- call then later raise
- raise then re-raise
- street closes / story carry
- main/side-pot continuation

Turn/river는 flop shortcut을 복사하지 않고 새 카드와 기존 story를 다시 판단한다.
River에는 future-card semibluff가 없다.

## 4. Current production pipeline

```
driver
-> Hand/state
-> preflop decision + pf provenance
-> seat-keyed range reconstruction
-> reads / perceived profile
-> update_plan
   -> make_plan or revise_plan
   -> refresh
   -> allowed
   -> intent
-> act_with_plan
-> Round.apply / legality
-> observation
-> Book/Tilt feedback into later decisions
```

핵심 규칙:
- public story는 actor별 실제 action을 기준으로 유지.
- range와 read는 hidden true persona를 직접 읽지 않는다.
- opponent identity가 필요한 곳에서 union/scalar로 압축하지 않는다.
- response to new bet/raise는 새 response-plan event다.

## 5. Preflop audit status

| Node | 상태 | 핵심 |
|---|---|---|
| P1 unopened | 구조 경로 닫힘 | limp/open/shove class와 provenance 보존. 전면 plan refactor는 별도 |
| P2 limped pot | CLOSED | wrong base context, double iso-skill, behind threats, wrong fold stat, sample confidence 수정 |
| P3 face first open | CLOSED | domain leak 제거, response context 보존 |
| P4 opener faces 3bet | CLOSED | story overwrite, raise-level loss, true-persona leak, dead provenance gate 수정 |
| P5 caller back-action | CLOSED | allin event classification, raise depth, fold/4bet stat contamination 수정 |
| P6 all-in/call-off | CLOSED | short shove routing, exact pot/call price, all-in-call provenance 수정 |
| P7 cold vs re-raise | **OPEN strategy** | decision class는 보존되지만 전용 cold-call/cold-4bet model 없음 |

P7 remaining gaps:
- generic defend threshold 재사용 금지 필요.
- original opener + re-raiser를 동시에 판단해야 함.
- cold-call/cold-4bet tendencies 별도 observation 필요.
- players behind가 first-class input이 아님.

검증:
- `verify_preflop_closure.py`: 4/4 PASS
- P2/P3/P4/P5/P6 targeted verifier는 각각 당시 전 항목 PASS.

## 6. Postflop audit status

| Node | 상태 | 핵심 |
|---|---|---|
| F1 free action | CLOSED structural | line plan/current action intent 분리 |
| F2 check-through | CLOSED | delayed-cbet/probe state ordering 수정 |
| F3 check then face bet | CLOSED | duplicate check-raise producer 제거, read semantics 분리 |
| F4 face bet | CLOSED | call price vs bet size, sizing-tell, aggressor event 수정 |
| F5 hero aggressed then raised | CLOSED | raise-to coordinate, cap, back-action classification 수정 |
| F6 caller back-action | CLOSED | original called target, raise depth, persistent response-plan 보존 |
| F7 street closure | CLOSED plumbing/story | range narrowing size coordinate, all-in-call story, closure classes 수정 |
| F8 main/side-pot decision | **OPEN strategy semantics** | settlement/legal primitive는 sound, decision EV는 layer-aware 필요 |

F7 downstream multiway semantics는 `RANGE_MODEL.md`에서 관리한다.

## 7. Global open boundaries

### P7
cold-facing re-raise의 dedicated judgment/plan model.

### F7-B
seat-keyed equity와 union/scalar heuristic가 혼재.
- joint relative strength: closed
- range advantage: closed
- nut semantics: open
- multi-opponent read/stack aggregation: open

### F7-C emotion
현재 planning/execution view는 구조만 준비되어 있고 consumer activation은 아직.

### F7-D sizing/execution
현재 provenance는 `calculated -> shaped -> legal -> final -> applied`를 기록한다.
execution이 strategy size를 silently reshape하지 않는지 최종 semantic closure가 필요.

### F8
main/side-pot mixed eligibility에서 scalar pot/equity/EV를 쓰면 안 된다.
pot-layer별 equity/EV가 판단층으로 연결되어야 한다.

## 8. Audit checklist

새 전략/수정마다 확인:
1. judgment producer
2. line-plan producer/reviser
3. current-action-plan producer
4. sole executor
5. motive concepts
6. execution-form concepts
7. perception/calculation concepts
8. emotion input location
9. observation source
10. duplicate/bypass path
11. multiway identity preservation
12. side-pot eligibility preservation

상태 표기:
`KEEP / SPLIT / ADD / REROUTE / REMOVE_COMPAT / ADD_OBSERVATION / ARCH_MISMATCH`.

## 9. Verification philosophy

- rule/legal fix와 strategy change를 분리한다.
- intentional behavior change는 frozen regression mismatch를 “업데이트”하기 전에 원인 attribution부터 한다.
- random stream 변화도 action 변화와 함께 검사한다.
- 새로운 임계값/계수는 구조 감사의 빈칸을 메우기 위한 임시 수치로 발명하지 않는다.

## 10. Historical sources

Consolidation 이전 원문:
- `POKER_DECISION_MODEL_V2.md`
- `POKER_SITUATION_SPEC_V1.md`
- `OPPONENT_ACTION_COVERAGE_V1.md`
- `CONCEPT_DECISION_CHECKLIST.md`
- `DECISION_ARCHITECTURE_AUDIT.md`
- `STRATEGY_CODE_CROSSCHECK_V1.md`
- `P1_UNOPENED_PREFLOP_AUDIT.md` ... `P7_COLD_RERAISE_PREFLOP_AUDIT.md`
- `F1_FLOP_FREE_ACTION_AUDIT.md` ... `F8_SIDE_POT_DECISION_AUDIT.md`

정확한 원문은 Git history의 pre-consolidation commit `4cfbfc3c...`에서 확인한다.


## 11. logic-tuning branch ownership map

이 section은 `chatgpt/logic-tuning-20260927` 계열에서 추가된 최신 semantic ownership을 기록한다.

## Core flow
runner.py
  Round.apply()
    -> rule truth: action_meta, contrib, stack, raise/all-in legality

action_events.py
  normalized_action()
  postflop_events()
  pending_response_context()
    -> canonical semantic events
    -> facing kind, raise depth, full/incomplete raise, all-in, price/context

session.py
  _acts_of()
  _postflop_response_context()
  _facing_wager_context()
  _run()
    -> rebuild each opponent perceived range from public history
    -> call ranges.perceived_range()
    -> build/update plan via plan.update_plan()
    -> execute action through runner.Round.apply()
    -> write reads / intents / telemetry

ranges.py
  preflop_range()
  perceived_range()
  narrow_by_actions()
  _bet_range()
  _raise_range()
  _call_range()
  _continue_range()
    -> range inference from preflop prior + canonical postflop events

plan.py
  relative_strength()
  joint_relative_strength()
  make_plan()
  refresh()
  river_fix()
  update_plan()
  attach_intent()
  act_with_plan()
  decide_response()
    -> decision layer using perceived ranges, equity, rel, board, plan, response context

reads.py
  Book / perceived_profile / range_profile
    -> observed opponent tendencies only
    -> feeds range inference and exploit adjustments

runner.py
  shape_size()
    -> execution-side human sizing noise
    -> disabled in pure-logic manual audit

## Important ownership rules
- Rule facts are owned by runner.Round.apply().
- Semantic postflop interpretation is owned by action_events.py.
- Opponent range reconstruction is owned by session.py + ranges.py.
- Strategic decision is owned by plan.py.
- Reads describe opponent tendencies; they must not replace public action history.
- Do not reconstruct raise depth / all-in semantics independently in multiple modules.
- rel is computed from the already-updated perceived opponent range; it is not the betting line itself.
- Same-street re-raises are not barrels. Barrel count = distinct aggressive streets.

