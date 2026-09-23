# STYLE_OBSERVER_DEPTH_V4_RESULT

기준: `STYLE_OBSERVER_DEPTH_V4.md`
브랜치: `chatgpt/style-observer-depth-v4`

## 구현

관찰자 자신의 능력에 따라 동일한 상대모델을 서로 다른 해상도로 읽는 SHADOW 층을 추가했다.

`reads.observer_resolution_v4(observer_prof)`:

- coarse_access = 1.0
- see_freq = attention 기반
- see_line = range_read 기반
- see_size = sizing_tell 기반
- apply_willingness = adaptability 기반
- trait_access = max(see_freq, see_line)
- detail_access = 0.30*see_freq + 0.45*see_line + 0.25*see_size

`reads.hierarchical_belief_v4(est, observer_prof)`는 V3의

- coarse style probability
- L/A/X + modifiers
- concrete observed behavior detail

을 그대로 보존하고 observer_depth만 덧붙인다.

표시용 mode:
- COARSE
- TRAIT
- DETAIL

mode 문자열은 action rule에 쓰지 않는다.

## 의미

약한 관찰자는 큰 분류 위주로 읽고,
중간 관찰자는 성향까지,
강한 관찰자는 구체 행동 빈도와 sizing까지 읽을 수 있다.

중요하게 이 차이는 상대의 유형이 아니라 **관찰자 자신의**
attention / range_read / sizing_tell / adaptability에서 나온다.

coarse 자체의 관측 품질은 기존 `perceived_profile`의
observer skill/noise/memory가 이미 조절하므로 V4에서 다시 벌점하지 않는다.

## production 연결

없다.

`session.py` intent snapshot에 `style_hierarchy_v4`만 추가했다.

- plan input 변화 없음
- range input 변화 없음
- sizing input 변화 없음
- read_opponent input 변화 없음
- style -> concept/action LIVE 연결 없음

## 계산 중복 방지

같은 decision에서 이미 계산된

`style_shadow -> hierarchy_v3 -> hierarchy_v4`

결과를 재사용하도록 했다.

독립 계산과 재사용 계산의 결과가 exact match인지 계약 테스트에 고정했다.

## 검증

GitHub Actions run `35807907118` 전부 PASS:

- compile
- observer depth contract
- hierarchy v3 contract
- style v1 contract
- OOP semantics
- blockbet selftest
- replan context
- current regression

따라서 현재 행동 변화는 0이고 V4는 관찰 해상도 SHADOW다.

## 다음 단계

LIVE 연결은 별도 실험으로 진행한다.

후보 구조:

- 낮은 observer depth: coarse hypothesis 영향 중심
- 중간 depth: coarse + traits
- 높은 depth: coarse + traits + detail

단, 문자열 mode로 hard switch하지 않고 연속 access weight를 사용해야 한다.
또한 기존 `persona.read_opponent`의 see_freq/see_line/see_size/use와 중복 계산되지 않게
하나의 공통 소비 경로로 합치는 설계가 먼저 필요하다.
