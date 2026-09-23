# HIERARCHICAL_READ_V7 — 사전등록

기준 integration: `2610ec9ffa68d36e7ab3fcc5167e0a74341a63fd`
선행: `HIERARCHICAL_READ_V6_PREREG.md` · `HIERARCHICAL_READ_V6_RESULT.md`

작성 시점: **측정 전.** 아래의 구조·규칙·성공조건은 결과를 보기 전에 고정한다.
적합(fit)되는 값은 **`c5` 하나뿐**이고 그 목표치도 여기에 미리 적는다.

## 0. 범위와 금지

- **V6 는 LIVE 로 올리지 않는다.** V7 은 별도 후보이고 V6 를 대체하지 않는다.
- production `persona.read_opponent` 를 교체하지 않는다. `plan.py` 무수정.
- **production wiring 금지.** 결과 보고 후 사용자와 전략 의미를 확인하고 정한다.
- 기존 baseline/reference/결과 문서 재생성·덮어쓰기 금지.
- 새 임계값을 발명하지 않는다. 아래 상수는 전부 **기존 코드에서 읽어온 값**이거나
  **구조적으로 유도된 값**이고, 유일한 자유 파라미터는 `c5` 다.

## 1. 다섯 단계 (사용자 확정)

능력 구간의 해석이다. **hard class 가 아니라 연속 능력의 구간**이다.

| # | 이름 | 뜻 |
|---|---|---|
| 1 | NO_EXPLOIT | 상대 성향을 거의 못 읽거나 읽어도 못 쓴다. 상대별 조정 ≈ 0 |
| 2 | IMPRESSION | 타이트/루즈·공격/수동 같은 큰 인상만. 정밀 분류·빈도 추론 없음. 대응 약함 |
| 3 | STYLE_EXPLOIT | 6-style coarse 가설 사용. 약한 B식 추론 허용. **수치 분석 금지** |
| 4 | QUALITATIVE_REG | style 안의 예외를 관찰로 수정. frequency/line/sizing 을 **정성적으로** 사용 |
| 5 | QUANTITATIVE_EXPERT | 빈도·표본수·신뢰도·라인·sizing 을 **수치적으로** 해석. 대응 폭까지 정량 조절 |

**1층을 반드시 명시적으로 남긴다.** 비어 있으면 설계 실패로 본다.

## 2. 능력 축 — 관찰과 적용을 분리한다

`attention` 이 높다고 exploit 를 잘하는 것이 아니다. 네 축이 **함께** 높아야
위로 올라간다. 그래서 합이 아니라 **곱과 최솟값**으로 묶는다.

공통 원천은 기존 helper 하나다 (`persona.read_resolution`). 새 변환을 만들지 않는다.

```
res = persona.read_resolution(prof)
      see_freq <- attention      see_line <- range_read
      see_size <- sizing_tell    use      <- adaptability
      각 값 = clamp((concept - 2)/6, 0, 1)
```

관찰 축 둘과 적용 축 하나:

```
obs_mean = (see_freq + see_line + see_size) / 3        전반적 관찰량
obs_min  = min(see_freq, see_line, see_size)           가장 약한 관찰 축 (상한 역할)
app      = use                                          알아도 쓸 의지
```

**exploit 능력 E**

```
E = app · ( ½·obs_mean + ½·obs_min )          E ∈ [0, 1]
```

`app` 이 곱이라 의지가 0 이면 관찰이 아무리 좋아도 E = 0 이다.
`obs_min` 이 절반을 차지하므로 한 축만 높은 사람은 위로 못 간다.

**수치 해석 능력 num** — 5단계 전용 추가 게이트.

```
NUMERIC = ('range_read', 'potodds', 'spr', 'blocker', 'fold_equity', 'board_texture')
num = mean over NUMERIC of persona.sk(prof, c) / 10
Q   = E · num                                  Q ∈ [0, 1]
```

`NUMERIC` 은 `persona.CALC` 안에서 "빈도·확률·레인지를 수로 다루는" 개념만 고른
것이다. 새 개념을 만들지 않았다.

## 3. 구간 경계

`_see(v) = clamp((v−2)/6, 0, 1)` 의 자연 앵커를 쓴다. 네 축이 모두 개념 레벨
`v` 로 같다면 `E = _see(v)²` 이다. 그래서 경계를 **개념 레벨로** 정한다.

| 경계 | 개념 레벨 | 값 |
|---|---|---|
| c1 (1↔2) | 4 | `(1/3)² = 1/9 ≈ 0.1111` |
| c2 (2↔3) | 5 | `(1/2)² = 1/4 = 0.2500` |
| c3 (3↔4) | 6 | `(2/3)² = 4/9 ≈ 0.4444` |

**c1·c2·c3 은 적합 대상이 아니다.** 기존 `_see` 의 앵커에서 유도된 값이다.

```
tier = 5  if Q >= c5
       4  elif E >= c3
       3  elif E >= c2
       2  elif E >= c1
       1  else
```

5단계는 E 구간이 아니라 **Q 로 따로 잘라낸다.** `Q = E·num` 이므로 E 가 낮으면
num 이 아무리 높아도 5로 못 간다 — "함께 높아야 한다"는 원칙이 식에 들어 있다.

## 4. `c5` 적합 — 유일한 자유 파라미터

목표: **400명 필드에서 5단계가 3~4명** (0.75% ~ 1.00%).

- **모집단**: `fieldsim.Field(entries=400, fmt='standard')`.
  `field.field_quality` 가 entries 에 의존한다 — entries=400 이면 `field_q = 0.9138`
  이고 entries=100 이면 0.7833 이다. **이 비율은 400인 필드 기준으로만 유효하다.**
  `pid == hero_pid(0)` 은 `make_player(rng, 0.9, ...)` 로 따로 만들어지므로
  모집단 통계에서 **제외**한다. 필드당 봇 399명.
- **적합 표본**: 시드 `860001..860050` (50필드 ≈ 19,950명).
  `c5 = Q 의 (1 − 3.5/400) 분위수`. 목표 구간의 한가운데(3.5명)를 겨냥한다.
- **검증 표본**: 시드 `870001..870020` (20필드). 적합에 쓰지 않는다.
  필드별 5단계 인원수를 세고 **3~4명 구간에 드는 필드 비율**을 보고한다.
- 검증이 목표를 벗어나면 **`c5` 를 다시 만지지 않는다.** 벗어난 사실을 그대로
  보고하고, 구조를 바꿔야 하는지 사용자와 정한다.

기존 시드 집합과 전부 배타적이다.

```
810001..810012  820001..820024  830001..830012  840001..840012
850001..850012  900001..900034  700001..700012
```

CF 용 시드는 `880001..880012` 로 따로 잡는다.

## 5. 단계별 읽기 규칙

층 세 개(coarse / trait / detail)의 **정의는 V6 것을 그대로 재사용한다.**
바뀌는 것은 "누가 어느 층을 어떤 세기로 쓰는가" 뿐이다.

```
coarse6  = Σ_style p(style) · _STYLE_V6_COARSE[style][k]
           채널 6개만: fold_gap, open_gap, barrel_gap, bluff_gap, passive, tb_gap
trait    = V6 의 trait 블록 (L/A/X + modifier)
detail   = V6 의 detail 블록 (opp_est 의 공개 행동 빈도)
```

**정밀 채널**(coarse 가 정의하지 않는 것):
`limp_gap, tb_polar, f2tb_gap, fb_gap, f2fb_gap, size_gap, size_info, size_big, size_river`

세기 계수는 새로 만들지 않고 **E 자신을 쓴다** (`s = E`). 구간 경계가 딱딱해지지
않고 능력이 연속으로 반영된다.

증거 혼합 비율도 새로 만들지 않고 **production 의 `data` 를 그대로 쓴다.**

```
data = min(1, confidence) · min(1, n/12)      persona.read_opponent 와 동일
w    = min(0.85, use · data)                   동일. 바꾸지 않는다
```

| tier | coarse6 | trait | detail | 정밀 채널 | 비고 |
|---|---|---|---|---|---|
| 1 | — | — | — | 전부 중립 | **모든 채널 0.** 상대별 조정 없음 |
| 2 | `open_gap`, `passive` 두 개만, ×s | — | — | 전부 중립 | 큰 인상만 |
| 3 | 6채널 전부, ×s | — | — | 전부 중립 | 수치 없음 |
| 4 | prior | prior 보조 | **정성 양자화** | detail 이 준 것만 | 증거가 prior 를 덮는다 |
| 5 | prior | 연속 혼합 | **연속 원값** | detail 이 준 것만 | 수치 해석 |

**4단계의 "정성"** — detail 값을 그 채널의 clamp 범위 위 **5점 격자**로 양자화한다.
범위는 V6 의 최종 clamp 를 그대로 쓴다(예: `barrel_gap` 은 [−1, 1] → 격자
{−1, −0.5, 0, +0.5, +1}). 방향과 대략의 크기만 남고 정확한 빈도는 사라진다.
"LAG 인데 턴 배럴은 적다" 가 표현되고 "배럴 0.37" 은 표현되지 않는다.

**4·5단계의 증거 덮어쓰기**

```
final = (1 − data)·prior + data·evidence
        evidence = qual5(detail)   (tier 4)
                 = detail          (tier 5)
```

관찰이 쌓이면(`n ↑ → data ↑`) evidence 가 prior 를 덮는다. 사용자 원칙 그대로다.

## 6. 가짜 수치 금지 (V6 결함의 직접 수정)

V6 에서 `see_freq ≈ 0.05` 인 관찰자가 coarse 를 **감쇠 없이** 받아
`passive` 를 production 의 +0.018 대신 **+0.262** 로 받았다
(`HIERARCHICAL_READ_V6_RESULT.md` 3-2). V7 은 두 가지로 막는다.

1. **정밀 채널은 1~3단계에서 구조적으로 0 이다.** coarse 나 trait 이 그 자리를
   메우지 못한다. coarse 가 정의하지 않는 값은 아무도 지어내지 않는다.
2. **coarse 기여에 `s = E` 를 곱한다.** 약한 관찰자의 coarse 추론은 약한 prior
   역할만 한다. E 가 낮으면 기여도 작다.

## 7. 반사실 측정

production 코드는 안 바꾼다. 도구에서만 주입한다.

```
CONTROL : persona.read_opponent
V7      : reads.hierarchical_read_v7
```

조건은 V6 와 동일하게 맞춘다 — entries 100 · 30 hands · hero fold driver ·
`engine_errors = 0` 필수. 시드 `880001..880012`.

**V6 결과에서 얻은 계측 교훈 두 개를 반영한다.**

- **bin 축을 `detail_access` 로 쓰지 않는다.** V7 의 구간은 `E`/`Q` 로 정의되므로
  tier 로 직접 집계한다. V6 의 freq 축 역전은 bin 축이 보간 축과 달라서 생긴
  계측 artifact 였다 (`HIERARCHICAL_READ_V6_RESULT.md` 2-1).
- **divergence 는 핸드 수가 아니라 독립 원인 수로 센다.** 핸드마다 읽기 이전의
  사전 상태 서명을 남기고, 사전 상태가 같은데 갈라진 핸드만 독립 원인으로 센다
  (`tools/v6_divergence_trace.py` 와 같은 방식).

## 8. 구조 성공 조건

이번 단계는 EV 승격 시험이 아니다.

**분포**
- `c5` 검증 표본에서 5단계가 필드당 3~4명
- 1단계(NO_EXPLOIT)가 비어 있지 않다
- 다섯 구간이 전부 비어 있지 않다

**구조 (전수 검사로 확인)**
- tier 1 의 모든 action-facing 채널이 정확히 0
- tier 1~3 에서 정밀 채널 9개가 전부 중립 — 한 건이라도 0 이 아니면 실패
- tier 4 의 detail 기여가 5점 격자 위에만 있다
- tier 5 만 연속 원값을 쓴다
- hidden target profile/concepts 참조 0 (입력은 observer 자신의 prof 와 `opp_est` 뿐)
- 같은 채널을 두 번 더하지 않는다

**반사실**
- `engine_errors = 0`
- production current regression exact match
- tier 가 올라갈수록 채널 크기 평균이 커진다 (단조)
- tier 4·5 에서 `n` 이 커질수록 detail 기여 비중이 커진다

행동 차이가 0 이어도 실패가 아니다. 위 구조 조건이 깨지면 설계 실패다.

## 9. LIVE 금지

이 결과만으로 `persona.read_opponent` 를 교체하지 않는다.
분포 calibration → 구조 검사 → 반사실까지가 이번 범위다.
production wiring 은 결과를 보고한 뒤 사용자와 전략 의미를 확인하고 정한다.
