# DECISION SYSTEM — target model + implementation audit

## 2026-10-02 코드 재감사 동기화

실제 층은 `make_plan/decide_response/act_with_plan`에 혼재한다. 감정 view의 판단층 유입은 미해결 설계 위반으로 남긴다. P7 cold observation과 F8 closing-call/river-veto는 실제 ACTIVE다. street별 continuation entry와 terminal river policy를 명시적으로 추출했다.

현재 근거: [전체 구조](docs/semantic_audit/CURRENT_ARCHITECTURE_AUDIT.md), [개념→함수](docs/semantic_audit/CONCEPT_FUNCTION_REGISTRY.md), [문서 차이](docs/semantic_audit/DOCUMENT_DRIFT.md), [리팩터링·검증](docs/semantic_audit/REFACTOR_AND_VERIFICATION.md). 아래 과거 실험/commit별 증거는 그 시점 기록이며 현재 배포 인증이 아니다.

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

## 2. Dual-source strategy rule — learned GTO prior + human reasoning

T2의 목표는 solver를 runtime 내부에서 재현하는 것이 아니라, **solver/GTO를 공부한 경험을 가진 인간이 실제 테이블에서 추론하는 방식**을 모델링하는 것이다.

전략 판단에는 두 소스가 동시에 존재해야 한다.

### A. Learned GTO prior / memory

solver, chart, study material을 통해 이미 학습된 기준점이다.

예:
- 포지션별 RFI/defense의 대략적 범위와 혼합 빈도
- 자주 공부한 stack-depth별 preflop pattern
- 특정 board family의 range/nut advantage에 대한 학습된 감각
- 반복 학습한 sizing/frequency pattern

이 층은 매 의사결정마다 CFR/solver를 다시 실행한 결과가 아니다.
사람이 solver 결과를 공부하고 기억하는 것과 같은 **학습된 prior**다.

### B. Human reasoning

현재 실제 상황을 보고 추론하는 층이다.

예:
- hole cards / board / blockers
- position / effective stack / SPR
- pot odds / implied odds
- public action story
- perceived opponent range
- reads / tendencies / confidence
- ICM / money-jump / table context
- exploit opportunity
- 계산 능력과 개념 숙련도

정확히 외운 spot이 아니거나 현재 조건이 학습된 prior와 다르면 reasoning이 보간·수정한다.

### Combination rule

최종 판단은 개념적으로 다음 구조를 따른다.

```
learned GTO prior / memory
        +
current human reasoning
        +
opponent / tournament adaptation
        ↓
JUDGMENT
        ↓
PLAN
        ↓
ACTION
```

GTO frequency를 곧바로 production action으로 복사하지 않는다.
반대로 human reasoning만 사용해 이미 학습 가능한 안정적 전략 지식을 매번 처음부터 재발명하지도 않는다.

GTO-study skill / memory가 높은 player일수록 matched spot에서 prior를 강하게 신뢰한다.
낮은 player일수록 heuristic/reasoning 의존도가 높고 solver baseline에서 더 멀어질 수 있다.

조건 mismatch가 커질수록 exact memorization의 신뢰도는 낮아지고 reasoning 비중이 커져야 한다.

### GTO discrepancy classification

T2와 GTO reference의 차이는 자동으로 bug가 아니다. 최소 세 종류로 분리한다.

1. **reasoning error**
   - 잘못된 hand ordering
   - pot odds/range/story 계산 오류
   - 잘못된 position/stack semantics
   - 의도와 다른 구현
   - 이런 차이는 수정 대상이다.

2. **human approximation / bounded knowledge**
   - solver는 37% mix인데 player는 "가끔" 수준으로만 기억
   - exact stack/size/node를 외우지 못해 근사
   - 제한된 계산/기억 때문에 coarse 전략 사용
   - 의도된 인간 모델일 수 있으며 자동 수정하지 않는다.

3. **intentional exploit / adaptation**
   - 상대가 과폴드/과콜/과3bet 등 특정 경향을 보여 GTO baseline에서 의도적으로 이탈
   - ICM/table state/read confidence 때문에 baseline을 조정
   - 이 경우 GTO와의 차이는 목적 있는 PLAN 변화다.

검증에서 discrepancy를 발견하면 먼저 이 세 범주 중 무엇인지 분류하고 나서 수정 여부를 결정한다.

### Calibration rule

공개 GTO/solver 데이터의 역할은 **T2를 solver clone으로 만드는 것**이 아니다.

사용 목적:
- learned prior의 기준점 교정
- reasoning이 명백히 잘못된 영역 탐지
- hand ordering / stack / position / range semantics 검산
- 높은 GTO-study skill player가 접근해야 할 reference behavior 정의

금지:
- `GTO와 다름 -> 즉시 production constant 수정`
- 단일 hand/단일 chart를 근거로 global tuning
- persona/read/exploit reasoning을 solver frequency로 덮어쓰기

현재 진행 중인 RFI/defense/POST_RANGE calibration은 이 원칙에 따라 **GTO prior/reference layer를 교정하는 작업**으로 해석한다.

### Implementation consequence

향후 두 축을 모두 구현·검증해야 한다.

**GTO knowledge axis**
- public/solver frequency database
- spot condition matching
- learned prior representation
- study/memory accuracy and confidence
- unseen/mismatched spot interpolation
- exact mix를 어느 정도 기억하는지에 대한 player variation

**Human reasoning axis**
- current range reconstruction
- action-story interpretation
- relative strength / equity / blockers
- stack/SPR/pot-odds reasoning
- opponent reads / exploit
- ICM/money-jump
- bounded calculation, approximation, mistakes

두 축의 결합 자체도 first-class design 대상이다.
한쪽을 다른 쪽의 fallback으로 취급하지 않는다.

## 3. Emotion rule

현재 tilt/emotion은 PLAN 선택/수정에만 들어간다.

- 안정적 skill/personality가 판단 정확도를 바꾸는 것은 허용.
- 일시적 tilt가 factual judgment를 바꾸는 것은 금지.
- plan이 정해진 뒤 execution이 tilt 때문에 call을 raise로 바꾸거나 size를 다시 전략적으로 바꾸는 것은 금지.

현재 코드는 base/planning/execution profile view를 갖지만 production consumer 전환은 아직 F7-C logic barrier다.

## 4. Sequential situation coverage

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

## 5. Current production pipeline

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

## 6. Preflop audit status

| Node | 상태 | 핵심 |
|---|---|---|
| P1 unopened | 구조 경로 닫힘 | limp/open/shove class와 provenance 보존. 전면 plan refactor는 별도 |
| P2 limped pot | CLOSED | wrong base context, double iso-skill, behind threats, wrong fold stat, sample confidence 수정 |
| P3 face first open | CLOSED | domain leak 제거, response context 보존 |
| P4 opener faces 3bet | CLOSED | story overwrite, raise-level loss, true-persona leak, dead provenance gate 수정 |
| P5 caller back-action | CLOSED | allin event classification, raise depth, fold/4bet stat contamination 수정 |
| P6 all-in/call-off | CLOSED | short shove routing, exact pot/call price, all-in-call provenance 수정 |
| P7 cold vs re-raise | **CORE + OBSERVATION ACTIVE / FULL EV OPEN** | original opener + re-raiser seat-keyed ranges, 실제 call price, players-behind(`icm.players_behind_required_equity_premium`), skill-dependent reasoning을 전용 P7 판단으로 소비. audit9 batch 1: 이미 올인한 상대가 있으면 그 레인지 대비 eq < need 일 때 공격 억제(`locked_allin_price_gate`), fair share 미만 공격의 근거는 4bet 폴드 읽기 또는 블러프 숙련×폴드 가능 상대 최상단 블로커 몫(`reraise_attack_evidence`). cold-call/cold-4bet 전용 Book 관측/estimate는 존재하나 **소비처 없음**(SHADOW); 독립 지식/전체 EV는 미완료 |

P7 current boundary:
- dedicated `cold_reraise_decision`이 generic defend를 baseline/fallback으로만 사용한다.
- original opener + re-raiser의 **두 seat-keyed perceived range**를 동시에 equity에 소비한다.
- 실제 pot/call price, ICM, pot-odds error, players-behind risk가 같은 판단에 들어간다.
- original-opener identity/range와 players-behind가 결과에 실제 영향을 주는 전용 verifier가 PASS한다.
- 남은 것은 cold-call/cold-4bet **전용 population observation/calibration**이다. 근거 없는 prior를 새로 만들지 않는다.

검증:
- `verify_preflop_closure.py`: 4/4 PASS
- P2/P3/P4/P5/P6 targeted verifier는 각각 당시 전 항목 PASS.

## 7. Postflop audit status

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

## 8. Global open boundaries

### P7
cold-facing re-raise의 dedicated judgment/plan 및 observation은 ACTIVE. 독립 prior/전체 EV는 OPEN.

### F7-B
seat-keyed 판단으로 계속 수렴 중.
- joint relative strength: closed
- range advantage: closed
- blocker effect: closed
- multi-opponent read aggregation: **core closed** — proactive bluff/value planning은 실제 seat별 read 중 가장 안 접는 상대를 constraint로, trap은 가장 bet 가능성이 높은 실제 상대를 사용한다. identity를 synthetic average로 합치지 않는다.
- multi-opponent stack aggregation: **core closed** — target-commit용 scalar가 필요할 때 live seat stack map의 최대 contest depth를 사용하며 원본 seat map도 state/provenance에 보존한다.
- joint strong-region occupancy: active; literal-nuts semantic definition: open

### F7-C emotion
현재 planning/execution view는 구조만 준비되어 있고 consumer activation은 아직.

### F7-D sizing/execution
현재 provenance는 `calculated -> shaped -> legal -> final -> applied`를 기록한다.
execution이 strategy size를 silently reshape하지 않는지 최종 semantic closure가 필요.

### F8
**PARTIAL STRATEGY ACTIVE.** main/side-pot mixed eligibility의 layer geometry와 seat eligibility는 구현되어 있다.
- postflop locked-allin call: complete layer summary + behind 없음 범위에서 layer-aware call equity/breakeven이 response 판단에 실제 소비된다.
- river bet: action-closing + fold/call exhaustive 범위에서 layer bet-vs-check EV가 intent를 veto할 수 있다.
- preflop pure calloff: layer-aware calloff judgment consumer가 있다.
- 남은 범위는 active players/raise branch가 있는 일반 side-pot decision과 비종결 street의 완전한 layer-aware EV다.

## 9. Audit checklist

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

## 10. Verification philosophy

- rule/legal fix와 strategy change를 분리한다.
- intentional behavior change는 frozen regression mismatch를 “업데이트”하기 전에 원인 attribution부터 한다.
- random stream 변화도 action 변화와 함께 검사한다.
- 새로운 임계값/계수는 구조 감사의 빈칸을 메우기 위한 임시 수치로 발명하지 않는다.

## 11. Historical sources

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


## 12. logic-tuning branch ownership map

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
  action_events.response_context()
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

