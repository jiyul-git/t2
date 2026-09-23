# STYLE_HIERARCHY_V3_RESULT

기준: `STYLE_HIERARCHY_V3.md`
브랜치: `chatgpt/style-hierarchy-v3`

## 구현

`reads.hierarchical_belief_v3(est)` 를 추가했다.

### Layer 1 — coarse hypothesis
기존 `style_shadow` 를 그대로 사용한다.

- NIT
- TAG
- LAG
- LOOSE_PASSIVE
- TIGHT_PASSIVE
- MANIAC

기록:
- 6개 probability
- top / second
- top margin
- certainty
- evidence q

V1의 probability/상위 tie semantics를 그대로 보존한다.

### Layer 2 — continuous traits

기존 SHADOW의 값을 그대로 기록한다.

- L / A / X
- sticky
- overfold
- bluffy
- limp_heavy
- threebet_heavy
- big_sizer
- size_volatile

추가로 현재 top-style center와 실제 L/A/X의 차이를
`residual_from_top`, `residual_scaled` 로 기록한다.

즉 "TAG 같지만 평균 TAG보다 더 공격적/루즈하다"를 별도 정보로 남긴다.

### Layer 3 — specific observed behavior

`perceived_profile`의 공개행동 추정치를 그대로 기록한다.

- vpip / pfr / rfi_rel / pf_limp
- pf_3bet / pf_4bet
- cbet / barrel / ftb / aggr / bluff
- sz_mean / sz_sd / sz_big

각 항목은 `value / population prior / delta` 로 저장한다.

## production 연결

없다.

`session.py` intent snapshot에 `style_hierarchy_v3`만 추가했다.

- plan input: 변화 없음
- range input: 변화 없음
- sizing input: 변화 없음
- read_opponent input: 변화 없음
- style -> concept: 변화 없음

따라서 현재 V3는 표현/관찰 SHADOW다.

## 검증

GitHub Actions run: `35805092357`

모두 PASS:

- compile
- STYLE_HIERARCHY_V3 contract
- STYLE_MODEL_V1 contract
- OOP semantics
- blockbet selftest
- replan current-context
- current regression

계약 예시:

```
STYLE_HIERARCHY_V3 contract: PASS
top=TAG second=LAG margin=0.525 certainty=0.388
traits L=3.78 A=8.07 X=1.88
residual={'L': -0.017967, 'A': 1.773324, 'X': -0.317248}
```

current regression:

```
기준선 : VPIP 19.1%  PFR 11.4%  flop 44.4%
현재   : VPIP 19.1%  PFR 11.4%  flop 44.4%
전 시드 지문 일치 — 동작 보존 확인.
```

## 해석

이번 구현의 목적은 "6개 스타일이 상대의 진짜 종족"이라고 강제하는 것이 아니다.

내부 표현은 다음 순서다.

```
큰 가설
  ↓
TAG 가능성이 가장 높음
  ↓
하지만 평균 TAG보다 aggression +1.77
  ↓
실제 3bet / barrel / sizing 관측은 각각 따로 유지
```

새 관찰이 들어오면 Book이 누적되고 세 층을 모두 다시 계산하므로,
TAG → LAG처럼 coarse hypothesis 자체도 바뀔 수 있다.

V2에서 확인된 overconfidence 때문에 coarse label은 아래 계층을 덮어쓰지 않는다.
MANIAC 역시 빈도를 늘리기 위해 threshold를 낮추지 않는다.

## 다음 단계

실제 production 판단에 연결하려면 별도 실험이 필요하다.

우선순위는:
1. Layer 3의 특정 행동 관측이 실제 같은 행동의 미래 빈도를 예측하는지 검증.
2. 그 다음 Layer 2 modifier가 direct statistic보다 추가 정보를 주는지 검증.
3. Layer 1 coarse style은 설명/초기 가설 역할을 우선 유지하고,
   action에 직접 연결하는 것은 별도 근거가 있을 때만 한다.
