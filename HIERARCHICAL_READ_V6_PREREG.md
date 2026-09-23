# HIERARCHICAL_READ_V6 — preregistration

기준 integration: `2610ec9ffa68d36e7ab3fcc5167e0a74341a63fd`

## 목적

사용자가 정한 상대 읽기 구조를 실제 판단 후보로 만든다.

- 약한 관찰자: 큰 스타일 가설(coarse)을 중심으로 본다.
- 중간 관찰자: coarse에서 연속 trait 쪽으로 이동한다.
- 강한 관찰자: 구체 행동 빈도(detail)를 주로 본다.

중요한 제약은 **같은 행동을 coarse + trait + detail에서 세 번 더하지 않는 것**이다.
각 채널은 하나의 값만 내고, coarse → trait → detail 순서로 보간한다.

이번 V6는 **SHADOW/반사실 후보**다.
production `persona.read_opponent`를 아직 교체하지 않는다.

---

## 1. 관찰자 해상도

V5의 공통 원천을 그대로 쓴다.

```
res = persona.read_resolution(observer)

see_freq <- attention
see_line <- range_read
see_size <- sizing_tell
use      <- adaptability
```

각 값 0~1.

데이터 사용 상한도 기존 production과 동일:

```
data = min(1, confidence) * min(1, n/12)
w = min(0.85, use * data)
```

정보가 없거나 `w=0`이면 중립.

---

## 2. 계층 보간

각 action-facing 채널마다 source 세 개를 만든다.

```
coarse  = 6-style probability에서 나온 넓은 인상
trait   = L/A/X + modifier에서 나온 중간 해상도
detail  = opp_est의 구체 행동 빈도
```

보간은 한 번만 한다.

```
mid   = coarse * (1-a) + trait * a
final = mid    * (1-a) + detail * a
```

여기서 `a`는 채널별 관찰 능력이다.

- 빈도 채널: `see_freq`
- 라인/블러프 채널: `see_line`
- 사이즈 채널: `see_size`

따라서:
- a=0 → coarse 100%
- a=0.5 → coarse 25% / trait 50% / detail 25%
- a=1 → detail 100%

trait는 중간 능력에서 가장 많이 쓰인다.

---

## 3. coarse semantic table

이 값은 calibration fit이 아니라 **행동 의미를 고정한 사전 규칙**이다.
holdout 결과를 본 뒤 숫자를 바꾸지 않는다.

채널:
`fold_gap, open_gap, barrel_gap, bluff_gap, passive, tb_gap`

| style | fold | open | barrel | bluff | passive | 3bet |
|---|---:|---:|---:|---:|---:|---:|
| NIT | +0.10 | -0.55 | -0.35 | -0.35 | +0.25 | -0.10 |
| TAG | 0.00 | -0.15 | +0.10 | 0.00 | -0.10 | +0.05 |
| LAG | -0.05 | +0.55 | +0.45 | +0.40 | -0.45 | +0.20 |
| LOOSE_PASSIVE | -0.15 | +0.55 | -0.45 | -0.40 | +0.55 | -0.10 |
| TIGHT_PASSIVE | +0.10 | -0.45 | -0.45 | -0.40 | +0.55 | -0.15 |
| MANIAC | -0.20 | +0.80 | +0.75 | +0.80 | -0.80 | +0.35 |

coarse는 여기 없는 정밀 채널을 추측하지 않는다.

다음은 coarse에서 0:
- limp_gap
- tb_polar
- f2tb_gap
- fb_gap
- f2fb_gap
- size_gap
- size_info
- size_big
- size_river deviation

---

## 4. trait source

V3의 공개행동 기반 SHADOW 값만 쓴다.

정규화:

```
l = clamp((L - 5)/5, -1, 1)
a = clamp((A - 5)/5, -1, 1)
x = clamp((X - 2)/6, -1, 1)
```

채널:

```
fold_gap   = 0.25 * (overfold - sticky)
open_gap   = l
barrel_gap = a
bluff_gap  = clamp(0.60*a + 0.40*x + 0.25*bluffy, -1, 1)
passive    = -a
tb_gap     = clamp(0.25*a + 0.50*threebet_heavy, -0.5, 1.0)
tb_polar   = clamp(0.50*max(0,x) + 0.50*bluffy, 0, 1)
size_gap   = clamp(0.70*big_sizer, 0, 1)
size_info  = size_volatile
```

trait에서도 직접 근거가 없는:
`limp_gap, f2tb_gap, fb_gap, f2fb_gap, size_river`
는 0 또는 모집단 기준값으로 둔다.

---

## 5. detail source

현재 `persona.read_opponent`가 사용하는 동일한 `opp_est`에서,
**see_*를 곱하기 전 raw signal**을 만든다.

기존 production 변환을 그대로 재사용한다.

- fold_gap / street fold_gap
- rfi_rel → open_gap
- pf_limp → limp_gap
- barrel → barrel_gap
- pf_3bet → tb_gap
- pf_3bet + n → tb_polar
- pf_fold_to_3bet → f2tb_gap
- pf_4bet → fb_gap
- pf_fold_to_4bet → f2fb_gap
- sz_mean/sz_sd/sz_n/sz_big/sz_river
- bluff → bluff_gap
- aggr → passive

detail은 target hidden profile/concepts를 읽지 않는다.

---

## 6. 출력 계약

`reads.hierarchical_read_v6(observer_prof, opp_est)`

기존 `persona.read_opponent`와 호환되는 action-facing key를 반환한다.

추가 진단:
- `source_weights`
- `coarse_top`
- `coarse_probs`
- `layer_sources`

production 소비처가 진단키를 읽지는 않는다.

---

## 7. 반사실 측정

production 코드는 안 바꾼다.

도구에서만:

```
CONTROL: persona.read_opponent
V6:      reads.hierarchical_read_v6
```

를 같은 시드에 각각 주입한다.

첫 구조 측정은 current regression fixture와 별도 seed set을 사용한다.

시드:
`850001..850012`

조건:
- entries 100
- 30 hands
- hero fold driver
- engine error 0 필수

보고:
1. seed별 full-log hash 동일/차이
2. action/chip 로그 차이 핸드 수
3. observer depth bin별 V6 사용량
   - LOW: detail_access < 0.34
   - MID: 0.34 <= detail_access < 0.67
   - HIGH: >= 0.67
4. source weight 평균
5. synthetic 방향성 계약

## 8. 구조 성공 조건

이번 단계는 EV 승격 시험이 아니다.

필수:
- engine_errors = 0
- HIGH는 V6가 current detail 쪽으로 수렴해야 한다
- LOW는 coarse source가 실제로 남아야 한다
- MID는 trait 비중이 LOW/HIGH보다 커야 한다
- hidden target 정보 0
- 동일 채널을 합산하지 않고 보간 1회
- production current regression은 exact match

행동 차이가 0이어도 실패는 아니다.
다만 LOW/MID/HIGH source 분리가 안 나오면 설계 실패다.

## 9. LIVE 금지

이 결과만으로 production `read_opponent`를 교체하지 않는다.

다음 단계에서 행동 차이와 방향을 검토한 뒤,
사용자와 전략 의미를 확인하고 별도 promotion 여부를 정한다.
