# ⑤ 반사실 Level 1 — 커버리지 확장판

`CF_RESULT_LEVEL1.md` 는 그대로 보존한다. 이 문서는 그 0절이 지적한
소비처 누락을 메운 뒤의 결과다.

```
entries=24 · hpl=12 · start_stack=30000 · 시드 5000–5054 (55개)
포스트플랍 31,236 결정 · 응답 11,758 호출 · 프리플랍 100,195 / 147,387 호출
엔진 오류 0건
```

---

## 1. 보강한 경로

```
aggression → persona.open_pct        SITE 누락이었다 (소비처 22곳 중 하나)
discipline → plan.decide_response    3곳 중 1곳이 빠져 있었다
bluff      → plan.decide_response×2  17곳 중 2곳
```

### `decide_response` 는 CRN 이 공짜가 아니다

`decide_aggression` 은 rng 소비가 **0** 이라 같은 주사위 눈을 그냥 쓸 수
있었다. `decide_response` 는 rng 를 5곳에서 쓰고(`plan.py:724·749·775·
787·806`) 조기 반환이 많아, 축을 바꾸면 분기가 달라져 소비 횟수가
어긋난다.

그래서 **기록·재생**을 넣었다. `RecordRandom` 이 원본 호출이 뽑은 난수를
순서대로 기록하고 `ReplayRandom` 이 개입 팔에 같은 순서로 먹인다.
소비 횟수가 다르거나 기록을 넘어서면 `rng_shifted` 로 분류하고
**정상 집계에서 제외한다.**

실측: `bluff` 에서만 **9건** 발생했고 제외했다. 나머지 축은 0건이다.

---

## 2. 결과

### 포스트플랍 `decide_aggression` — 초판과 동일

```
축                결정      f(1)     f(9)   action flip   방향            |Δ|>0.01
aggression       31,236   0.215 →  0.434      9.2%     ↑16,169 / ↓0      50.8%
discipline       31,236   0.336 →  0.180      4.3%     ↑0 / ↓4,240       13.6%
bluff            31,236   0.246 →  0.295      3.5%     ↑6,100 / ↓0       19.4%
thin_value_turn  31,236   0.271 →  0.278      2.7%     ↑2,960 / ↓0        9.5%
cbet_flop        31,236   0.257 →  0.288      1.0%     ↑2,209 / ↓0        7.1%
potcontrol       31,236   0.275 →  0.275      0.0%     ↑0 / ↓0            0.0%
looseness             0        —        —       —      소비처 없음          —
```

**역방향이 전 축 0건.** 완전 단조다. 이 층은 보강 대상이 아니었으므로
초판과 같은 값이 나온 것이 정상이다.

### 응답 층 `decide_response` — 새로 드러난 경로

```
축                호출      act flip   주요 전환                          shifted
aggression      11,758       5.7%     call→raise×470 · fold→call×180        0
discipline      11,758       1.6%     call→fold×96 · raise→fold×93          0
bluff           11,758       1.4%     fold→raise×163                        9
potcontrol      11,758       0.0%     —                                     0
thin_value_turn 11,758       0.0%     —                                     0
cbet_flop       11,758       0.0%     —                                     0
```

전환 방향이 축 의미와 맞는다 — `discipline` 은 폴드 쪽으로,
`bluff` 는 `fold→raise` 로, `aggression` 은 `call→raise`·`fold→call` 로.

### 프리플랍 — 누락됐던 `aggression → open_pct`

```
축          지표          호출      중앙(1)   중앙(9)   배율     |Δ|>0
looseness   defend_tot   100,195   0.1484   0.3488   2.35×    100%
looseness   open_pct     147,387   0.1663   0.3068   1.84×     86%
aggression  defend_tp    100,195   0.0355   0.0709   2.00×    100%
aggression  open_pct     147,387   0.2133   0.2585   1.21×     86%
```

누락됐던 경로는 **실재하지만 `looseness` 보다 약하다** (1.21× vs 1.84×).

---

## 3. `potcontrol` — 계획 층 축이다

```
POST 0.0%   ·   응답 0.0%   ·   |Δ|>0.01  0.0%
```

**"`potcontrol` 이 행동에 영향이 없다" 로 쓰면 안 된다.** 정확한 진술은:

> **현재 Level 1 execution-layer 에서는 직접적인 효과가 없으며,
> 관측된 행동 연관은 plan-routing 경로를 통해 발생한다.**

근거:

```
CLAUDE.md  "potcontrol 은 빈도 축이 아니라 스위치다.
            확률식 _pc_p 에 축이 안 들어간다"
plan.py    decide_aggression 의 pot_control 분기는
             return max(0.05, min(0.6, 0.18 + 0.035*a))
           → aggr 을 읽지 potcontrol 을 읽지 않는다
④          이 축은 **라우팅 비율**로 쟀고 (ρ +0.466, 통제 후 +0.365)
           라우팅은 make_plan 에서 일어난다 — Level 2 영역이다
```

**이것이 Level 2 를 해야 할 가장 강한 이유다.** 계획 층과 실행 층이
실측으로 완전히 갈린 첫 사례다.

---

## 4. 사전 예측 — 둘 다 틀렸다

`CF_DESIGN.md` 4절에 측정 전 적어둔 것을 **수정하지 않는다.**

```
적어둔 것 ①  aggression 은 통제 후 ρ 가 절반 이하라
            개입 효과가 관측 ρ 보다 작을 것으로 예상
적어둔 것 ②  cbet_flop 은 통제 후 ρ 가 올랐으니
            개입 효과가 관측 ρ 보다 클 것으로 예상
```

사전에 정한 판정 방식(전 축의 두 순서 비교)으로 봤다.

```
축                통제후 ρ(④)   POST flip(⑤)   응답 flip
discipline         -0.811          4.3%          1.6%
looseness          +0.810       (소비처 없음)      —
bluff              +0.512          3.5%          1.4%
thin_value_turn    +0.473          2.7%          0.0%
potcontrol         +0.365          0.0%          0.0%
aggression         +0.338          9.2%          5.7%
cbet_flop          +0.263          1.0%          0.0%
```

```
|통제후 ρ| 순위   discipline > looseness > bluff > thin_value
                > potcontrol > aggression > cbet_flop(7위)

POST flip 순위   aggression > discipline > bluff > thin_value
                > cbet_flop(5위) > potcontrol
```

**① 틀렸다** — `aggression` 이 ρ 6위인데 flip 1위다.
**② 틀렸다** — `cbet_flop` 이 양쪽에서 모두 하위다.

### 이번 실험이 확정한 것

> **관측 연관이 강해진다고 해서 해당 축의 execution-layer 개입효과가
> 커지는 것은 아니다.**

두 순서가 서로 예측하지 못한다. `aggression` 은 ρ 가 작은데 개입이 크고,
`cbet_flop` 은 통제로 ρ 가 올랐는데 개입은 작다.

`cbet_flop` 의 경우 레버 폭(1.6배 vs `discipline` 2.9배)과 도달률
(7.1% vs 13.6%)이 낮은 것이 관련돼 보이지만, **이를 확정적 인과
메커니즘으로 단정하지 않는다.** 지금 고정하는 것은
**관측 결과와 반사실 결과가 분리됐다는 사실**까지다.

---

## 5. 주장의 범위

```
말할 수 있는 것
  동일 상황·동일 실행 조건에서 해당 축만 개입했을 때 행동이 결정론적으로
  변화했으며, 이는 execution-layer causal influence 에 대한 강한
  반사실적 증거다 — 1절의 확장된 커버리지 범위 안에서.

말하지 않는 것
  계획 층의 인과 (Level 2)
  하류 전파 (한 결정의 효과만 격리)
  축 1↔9 는 필드 실재 범위를 넘을 수 있다
  entries=24 / hpl=12 / stack=30000 조건이다
  bluff 는 여전히 make_plan×4 · line_bluff_prior 가 안 덮였다
  aggression 은 make_plan×2 · calldown_need · opp_bet_prob 가 안 덮였다
```

---

## 6. 이번 확장으로 만들어진 구조

```
관측 (④)     축 → 행동 연관
   ↓
Level 1 (⑤)  축 → execution-layer parameter → action
   ↓
Level 2       축 → plan → execution → action        ← 다음
```

`potcontrol` 이 그 차이를 보여줬다. 다음 질문은 이것이다.

> **축이 행동을 직접 조절하는가, 아니면 계획을 바꿔서 행동을 바꾸는가?**

`potcontrol` 은 후자의 강한 후보, `aggression` 은 전자의 강한 후보다.
같은 Level 2 실험에서 비교한다.
