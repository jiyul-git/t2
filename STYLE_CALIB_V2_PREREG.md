# STYLE_CALIB_V2 — 사전등록 (preregistration)

작성 시점: 측정 전. **이 문서의 수치·규칙은 calibration 출력을 보기 전에 고정한다.**
결과가 게이트를 통과하지 못하더라도 이 문서의 상수·규칙을 사후에 바꾸지 않는다.
바꿔야 한다면 V3 를 새로 사전등록한다.

상위 맥락: `STYLE_MODEL_V1.md`(모델 정의), `STYLE_NATURAL_V1_RESULT.md`(자연상태 V1 측정),
`AUDIT_LEDGER.md` A-1(SHADOW 상태).

---

## 0. 범위와 금지

- **production 판단 로직을 수정하지 않는다.** `reads.style_shadow` 는 integration 에
  이미 들어가 있고 regression fingerprint 동일이 확인된 SHADOW 코드다. 손대지 않는다.
- **LIVE 배선 금지.** style → concept / exploit 연결은 이번 범위가 아니다.
- 기존 baseline/reference 재생성·덮어쓰기 금지.
- calibration 결과물은 `style_params_v2.json` 이라는 **별도 동결 artifact** 이고,
  이를 읽는 것은 `tools/` 아래 측정 도구뿐이다. 엔진은 이 파일을 모른다.

## 1. 시드 집합 (분리 고정)

| 역할 | 시드 | 개수 |
|---|---|---|
| CALIBRATION | 820001 … 820024 | 24 |
| HOLDOUT A | 830001 … 830012 | 12 |
| HOLDOUT B | 840001 … 840012 | 12 |

세 집합은 서로 배타적이고, 아래 기존 집합과도 배타적이다.

```
810001..810012   STYLE_NATURAL_V1 (tools/style_shadow_natural.py)
900001..900034   tools/calibrate.py CALIB_GAME_SEEDS
700001..700012   tools/belief_diag.py TEST_SEEDS
```

타이밍 측정용으로만 999123 을 썼다. 어느 집합에도 넣지 않는다.

실행 조건은 V1 과 동일: `entries=100`, `rounds=40`, `fmt='standard'`,
모든 Hand 가 하나의 `RD.Book()` 을 공유(`MeasuredField`).

## 2. 무엇을 calibration 하는가

**바꾸는 것 (3종)**

1. `CENTERS_V2` — 6개 스타일의 L/A/X 중심 좌표 (6×3)
2. `SCALES_V2` — posterior 거리 `d2` 의 축별 스케일 (3)
3. `POP_V2` — 경험적 모집단 L/A/X 중심 (3). baseline A 의 상수 예측값

**바꾸지 않는 것**

- L / A / X **산출식 자체** (`reads.style_shadow` 의 계수·center·scale 전부).
  V2 는 `RD.style_shadow(est)` 를 호출해 나온 `L, A, X, q` 를 그대로 받아
  **posterior 기하만** 다시 계산한다. 좌표는 비트 단위로 shipped 코드와 같다.
- `q = sqrt(confidence * min(1, n/24))` — 표본 포화식.
- 6개 스타일의 **이름과 의미**. FISH/ROCK/STATION 을 base style 로 되살리지 않는다.
  style 은 행동 패턴이고 skill 이 아니다. modifier 는 style 과 분리된 채로 둔다.
- **평가 지표의 축 스케일** `SCALES_METRIC = (1.7, 1.7, 2.2)`.
  V1 결과와 직접 비교 가능해야 하므로 오차 정규화 상수는 고정이다.
  (posterior 내부 스케일과 평가 지표 스케일은 별개 상수로 취급한다.)
- pair 필터: belief pair `hands >= 4`, future window `hands >= 6`. V1 과 동일.

## 3. calibration 절차 (설명 가능성 요건)

목표는 "숨은 archetype 라벨 맞히기"가 **아니다.** 행동공간 L/A/X 안에서
실제로 밀도가 있는 위치를 찾고, 그 위치를 6개 이름에 규칙으로 배정하는 것이다.
archetype/persona/concept 등 내부 상태는 fitting 입력으로 쓰지 않는다.

### 3-1 입력

CALIBRATION 시드 24개에서, 각 (observer, target) pair 에 대해
**관찰자 노이즈가 없는 raw 행동 집계**로 만든 L/A/X 두 개를 표본으로 쓴다.

```
W1 = 라운드 1..20 누적            (hands >= 6)
W2 = 라운드 21..40 구간 delta     (hands >= 6)
```

두 창을 각각 독립 표본으로 센다. 이유: 예측 대상이 "20라운드 길이의 raw 행동 창"
이므로 fitting 표본도 같은 객체여야 한다.

`raw_est` 는 `tools/style_shadow_natural.py` 의 것을 그대로 쓴다 (관찰 노이즈·shrink 없음).

### 3-2 모집단 기준

- `POP_V2` = W1∪W2 표본의 축별 **평균**.
- 축별 표준편차 `SD_POP` 도 기록한다 (z-scoring 과 MANIAC 진단에 쓴다).
- 공분산 행렬도 기록만 한다. baseline A 는 **평균 상수 예측**이다 (공분산은 안 쓴다).

`(5.0, 5.0, 1.0)` 은 V1 의 임의 상수였다. V2 의 baseline A 는 경험적 평균이므로
**baseline A 는 V1 보다 강해진다.** 게이트가 어려워지는 방향이다. 그대로 간다.
비교 편의를 위해 V1 상수 `(5,5,1)` 의 RMSE 도 legacy 참고값으로 같이 보고하되
게이트 판정에는 쓰지 않는다.

### 3-3 군집

- 표본을 축별로 z-scoring (`SD_POP`) 한 좌표에서 **k-means, k = 6**.
- 초기화: k-means++ , RNG 시드 777..796 으로 **20회 재시작**, inertia 최소해 채택.
  (완전 결정적이다. 재실행하면 같은 답이 나온다.)
- 빈 군집이 생기면 그 재시작은 폐기하고 다음 시드로 넘어간다.
- 수렴 조건: 배정이 안 바뀌거나 100 iteration.
- 군집 중심을 원좌표로 되돌린 것이 `CENTERS_V2` 후보다.

### 3-4 이름 배정 규칙 (사전 고정, 순서대로 적용)

z-좌표 `(Lz, Az, Xz)` 로 판정한다. 각 단계는 아직 배정되지 않은 군집만 본다.

```
1. MANIAC        := Xz 최대 (동률이면 Az 최대)
2. LAG           := (Lz + Az) 최대
3. LOOSE_PASSIVE := (Lz − Az) 최대
4. TIGHT_PASSIVE := (Lz + Az) 최소
5. NIT           := 남은 둘 중 Lz 작은 쪽
6. TAG           := 마지막 하나
```

이 규칙은 L/A/X 위치만 쓴다. 숨은 라벨을 보지 않는다.

**정합성 점검(보고 전용, 재배정 금지).** 아래가 깨지면 깨졌다고 보고한다.

```
C1  L(NIT) < L(TAG) < L(LAG)
C2  L(TIGHT_PASSIVE) < L(LOOSE_PASSIVE)
C3  A(TIGHT_PASSIVE) < A(NIT),  A(LOOSE_PASSIVE) < A(LAG)
C4  X(MANIAC) = max over 6
C5  어느 군집도 표본의 1% 미만이 아니다
```

### 3-5 posterior 스케일

`SCALES_V2` = 축별 **군집 내 잔차 표준편차**(pooled within-cluster sd).
혼합모델에서 자연스러운 스케일이고, 계산식이 한 줄이라 검증 가능하다.
하한 0.5 를 둔다(0 분산 방어). 그 외 손보정 없음.

### 3-6 동결

위 세 값을 `style_params_v2.json` 에 쓰고 커밋한다. **커밋 이후 수정 금지.**
holdout 은 이 파일만 읽는다.

## 4. holdout 측정 (A, B 각각 독립)

calibration 시드를 재사용하지 않는다. holdout 실행은 calibration 동결 커밋 이후에 한다.

### 4-1 안정성

컷 10/20/30/40 에서:

- pair 수, 평균 certainty, 평균 entropy
- top1 분포 (6 스타일 각각의 건수), MANIAC 빈도
- 연속 컷 (10→20, 20→30, 30→40) top1 flip 율

`certainty = q·(1 − H/ln 6)` 은 V1 식 그대로, 단 `H` 는 V2 posterior 의 엔트로피다.

### 4-2 예측력

라운드 20 시점 belief → 라운드 21..40 의 raw L/A/X 예측. V1 과 동일한 구조.

```
A  population : 상수 POP_V2
B  direct     : 라운드 20 시점 관찰자 추정 (L, A, X) 그대로
C  style      : posterior 가중 중심  Σ p_i · CENTERS_V2[i]
```

오차: `sqerr = 1/3 · Σ_axis ((pred − actual)/SCALES_METRIC_axis)²`, RMSE 는 그 제곱평균의 제곱근.
`actual` 은 `raw_est(future)` 를 `RD.style_shadow` 에 넣어 나온 L/A/X 다.
좌표식은 calibration 대상이 아니므로 **타깃은 V1/V2 에서 동일하다.**

pooled RMSE 는 시드별 제곱합을 합산해서 계산한다 (시드별 RMSE 의 평균이 아니다).
시드별 통과 건수도 같이 보고한다.

### 4-3 게이트 (V1 과 동일, 변경 없음)

```
G1   RMSE_style <= 0.90 × RMSE_population
G2   RMSE_style <= 1.10 × RMSE_direct
```

**holdout A 와 B 가 둘 다 pooled 기준으로 G1·G2 를 통과해야 promotion candidate 다.**
하나라도 떨어지면 candidate 아님으로 보고한다. 수치를 맞추려고 상수를 바꾸지 않는다.

같은 dump 로 **V1 파라미터의 게이트 결과도 같이 계산**해 나란히 싣는다
(V1 대비 개선 여부를 보기 위함이며, V1 수치는 게이트 기준이 아니다).

## 5. MANIAC 희소성 진단 (사전 정의)

V1 자연상태에서 round40 top1 MANIAC 이 **0** 이었다. 세 가지를 분리해 잰다.

**(a) 식(formula) 병목.** X 는
`X = 1 + 9·Σ w_i · hi(x_i, c_i, s_i)`, `hi = max(0, tanh(·))`, `Σ w_i = 1` 이므로
정의역 최대가 10 이다. calibration 표본에서 6개 항 각각의
평균·중앙값·p90·p99·**0 인 비율**을 보고한다. 어떤 항이 구조적으로 0 인지 특정한다.
`X_p99` 와, 모든 항을 각자의 p99 로 놓았을 때의 가상 X 값을 같이 낸다.

**(b) 중심(center) 병목.** V1 MANIAC 중심 `(8.6, 9.0, 8.0)` 에서
가장 가까운 calibration 표본까지의 거리(V1 스케일 단위)와,
V1 스케일에서 MANIAC 이 argmax 가 되는 표본 수를 센다.

**(c) 스케일(scale) 병목.** 같은 중심·같은 표본에서 스케일만
`(1.7,1.7,2.2)` → `SCALES_V2` 로 바꿨을 때 MANIAC argmax 수가 어떻게 변하는지 센다.

셋의 기여를 분리해 보고한다. **MANIAC 을 만들어내려고 임계값을 낮추지 않는다.**
극단 공격 영역에 표본이 없으면 "없다"고 보고한다.

## 6. 산출물

```
tools/style_dump_v2.py     시드 1개 실행 → pair×cut belief + raw window 덤프 (JSON)
tools/style_fit_v2.py      CALIB 덤프 → style_params_v2.json (+ MANIAC 진단)
tools/style_eval_v2.py     holdout 덤프 + 동결 params → 안정성·예측력·게이트
.github/workflows/style-calib-v2.yml   시드 단위 matrix, job 당 timeout 명시
STYLE_CALIB_V2_RESULT.md   결과 문서
```

실행은 GitHub Actions 에서 시드 단위로 병렬화하고 job/step 양쪽에 timeout 을 건다.
무한 대기 감시 루프를 쓰지 않는다.

## 7. 사전 선언한 실패 조건

- engine_errors 가 하나라도 있으면 해당 시드는 INVALID 로 보고하고 pooled 에서 제외한다.
  전체의 10% 를 넘으면 측정 전체를 INVALID 로 본다.
- C1~C5 정합성 위반이 나오면 배정을 고치지 않고 위반 사실을 결과 문서에 남긴다.
- 게이트 미통과는 실패가 아니라 결과다. LIVE 승격 근거가 없다고 쓴다.
