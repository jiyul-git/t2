# EV 결과 — `465` 라벨 플립의 칩 효과

설계 `CF_DESIGN_EV.md`. **예측 V1~V4 를 고치지 않았다.** `plan.py` 무수정.

```
자료   시드 7000-7019, 1,000핸드
모집단 기준 실행에서 465 에 정확히 1회 도달한 핸드  28건
제외   0회 965핸드 · 2회 이상 6핸드   (설계 4절, 측정 전 규칙)
단위   대상 좌석의 핸드 순칩 변화. 분기 전 기여는 두 경로에서 같아 차분에서 소거된다
```

---

## 1. 판정

```
팔        페어   액션 동일   액션 다름   ΔEV≠0   ΔEV 평균   중앙
ARM-S      28        26          2        0       +0.0     +0.0
ARM-R      28        26          2        0       +0.0     +0.0
ARM-D      28        28          0        0       +0.0     +0.0
```

```
V1  액션 동일 페어의 ΔEV≠0                  0건        충족
V2  ΔEV≠0 페어 수 ≤ 플립 건수                0 ≤ 41     충족
V3  fold→call 과 call→fold 가 둘 다 나온다   **불충족**
V4  ΔEV 부호 비예측                          해당 없음 (전부 0)
```

### 1-1. `V3` 는 틀렸다 — 그대로 남긴다

**응답 전환이 한 건도 없었다.** `fold→call` 도 `call→fold` 도 0건이다.
관측된 유일한 갈림은 `bet→bet`(같은 행동, 다른 금액) 2건이다.

설계가 기대한 기전(`plan.py:812` 의 raw need ↔ `834` 의 `need_seen`)은
**발동할 자리가 없었다.** 28쌍에서 대상 좌석이 분기 이후 벳에 직면해
새로 판정한 경우가 없었다.

---

## 2. 이 표본에서 라벨 플립은 칩을 바꾸지 않았다

**28쌍 전부 `ΔEV = 0` 이다. 세 팔 모두.**

**이것을 "made 라벨 플립은 EV 효과가 없다" 로 확장하지 않는다.**
정확한 진술은 이것이다.

> 사전등록한 1,000핸드에서, 귀속 가능한 28쌍의 `ΔEV` 가 전부 0 이었다.

표본이 28쌍이다. 1,000핸드 중 965핸드가 `465` 에 한 번도 도달하지 않았다.
**검정력을 주장하지 않는다.**

---

## 3. `bet→bet` 2건의 기전 — 추적 완료

추측을 두 번 했고 둘 다 코드에서 틀렸다. 실제 두 핸드를 재생해 추적했다.

```
1fab5c3e  seat 8  seed 7004
  기준   flop giveup → turn giveup → river  **value_2street**   river bet 1600
         why  river: 포기했으나 강도 상승(rel 0.98, made 2) → value_2street
  ARM-S  flop showdown → turn showdown → river  **value_3street**  river bet 1700
         why  river: 강도 상승(rel 0.98, made 2) → 밸류 전환

a65f7f3d  seat 5  seed 7005
  기준   flop giveup → turn  **value_2street**  turn bet 2300
  ARM-S  flop showdown → turn  **value_3street**  turn bet 2600
```

### 3-1. 원인은 `refresh` 의 승격 사다리가 둘로 갈리는 것이다

```
plan.py:1795   elif old == 'giveup' and (rel >= 0.55 or made >= 2):
                   st['plan'] = 'value_2street' if (rel >= 0.72 or made >= 3) else 'showdown'

plan.py:1803   elif old in ('pot_control', 'block', 'showdown') and (rel >= 0.70 or …):
                   st['plan'] = 'value_3street' if rel >= 0.88 else 'value_2street'
```

**문턱도 도착지도 다르다.**

```
giveup   에서 출발   문턱 rel 0.55   갈림 rel 0.72   도착 {showdown, value_2street}
showdown 에서 출발   문턱 rel 0.70   갈림 rel 0.88   도착 {value_2street, value_3street}
```

두 사례 모두 `rel` 0.97~0.98 이라 한쪽은 `value_2street`, 다른 쪽은
`value_3street` 가 됐다. **`SIZING` 이 다르므로 벳 금액이 달라진다.**

### 3-2. 구조적 귀결

> **단일 `refresh` 단계에서 `giveup` 은 `value_3street` 로 승격되지 못한다.**
> 같은 핸드가 `showdown` 이었으면 된다. 도착지 집합 자체가 다르다.

`giveup` → `showdown` 을 거쳐 다음 스트리트에 `value_3street` 로 가는
두 단계 경로는 남아 있다. **한 단계에서 불가능하다는 뜻이다.**

`plan.py:1811-1822` 의 주석이 이 사다리의 `made` 항이 죽어 있다고 이미
적어 두었다(known issue E). 이번 두 사례는 그 사다리 위에서 갈렸다.

### 3-3. 그런데 칩은 그대로였다

두 건 모두 최종 순칩이 같았다. **금액 차이가 결과로 이어지지 않은 이유는
확인하지 않았다.** 표본 2건이라 추적하지 않았다.

---

## 4. 설계 진술 하나를 좁힌다

설계 1절은 "라벨 플립은 베팅을 **바꾸지 못한다**. 효과는 벳에 직면했을
때의 응답과 `refresh` 의 구제 경로로만 흐른다" 였다.

전반부만 떼어 읽으면 틀린다. **정확히는 이렇다.**

```
분기 스트리트    decide_aggression(857)이 giveup·showdown 을 같은 분기로 다루고
                 SIZING · BUDGET 도 같으므로 베팅이 바뀌지 않는다
후속 스트리트    refresh 의 승격 사다리가 갈려 **베팅 금액이 바뀐다** ← 실측
```

설계 문장은 `refresh` 경로를 이미 포함했으므로 고치지 않는다. 다만
"베팅을 바꾸지 못한다" 를 단독으로 인용하지 않는다.

---

## 5. 하지 않은 것

```
팔 간 우열을 가르지 않았다
플립 건수(41 · 33 · 11)를 EV 로 읽지 않았다
pcz 개입과 같이 켜지 않았다
유의성 문턱을 만들지 않았다
사후 조건으로 decision state 를 넣거나 빼지 않았다
```

---

## 6. 재현

```
python3 tools/cf_ev.py --seeds 7000-7019 --hands 1000
```

액션이 달라진 페어의 원자료는 도구가 직접 찍는다 — 기전을 추측하지 않기
위해서다.
