# ⑥ 설계 — 축별 서열은 무엇을 의미하는가

> **측정 완료. 결과는 `CF_RESULT_ORDER.md` 에 있다.**
> 다섯 후보 전부 "단독으로는 서열을 설명하지 못한다" 로 닫혔다.

아래는 그 설계다. H5-B 설계(4-9)는 측정 전 `6416d98` 로 고정했고 이후
수정하지 않았다.

---

## 0. 출발점

Level 1 과 Level 2 에서 축별 서열이 같게 나왔다.

```
L1 POST flip   aggression 9.2 > discipline 4.3 > bluff 3.5 > tvt 2.7 > cbet 1.0 > potcontrol 0.0
L2 D           aggression 3.5 > discipline 1.8 > bluff 1.3 > tvt 1.1 > cbet 0.4 > potcontrol 0.0
```

**확인된 것은 서열의 재현이다.** 원인의 동일성도, 효과 크기의 동일성도
아니다. 두 층은 개입 지점·관측량·분모가 전부 다르다.

### 이 단계에서 쓰면 안 되는 문장

```
"aggression 이 가장 중요한 축이다"
"L2 D 가 L1 flip 의 40% 를 포착한다"        (비율 0.37~0.42 는 해석 대상이 아니다)
"D = 실행층, M = 계획층"                    (5-1·5-2 로 정정됨)
```

현재의 정확한 모델은 이것이다.

> D 와 M 모두 서로 다른 층의 계산과 일부 구조적으로 연결되어 있다.
> 그러나 실제로 최종 `plan` 을 변경하는지와 최종 `act` 를 변경하는지는
> **별개의 관측 문제**다.

---

## 1. 먼저 분리할 것 — 두 층이 무엇을 재고 있는가

서열을 해석하기 전에 표로 고정한다. 아직 채우지 않은 칸은 코드를 읽어
채운다. **통계로 추정하지 않는다.**

| | Level 1 | Level 2 D |
|---|---|---|
| 개입 지점 | 실행층 함수 인자 | 실행층 함수 인자 (동일 집합) |
| 재실행 범위 | 재실행 없음. 기록된 roll 과 반사실 `p` 로 직접 계산 | `update_plan` 전체 재실행 |
| 관측량 | `decide_aggression` 의 행동 flip | `update_plan` 이 낸 `intents[street].act` flip |
| 분모 | 포스트플랍 결정 31,189 (`CF_RESULT_LEVEL1.md`) | `update_plan` 호출 × 2 = 74,848 |
| 분모에 들어가는 것 | 결정이 일어난 자리만 | 계획을 세운 모든 자리 |
| 난수 | 기록된 roll 재사용 (정렬 100%) | 기록·재생, 정렬 검사 통과분만 |

Level 2 의 분모에는 행동 결정이 일어나지 않는 자리가 섞여 있다.
**분모 차이가 비율 0.37~0.42 를 설명할 수 있는 후보인지 검증한다.**
"분모 차이가 설명한다" 고 쓰지 않는다 — 아직 확인되지 않았다.

**그리고 분모를 맞추는 것 자체가 목적이 아니다.** 동일한 action-decision
subset 을 찾아내도 "이제 L1 과 L2 가 같은 것을 측정한다" 가 되지는 않는다.
L2 는 여전히 `update_plan` 재실행이라는 경로를 통과한다. 분모 효과와 경로
효과는 별개이고, 3-1 은 그 둘을 분리하기 위한 것이다.

---

## 2. 서열이 재현되는 이유 — 경쟁 가설

축별 서열이 나오는 경로는 여럿이다. 하나로 단정하기 전에 전부 적는다.

```
H1  도달 범위     축이 닿는 분기의 개수와 위치
H2  기저 빈도     그 분기가 애초에 얼마나 자주 실행되는가
H3  계수 크기     p 식에서 축의 기울기
H4  게이트 위치   포화·절단으로 축의 가동 구간이 잘리는가
H5  개입 크기     1↔9 스왑이 축마다 실제로 같은 크기의 변화인가
```

**H1·H3·H4 는 코드 정적 분석으로 계산 가능한 후보다.** H2 의 실제 발생
빈도는 **기존 archive 의 관측 로그로 계산 가능한지 먼저 확인한다.** 기존
자료로 충분하지 않을 경우에만 추가 시뮬레이션·계측을 고려한다.
**"H2 는 시뮬레이션이 필요하다" 고 전제하지 않는다.**

**H5 가 가장 위험하다.** 1↔9 는 축의 정의역 양 끝이지 같은 크기의 개입이
아니다. `persona.bias` 를 거치는 축(`discipline`·`looseness`)은
`max(0.0, ...)` 클램프로 정의역 절반이 0 이고 (CLAUDE.md 기존 기록),
`aggression` 은 `aggro + gauss(0, 0.8)` 로 고유 분산이 0.107 뿐이다.

**그러나 sd 로 정규화하면 끝나는 것이 아니다.** 실제 효과는 필드 sd 하나로
정해지지 않는다. 다음 변환을 전부 거친다.

```
입력 변화량 → p 식 → gate/clamp → downstream branch → action
```

그래서 H5 는 둘로 나눈다.

```
H5-A  입력공간 정규화   1↔9 가 실제 생성되는 필드에서 몇 sd 의 차이인가
H5-B  함수공간 정규화   그 필드 차이가 최종 p 또는 관련 decision quantity 를
                       실제로 얼마나 변화시키는가
```

**H5-A 만 하고 "그러므로 `aggression` 의 raw flip 이 큰 것은 입력 분산
때문이다" 라고 말하지 않는다.** 그것도 과한 결론이다.

---

## 3. 측정하지 않고 먼저 답할 수 있는 것

순서대로 한다. 앞 단계가 서열을 설명해버리면 뒤 단계는 필요 없다.

### 3-1. 분모 분해 — 세 단계로 내려간다

> **수행 완료.** 결과는 `CF_RESULT_NORM.md` 에 있다. 구조도는
> `docs/ARCH_V1.png`(생성: `tools/draw_arch.py`).

단순한 분모 비교로 끝내지 않는다. **각 단계의 N 과 flip rate 를 따로
기록한다.**

```
①  L2 전체                          N = 74,848      flip rate = ?
②  ① 중 실제 action decision 에      N = ?           flip rate = ?
    도달한 subset
③  ② 중 L1 과 대응 가능한             N = ?           flip rate = ?
    동일 decision unit
```

**①→② 가 분모 효과, ②→③ 과 ③ vs L1 이 경로 효과다.** 세 개를 같이
봐야 0.37~0.42 가 분모 차이 때문인지 판단할 수 있다. ③ 이 L1 의 31,189 와
맞아도 L2 는 `update_plan` 재실행 경로를 통과한 값이므로 **"같은 것을
측정했다" 가 되지는 않는다.**

### 3-2 이후

```
3-2  도달 범위     tools/axis_dataflow.py 로 축별 분기 수를 센다 (H1)
                  이미 있는 도구다. 새로 만들지 않는다
3-3  계수 크기     각 축이 들어가는 p 식의 기울기를 소스에서 읽는다 (H3)
                  CLAUDE.md 에 이미 일부 기록돼 있다 — sk() 0~3 스케일,
                  potcontrol 은 기울기 0 인 스위치, bias 클램프
3-4  기저 빈도     H2 를 기존 archive 의 관측 로그로 낼 수 있는지 먼저 본다
                  낼 수 없을 때만 추가 계측을 고려한다
3-5  입력 정규화   persona 로 필드를 생성해 축별 실재 sd 를 잰다 (H5-A)
                  1↔9 가 sd 몇 배에 해당하는지 환산한다
3-6  함수 정규화   그 sd 차이가 p·decision quantity 를 얼마나 바꾸는지 잰다
                  (H5-B). 3-5 만으로 원인을 확정하지 않는다
```

**3-5·3-6 을 하면 서열이 바뀔 수 있다.** 바뀌면 그대로 보고한다.
**Level 1·2 의 숫자는 어느 단계에서도 수정하지 않는다** — 그 실험들은
"1↔9 를 줬을 때" 를 정확히 잰 것이고, 정규화는 별개 질문이다.

### 이 단계에서 먼저 할 일

**새 측정을 설계하기 전에, 이미 가진 것으로 무엇을 확정할 수 있는지부터
확인한다.** `tools/axis_dataflow.py`, 기존 archive, 기존 로그를 실제로
뒤진다. → **4절에서 수행했다.** 3-2~3-6 중 어디가 확정됐고 어디가 추가
계측을 요구하는지는 4-6 의 표를 본다.

---

## 4. 기존 자료 재고 조사 결과 (2026-09-16)

**이번 조사는 기존 자료의 정보량을 확인한 것이며 새로운 측정 결과가 아니다.**
시뮬레이션·사전등록을 하지 않았고 `plan.py` 도 읽기만 했다.

조사 대상: `tools/axis_dataflow.py`, `/tmp/bl2/collected.jsonl`(4,000핸드),
저장소의 `review_*`·`hand_archive2*`·`bak_*`, `plan.py`, `persona.py`.

### 4-1. 기존 자료로 확정된 것

**H2 기저 빈도 — 기존 archive 로 산출 가능.** `collected.jsonl` 에서
`(hand_no, seat, board, street)` 중복 제거 후 포스트플랍 intent 7,064건.
`plan` 라벨과 `trace.why` 로 분기 실행 빈도가 그대로 나온다. 추가 측정
불필요.

```
plan 라벨                             aggression 분기 why
  giveup         2540  36.0%           포기 계획 + 이니셔티브 없음 → 체크   2317
  pot_control    1208  17.1%           밸류 계획 실행(N%)                  1949
  value_3street  1031  14.6%           DEVIATE:포기 계획이나 지속벳(N%)    1055
  value_2street   885  12.5%           팟컨트롤 → 대부분 체크               905
  showdown        832  11.8%           블러프 계획 실행(N%)                 428
  bluff_2street   280   4.0%           함정 계획 → 체크                     105
  semibluff       146   2.1%         response 판정 1,144건
  trap            105   1.5%
  thin_river       33   0.5%         ※ '팟컨트롤 + 강도 0.NN' 은 강도값마다
  river_bluff       4   0.1%            갈려 있다. 합치면 262건 — 정규화 필요
```

**기저 빈도가 높으므로 flip 이 크다 같은 인과 해석은 하지 않는다.**

**H3 계수 크기 — 소스 전수 추적으로 확정.** 파생 변환부터.

```
aggr  = temper['aggression']        ← 항등
bluff = concepts['bluff']           ← 항등
tight = 10 − temper['looseness']
value = 'xr' if checkraise_flop ≥ 6.5 else ('lead' if aggression ≤ 4 else 'mixed')
goal  = 'survive' if icm ≥ 7 else ('spot' if discipline ≤ 3.5 else 'accum')
bias  = _z(가중합),  _z(v) = clamp((v−5)/5, −1, +1)
```

실행층 소비처 전수 (축 1→9, 교락축 5.0 고정):

```
-- aggression
   decide_aggression 밸류       p = 0.30+0.058·a+0.018·gamble      0.448 → 0.912  ×2.04
   decide_aggression 팟컨트롤     max(.05,min(.6, 0.18+0.035·a))     0.215 → 0.495  ×2.30
   cbet_freq                  f = base+0.035·a+0.020·b           0.555 → 0.835  ×1.50
-- bluff
   decide_aggression 블러프계획    p = 0.25+0.070·b+0.02·gamble       0.420 → 0.980  ×2.33
   cbet_freq                  +0.020·b                           0.615 → 0.775  ×1.26
-- thin_value_turn
   decide_aggression 밸류       p ×= (0.55+0.09·sk)                0.640 → 1.360  ×2.12
-- cbet_flop
   cbet_freq                  base ×= (0.45+0.11·sk)             0.560 → 1.440  ×2.57
-- discipline
   decide_aggression:866       cf ×= max(.05, 1−0.085·disc)       0.915 → 0.235  ×0.26
   decide_response:805         p_dev ×= max(.05, 1−0.085·disc)    0.915 → 0.235  ×0.26
   calldown_need station       need ×= max(.55, 1−0.22·station)   0.965 → 1.000  ×1.04
   call_bias sticky            m ×= 1−0.12·sticky                 0.947 → 1.000  ×1.06
-- looseness
   calldown_need station       need ×= max(.55, 1−0.22·station)   1.000 → 0.921  ×0.92
   call_bias draw_love         m ×= 1−0.18·draw_love              1.000 → 0.978  ×0.98
   call_bias sticky            m ×= 1−0.12·sticky                 1.000 → 0.976  ×0.98
-- potcontrol
   실행층 소비처 **없음**
```

`discipline` 의 실행층 진입점은 `cbet_freq` 안이 아니라 그 **바깥**
(`plan.py:866-867`)이다. `cbet_freq` 자체는 `discipline` 을 읽지 않는다.

**H4 게이트·클램프·포화 — 위치와 접촉 여부 확정.**

`max(0.0, bias(...))` 가 정의역 절반을 차단한다 (교락축 5.0 고정):

```
                    축1      축9    max(0,·) 후      가동 구간
station(looseness)  −0.360  +0.360  0.000 → 0.360   상반만
station(discipline) +0.160  −0.160  0.160 → 0.000   하반만
sticky(discipline)  +0.440  −0.440  0.440 → 0.000   하반만
sticky(looseness)   −0.200  +0.200  0.000 → 0.200   상반만
draw_love(looseness)−0.120  +0.120  0.000 → 0.120   상반만
```

**`discipline` 과 `looseness` 는 정확히 반대쪽 절반에서만 작동한다.**

이산 게이트:

```
plan.py:456·504  sk('potcontrol') >= 1   → PS.sk ≥ 3.33   계획층. 위에서 기울기 0
plan.py:490      sk('bluff') >= 1        → PS.sk ≥ 3.33
plan.py:468      sk('semibluff') >= 0.4  → PS.sk ≥ 1.33
plan.py:940      has_c and rel < 0.85    → thin_value 계수의 진입 조건
persona.derive   aggression ≤ 4 → value='lead' → p ×= 1.12    **계단**
persona.derive   discipline ≤ 3.5 → goal='spot'
```

`make_plan` 안의 `sk()` 는 `PS.sk/3.33`(0~3), `decide_aggression`·
`cbet_freq` 의 `PS.sk(...)` 는 0~10 날것이다. **두 스케일이 같은 파일에
섞여 있다.**

**1↔9 범위에서 실제로 닿는 클램프는 하나뿐이다** — `bluff` 축 9 에서
`p = 0.980 > 0.95` 라 `decide_aggression` 블러프 상한에 잘린다. 나머지
(`0.6` 팟컨트롤 상한, `0.55` station 하한, `0.05` disc 하한, `cbet_flop`
`[0.35,1.85]`)는 전부 미접촉이다.

`rel >= 0.65` 의 `p = p + (1−p)·((rel−0.65)/0.35)^0.8` 은 `p` 를 1 쪽으로
밀어 **그 앞의 축 계수를 압축한다.** ④ 에서 `thin_value` 를 `rel < 0.85`
로 제한하니 ρ 가 +0.130 → +0.391 로 올랐던 자리와 같다.

**`potcontrol` 은 실행층 소비처가 없다.** `decide_aggression` 의
`pot_control` 분기는 `0.18 + 0.035·a` 로 `aggression` 만 읽는다. 계획층
에서도 게이트 두 번뿐이고 `_pc_p` 산식에 축이 없다. **이름 때문에 실행층
행동 확률을 조절하는 축처럼 보이지만 아니다.** 반대로 `bluff` 는 `p` 에
직접 들어가고 상한에 실제로 닿는다. **"축이 존재한다 → 실행층 flip 에
영향을 준다" 로 취급하면 안 된다.**

**`tools/axis_dataflow.py` 의 `L1F` 는 정의만 되고 사용되지 않는다.**
`L1F` 출현 1회(38줄), `L2F` 출현 6회(35·139·145·153·159·164줄).

### 4-2. 기존 자료로 확정할 수 없는 것

```
H5-B  함수공간 변화량
```

②·③ 은 이 목록에서 **삭제됐다.** 소스 추적으로 확정됐다 — 4-3 을 본다.

### 4-3. ②·③ — 추가 계측 불필요. 소스 추적으로 확정

**앞선 판이 틀렸다.** "archive 는 intent 생성 이후의 레코드만 담는다"고
적었는데 아니다. `session.py:456` 은 `if True:` 이고 `session.py:460` 의
기록은 `update_plan` 호출마다 무조건 남는다. 그때 `trace` 가 빈 레코드가
0건으로 보인 것은, 내가 archive 를 `(hand_no, seat, board, street)` 로
중복 제거해 **반복 호출을 스스로 지웠기** 때문이고, `hand_no` 는 실행 간
중복돼 고유키도 아니었다(고유키는 레코드 최상위 `hash`).

**`trace` 는 이 목적에 쓸 수 없다.** `plan.py:1483` 의 승계 목록
(`intents`·`deviations`·`streets`·`refreshed`·`bet_streets`·`plan_since`·
`_rsig`)에 `'trace'` 가 없다. 플랍은 `session.py:443` 의
`first=(key not in h.plans or street == 'flop')` 때문에 매 호출
`make_plan` 이 새 dict 를 만들고 그때 `trace` 가 사라진다. 실측에서
3스트리트를 간 (핸드, 좌석) 중 605건의 마지막 레코드에 aggression trace 가
0개였다.

**대응 단위 — `idx == 0`**

```
session.py:454   _oidx = sum(1 for i in h.intents
                             if i['street']==street and i['seat']==s)
plan.py:1521     if intent_of(st, street) is None:
plan.py:1522         st = attach_intent(...)
```

`attach_intent` 는 세 경로 전부에서 `set_intent` 를 부른다
(`plan.py:569`·`575`·`577`). 한 번 돌면 `intent_of` 가 영구히 non-None 이
되고 `intents` 는 승계 목록에 있어 유지된다. 따라서

```
idx == 0  ⟺  그 (좌석, 스트리트)의 첫 update_plan  ⟺  attach_intent 실행
```

archive 실측에서 `(hash, seat, street)` 고유 조합 7,064 와 `idx==0` 건수
7,064 가 **정확히 일치**하고, 그 7,064건 전부에 `intent_act` 가 있다.

**호출 경로 — L2 분모는 `session.py:436` 의 postflop 호출이다**

```
tools/cf_axis_l2.py:228  PL.update_plan = wrap_up        ← 세는 대상
fieldsim.Field._play_table → play.Hand(..., hero=None) → SE.HandRun(h)
  → run.start()  session.py:66 → HandRun._run()  session.py:113
  → session.py:306  for street, nc in [('flop',3),('turn',4),('river',5)]:
  → session.py:315    while True:
  → session.py:436      h.plans[key] = PL.update_plan(...)
```

프리플랍은 포함되지 않는다. 저장소 전체에서 프로덕션 호출부는
`session.py:436` 하나뿐이다. `_run` 의 `yield` 네 곳
(`session.py:141`·`151`·`321`·`331`)이 전부 `s == h.hero` 로 가드돼 있어
`hero=None` 이면 한 번도 yield 하지 않고 핸드를 끝까지 돈다.

**L1 분모 — `attach_intent` 호출 단위**

```
tools/cf_axis.py:216  PL.attach_intent = wrap_ai
tools/cf_axis.py:213    rows.append(rec)                  ← 축마다 한 행
tools/cf_axis.py:336  print('  결정 %d건' % (len(rows)//len(axes)))
```

**L1 과 L2 는 실행 조건이 같다** — `entries=24 · hpl=12 · stack=30000 ·
시드 5000–5054`. 두 harness 모두 원본 함수를 먼저 부르고 그 결과를 그대로
반환한다(`cf_axis.py:180→214`, `cf_axis_l2.py:177→227`) — 비개입 wrapper 다.

**확정값**

```
①  L2 전체 update_plan            37,424      (× 2 = 74,848 비교쌍)
②  action-decision 대응 단위        31,189      ← 원자료가 직접 센 값
①→② 반복 호출 제거                 6,235
②/①                              83.34%
③  L1 대응 decision unit           31,189
```

**정정.** 처음에는 ②·③ 을 `CF_RESULT_LEVEL1_EXT.md` 의 31,236 으로 적었다.
이후 55시드 원자료에서 `attached_O == True` 를 직접 세니 218,323행 / 7축 =
**31,189** 였고, `CF_RESULT_LEVEL1.md` 의 결정 수와 같다. 31,236 은 다른
실행의 값이고 47 차이는 미검증 항목으로 남는다 (`CF_RESULT_NORM.md` 7절).

L2 의 action-decision 대응 단위는 `idx == 0` 인 (hand, seat, street) 최초
`update_plan` 호출이며, 이는 L1 의 `attach_intent` 호출 단위와 대응한다.
55시드 원자료에서 `attached_O` 를 직접 세니 **31,189** 이고,
`CF_RESULT_LEVEL1.md` 의 결정 수와 같다. ② 의 대응 N 은 31,189 다.
**`CF_RESULT_LEVEL1_EXT.md` 의 31,236 은 다른 실행의 값이므로 쓰지 않는다.**
47 차이의 원인과, L1 harness 의 `trace` 40개 상한(`plan.py:_trace`)에 따른
결과 행 누락 여부는 미검증으로 남는다
(`tools/cf_axis.py:186` 이 `p`·`roll` 없는 경우 행을 만들지 않는다).

독립 archive(4,000핸드, 다른 설정)의 `idx==0` 비율은 83.29% 로 위
83.47% 와 0.18%p 차이다. **참고값이지 검증이 아니다** — 실행 조건이 다르다.

**83.47% 를 "flip 을 설명하는 비율" 로 읽지 않는다.** 이 수는 L2 전체 호출
분모에서 최초 decision unit 이 차지하는 비율일 뿐이고, denominator/path
decomposition 을 가능하게 하는 값이다.

`idx == 0` 과 L1 decision unit 의 대응은 **소스 구조와 기존 결과로 정의한
것이며, 새로운 측정·시뮬레이션은 하지 않았다.** 두 harness 가 핸드별로
1:1 동일한 시퀀스를 만든다는 것까지는 증명하지 않았다 — 동일 시드·동일
`entries/hpl/stack`·비개입 wrapper 라는 소스 확인까지가 현재 근거다.

### 4-4. 결합식은 만들지 않는다

H3 배율만으로는 관측 서열이 설명되지 않는다. `cbet_flop` 의 배율이
×2.57 로 가장 큰데 L1 POST flip 은 1.0% 로 뒤에서 두 번째다. `bluff` 도
배율(×2.33)이 `aggression`(×2.04)보다 큰데 flip 은 작다.

**배율 × 빈도 × gate 를 사후적으로 결합해 결과를 설명하는 식을 만들지
않는다.** 지금 만들면 결과를 보고 모형을 맞춘 것이 된다. 현재 결과는
**구조적 후보를 확인한 것으로만 기록한다.**

### 4-5. H5-A · H5-B

```
H5-A  persona 생성기 호출로 산출 가능하다는 사실만 기록한다. 아직 실행하지 않는다
H5-B  decision quantity 를 정의하기 전까지 보류한다
```

`max(0.0, bias(...))` 구조가 H5-A·H5-B 분리를 소스 수준에서 뒷받침한다.
`discipline` 은 한 방향에서만 효과가 나고 반대 방향에서는 클램프로
사라진다. 그래서 **"discipline 의 1↔9 변화량은 8 이다" 라고 비교하는 것
자체가 함수상의 실제 개입 크기를 표현하지 않는다.**

### 4-7. H1 — 실행층 함수에서 읽히는 축

`axis_dataflow.py` 가 `L1F` 를 실제로 쓰게 했다. 기존 계획층 표는
**바이트 단위로 그대로**이고 아래 표가 뒤에 붙는다.

```
축                 직접 실행층(L1)                     간접 실행층 경로
cbet_flop         cbet_freq                          없음
thin_value_turn   decide_aggression                  없음
discipline        decide_aggression decide_response   bias:station→decide_response
aggression        attach_intent(D팔밖) decide_response  derive:aggr→{calldown_need,
                                                     cbet_freq, decide_aggression,
                                                     decide_response, decide_size,
                                                     overbet_frac, opp_bet_prob}
                                                     derive:value→decide_aggression
                                                     bias:{bluff_fear,hero_call}→decide_response
bluff             cbet_freq decide_aggression         derive:bluff→(같은 넷)
                  decide_response act_with_plan(D팔밖)
looseness         **없음**                             bias:station→decide_response
potcontrol        (실행층 함수에서 전혀 읽히지 않는 18축 중 하나)
```

**세 가지 한계. "실행층 도달 범위가 확인됐다" 라고 쓰지 않는다.**

```
1  5-2  make_plan 이 barrel_size(480)·bluff_mode(497) 를, trap_judgment 가
        opp_bet_prob(224) 을 부른다. 이 셋에서 읽힌 축은 계획 구축 중에도
        읽힌다 → 표에 (계획층내:…) 로 표시한다
2  5-1  perceived_rel(계획층)이 만든 rel 을 실행층이 읽는다. 계획층에서만
        읽히는 축도 행동에 닿을 수 있다
3       이 표는 **호출 그래프가 아니라 읽기 지점 표다.** 실행층 안의 중첩
        호출이 안 보인다 — cbet_freq 는 decide_aggression:863, overbet_frac 는
        decide_size:1038, barrel_size 는 bluff_mode:1995 안에서 불린다
```

또 `attach_intent`·`act_with_plan` 은 이 도구의 `L1F` 에는 있지만
`cf_axis_l2.py` 의 D 팔 개입 집합에는 **없다**. 표에 `(D팔밖)` 으로 적는다.

**타당성 검사.** L1 POST 는 `decide_aggression` 에서만 개입한다. 그 도달
여부가 실측 flip 과 맞는지 본다.

```
축                 L1 POST   지도상 decide_aggression 도달
aggression           9.2%    derive:aggr→ · derive:value→
discipline           4.3%    직접 (plan.py:866)
bluff                3.5%    직접 · derive:bluff→
thin_value_turn      2.7%    직접 (plan.py:941)
cbet_flop            1.0%    cbet_freq — decide_aggression:863 안 (한계 3)
potcontrol           0.0%    없음
looseness              —     없음 (bias:station→decide_response 뿐)
```

**도달 없음 두 축이 실측 0 이고, 도달 있는 다섯 축이 실측 비 0 이다.**
다만 `cbet_flop` 은 한계 3 때문에 표만 보면 도달이 없어 보인다 — 순위나
크기를 이 표로 설명하지 않는다.

### 4-8. H5-A — 입력 공간 분산

`tools/axis_sd.py`. L1/L2 본측정과 **같은 필드를 그대로 재구성**해서 쟀다
(`entries=24`, 시드 5000-5054, `field_quality=0.6490`). 핸드를 돌리지
않는다 — `fieldsim.Field` 생성만으로 `persona.make_player` 가 호출되고 거기서
멈춘다. 0.2초, 시뮬레이션이 아니다. 표본은 히어로(q=0.9 고정)를 뺀 1,265명.

```
축                 평균     sd    경계%   1↔9=?sd    R²(잠재3)   잔차sd   1↔9=?잔차sd
aggression        5.01  2.420   5.1%      3.31       0.880     0.839       9.53
discipline        5.51  2.244   3.8%      3.56       0.106     2.123       3.77
looseness         4.75  2.261   3.0%      3.54       0.141     2.096       3.82
potcontrol        4.96  1.974   1.5%      4.05       0.530     1.353       5.91
thin_value_turn   4.50  1.858   0.7%      4.31       0.524     1.281       6.24
bluff             4.48  1.711   0.6%      4.67       0.566     1.127       7.10
cbet_flop         5.72  1.549   0.1%      5.17       0.535     1.056       7.57
```

**1↔9 는 축마다 같은 크기의 개입이 아니다.** 전체 sd 기준 3.31~5.17배
(1.56배 차), 잔차 sd 기준 3.77~9.53배(2.53배 차)다.

**생성분포에서 매우 희귀한 조합이 만들어질 수 있다.** 반사실 스왑은
`latent`(study·aggro·exp)를 그대로 두고 축만 1 또는 9 로 바꾼다.
`aggression` 은 `r:aggro = 0.938`, `R² = 0.880` 이라 `aggro 3 인데
aggression 9` 같은 조합이 나온다.

**생성식상 불가능한 값은 아니다** — `aggression = _clamp(aggro + gauss(0, 0.8))`
이라 확률이 0 이 아니다. 다만 상관이 0.938 이라 **실제 필드 분포에서
대표적이지 않은 반사실 조합**이다. `discipline`(R² 0.106)·`looseness`(0.141)
는 잠재와 거의 독립이라 그 문제가 작다.

**그러나 H5-A 는 서열을 설명하지 못한다.**

```
축                 L1 POST   1↔9/sd   1↔9/잔차sd
aggression           9.2%      3.31        9.53
discipline           4.3%      3.56        3.77
bluff                3.5%      4.67        7.10
thin_value_turn      2.7%      4.31        6.24
cbet_flop            1.0%      5.17        7.57
potcontrol           0.0%      4.05        5.91

flip 과의 Spearman ρ    전체 sd  −0.600    잔차 sd  +0.257
```

**두 정규화가 부호부터 다르다.** 어느 쪽도 관측 서열을 재현하지 않고,
n=6 이라 두 ρ 모두 정보가 거의 없다. 정규화를 하면 서열이 바뀔 수 있다고
적었는데 — **바뀌는 방향이 정규화 방식에 달려 있다.**

**따라서 H5-A 단독으로는 서열을 설명하지도, 배제하지도 못한다.**
입력 공간만으로 부족하고 H5-B(함수 공간)가 필요한데, 그 "decision
quantity" 는 아직 정의하지 않았다.

**Level 1·2 의 숫자는 이 절에서 수정하지 않았다.** 그 실험들은 "1↔9 를
줬을 때" 를 정확히 잰 것이고, 정규화는 별개 질문이다.

### 4-9. H5-B 설계 — **측정 전에 고정한다**

H5-A 가 입력 공간을 쟀다. H5-B 의 질문은 다음이다.

> 같은 개입이 함수 내부의 decision quantity 를 얼마나 움직이는가?

**decision quantity = `decide_aggression` 이 반환한 `p`.**

근거는 둘이다. `p` 는 `attach_intent` 가 `roll < p` 로 행동을 가르는 그
값이고(`plan.py:556`·`562`), `rows55b` 에 팔·tag 별로 **이미 기록돼 있다**
(`d1e6cac`). 새 시뮬레이션이 필요 없다.

**쌍별 관측량**

```
Δp = p_hi − p_lo        같은 decision unit 의 두 반사실
```

**1차 지표 = `median(|Δp|)`.** `Δp` 는 방향이 상쇄되므로 절대값의 중앙값을
쓴다. 함께 낼 것:

```
axis · arm    N          쌍 수
              median(Δp)      방향 포함. 상쇄를 확인하는 용도
              median(|Δp|)    ← 1차 지표
              mean(|Δp|)      꼬리에 끌리는 정도
              Δp ≠ 0 비율     개입이 p 에 닿기라도 하는가
              방향성          p_hi > p_lo 건수 / p_hi < p_lo 건수
```

**모집단** — ② `attached_O` 안에서 양쪽 tag 가 정렬·불변량을 통과한 쌍.
(b)(c)(e) 와 같은 집합이라 서로 붙여 볼 수 있다.

#### 이 단계에서 하지 않을 것

```
Δp / 잔차sd 같은 H5-A × H5-B 결합식을 만들지 않는다
  두 결과를 별개로 나란히 놓고 본다. 사후 결합은 4-4 에서 금지했다
새 설명변수를 끌어오지 않는다 — decision quantity 는 p 하나다
p 변화량으로 관측 flip 서열을 설명하지 않는다
```

### 4-10. H5-B 결과

`tools/l2_recount.py` (f) 블록. `rows55b` 만 썼고 새 실행은 없다.
설계(4-9)는 측정 전 커밋 `6416d98` 로 고정했고 **이후 수정하지 않았다.**

```
축                팔          N    med(Δp)   med(|Δp|) mean(|Δp|)      Δp≠0         ↑ / ↓
aggression       D      31176     0.0200      0.0200     0.0942     51.9%    16174 / 0
                 M      31170     0.0000      0.0000     0.0031      1.1%      265 / 76
                 T      31170     0.0195      0.0206     0.0968     52.0%    16153 / 49
discipline       D      31176     0.0000      0.0000     0.0432     13.5%        0 / 4212
                 M      30911     0.0000      0.0000     0.0126     18.4%       63 / 5633
                 T      30911     0.0000      0.0000     0.0560     31.3%       63 / 9616
bluff            D      31176     0.0000      0.0000     0.0359     19.5%     6093 / 0
                 M      22778     0.0000      0.0000     0.0109      2.4%      517 / 22
                 T      22778     0.0000      0.0000     0.0332     14.9%     3383 / 21
thin_value_turn  D      31176     0.0000      0.0000     0.0271      9.4%     2927 / 0
                 M      31176     0.0000      0.0000     0.0000      0.0%        0 / 0
cbet_flop        D      31176     0.0000      0.0000     0.0103      7.1%     2198 / 0
                 M      31176     0.0000      0.0000     0.0000      0.0%        0 / 0
potcontrol       D      31176     0.0000      0.0000     0.0000      0.0%        0 / 0
                 M      22667     0.0000      0.0000     0.0098      5.0%      963 / 172
looseness        D      31176     0.0000      0.0000     0.0000      0.0%        0 / 0
                 M      31130     0.0000      0.0000     0.0010      2.0%      610 / 7
```

#### 1차 지표가 퇴화했다

**사전에 고정한 1차 지표 `median(|Δp|)` 가 `aggression` D·T 를 빼면 전부
0.0000 이다.** 분포가 0 에 심하게 몰려 있어(대부분의 결정이 그 축을 읽는
분기에 도달하지 않는다) 중앙값이 정보를 담지 못한다.

**지표를 사후에 바꾸지 않는다.** 4-9 에 함께 적어둔 나머지 통계량은
그대로 보고한다. `Δp≠0` 비율과 `mean(|Δp|)` 는 0 이 아니다.

조건부 통계량(`Δp≠0` 인 쌍만의 `median(|Δp|)`)이 자연스러운 비퇴화
대안이지만 **4-9 에 없던 통계량이라 계산하지 않았다.** 추가 여부는 설계
결정이다.

#### 숫자에서 직접 확인되는 것

- `potcontrol` D 와 `looseness` D 는 `Δp≠0` 이 **정확히 0.0%** 다. 실행층에서
  `p` 에 닿지 않는다 — H1 정적 지도와 일치한다
- `thin_value_turn` M 과 `cbet_flop` M 도 0.0% 다. 계획층 소비처가 없다는
  4-1 과 일치한다
- 방향이 거의 완전 단조다. `aggression` D 는 16,174↑ / 0↓, `discipline` D 는
  0↑ / 4,212↓, `bluff` D 는 6,093↑ / 0↓ 로 역방향이 0 이다.
  T 팔에서만 역방향이 조금 생긴다 (`aggression` T 49, `discipline` T 63)

#### 해석하지 않는 것

`mean(|Δp|)` 의 D 팔 순서가 관측 flip 순서와 같다.

```
mean(|Δp|) D   aggression .0942 > discipline .0432 > bluff .0359
               > thin_value_turn .0271 > cbet_flop .0103 > potcontrol/looseness 0
L1 POST flip   aggression 9.2% > discipline 4.3% > bluff 3.5%
               > thin_value_turn 2.7% > cbet_flop 1.0% > potcontrol 0.0%
```

**이것으로 서열을 설명하지 않는다.** 4-9 가 "p 변화량으로 관측 flip 서열을
설명하지 않는다" 를 측정 전에 금지했고, 4-4 의 사후 결합식 금지도 유효하다.
순서가 같다는 관측만 기록한다.

`Δp≠0` 비율의 순서는 다르다 — `aggression` 51.9% > `bluff` 19.5% >
`discipline` 13.5% 로 가운데 둘이 뒤집힌다. **두 통계량이 서로 다른 순서를
낸다는 것도 같이 적어둔다.**

### 4-6. 현재 경계

| 항목 | 상태 |
|---|---|
| H2 기저 빈도 | **구조적으로 확인 완료** — archive 로 산출 가능 |
| H3 계수 크기 | **구조적으로 확인 완료** — 전수표 위 |
| H4 게이트·클램프 | **구조적으로 확인 완료** — 닿는 클램프는 `bluff` 상한 하나 |
| H1 도달 범위 | **실행층 표 산출 완료 (4-7).** `axis_dataflow.py` 가 `L1F` 를 쓰게 했다. 다만 **호출 지점 분류이지 런타임 도달 범위가 아니다** — 세 가지 한계가 있다 |
| ② subset | **확정 — 31,189** (4-3). `attached_O` = `attach_intent` 실행. 원자료가 직접 셌다 |
| ③ 대응 unit | **확정 — 31,189.** L1 과 동일한 (hand, seat, street) decision-unit 정의 |
| H5-A | **측정 완료 (4-8).** 1↔9 는 축마다 3.31~5.17 sd (잔차 기준 3.77~9.53)로 크기가 다르다. 다만 **서열을 설명하지도 배제하지도 못한다** — 두 정규화의 Spearman ρ 가 −0.600 / +0.257 로 부호부터 다르다 |
| H5-B | **측정 완료 (4-10).** decision quantity = `p`. 사전 1차 지표 `median(\|Δp\|)` 는 0 편중으로 퇴화했고 지표를 사후 변경하지 않았다. `Δp≠0`·`mean(\|Δp\|)` 는 비 0 이고 방향은 거의 완전 단조다. **서열 설명에 쓰지 않는다** |

**Level 1·2 의 기존 숫자는 이 조사에서 어느 것도 수정하지 않았고, 앞으로도
수정하지 않는다.**

---

## 5. 이 실험이 답하지 않을 것 (미리 적는다)

```
축의 "중요도" 순위를 매기지 않는다
어떤 축을 고쳐야 하는지 말하지 않는다
Level 1·2 의 숫자를 사후 조정하지 않는다
plan.py 를 수정하지 않는다
```

---

## 6. 열린 항목

```
H5-B 의 "decision quantity" 를 무엇으로 잡을지 미정
L1 harness 의 trace 40 상한이 31,236 을 깎았는지 — 미검증
사전등록 예측은 설계 확정 후에 쓴다 — 아직 쓰지 않았다
```

4절에서 해소된 항목: H2 산출 가능 여부, H3, H4, `potcontrol` 실행층 부재,
`L1F` 미사용, **②(31,189)**, **③(31,189)**.

**이 수정 후에도 새 측정과 사전등록 예측은 시작하지 않는다.** 설계 문서의
논리적 누락이 없는지 다시 검토한다.
