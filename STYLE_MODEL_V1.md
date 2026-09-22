# STYLE_MODEL_V1 — 행동 스타일 6종 / 개념 능력 분리

기준 브랜치: `integration/ui-v49-money-jump-20260920` @ `cadf41cc`

이 문서는 **설계 명세만 고정**한다. production 판단은 바꾸지 않는다.
다음 단계는 SHADOW 기록이며, LIVE 승격은 별도 검증 후 결정한다.

---

## 0. 핵심 원칙

1. **스타일 = 행동 패턴**이다.
2. **개념 = 능력/이해도**다.
3. **기질 = 성격/방향**이다.
4. 같은 스타일 안에서도 개념 능력은 넓게 퍼질 수 있다.
5. 스타일은 단일 라벨이 아니라 **6개 확률분포**로 유지한다.
6. STATION, BLUFFY, LIMP_HEAVY 등은 기본 스타일이 아니라 **modifier**다.
7. 현재 `reads.opponent_belief` 의 “스타일 → 개념” 경로는 곧바로 LIVE 하지 않는다.
   같은 행동을 두 경로에서 다시 세는 double-count 위험이 있기 때문이다.

---

## 1. 기본 스타일 6종

| 스타일 | 의미 |
|---|---|
| NIT | 매우 좁게 참여. 들어온 뒤 반드시 수동적인 것은 아님 |
| TAG | 비교적 좁게 참여하고 주도권을 잡음 |
| LAG | 넓게 참여하면서 적극적으로 압박 |
| LOOSE_PASSIVE | 넓게 참여하지만 콜/체크 중심 |
| TIGHT_PASSIVE | 적게 참여하고 들어가서도 수동적 |
| MANIAC | 루즈함 + 공격성 + 극단적 압박이 동시에 큼 |

ROCK, STATION, FISH, TAG_TRICKY, HYPER_3BET 같은 이름은 기본 스타일로 두지 않는다.
필요한 정보는 기본 스타일 + modifier + 개념/기질 연속값으로 표현한다.

---

## 2. 스타일 좌표

관찰값은 모두 `reads.perceived_profile` 에서 나온 **관찰자 시점 추정치**를 쓴다.
실제 상대 프로필/개념 벡터는 절대 읽지 않는다.

### 2-1. 보조 함수

```
z(x, center, scale) = tanh((x - center) / scale)       # -1 ~ +1
hi(x, center, scale) = max(0, z(x, center, scale))     # 기준보다 높은 쪽만
lo(x, center, scale) = max(0, -z(x, center, scale))    # 기준보다 낮은 쪽만
clamp10(x) = min(10, max(0, x))
```

현재 모집단 prior를 중심으로 둔다.

```
vpip       0.26
pfr        0.15
pf_3bet    0.07
pf_4bet    0.04
pf_limp    0.06
cbet       0.55
barrel     0.42
post aggr  4.2     # reads.aggr 축의 모집단 중심 근사
sz_big     0.15
sz_sd      0.22
rfi_rel    1.0
```

### 2-2. L — looseness

```
L = clamp10(
    5.0
  + 2.4 * z(vpip,     0.26, 0.10)
  + 1.4 * z(rfi_rel,  1.00, 0.45)
  + 0.9 * z(pf_limp,  0.06, 0.12)
)
```

VPIP가 가장 큰 축이다.
RFI 상대폭은 포지션 차이를 이미 기준화한 값이라 두 번째로 중요하다.
림프는 “루즈함”의 보조 증거일 뿐, passive 여부는 A에서 따로 본다.

### 2-3. A — aggression

```
pfr_ratio = pfr / max(vpip, 0.08)

A = clamp10(
    5.0
  + 1.3 * z(pfr_ratio, 0.58, 0.20)
  + 1.2 * z(pf_3bet,   0.07, 0.05)
  + 1.5 * z(aggr,      4.20, 1.70)
  + 0.7 * z(cbet,      0.55, 0.18)
  + 0.9 * z(barrel,    0.42, 0.18)
)
```

preflop과 postflop을 섞되, 한 지표가 전체를 지배하지 못하게 한다.
cbet은 기회가 적기 쉬워 가중치를 낮게 둔다.

### 2-4. X — pressure extremeness

MANIAC을 “LAG보다 조금 더 공격적인 사람”과 구분하는 축이다.
평균적 행동이면 약 1 근처, 극단적인 압박이 겹칠수록 10에 접근한다.

```
X = clamp10(
  1.0 + 9.0 * (
      0.22 * hi(pf_3bet, 0.09, 0.06)
    + 0.16 * hi(pf_4bet, 0.055, 0.04)
    + 0.20 * hi(barrel,  0.52, 0.20)
    + 0.18 * hi(aggr,    5.20, 1.80)
    + 0.14 * hi(sz_big,  0.22, 0.18)
    + 0.10 * hi(sz_sd,   0.28, 0.20)
  )
)
```

X는 “이상함” 전체가 아니라 **공격 압박의 극단성**이다.
극단적으로 타이트한 사람은 NIT이지 X가 높지 않다.

---

## 3. 6개 스타일 중심점

```
NIT            (L=1.8, A=4.6, X=1.5)
TAG            (L=3.8, A=6.3, X=2.2)
LAG            (L=7.0, A=7.3, X=4.0)
LOOSE_PASSIVE  (L=7.3, A=2.8, X=1.5)
TIGHT_PASSIVE  (L=2.8, A=2.7, X=1.3)
MANIAC         (L=8.6, A=9.0, X=8.0)
```

공통 거리척도:

```
d2(style) =
    ((L-Lc)/1.7)^2
  + ((A-Ac)/1.7)^2
  + ((X-Xc)/2.2)^2
```

---

## 4. 확률분포와 확신도

스타일은 top-1 라벨이 아니라 항상 6개 확률을 가진다.

관찰정보량:

```
q = sqrt(
      confidence
    * min(1.0, n_hands / 24.0)
)
```

표본이 0이면 q=0이고 6개 스타일이 정확히 균등분포가 된다.
초반에 억지 라벨을 붙이지 않는다.

```
raw(style) = exp(-0.5 * q * d2(style))
P(style) = raw / sum(raw)
```

확신도는 top 하나가 아니라 전체 엔트로피를 쓴다.

```
H = -sum(P * log(P))
certainty = q * (1 - H/log(6))
```

표시 기준:

| certainty | 의미 |
|---:|---|
| < 0.20 | 미분류 |
| 0.20~0.40 | 약한 추정 |
| 0.40~0.65 | 유력 |
| 0.65~0.82 | 강한 추정 |
| > 0.82 | 매우 강한 추정 |

UI/로그에 top style을 표시하더라도 내부에는 6개 확률을 모두 보존한다.

---

## 5. modifier — 스타일과 별도

modifier는 전부 0~1 연속값이다.
현재 Book에서 실제로 관찰 가능한 것만 v1에 넣는다.

공통 정보량 게이트는 `q`를 쓴다.

### STICKY
잘 안 접고, 비교적 많이 참여하며, 수동적일수록 높다.

```
sticky = q * (
    0.55 * lo(ftb,  0.42, 0.15)
  + 0.25 * hi(vpip, 0.30, 0.10)
  + 0.20 * lo(aggr, 4.00, 1.50)
)
```

### OVERFOLD
상대 베팅에 과도하게 접는 경향.

```
overfold = q * hi(ftb, 0.62, 0.15)
```

### BLUFFY
블러프 축, 배럴 지속, 큰 사이즈를 함께 본다.

```
bluffy = q * (
    0.45 * hi(bluff,  5.5, 1.8)
  + 0.35 * hi(barrel, 0.52, 0.18)
  + 0.20 * hi(sz_big, 0.22, 0.18)
)
```

### LIMP_HEAVY

```
limp_heavy = q * hi(pf_limp, 0.12, 0.10)
```

### THREEBET_HEAVY

```
threebet_heavy = q * hi(pf_3bet, 0.10, 0.07)
```

### BIG_SIZER

```
big_sizer = q * (
    0.60 * hi(sz_mean, 0.72, 0.25)
  + 0.40 * hi(sz_big,  0.22, 0.18)
)
```

### SIZE_VOLATILE

```
size_volatile = q * hi(sz_sd, 0.30, 0.20)
```

modifier 표시 기준:

| 값 | 표시 |
|---:|---|
| < 0.30 | 숨김 |
| 0.30~0.50 | mild |
| 0.50~0.70 | clear |
| > 0.70 | strong |

### v1에서 보류하는 modifier

`TRICKY`, `TRAP_HEAVY`, `CHECKRAISE_HEAVY`, `PROBE_HEAVY` 는 아직 Book이
해당 공개 행동을 독립 카운터로 충분히 기록하지 않는다.
개념 벡터를 보고 붙이면 정보 누출이다.
먼저 공개행동 counter를 추가한 뒤 SHADOW로 검증한다.

---

## 6. 개념값 0~10의 의미

스타일과 분리된 **능력/이해도**다.

| 값 | 의미 |
|---:|---|
| 0~2 | 거의 모르거나 실행 불가 |
| 2~4 | 개념은 있으나 적용 불안정 |
| 4~6 | 기본 상황에서 사용 |
| 6~8 | 안정적으로 활용 |
| 8~9.5 | 명확한 강점 |
| 9.5~10 | 최상급 / 주무기 |

“많이 한다”와 “잘한다”를 절대 같은 값으로 만들지 않는다.

예:
- MANIAC: aggression 9.3, looseness 9.0, discipline 2.1, bluff skill 4.2
- 숙련 LAG: aggression 7.8, looseness 7.3, discipline 7.0, bluff skill 7.8

둘 다 공격적이지만 완전히 다른 플레이어다.

---

## 7. 개념 분류

### A. 프리플랍 구조
`pf_range`, `open_size`, `pf_defend`, `reraise`, `positional`, `stack_decay`

### B. 에쿼티·수학
`outs`, `potodds`, `spr`, `board_texture`, `stackoff`, `multiway`

### C. 레인지·상대 읽기
`range_read`, `sizing_tell`, `blocker`, `range_merge`, `fold_equity`

### D. 공격 실행
`cbet_flop`, `semibluff`, `bluff`, `barrel_turn`, `barrel_river`,
`checkraise_flop`, `checkraise_late`, `overbet`, `probe`,
`delayed_cbet`, `equity_denial`, `reraise`

### E. 밸류·수비·팟관리
`thin_value_turn`, `thin_value_river`, `blockbet`, `potcontrol`, `trap`,
`bluffcatch_early`, `bluffcatch_river`, `stackoff`

### F. 토너먼트 인식
`icm`, `money_jump`

한 개념이 논리적으로 두 영역과 닿더라도 실제 저장값은 하나뿐이다.

---

## 8. 스타일 → 개념 prior 정책

### 8-1. 기본값은 **연결 안 함**

스타일은 행동 분류다.
개념은 능력이다.

따라서 STYLE_MODEL_V1의 SHADOW 단계에서
`style -> concept skill`은 **기본 weight 0**이다.

기존 `opponent_belief` 의 style prior는 바로 LIVE 하지 않는다.

### 8-2. 후보 tier

행동으로 어느 정도 드러날 수 있는 실행 개념만 우선 후보로 둔다.

**Tier E — 검증 후보, 최대 weight 0.20**
- cbet_flop
- barrel_turn
- barrel_river
- semibluff
- bluff
- checkraise_flop
- checkraise_late
- overbet
- probe
- delayed_cbet
- reraise
- potcontrol
- blockbet
- trap
- thin_value_turn
- thin_value_river
- bluffcatch_early
- bluffcatch_river

**Tier C — 강한 증거가 있을 때만, 최대 weight 0.10**
- pf_range
- open_size
- pf_defend
- positional
- outs
- potodds
- spr
- range_read
- sizing_tell
- blocker
- board_texture
- stackoff
- multiway
- range_merge
- fold_equity
- equity_denial
- stack_decay

**Tier T — style prior 금지**
- icm
- money_jump

토너먼트 상황 인식은 TAG/LAG 같은 행동 스타일만으로 추정하지 않는다.

### 8-3. 승격 조건

offline calibration에서 각 개념별로 direct-only와 style-blend를 비교한다.

style prior를 허용하려면 **두 독립 holdout split 모두**:

```
MAE(style_blend) <= 0.95 * MAE(direct_only)
abs(bias_style - bias_direct) <= 0.15
corr_style >= corr_direct - 0.02
```

셋 중 하나라도 실패하면 해당 개념의 style weight는 0으로 둔다.

즉, “그럴 듯하니까 TAG면 range_read가 높겠지” 같은 수기 가정은 LIVE 하지 않는다.

---

## 9. 캘리브레이션 방법

기존 10개 hidden label 정확도를 목표로 하지 않는다.
새 스타일은 **행동 자체의 요약**이므로 old persona label과 일치할 필요가 없다.

### 9-1. 데이터 분리

- calibration seeds
- holdout A seeds
- holdout B seeds

세 묶음을 완전히 분리한다.

### 9-2. 스타일 검증

첫 구간 행동으로 스타일 posterior를 만든 뒤
**다음 구간 행동**을 예측한다.

예:
- 앞 20핸드 -> style belief
- 뒤 20핸드 -> 실제 VPIP/PFR/3bet/cbet/barrel/aggr 등

style centroid 기반 예측이 flat population prior보다 좋아야 한다.

승격 기준:

```
weighted RMSE(style) <= 0.90 * weighted RMSE(population_prior)
```

그리고 richer direct-stat estimator보다 10% 이상 나빠지면 안 된다.

```
weighted RMSE(style) <= 1.10 * weighted RMSE(direct_stats)
```

스타일은 압축 표현이므로 direct stats를 이기는 것이 필수는 아니다.

### 9-3. 안정성

표본이 늘수록 평균적으로:
- posterior entropy 감소
- top1 flip rate 감소
- certainty 증가

해야 한다.

한 스타일이 전체의 60% 이상을 차지하면 자동 실패는 아니지만,
필드 분포/중심점 붕괴 여부를 먼저 조사한다.

---

## 10. SHADOW 배선 범위

SHADOW에서 기록할 것:

```
style_probs
style_top
style_certainty
style_L
style_A
style_X
modifier_scores
```

행동에 쓰지 않는다.
`plan`, `range`, `sizing`, `read_opponent` 결과를 바꾸지 않는다.

SHADOW 결과를 확인한 뒤에만 다음을 논의한다.

1. style을 UI/리뷰에 표시할지
2. modifier를 exploit 해석에 쓸지
3. style prior를 어떤 concept에 제한적으로 허용할지

---

## 11. v1에서 의도적으로 하지 않는 것

- FISH를 스타일로 사용하지 않음
- ROCK/STATION을 기본 스타일로 사용하지 않음
- MANIAC의 bluff skill을 자동으로 높이지 않음
- TAG의 blocker/range_read를 자동으로 높이지 않음
- old archetype label 맞히기를 성공 기준으로 삼지 않음
- 관찰 불가능한 TRICKY/TRAP 성향을 숨은 프로필에서 읽지 않음
- style top1 하나만 저장하지 않음
- style belief를 즉시 production 의사결정에 넣지 않음

