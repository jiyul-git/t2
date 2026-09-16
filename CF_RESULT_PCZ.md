# 반사실 결과 — `pcz` 에 `_pen` 을 적용하면 무엇이 바뀌는가

설계 `CF_DESIGN_PCZ.md` (`0fec146`). **예측 C1~C5 를 고치지 않았다.**
`plan.py` 무수정. EV·손익은 재지 않았다.

```
자료   시드 7000-7007, 1,000핸드, make_plan 호출 1,308건
단위   **make_plan 반환 시점의 라벨**
       update_plan 의 뒷 단계(_allowed · refresh · river_fix)를 통과하기 전이다
```

---

## 0. 측정 버그를 한 번 냈다 — 기록한다

첫 실행에서 `wrap` 이 `make_plan` 반환 dict 를 **참조로** 담았다. 그 dict 를
`update_plan` 의 뒷 단계가 그대로 변형하므로, O 만 파이프라인 통과 후
라벨이 되고 반사실 팔은 `make_plan` 원출력이 됐다.

증상은 건전성 검사에 잡혔다 — "분기가 안 갈렸는데 라벨이 다른" 6건이
나왔고, 열어 보니 `_allowed` 가 `semibluff` 를 `showdown` 으로 강등한
것이었다. **패치와 무관했다.**

사본으로 고친 뒤 불일치는 양 팔 모두 **0건**이다. 버그 이전 집계는
폐기했다 (`fix` 커밋에 적었다).

**`TRACE_EQREL_COUNT.md` 의 183 / 36 / 31 과 아래 숫자를 직접 비교하지
마라.** 그쪽은 최종 intent 기준(관측 1,689)이고 이쪽은 `make_plan` 반환
기준(호출 1,308)이다.

---

## 1. 건전성

```
ARM-A   분기 동일 1,195건 중 라벨 불일치 0건
ARM-B   분기 동일 1,171건 중 라벨 불일치 0건
```

---

## 2. 집계

```
팔        pcz진입   465탈락   giveup   semibluff   bluff_2street
O            207       41      543          32              63
ARM-A        100        9      511          40              63
ARM-B         76        6      508          43              63
```

---

## 3. 사전등록 예측 대조

```
C1  진입 건수가 줄어든다. O >= ARM-A >= ARM-B
    207 >= 100 >= 76                                   충족

C2  465 탈락 건수가 줄어든다
    41 → 9 → 6                                         충족

C3  빠져나온 핸드의 다수가 502 로 가서 pot_control 또는 showdown 이
    되고 giveup 총량이 줄어든다
    giveup 543 → 511 → 508.
    ARM-A 에서 giveup 을 벗어난 32건의 행선지는
    showdown 18 · pot_control 10 · semibluff 4 다 (87.5% 가 502 경로)   충족

C4  outs >= 8 인 핸드 중 일부가 468 semibluff 를 새로 받는다 (0 이 아니다)
    ARM-A 8/23 (34.8%)   ARM-B 11/23 (47.8%)           충족

C5  490 bluff_2street 로 가는 것은 거의 없다
    **0건이다.** 세 팔의 bluff_2street 총량도 63 으로 동일하다   충족
```

**C1~C5 전부 충족했다.**

---

## 4. 라벨 전이 — 예측하지 않았던 것이 더 크다

```
ARM-A   O 에서 pcz 진입했다가 빠져나온 110건
    value_2street  → showdown       31
    value_2street  → pot_control    25
    giveup         → showdown       18
    pot_control    → pot_control    15
    giveup         → pot_control    10
    pot_control    → semibluff       4
    giveup         → semibluff       4
    pot_control    → showdown        3

ARM-B   빠져나온 134건
    value_2street  → showdown       39
    value_2street  → pot_control    27
    pot_control    → pot_control    21
    giveup         → showdown       18
    giveup         → pot_control    13
    pot_control    → semibluff       6
    pot_control    → showdown        5
    giveup         → semibluff       4
    value_2street  → semibluff       1
```

### 4-1. 가장 큰 덩어리는 `giveup` 구제가 아니다

```
ARM-A   value_2street 에서 나온 것   56 / 110   (50.9%)
        giveup 에서 나온 것          32 / 110   (29.1%)
        pot_control 에서 나온 것     22 / 110   (20.0%)
```

**이 개입의 최대 효과는 얇은 밸류 강등이다.** 조사의 출발점이었던
`giveup` 은 두 번째다. `pcz` 를 올리면 `eq` 가 그 위에 못 미치는 핸드가
전부 빠지므로, 원래 `458` 을 통과해 `value_2street` 를 받던 핸드들도
같이 빠진다.

**이것이 더 나은 행동이라고 말하지 않는다.** EV 를 재지 않았다.

### 4-2. 빠져나온 핸드 중 `giveup` 이 된 것은 0건이다

전이표에 `→ giveup` 행이 없다. `502` 의 `has_sd = made >= 1 or
eq >= 0.42 + 0.05*mw` 가 전부 참이었다 — 빠져나온 핸드는 정의상
개입 전 `pcz` 이상의 `eq` 를 갖는다.

### 4-3. `pot_control → pot_control` 은 라벨이 안 바뀐 것이다

`439` 안에서도 `457` 로, `502` 에서도 `pot_control` 이 나온다.
**분기는 갈렸지만 라벨은 같다.** 전이 건수에 들어 있으니 "바뀐 것"으로
세지 않는다.

---

## 5. 이 결과가 말하지 않는 것

```
어느 팔이 옳은가 — 가르지 않는다. 계수 선택은 수정 단계의 결정이다
더 나은 행동인가 — EV 를 재지 않았다
made >= 1 게이트를 고치면 어떻게 되는가 — 다른 개입이다 (설계 2-1)
baseline 지문 — 재지 않았다. plan.py 는 무수정이다
최종 행동 — 비교 단위는 make_plan 반환 라벨이고 파이프라인 통과 후가 아니다
```

---

## 6. 재현

```
python3 tools/cf_pcz.py --seeds 7000-7019 --hands 1000
```
