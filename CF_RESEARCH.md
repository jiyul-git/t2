# COUNTERFACTUAL RESEARCH — consolidated history

이 문서는 personality/plan path와 pcz/made gate에 대한 반사실 연구의 최종 기록이다. production tuning 지침이 아니라 과거 causal evidence다.

## 1. 공통 실험 규칙

- 코드보다 설계를 먼저 고정.
- 결과를 본 뒤 threshold/arm을 발명하지 않음.
- 모집단을 baseline policy가 정하면 사후 확장하지 않음.
- 가능한 경우 common random numbers 사용.
- RNG stream이 branch 때문에 달라지는 경우 그 자체를 기록.
- label change, action change, EV change를 별도 결과로 분리.
- 한 axis를 1↔9로 흔드는 실험은 field-realistic effect와 구분.
- result가 예측과 다르면 예측을 고치지 않고 틀렸다고 기록.

## 2. Level 1 — execution layer

초기 Level 1은 `decide_aggression`과 일부 preflop threshold consumer를 측정.
중요 결론:
- 일부 axis는 실제 행동을 직접 뒤집음.
- `aggression`은 direct execution candidate.
- 첫 버전은 consumer coverage가 불완전해 확장 실험 실시.

## 3. Level 1 extension

추가:
- response layer
- preflop aggression -> open_pct path

`potcontrol`은 direct action frequency보다 plan layer candidate 성격이 강함.
질문이 “직접 조절 vs plan을 바꿔 간접 조절”로 이동.

## 4. Level 2 — plan layer

D/M/T 팔로 direct와 mediated effect를 분리.
계획 변화와 행동 변화가 항상 1:1이 아님을 확인.

핵심 해석:
- `plan≠, action=` 가능
- `plan=, action≠` 가능
- layer attribution 없이 axis effect 하나로 합치면 안 됨

## 5. Normalization / order / path

L1/L2 denominator와 정의가 달라 직접 서열 비교를 폐기하고 normalization 수행.

이후 axis effect order를 설명하기 위한 후보들을 측정했지만:
- reach
- base frequency
- coefficient size
- gate/clamp/saturation
- 단순 단일-stage explanation
중 어느 하나도 단독 원인으로 확정되지 않음.

Path experiment의 preregistered 네 가설은 모두 기각.
“한 S1~S8 단계가 effect ordering을 만든다”는 설명을 채택하지 않음.

## 6. Divergence / replication / arithmetic

Divergence 단계에서 axis별 path occupancy/transition 차이를 관측.
새 시드로 표본 밖 재현 수행.

DEVIATE 내부 arithmetic audit는 가산 위치와 clamp/nonlinearity를 코드/측정으로 분해.
이 연구는 “역추론 가능한 구조가 재현됨”까지 확인하고 종료.

## 7. PCZ experiment

질문:
`pcz` threshold에 기존 penalty를 적용하면 어떤 plan label이 이동하는가.

원칙:
- 새 penalty coefficient 발명 금지
- 기존 code의 값만 arm으로 사용
- fixed eq band가 아니라 실제 진입 population 사용

초기 measurement bug가 한 번 있었고 폐기/재측정 기록을 유지.

결과는 “giveup rescue” 하나로 단순화되지 않았고, label 이동이 더 넓게 나타났다.

## 8. MADE gate experiment

`plan.py`의 `made >= 1` predicate만 세 arm으로 교체.
`made` 값 자체를 바꾸지 않아 다른 consumer contamination을 피함.

핵심:
- `made` 생성식은 draw를 포함하지 않는 integer category.
- board<5에서 board-category 추정이 단순 rank-frequency 기반.
- kicker는 반영하지 않음.
- 해당 predicate의 잔존 population을 arm별로 분리 가능.

사전등록 D1-D6는 당시 결과에서 모두 충족.

## 9. EV experiment

baseline에서 465에 정확히 한 번 도달한 hand를 snapshot replay.

초기 1,000-hand sample에서 모집단 28건.
label/action 일부가 달라도 chip EV가 그대로인 pair가 존재.
일부 `bet -> bet`은 refresh promotion ladder가 달라진 것이고 최종 chip result는 같았음.

따라서 “label flip = EV change”로 해석하지 않는다.

## 10. Joint PCZ × MADE experiment

고정:
- seeds 7000-7199
- 10,000 hands
- pcz 2 arms
- made 3 arms
- combined 12 replay paths per hand
- plan.py production code 수정 없음

관찰:
- PM interaction에서 `ΔEV_PM = ΔEV_P`가 pair 전반에서 나타남.
- 이것이 MADE가 무효라는 뜻은 아님. 다른 label/path 변화가 downstream chip EV에 전달되지 않은 경우를 분리해야 함.
- mean EV는 소수 hand에 민감하여 부호를 과해석하지 않음.

## 11. EQ/REL diagnostic link

중간 추적에서:
- 진입은 미래 포함 equity
- 내부 일부 gate는 current-board relative/made
가 섞여 있었다.

1,000-hand count에서 465 도달 36건의 실제 binding condition을 재검토했고, 초기에 “rel이 막는다”는 진단을 수정:
- 36 중 25는 rel threshold를 통과
- 다수의 binding gate는 `made >= 1`

이 오류 수정이 MADE counterfactual 설계의 직접 근거가 됨.

## 12. Historical sources

모든 `CF_DESIGN_*.md`, `CF_RESULT_*.md`, `CF_PROFILE.md`,
`TRACE_EQREL.md`, `TRACE_EQREL_COUNT.md`, `TRACE_MADE.md`.

정확한 preregistration 문구와 수치는 pre-consolidation Git history에 보존.
