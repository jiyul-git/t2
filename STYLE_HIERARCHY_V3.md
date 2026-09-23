# STYLE_HIERARCHY_V3 — coarse hypothesis → traits → details

기준 integration: `035a2981ea65536511bde40f8014ff2d99481a02`

이 문서는 **구현 전 설계 고정**이다.

## 목표

상대 읽기를 사람이 흔히 하는 방식처럼 계층적으로 표현한다.

1. 먼저 큰 범주의 가설을 가진다.
2. 그 가설을 고정된 정답으로 쓰지 않고, 관찰이 쌓일수록 확률을 갱신한다.
3. 동시에 "그 스타일 안에서도 무엇이 다른가"를 연속형 성향으로 기록한다.
4. 마지막에는 구체 행동 빈도 자체를 본다.

핵심은 **위 계층이 아래 계층을 덮어쓰지 않는 것**이다.
TAG라고 추정했다고 해서 aggression, bluff skill, range_read 등을 TAG 평균으로 강제하지 않는다.

---

## 1. Layer 1 — coarse style hypothesis

기존 `STYLE_MODEL_V1`의 6개 확률분포를 그대로 쓴다.

- NIT
- TAG
- LAG
- LOOSE_PASSIVE
- TIGHT_PASSIVE
- MANIAC

새로운 center fitting을 하지 않는다.
V2의 unconstrained k-means 결과는 이름 의미를 깨뜨렸고 LIVE 승격 기준도 실패했다.

Layer 1은 다음만 한다.

- 6개 확률
- top1 / top2
- top1 margin
- entropy 기반 certainty
- 현재 evidence q

**금지:** top1 문자열을 production action rule에 직접 넣지 않는다.

---

## 2. Layer 2 — continuous traits

기존 `style_shadow`가 계산하는 값을 그대로 노출한다.

- L — looseness
- A — aggression
- X — pressure extremeness
- sticky
- overfold
- bluffy
- limp_heavy
- threebet_heavy
- big_sizer
- size_volatile

Layer 1의 style label이 이 값을 재설정하지 않는다.

추가로 coarse style center와 실제 L/A/X의 잔차를 기록한다.

예:

```
top = TAG
observed = L 5.2 / A 7.0 / X 2.7
TAG center = L 3.8 / A 6.3 / X 2.2

residual = +1.4 / +0.7 / +0.5
```

이 값이 "TAG로 보이지만 평균 TAG보다 훨씬 루즈하다" 같은 세분화다.

---

## 3. Layer 3 — specific observed behavior

`perceived_profile`에 이미 있는 공개 행동 추정값을 그대로 보존한다.

v3 shadow에서 최소 기록:

- vpip
- pfr
- rfi_rel
- pf_limp
- pf_3bet
- pf_4bet
- cbet
- barrel
- ftb
- aggr
- bluff
- sz_mean
- sz_sd
- sz_big

각 항목은:
- current estimate
- population prior
- delta = estimate - prior

를 기록한다.

이 계층도 style label로 보정하지 않는다.

---

## 4. 업데이트 의미

관찰 장부가 쌓이면 `perceived_profile`이 갱신되고,
그 결과 Layer 1/2/3이 모두 새로 계산된다.

따라서 "처음 TAG 같아 보였다가 나중에 LAG 쪽으로 이동"하는 것이 가능하다.
별도의 고정 label memory는 만들지 않는다.

큰 가설을 먼저 표현하지만, 이후의 관찰이 가설을 수정할 수 있어야 한다.

---

## 5. MANIAC 처리

MANIAC은 6개 coarse hypothesis 안에는 남겨둔다.

다만 V2 결과 때문에 다음을 명시한다.

- MANIAC은 매우 희소한 tail일 수 있다.
- 빈도가 낮다는 이유로 threshold를 낮추지 않는다.
- MANIAC top1 빈도를 목표함수로 사용하지 않는다.
- 실제 판단에서는 X와 구체 행동 빈도를 별도로 보존한다.
- MANIAC label이 없더라도 높은 X/3bet/barrel 등은 Layer 2/3에 남는다.

즉 "MANIAC이라는 이름을 못 붙였다 = 극단 행동 정보를 잃었다"가 되지 않게 한다.

---

## 6. concept / exploit 연결

이번 V3의 production weight는 모두 0이다.

- style → concept: 0
- style → range: 0
- style → sizing: 0
- style → bluff read: 0
- modifier → action: 0

V3는 **내부 표현과 기록 구조**만 만든다.

향후 LIVE 연결은 Layer 3의 특정 행동 예측력이 검증된 뒤 별도 사전등록한다.

---

## 7. 구현 출력

`reads.hierarchical_belief_v3(est)`:

```
{
  version,
  evidence,
  coarse,
  traits,
  detail
}
```

coarse:
- probs
- top
- second
- margin
- certainty

traits:
- L/A/X
- modifiers
- center
- residual_from_top

detail:
- 각 공개행동 estimate/prior/delta

---

## 8. 계약

1. 입력은 `perceived_profile` 출력뿐이다.
2. 실제 상대 profile/concepts/archetype을 읽지 않는다.
3. `style_shadow`의 6개 확률과 L/A/X/modifier를 바꾸지 않는다.
4. 입력 dict를 mutate하지 않는다.
5. production 판단 함수의 인자로 전달하지 않는다.
6. current regression fingerprint가 완전히 같아야 한다.
7. 기존 STYLE_MODEL_V1 / V2 결과 문서는 보존한다.

