# STYLE_OBSERVER_DEPTH_V4 — observer-dependent belief resolution

기준: `STYLE_HIERARCHY_V3`

목표는 같은 상대 모델을 모든 봇이 똑같은 해상도로 소비하지 않게 하는 것이다.

## 원칙

사람은 상대를 볼 때 읽기 능력에 따라 해상도가 다르다.

- 약한 관찰자: "TAG 같다 / LAG 같다" 같은 큰 분류 중심
- 중간 관찰자: 큰 분류 + 루즈함/공격성/sticky/3bet-heavy 같은 성향
- 강한 관찰자: 위 둘 + 구체적인 3bet/cbet/barrel/fold/sizing 정보

이 차이는 **상대가 누구냐가 아니라 관찰자 자신의 능력**에서 나온다.

이번 V4는 이 해상도만 SHADOW로 기록한다. 실제 action rule에는 아직 연결하지 않는다.

## 기존 생산 코드와의 관계

`persona.read_opponent`는 이미 관찰자의

- attention -> frequency read
- range_read -> line read
- sizing_tell -> size read
- adaptability -> 실제로 전략을 바꿀 의지

를 서로 분리해 사용한다.

V4는 이 기존 의미를 새로 invent하지 않고 같은 0~1 변환을 재사용한다.

```
see(v) = clamp((v - 2) / 6, 0, 1)
```

## V4 depth

```
coarse_access = 1.0

see_freq = see(attention)
see_line = see(range_read)
see_size = see(sizing_tell)
apply_willingness = see(adaptability)

trait_access = max(see_freq, see_line)

detail_access =
    0.30 * see_freq
  + 0.45 * see_line
  + 0.25 * see_size
```

coarse를 1.0으로 둔 이유:
큰 가설 자체의 품질은 이미 `perceived_profile`에서 observer의
skill/noise/memory를 통해 나빠질 수 있다. 여기서 다시 coarse를 약하게 만들면
같은 능력을 이중으로 벌점 준다.

traits/detail access는 "추가로 어느 깊이까지 읽을 수 있는가"만 표현한다.

## 표시용 mode

action gate가 아니라 로그/UI 요약용이다.

```
detail_access >= 0.67 -> DETAIL
else trait_access >= 0.34 -> TRAIT
else -> COARSE
```

실제 production 연결 시 이 mode 문자열로 분기하지 않는다.
연속 access 값을 쓴다.

## 출력

`reads.hierarchical_belief_v4(est, observer_prof)`

- coarse: V3 6-style probability 그대로
- traits: V3 L/A/X + modifiers + residual 그대로
- detail: V3 observed behavior detail 그대로
- observer_depth:
  - coarse_access
  - trait_access
  - detail_access
  - see_freq
  - see_line
  - see_size
  - apply_willingness
- mode: 로그/UI 요약

## 금지

- target의 hidden profile/concepts를 읽지 않는다.
- observer 자신의 profile만 읽는다.
- coarse label로 trait/detail 값을 덮어쓰지 않는다.
- mode 문자열을 action rule에 쓰지 않는다.
- 이번 단계에서 baseline을 갱신하지 않는다.
- style -> concept / range / sizing / action LIVE 배선 없음.

