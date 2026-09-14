# 배선 추적 — 성향이 계획 라벨까지 가는가

읽기 전용 추적이다. `plan.py` 를 수정하지 않았다.
대상: `make_plan`(plan.py:256-550) — 플랍에서 계획 라벨을 정하는 유일한 지점.

측정: `review_2.jsonl` 234핸드, 플랍 계획 185건.
재현: `python3 tools/field_audit.py review_2.jsonl --chain`

---

## 결론 먼저

```
플랍 계획 라벨 185건이 어디서 정해졌나

  성향이 확률·문턱에 들어가는 갈림길      53건  28.6%   ●
  게이트만 있는 갈림길(있냐 없냐)          41건  22.2%   ◐
  성향이 전혀 안 들어가는 갈림길           91건  49.2%   ○
```

**절반이 성향을 한 번도 읽지 않는 분기에서 나온다.**
그리고 그 절반의 대부분은 사다리 맨 끝 `else` 블록이다.

`성향 → 계획 라벨 rho +0.04` 는 배선이 미묘하게 약한 게 아니라,
**결정의 절반이 배선 자체를 지나가지 않기 때문**이다.

---

## 1. 사다리 구조

`make_plan` 은 `eq`(올인 에쿼티) 로 6단 사다리를 탄다.

```
eq >= v3    → trap  |  value_3street
eq >= v2    → value_2street  |  value_3street
eq >= pcz   → block | pot_control | value_2street(얇은) | showdown/giveup
outs >= 8   → semibluff
eq < 0.42   → bluff_2street
else        → pot_control | showdown | giveup
```

**사다리를 타는 값(`eq`)에는 성향이 없다.** `_eq_vs()` 는 홀카드·보드·
상대 레인지만 본다. 어느 칸에 떨어질지는 프로필과 무관하게 정해진다.

성향은 **같은 칸 안에서 무엇을 고를지**에만 들어간다.

---

## 2. 실측 — 각 칸이 얼마나 쓰였나 (플랍 185건)

| 갈림길 | 건수 | 비율 | 성향이 들어가는 자리 | |
|---|---|---|---|---|
| **6 → giveup** | **71** | **38.4%** | 없음 | ○ |
| 6 → pot_control | 33 | 17.8% | `sk('potcontrol')>=1` 게이트, 확률 **0.72 고정** | ◐ |
| 6 → showdown | 20 | 10.8% | 없음 | ○ |
| 5 → bluff_2street | 15 | 8.1% | `sk('bluff')`, `bluff_ok` | ● |
| 3 → pot_control/얇은밸류 | 14 | 7.6% | `pc`, `sk('range_merge')` | ● |
| 1 → value_3street | 10 | 5.4% | `trap_judgment` 에서 떨어진 쪽 | ● |
| 3 → showdown/giveup | 8 | 4.3% | 확률 없음, `rel` 만 | ◐ |
| 2 → value_3street | 4 | 2.2% | `_p2` 반대편 | ● |
| 1 → trap | 4 | 2.2% | `trap_judgment(profile,...)` | ● |
| 2 → value_2street | 2 | 1.1% | `sk('stackoff')`, `sk('thin_value')` | ● |
| 3 → block | 2 | 1.1% | `profile['aggr']`, `profile['bluff']` | ● |
| 4 → semibluff | 2 | 1.1% | `sk('semibluff')` | ● |

**마지막 `else` 블록 하나가 124건, 전체의 67%다.**

```python
has_sd = made >= 1 or eq >= 0.42 + 0.05*mw          # 프로필 없음
if has_sd and sk('potcontrol') >= 1 and rng.random() < 0.72:
    plan = 'pot_control'
elif has_sd:
    plan = 'showdown'
else:
    plan = 'giveup'
```

이 블록에서 프로필이 닿는 곳은 **`sk('potcontrol') >= 1` 게이트 하나**다.
`0.72` 는 상수다. `has_sd` 는 `made` 와 `eq` 만 본다.

---

## 3. 게이트는 거의 모두를 통과시킨다

생성기 표본 4,000명 (entries 100, buyin 1.0):

| 게이트 | 통과율 |
|---|---|
| `sk('semibluff') >= 0.4` | **99.0%** |
| `sk('potcontrol') >= 1` | **85.8%** |
| `sk('bluff') >= 1` | 78.0% |
| `sk('blockbet') >= 1` | 71.4% |

`sk()` 는 `PS.sk/3.33` 이라 `>= 1` 은 원래 개념 3.33 이상을 뜻한다.
개념 분포가 5 근처에 몰려 있어(25%~75% 가 3.6~6.5) 이 문턱은 사실상
바닥이다. **게이트는 개성을 만들지 못한다.**

---

## 4. 성향이 들어가는 자리에서는 폭이 크다

통과한 사람들 안에서 (5% ~ 95% 구간):

| 항목 | 5% | 중앙 | 95% | 폭 |
|---|---|---|---|---|
| `semibluff` 확률 `0.25+0.24·sk` | 0.44 | 0.62 | 0.82 | 0.38 |
| `bluff` 배수 `0.45+0.28·sk` | 0.75 | 0.89 | 1.11 | 0.35 |
| `bluff_ok` 의 `profile['bluff']/10` | 0.19 | 0.47 | 0.76 | **0.57** |
| `pc` (icm/gamble/aggr) | 0.24 | 0.51 | 0.79 | **0.55** |
| `_p2` 배수 (stackoff) | 0.59 | 0.92 | 1.22 | **0.63** |
| `block_p` (aggr, bluff) | 0.07 | 0.23 | 0.40 | 0.33 |
| `_pc_p` 배수 (range_merge) | 0.41 | 0.71 | 1.00 | **0.59** |

**배선이 약한 게 아니다.** 닿는 자리에서는 두 배 이상 벌어진다.
문제는 그 자리가 전체의 28.6% 밖에 안 쓰인다는 것이다.

---

## 5. 문턱(v3/v2/pcz)으로 가는 두 경로 — 둘 다 거의 죽어 있다

사다리의 칸 경계를 옮길 수 있으면 성향이 사다리 자체에 들어간다.
경로는 둘뿐이다.

### (1) `PS.read_opponent(profile, opp_est)` → v3/v2/pcz 이동

```python
rd = PS.read_opponent(profile, opp_est)
if rd['w'] > 0:
    v3 += rd['w'] * 0.55 * sg ;  v2 += ... ;  pcz += ...
```

`opp_est` 가 없으면 `w = 0` 이라 이동이 0 이다. 상대 표본이 쌓여야 작동한다.
실측(1차 보고서 4절): 이 경로가 실제로 만든 포기 문턱 이동은
**0.29 ~ 0.32, 폭 0.03** 이었다.

### (2) `perceived_rel(profile, ...)` → `_pen` → v3/v2 이동

`rel` 을 `PS.bias` 세 축으로 흔든다. 그런데 **bias 중앙값이 세 축 모두
0.00 이다.**

| 축 | bias 중앙 | bias 95% | rel 보정 최대 |
|---|---|---|---|
| `overpair_love` | 0.00 | 0.46 | +0.064 |
| `draw_love` | 0.00 | 0.41 | +0.041 |
| `sticky` | 0.00 | 0.35 | +0.028 |

`max(0.0, PS.bias(...))` 로 음수를 잘라내므로 **필드의 절반은 `rel` 보정이
정확히 0** 이다. 나머지 절반도 상위 5%에서 +0.06 수준이고, 조건부다
(`overpair_love` 는 `made>=1 & rel>=0.45`, `draw_love` 는 `outs>=4`,
`sticky` 는 `rel<0.45` 일 때만).

**두 경로 다 사다리 칸 경계를 의미 있게 못 옮긴다.**

---

## 6. 축별 판정

| 축 | 어디서 읽히나 | 판정 |
|---|---|---|
| `aggression` (temper) | `block_p` 한 곳, `pc` 안에 `(10-aggr)` | **거의 미사용** — 라벨 사다리에서 `block`(1.1%)에만 직접 들어간다 |
| `discipline` | `make_plan` 안에 **없음**. `decide_aggression` 의 이탈 확률에만 | **라벨에 미사용** |
| `looseness` | `make_plan` 안에 **없음** | **라벨에 미사용** |
| `bluff` (concept) | `bluff_ok`, 게이트, 배수 | **직접 배선** — 다만 해당 칸이 8.1% |
| `semibluff` | 게이트 + 확률 | **직접 배선** — 게이트가 99% 통과, 칸이 1.1% |
| `potcontrol` | 게이트만 (확률은 0.72 고정) | **게이트만** — 17.8% 에서 쓰이나 86% 통과 |
| `range_merge` | `_pc_p` 배수 | 직접 배선, 7.6% |
| `stackoff`/`thin_value` | `_p2` 배수 | 직접 배선, 3.3% |
| `trap`/`checkraise` | `trap_judgment` | 직접 배선, 7.6% (trap + 그 반대편) |
| `board_texture`/`blocker`/`spr`/`outs` | 지각 보정(`dang`,`blk`,`s`,`outs`) | **간접** — 라벨을 직접 안 고르고 입력값을 흔든다 |
| `icm`/`gamble` | `pc` | 간접, 7.6% |
| bias 3축 | `perceived_rel` | **참조하지만 영향 거의 없음** (중앙 0.00) |

---

## 7. 이게 설계인가 결함인가

**설계로 보이는 부분**: 사다리를 `eq` 로 타는 것 자체는 합리적이다.
핸드 강도가 계획의 뼈대인 건 포커적으로 맞다.

**결함으로 보이는 부분**은 셋이다.

1. **마지막 `else` 블록이 67%를 먹는데 그 안에 성향이 없다.**
   `has_sd` 는 `made` 와 `eq` 만 보고, 분기 확률은 상수 `0.72` 다.
   "같은 상황에서 사람마다 다르게 판단한다"가 여기서 일어나지 않는다.

2. **게이트가 개성을 만들도록 설계됐는데 문턱이 너무 낮다.**
   개념 3.33 은 필드의 78~99%가 넘는다. `sk(...) >= 1` 은 거의
   `if True` 다.

3. **`perceived_rel` 이 사실상 꺼져 있다.** bias 중앙값 0.00.
   docstring 은 "피시도 레귤러와 똑같이 자기 핸드 강도를 안다는 건
   사실이 아니다"라고 쓰여 있는데, 실제로는 절반이 정확히 안다.

---

## 8. 그래서 개념을 추가할 이유는 없다

`aggression` 은 이미 있고 `block_p` 한 줄에서만 쓰인다.
`pf_defend` 는 이미 있고 BB 방어를 +4%p 밖에 못 움직인다.
`bluff`/`semibluff` 는 제대로 배선돼 있는데 그 분기가 9% 밖에 안 쓰인다.

**없어서 안 되는 게 아니라, 있는데 안 닿는다.**

---

## 아직 안 본 것

- `decide_response`(plan.py:676) — 상대 벳에 대한 응답. 실측에서 성향
  단조성이 없었다. 라벨 경로와 별개로 추적해야 한다
- `refresh`(plan.py:1633) / `update_plan`(plan.py:1423) — 턴·리버 계획의
  37%가 `make_plan` 사다리가 아니라 이쪽에서 나온다. 미추적
- `preflop.defend_decision` — BB 방어. 3순위
- 이 추적은 **어디서 읽히는가**까지다. 읽힌 값이 최종 라벨을 실제로
  뒤집었는지는 반사실(counterfactual) 로만 확정할 수 있다.
  같은 시드로 프로필만 바꿔 돌리는 evaluator 가 필요하다
