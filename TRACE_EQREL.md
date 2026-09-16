# eq ↔ rel 모순 — 코드 전수 추적

**원인 규명이다. 수정하지 않았다** (작업 원칙 1).
기준 커밋 `8bc42b3`. 행번호는 이 시점 기준이다.
그림: `docs/EQREL_V1.png` (`tools/draw_eqrel.py`)

---

## 1. 세 값의 정의와 계산 위치

```
eq          plan.py:268   _eq_vs(...) → bot.equity_vs_combos
            남은 보드를 끝까지 돌린 승률. **미래 카드 전개를 포함한다**
            레인지 6콤보 미만이면 비율 근사로 물러난다 (plan.py:170-174)

eq_current  plan.py:271   _eq_current(...)  **기록 전용**
            판단에 쓰지 않는다. eq_delta 로만 남는다 (plan.py:519)

rel_true    plan.py:311   relative_strength(...)   plan.py:29
            bot.eval7(hero + board) — **지금 보드에서만** 평가한다
            보드가 3장 미만이면 0.5 고정

rel         plan.py:312   perceived_rel(profile, rel_true, ...)   plan.py:72
            overpair_love · draw_love · sticky 로 편향을 얹는다
            **이 값이 plan_state['rel'] 로 저장된다**
```

`refresh` 경로에도 같은 쌍이 있다 — `plan.py:1698-1699` (`sims=300`).

---

## 2. 사용처 분류

### 2-1. 진입 조건 — 전부 `eq`

```
plan.py:403   eq >= v3     → trap / value_3street
plan.py:420   eq >= v2     → value_2street / value_3street
plan.py:439   eq >= pcz    → (내부 심사로)
plan.py:490   eq <  0.42   → bluff_2street
plan.py:503   has_sd = made >= 1 or eq >= 0.42 + 0.05*mw
```

### 2-2. 문턱 조정 — `rel` 이 **일부에만** 들어간다

```
plan.py:337-339   v3 = 0.80+0.06*mw   v2 = 0.66+0.07*mw   pcz = 0.50+0.06*mw
plan.py:354-356   상대 읽기 보정 — v3 · v2 · pcz  **셋 다**
plan.py:381-394   rel 페널티      — v3 · v2  **만**
```

**`pcz` 에는 `rel` 페널티가 닿지 않는다.** 이것이 모순의 발생 지점이다.

### 2-3. 내부 조건 — `eq >= pcz` 로 들어온 뒤 전부 `rel`

```
plan.py:442   0.25 <= rel <= 0.80               → block
plan.py:458   rel >= max(0.28, 0.52-0.080*_mg) and made >= 1  → value_2street
plan.py:465   else → showdown if made >= 1 else giveup
```

`465` 가 `CLAUDE.md` 의 "402줄 폴백" 이다. **행번호는 그 시점의 것이고
현재는 465 다.** 라벨을 바꾸지 않고 여기 기록만 남긴다.

### 2-4. 최종 행동 결정

```
rel   decide_aggression(838)  decide_size(953)  cbet_freq(1169)  overbet_frac(1113)
eq    decide_response(695)    — 797 · 800 · 816 · 834
```

---

## 3. 모순 경로 — 진입은 미래 포함 `eq`, 내부 심사는 현재 보드만

**"eq 로 들어와 rel 로 죽는다" 는 표현은 폐기한다.** 1,000핸드 집계에서
다수 사례의 직접 병목은 `rel` 이 아니라 `made` 였다
(`TRACE_EQREL_COUNT.md` 2절). 정확한 진술은 이것이다.

```
진입        eq >= pcz                      미래 카드 전개를 포함한 값 하나
   ↓
내부 심사    rel 조건  AND  made >= 1       둘 다 현재 보드만 보는 값
   ↓
465 else    showdown if made >= 1 else giveup
```

`made` 도 `rel` 과 같은 성질이다.

```
eq    plan.py:268   _eq_vs → equity_vs_combos     남은 보드를 끝까지 돌린다
rel   plan.py:29    bot.eval7(hero + board)       지금 보드만
made  plan.py:310   bot.made_strength(hero, board) 지금 보드만
```

### 3-1. 문턱 비대칭

`rel <= 0.45` 이면 `_pen = 1.0` 이다 (`plan.py:381-382`). 헤즈업(mw=0)·
상대 읽기 없음 기준으로 문턱은 이렇게 된다.

```
v3  = 0.80 + 0.30 = 1.10     eq <= 1 이므로 도달 불가
v2  = 0.66 + 0.22 = 0.88
pcz = 0.50                    **rel 페널티가 닿지 않는다**
```

`pcz` 만 `rel` 을 반영하지 않으므로, `rel` 이 낮아도 `eq` 만 높으면
`439` 로 진입한다. 진입한 뒤에는 현재 보드만 보는 두 값이 심사한다.

**`[0.50, 0.88)` 을 대상 집합의 정의로 쓰지 마라.** 이 경계는 헤즈업·
무리딩 유도값이고, `street_gap` 이 음수면 `pcz` 가 0.50 밑으로 내려간다
(`plan.py:356`). 실측 giveup 의 `eq` 최소가 0.448 이다. **영향 범위를 잴
때는 고정 구간이 아니라 실제 코드 조건으로 집합을 정의한다.**

### 3-2. 세미블러프 선점은 같은 비대칭이다

`semibluff` 분기(`plan.py:468`)는 `elif` 체인에서 `eq >= pcz` **아래**에
있다. 그래서 `pcz` 로 진입한 핸드는 `outs >= 8` 이어도 `468` 에 도달하지
못한다.

```
구조적 사실   eq >= pcz 가 먼저 성립하면 semibluff 분기는 평가되지 않는다
아직 아님     그래서 더 나쁜 행동·EV 가 났는지는 **재지 않았다**
```

실측 규모는 `TRACE_EQREL_COUNT.md` 3절이다 — `outs >= 8` 인 115건 중
21건(18.3%)이 이 경로로 세미블러프 심사를 받지 못했다.

## 4. h18 과 코드 경로

```
h18   flop   eq .586   eq_current .000   eq_delta +.586   outs 20   rel .02   made 0
```

```
439   eq .586 >= pcz .50                      →  진입
442   0.25 <= rel 조건 — rel .02 < 0.25       →  탈락
458   rel >= max(0.28, …) and made >= 1       →  탈락 (rel .02, made 0)
465   else → made 0 이므로 giveup             →  giveup
468   semibluff — elif 체인이라 도달하지 않는다
```

**기록된 값에서 분기를 따라간 것이고 재실행으로 확인한 것은 아니다.**
`457` 의 `pot_control` 은 확률 분기라 발동하지 않았음을 결과(giveup)로
역산했다.

### 4-1. `465` 의 도입 의도와 실제 대상

주석(`plan.py:462-464`)은 대상을 "rel 0.0 에 made 0 인 완전 미스" 라고
적었다. **완전 미스는 `eq >= pcz` 를 통과하지 못해 여기 도달하지 못한다.**
실제로 도달하는 것은 두 부류다.

```
rel 0.5~0.7  현재 이기고 있는데 문턱 max(0.28, …) 을 못 넘은 핸드
드로우       rel ≈ 0 인데 eq 가 미래 지분으로 0.50 을 넘은 핸드   ← h18
```

1,000핸드 실측에서 이 분기 발동은 22건(전체 1.8%)이고 rel 0.5~0.7 이
14건, 드로우가 5건이었다 (`CLAUDE.md` 기록). **이번에 새로 재지 않았다.**

---

## 5. 같이 나온 것 — `decide_response` 의 rel 이 두 개다

```
plan.py:707   rel_ps = plan_state.get('rel', 0.5)     ← 인지 rel (perceived_rel 통과)
plan.py:712   rel = relative_strength(hero, board, opp_range)   ← 날것 rel
```

같은 함수 안에서 두 값이 공존한다. `712` 는 `made_now >= 5` 인 몬스터
분기에서만 쓰이지만, **인지 편향을 거친 값과 안 거친 값이 한 함수에
섞여 있다.** 별도 항목으로 기록만 한다 — 이번 추적의 대상이 아니다.

---

## 6. 확정된 것과 확정되지 않은 것

```
확정   진입 심사는 eq 하나, pcz 내부 심사는 rel AND made 다 (2-1 · 2-3)
확정   rel 페널티가 v3 · v2 에만 들어가고 pcz 에는 안 들어간다 (2-2)
확정   실측 다수 사례의 병목은 rel 이 아니라 made 다 (COUNT 2절)
확정   semibluff 분기가 pcz 아래에 있어 진입한 핸드는 도달 불가다 (3-2)
확정   h18 이 이 경로를 탄다 — rel · made 둘 다 탈락이다 (4)
확정   진입 건수 183 / 1,689, 465 탈락 36, 최종 giveup 31 (COUNT 1절)

미확정  이 구조가 실제로 손해를 냈는가 — EV 를 재지 않았다
미확정  pcz 에 rel 페널티를 넣는 것이 옳은 수정인가 — 수정 단계의 질문이다
미확정  made >= 1 게이트를 푸는 것이 옳은가 — 같다
폐기    "eq 로 들어와 rel 로 giveup" 이라는 표현 (3절)
폐기    eq ∈ [0.50, 0.88) 을 대상 집합의 정의로 쓰는 것 (3-1)
```

**수정안을 여기서 만들지 않는다.** 작업 원칙 1 에 따라, 수정에 들어갈
때는 먼저 반사실 evaluator 로 영향 범위를 재고 별도 브랜치에서 한다.
그리고 원칙 2 에 따라 새 임계값을 발명하지 않는다 — `_pen` 과
`0.30 / 0.22` 는 이미 코드에 있는 값이다.

---

## 7. 정정 이력

초판(`c4ee28e`)은 이 경로를 "`442`·`458` 에서 `rel` 로 탈락" 이라고 적었다.
1,000핸드 집계에서 `465` 로 온 36건 중 25건이 `rel >= 0.52` 라 `458` 의
`rel` 문턱을 넘었고, 막은 것은 `made >= 1` 이었다.

**3절·6절 본문을 정정했다.** 초판 표현은 폐기하고 남기지 않는다.
숫자 근거는 `TRACE_EQREL_COUNT.md` 다.
