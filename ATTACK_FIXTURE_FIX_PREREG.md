# ATTACK_FIXTURE_FIX — 사전등록

기준 커밋: `b9e3387` (`claude/synth-channel-split`, 동결)
브랜치: `claude/attack-fixture-fix`
작성 시점: **측정 수치를 보기 전.** 아래 "구성 확인"은 상태 구성 진단이고
regret·arm 비교는 한 번도 돌리지 않았다.

---

## 0. 질문

`SYNTH_CHANNEL_SPLIT` 이 `PIPE_ONLY` null 의 정체를 밝혔다 —
수비 `+0.00527` 과 공격 `−0.00200` 을 24:48 로 섞어 `+0.00042` 가 된 것이고,
**공격의 음수는 production 판단이 아니라 fixture 배선 오류**였다.

```
qx_ev_fixture.State.book()        ftb = 1 − b_true             r(b_true, ·) = −1.000
qx_ev_fixture.State.ev_actions()  P(fold) = .18 + .60·b_true   r(b_true, ·) = +1.000
```

그래서 남은 질문은 하나다.

> **공격 정보를 정상적으로 배선했을 때도 읽기 정확도가 실제 EV 를 개선하는가?**

## 1. 동결과 범위

- **`tools/qx_ev_fixture.py` 를 수정하지 않는다.** `QX_EV_VALIDATION` 과
  `SYNTH_CHANNEL_SPLIT` 의 재현이 거기 걸려 있다. 새 파일에서 파생만 한다.
- 기존 QX / READ_USE / SYNTH 산출물 **전부 무수정.**
  옛 공격 결과 `−0.00200` 은 **결함 fixture 의 역사적 결과로 동결**한다.
  재현하려 하지 않는다.
- production 무수정. `stat_read` 구현 금지. **새 축 추가 금지.**
- `c5` · V7 tier 경계 · baseline 무변경.

## 2. 무엇을 고쳤나

공격 상태에서 두 파라미터를 **독립**으로 만든다.

| 파라미터 | 뜻 | 장부에 남는 곳 | 오라클에서 쓰이는 곳 |
|---|---|---|---|
| `b_true` | 상대가 **벳할 때** 블러프인 비율 | `cbet`, `barrel`, `sd_weak` | 히어로 에쿼티, 리버 배럴 확률 |
| `ftb_true` | 상대가 **벳을 마주쳤을 때** 접는 빈도 | `fold_to_bet`, `f2b_*` | 내 벳에 접을 확률 |

```python
f_bluff = ftb_true + (1 − b_true)·D
f_value = ftb_true − b_true·D
#   주변 폴드확률 = b·f_bluff + (1−b)·f_value ≡ ftb_true      (항등)
#   그리고 f_value < f_bluff — 약한 손이 더 접는다는 구조는 유지
```

`D = 0.28` 을 **상수**로 둔다. 상태마다 다르면 "손 종류가 주는 정보량"이
`ftb_true` 와 교락된다. 격자에서 `f_bluff` 최대 `0.918`, `f_value` 최소
`0.110` 이라 클램프가 걸리지 않고 항등이 정확히 성립한다.

격자는 **교차(crossed)** 다 — `ftb_true ∈ {0.32, 0.44, 0.56, 0.68}` ×
`b_true ∈ {0.15, 0.35, 0.55, 0.75}` × `n_obs ∈ {6, 40}`.

**수비 상태는 옛 `qx_ev_fixture.State` 를 그대로 쓴다.** 수비 경로
(`calldown_need`)는 `ftb` 를 읽지 않으므로 결함의 영향이 없고, 그래야
옛 수비 결과와 **비트까지 대조**된다. 이것이 §3 게이트 5 다.

### 구성 확인 (regret 은 안 봤다)

```
공격 셀 9  (층 4~6 / 7~9 / 10~12 벳최적 각 3셀, 보드 6개, 핸드당 최대 2셀)
공격 상태 288   수비 상태 24
최적=bet 비율 0.500          (구성상 균형)
ftb 로 최적이 뒤집히는 (셀,b) 32/36
```

`ftb` 가 최적을 2개 미만의 `b` 수준에서만 바꾸는 셀은 후보에서 제외했다 —
공격 채널에서 읽어야 할 것이 `ftb` 이므로 그런 셀로는 읽기 능력을 못 잰다.

## 3. 게이트 — 측정 전에 전부 통과해야 한다

`--check` 로 **regret 집계 없이** 돌린다. 하나라도 실패하면 `INCONCLUSIVE`.

**G1 — `ftb_true` 와 `b_true` 의 독립성.**
공격 상태 전체에서 `|r(ftb_true, b_true)| < 1e-12`. 교차 격자이므로
설계상 0 이고, 코드에서 실제로 0 인지 확인한다.

**G2 — 장부가 `ftb` 를 올바른 방향으로 추적한다.**
잘 읽는 arm 기준 `r(ftb_true, est['ftb']) > 0.5` 이고
`r(ftb_true, fold_gap(turn)) > 0.5`.
추가로 **`r(b_true, est['ftb'])` 의 절대값이 0.2 미만**이어야 한다 —
옛 결함(`−1.000`)이 사라졌다는 직접 확인이다.

**G3 — 오라클이 `ftb` 와 같은 방향이다.**
`r(ftb_true, P(fold)) > 0.99` 이고, 항등 잔차
`max |b·f_bluff + (1−b)·f_value − ftb_true| < 1e-9`.

**G4 — 소비 지점이 arm 별로 갈린다.**
공격 상태에서 `PIPE_ONLY` 는 `plan.py:918` 과 `plan.py:1240` 둘 다
`w > 0` 비율 **100%**, `CALC_ONLY` 는 **0%**.

**G4b — 봇의 행동이 `ftb` 를 따라간다.**
`PIPE_ONLY` 의 벳 확률에 대해 `r(ftb_true, p_bet) > 0.1`,
`CALC_ONLY` 는 `|r| < 0.02`. (읽는 쪽만 반응해야 한다.)

**G5 — 수비 대조는 옛 결과를 그대로 낸다.**
같은 프로필 150 에서 수비 채널이
`CALC_ONLY 0.03323 / PIPE_ONLY 0.02796 / d = +0.00527` 을
**소수점 다섯째 자리까지** 재현.
수비 상태를 옛 `State` 그대로 쓰므로 정확히 나와야 한다.
안 나오면 내가 모르는 곳이 바뀐 것이고, 그러면 공격 결과도 못 믿는다.

**G6 — 판별력.** 최적=bet 비율이 `[0.45, 0.55]` 안, `ftb` 뒤집힘 `≥ 30/36`.

## 4. 통계량과 판정 — 결과를 보기 전에 고정

```
d_X = mean regret(CALC_ONLY, X) − mean regret(PIPE_ONLY, X)     > 0 이면 잘 읽는 쪽이 낫다
```

- 표본: `base_profiles(seeds, entries=400, n=400)[:150]`
  - **SET_A** `940001-940010` — `QX_EV_VALIDATION` · `SYNTH_CHANNEL_SPLIT` 과
    같은 집합. 과거 대조를 위해 주 집합으로 쓴다.
  - **SET_B** `950001-950010` — 재현 집합.
- 신뢰구간: **프로필 단위 클러스터 부트스트랩 4000회**, 시드
  `v7_num_battery.SEED`. (`v7_num_intervention.boot_ci` 와 같은 절차.)
- **`FLOOR = 0.002`** (팟 대비). `READ_USE_SEPARATION`·`SYNTH_CHANNEL_SPLIT`
  과 같은 값·같은 근거 — `QX_EV_VALIDATION` 의 `QX_E` 사분위 격차 0.0130 의
  약 1/6. 묶음 전체에서 문턱을 바꾸지 않는다.

`OK(d)` = `d ≥ FLOOR` 이고 95%CI 가 0 을 배제하며 **SET_A·SET_B 둘 다** 성립.
`OK₋(d)` = 같은 조건을 `d ≤ −FLOOR` 로.

```
V0  INCONCLUSIVE        G1~G6 중 하나라도 실패
V1  ATTACK_READ_HELPS   OK(d_A)
V2  ATTACK_READ_HURTS   OK₋(d_A)
V3  ATTACK_READ_NULL    그 외 (부호가 집합 간에 엇갈리거나, FLOOR 미만이거나,
                        CI 가 0 을 포함)
```

`V3` 은 "효과 없음"이 아니라 **"이 설계로는 문턱 위 효과를 못 보였다"** 로
쓴다. `d_A` 가 유의하지만 FLOOR 미만이면 그 값을 본문에 그대로 적는다 —
`READ_USE_SEPARATION` 에서 `R4` 라벨이 데이터를 잘못 요약한 일을 반복하지
않기 위해, **라벨과 수치를 분리해서 보고한다.**

### 사용자 결정 지점과의 대응

```
A  stat_read 설계 진입 가능     V1 이고 수비 대조 d_D 도 양수 (G5 로 이미 보장)
B  채널별 분리 또는 개념 재검토   V2 또는 V3
```

이 대응은 **결과를 보기 전에** 고정한다. 판단은 사용자가 한다.

## 5. 보고 항목

1. 게이트 G1~G6 전부
2. 공격 채널 단독 `d_A` (SET_A / SET_B, 평균 + 95%CI)
3. 수비 채널 `d_D` (옛 결과와의 대조)
4. 정상 fixture 에서의 합산 — 가중치(상태 수)를 명시한다.
   **옛 24:48 과 새 24:288 은 다르다.** 합산 값은 가중치에 크게 의존하므로
   상태 수 비율을 바꾸면 값이 바뀐다는 점을 본문에 적고, 채널별 값을
   1차 근거로 삼는다.
5. `n_obs` 6 / 40 분리
6. 옛 `−0.00200` 과 **나란히 놓되 비교하지 않는다** — 다른 fixture, 다른 상태다.

## 6. 금지

- `qx_ev_fixture.py` 수정 금지. 기존 산출물 수정 금지.
- 옛 공격 결과 `−0.00200` 재현 시도 금지.
- production/LIVE 변경 금지. baseline 갱신 금지.
- `stat_read` 구현 금지. 새 persona 축 추가 금지.
- 결과를 보고 `FLOOR`·판정 규칙·격자·`D` 변경 금지.
- 게이트 결함이 나오면 **결과를 보기 전에** amendment 로 남기고 고친다.
  이번에는 게이트와 본 측정을 **분리된 실행**으로 돌린다
  (`SYNTH_CHANNEL_SPLIT` Amendment C1-4 의 반성).

## 7. 산출물

- 본 문서 (측정 전 커밋)
- `tools/attack_fixture.py` — 고친 공격 상태 + 옛 수비 상태
- `tools/attack_read_measure.py` — 게이트(`--check`)와 측정
- `ATTACK_FIXTURE_FIX_RESULT.md`
- `docs/ATTACK_FIXTURE_FIX.png`
- production 무수정 / regression 지문 **전 시드 일치** / 실험 프로세스 0 /
  worktree clean / local=remote 확인

---

# Amendment D1 — 깨끗한 읽기 대조를 보조 분석으로 추가

## D1-0. 공개 — 이 amendment 는 주 결과를 본 뒤에 쓴다

§4 의 주 판정(`d_A` 기반)은 이미 측정했고 수치를 봤다. 주 판정과 그 규칙은
**바꾸지 않는다.** 여기서 추가하는 것은 **별도 통계량의 보조 분석**이고,
그 규칙을 돌리기 전에 고정한다.

## D1-1. 왜 필요한가 — 주 통계량이 교락돼 있다

`tier5_axis_validate.make_arms` 는

```python
PIPE_CONCEPTS   = ('range_read', 'sizing_tell')
PIPE_TEMPER     = ('attention', 'adaptability', 'consistency')
APPLY_ONLY_CALC = PS.CALC 에서 PIPE_CONCEPTS 를 뺀 나머지 전부
HI, LO = 9.0, 2.0
```

로 두 arm 을 만든다. 즉 `CALC_ONLY` 와 `PIPE_ONLY` 는 **읽기 파이프라인만
다른 것이 아니라 `fold_equity`·`board_texture`·`multiway`·`potodds`·`spr`·
`blocker` 등 APPLY 쪽 개념 다발이 통째로 반대**다. 그리고 그 개념들은
`decide_aggression` 과 `cbet_freq` 가 **상대 추정치 없이 직접** 읽는다.

실측이 이것을 확인한다.

```
CALC  n_obs=6  p_bet 0.5322     n_obs=40  p_bet 0.5322    차이 +0.00000  (안 읽으니 당연)
PIPE  n_obs=6  p_bet 0.5159     n_obs=40  p_bet 0.5116
PIPE − CALC    n_obs=6  −0.01628      n_obs=40  −0.02059
```

`n_obs = 6` 에서 `w ≈ 0.110` 이라 읽기 조정이 거의 없는데도 두 arm 의 벳
확률이 이미 **−0.016** 벌어져 있다. 읽기가 만든 차이가 아니다.

`make_arms` 는 `TIER5_AXIS_DESIGN` 에서 **배터리 음성 대조**(QX_E 가 두 종류의
능력을 구분하는가)로 만들어진 것이다. 그것을 "읽기 정확도의 EV 효과" 측정에
쓴 것은 내 사전등록의 통계량 선택 실수다. 이 결함은 `QX_EV_VALIDATION` 의
합성 대조와 `SYNTH_CHANNEL_SPLIT` 의 채널 분리에도 **똑같이** 있다.
(채널 분리의 산술은 그대로 유효하다 — 같은 수치를 다시 묶은 것이므로.)

## D1-2. 보조 분석 — READ_USE 의 R 축을 공격 채널에 적용

`READ_USE_SEPARATION` 이 이미 검증한 깨끗한 개입을 그대로 쓴다.
`tools/read_use_fixture.read_arm(a)` — `reads.estimate` 반환값을 모집단
사전분포로 블렌드한다. `n`·`confidence` 를 제외하므로 `w` 가 비트까지 같고,
난수 소비 횟수도 같다.

- `LOW_READ  a = 0.20` / `HIGH_READ a = 1.00` — READ_USE 와 같은 수준
- `u` 는 조작하지 않는다. production 값(= 개입 없음)이다
- arm 합성 프로필을 쓰지 않는다 — **실제 필드 프로필** 그대로다.
  그래서 개념 다발 교락이 원리적으로 없다 (같은 프로필의 믿음만 바꾼다)

```
ΔR_A = mean regret(LOW_READ, 공격) − mean regret(HIGH_READ, 공격)   > 0 이면 읽기가 이득
```

- 표본: SET_A `940001-940010`, SET_B `950001-950010`, 각 `[:150]`
- 프로필 단위 클러스터 부트스트랩 4000회, 시드 `v7_num_battery.SEED`
- `FLOOR = 0.002` — 묶음 전체에서 동일

### 보조 판정 (돌리기 전에 고정)

```
W0  AUX_INCONCLUSIVE   조작 점검 실패
                       (HIGH_READ 의 r(ftb_true, 믿는 ftb) 가 LOW_READ 보다 크지 않다)
W1  AUX_READ_HELPS     ΔR_A >= FLOOR 이고 95%CI 가 0 배제, SET_A·SET_B 둘 다
W2  AUX_READ_HURTS     ΔR_A <= −FLOOR 이고 95%CI 가 0 배제, SET_A·SET_B 둘 다
W3  AUX_READ_NULL      그 외
```

`n_obs` 6 / 40 분리도 같이 보고한다. 게이트는 아니다.

## D1-3. 사용자 결정 지점 재대응

주 판정(`d_A`)이 교락돼 있으므로 A/B 판단의 1차 근거를 **보조 분석**으로
옮긴다. 이 대응도 돌리기 전에 고정한다.

```
A  stat_read 설계 진입 가능     W1 (공격에서도 읽기 정확도가 EV 개선)
B  채널별 분리 또는 개념 재검토   W2 또는 W3
```

주 판정은 그대로 보고하되, 교락 사실과 함께 읽는다.

## D1-4. 바뀌지 않는 것

`FLOOR`, 게이트 G1~G6, 주 판정 규칙 V0~V3, 격자, `D = 0.28`, 상태 집합,
`qx_ev_fixture.py` 동결 — 전부 그대로다. 주 판정 결과도 그대로 보고한다.

---

# Amendment D2 — D1 의 조작 점검이 무효다 (수치는 이미 봤다)

## D2-0. 공개

D1 의 보조 분석을 돌렸고 `ΔR_A` 수치를 봤다. **`ΔR_A` 와 보조 판정 규칙
`W1~W3` 은 바꾸지 않는다.** 바꾸는 것은 **무효인 조작 점검 하나**다.

## D2-1. 무엇이 틀렸나

D1-2 의 `W0` 이 이렇게 쓰여 있었다.

> `HIGH_READ` 의 `r(ftb_true, 믿는 ftb)` 가 `LOW_READ` 보다 크지 않으면 실패

**이 양은 개입에 대해 불변이다.** R 축 개입은

```
est' = PRIOR·(1 − a) + est·a
```

즉 **양의 아핀 변환**이고, 피어슨 상관은 양의 아핀 변환에 불변이다.
그래서 `a` 가 무엇이든 상관은 정확히 같은 값이 나온다. 실측이 그렇다.

```
SET_A  LOW +0.8688   HIGH +0.8688      (완전 동일)
SET_B  LOW +0.8765   HIGH +0.8765      (부동소수점 잡음으로만 갈렸다)
```

`W0` 은 **원리적으로 통과할 수 없는 검사**였다. 개입이 실패한 것이 아니라
검사가 무의미했다. `READ_USE_SEPARATION` 에서 같은 이유로 상관 대신
**기울기와 sd** 를 쓴 것을 여기서 되풀이하지 못했다.

## D2-2. 고친 조작 점검

불변이 아닌 양으로 바꾼다. 블렌드에서 기울기와 sd 는 `a` 에 **비례**한다.

```
W0'  slope(ftb_true -> 믿는 ftb) 와 sd(믿는 ftb) 가
     HIGH_READ 에서 LOW_READ 보다 크다. 비율이 A_HI/A_LO = 5.0 에
     가까우면(±20%) 개입이 설계대로 작동한 것이다.
```

`A_HI / A_LO = 1.00 / 0.20 = 5.0` 이 이론값이다.

## D2-3. 바뀌지 않는 것

`ΔR_A` 의 정의, `FLOOR = 0.002`, 부트스트랩 절차, 표본 집합,
보조 판정 `W1/W2/W3`, `n_obs` 분리 보고, D1-3 의 A/B 대응 — 전부 그대로다.
`W0` 실패로 인한 `AUX_INCONCLUSIVE` 는 **무효인 검사에서 나온 것이므로
채택하지 않고**, `W0'` 결과로 다시 판정한다.
