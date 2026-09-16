# ⑤ Level 2 반사실 — 결과

**질문:** 축이 행동을 직접 조절하는가, 아니면 계획을 바꿔서 행동을 바꾸는가.

설계는 `CF_DESIGN_LEVEL2.md`. 본측정은 그 설계대로 한 번 돌렸고 이후
재실행하지 않았다. `plan.py` 는 수정하지 않았다.

**기준점: `8be8b4e`** — 이 문서가 처음 들어간 커밋이다. Level 2 결과는
여기서 고정한다. 이후 결과를 바꾸려면 **새 측정과 새 문서**를 만든다.
이 문서의 숫자는 수정하지 않는다. 오탈자·서술 보강은 숫자를 건드리지
않는 선에서만 한다.

**후속:** 이 결과를 L1 과 비교 가능한 단위·정의로 다시 읽은 것이
`CF_RESULT_NORM.md` 다. **여기 숫자는 그대로 두고** 다른 계수 규약으로
재집계한 것이다.

```
entries=24  hands_per_level=12  start_stack=30000
시드 5000-5054 (55개)   update_plan 호출 37,424건   엔진 오류 0건
축  potcontrol · aggression · bluff · thin_value_turn · discipline · looseness · cbet_flop
네 팔  O(원본) / D(실행층 개입) / M(계획층 개입) / T(전체)
```

**T = D + M 가산성을 가정하지 않는다.** 네 팔을 독립적으로 재고 경로를
비교한다.

---

## 0. 시간 순서 — 무엇이 언제 정해졌는가

결과를 본 뒤 설계를 고친 것과, 결과를 보기 전에 고친 것을 구분하기 위해
순서를 남긴다.

```
1  CF_DESIGN_LEVEL2.md 작성. 8절에 측정 전 예측을 적는다 (수정 금지)
2  SITE_L2 를 문자열 검색으로 만든 것이 틀렸음을 발견.
   tools/axis_dataflow.py 로 데이터 흐름 기준 재작성
   → discipline M=0 예측 철회, looseness 를 대상에 추가
   → cbet_flop M=0 만 구조적 타당성 검사로 남음        ← **여기까지 측정 전**
3  측정 적격 기준 alignment_rate >= 0.50 을 측정 전에 고정 (커밋 1512fba)
4  본측정 실행 (55시드)                                 ← **여기서 결과를 처음 봄**
5  looseness 0.0% 검증, M plan=,act≠ 원인 규명, 세 칸 정의 정정 (5-1/5-2)
```

**`discipline M = 0` 예측은 결과를 보고 삭제한 것이 아니다.** 2 단계에서
코드 경로를 읽어 철회했고, 그 시점은 4 단계보다 앞선다. 그래서 ④ 에서
적중/불일치로 채점하지 않고 무효로 처리했다.

---

## 1. 타당성 검사

| 검사 | 기대 | 관측 | 판정 |
|---|---|---|---|
| 엔진 오류 | 0 | 0건 / 37,424 호출 | 통과 |
| 불변량 위반 | 0 | 경고 출력 없음 (전 축·전 팔) | 통과 |
| `potcontrol` D = 0 | 실행층 소비처 없음 | 세 칸 0.0%, 8시드·2시드 정확히 0 | 통과 |
| `potcontrol` T = M | D 가 0 이므로 | 세 칸·aligned·shifted 전부 동일 | 통과 |
| `looseness` D = 0 | 실행층 소비처 없음 | 세 칸 0.0%, 8시드·2시드 정확히 0 | 통과 |
| `looseness` T = M | 위와 같음 | 8시드 count 까지 동일 (3/4/0) | 통과 |
| D 팔 `plan≠` = 0 | 설계 진술 | 7축 전부 0, 8시드·2시드 정확히 0 | 통과 (5-2 단서) |
| M 팔 `plan=,act≠` = 0 | 설계 진술 | `discipline`·`looseness` 만 비 0 | **정정됨 (5-1)** |

마지막 줄이 이번 측정에서 가장 많은 시간을 쓴 항목이다. 2절에 원인을
남긴다.

---

## 2. M 팔 `plan=,act≠` 의 원인 — 격리 위반이 아니다

M 팔에서 계획 라벨은 같은데 행동이 바뀐 건이 `discipline` 0.3% /
`looseness` 0.026% 남았다. 세 층에서 확인했다 (`tools/diag_mleak.py`).

```
AST 전수 호출 지점    L2 함수가 실행층 함수 안에서 호출되는 자리 0
난수 정렬             roll 동일, p 만 이동 (0.596 → 0.533 등)
반환 state 전수 diff   rel 19/19 · stackoff 5/19 · why·why_by_street 은 기록 전용
실행층 참조 지점       rel      attach_intent:555   decide_response:707
                      stackoff attach_intent:567   decide_response:752
축별 (4시드 19건)      discipline 18 / looseness 1 / 나머지 5축 정확히 0
```

계획층 `perceived_rel` 이 만든 `rel` 을 실행층이 읽는다. 같은 roll 에서
`p` 가 달라져 행동이 뒤집힌다. **개입이 실행층 함수에 새어든 것이 아니라,
계획층이 라벨 아닌 자기 산출물을 통해 실행층을 움직인 것이다.**

5축이 0 인 것은 `perceived_rel` 이 읽는 `persona.bias` 세 식에 그 축들이
없기 때문이다. 측정 7축 중 거기 있는 것은 두 개뿐이다.

```
overpair_love = _z(0.40·(10−range_read) + 0.30·(10−potodds) + 0.30·(10−discipline))
draw_love     = _z(0.50·(10−outs) + 0.35·gamble + 0.15·looseness)
sticky        = _z(0.55·(10−discipline) + 0.25·looseness + 0.20·tilt_prone)
```

세 칸의 정의를 팔별로 갈랐다 (`CF_DESIGN_LEVEL2.md` 5-1). D 를 "직접
효과" 라고 쓰지 않고 **실행층 소비 경로에서의 효과**로 바꿨다.

---

## 3. alignment_rate

측정 적격 기준 `alignment_rate >= 0.50` 은 측정 **전에** 고정했다.
효과 유의성 기준이 아니라 **동일 stochastic realization 을 충분히
유지해서 비교할 수 있는지에 대한 측정 가능성 기준**이다. 0.50 에 통계적
의미는 없다.

```
축                 D        M        T      status
potcontrol      100.0%    86.4%    86.4%    전부 OK
aggression      100.0%   100.0%   100.0%    OK
bluff           100.0%    85.1%    85.1%    OK
thin_value_turn 100.0%   100.0%   100.0%    OK
discipline      100.0%    99.5%    99.5%    OK
looseness       100.0%    99.9%    99.9%    OK
cbet_flop       100.0%   100.0%   100.0%    OK
```

21개 팔 전부 기준을 넘었다. 측정불가로 제외된 팔은 없다.

**`potcontrol` M(86.4%)과 `bluff` M(85.1%)의 제외는 무작위가 아니다.**
두 축은 계획 구축 중 확률 게이트를 직접 굴린다. 축 값이 바뀌면 게이트
통과 여부가 갈리고 그 뒤로 난수 소비가 어긋난다. **효과가 가장 클 자리가
우선적으로 제외된다.** 기준을 넘었다는 것은 "비교 가능하다" 일 뿐이고,
남은 86% 에서 잰 수치는 **하한으로 읽는다.**

---

## 4. 세 칸 — 원자료

본측정은 백분율 한 자리만 남아 있어 count 를 반올림 구간으로 환산했다
(`x.y%` → `[(x.y−0.05)·aligned, (x.y+0.05)·aligned]`, 폭 약 ±37).
`count8` 은 시드 5000-5007 을 **동일한 7축 목록·동일 인자**로 돌린 것이라
정확하다. 부분집합 논리는 6절에서 검증했다.

### 4-1. D `plan=,act≠` — 실행층 소비 경로

```
축                 aligned55  count55(반올림구간)      aligned8  count8
potcontrol           74822      0 – 37    ( 0.0%)     11374       0
aggression           74822   2582 – 2656  ( 3.5%)     11374     394
bluff                74822    936 – 1010  ( 1.3%)     11374     132
thin_value_turn      74822    786 – 860   ( 1.1%)     11374     133
discipline           74822   1310 – 1384  ( 1.8%)     11374     215
looseness            74822      0 – 37    ( 0.0%)     11374       0
cbet_flop            74822    262 – 336   ( 0.4%)     11374      41
```

### 4-2. M `plan≠,act=` — 계획이 바뀌었는데 행동이 같다

```
축                 aligned55  count55(반올림구간)      aligned8  count8
potcontrol           64673   1326 – 1390  ( 2.1%)      9883     196
aggression           74816    262 – 336   ( 0.4%)     11371      37
bluff                63712   1052 – 1114  ( 1.7%)      9691     150
thin_value_turn      74822    113 – 187   ( 0.2%)     11374      25
discipline           74511    336 – 409   ( 0.5%)     11320      70
looseness            74771      0 – 37    ( 0.0%)     11365       4
cbet_flop            74822      0 – 37    ( 0.0%)     11374       0
```

**이 칸을 효과 크기로 읽지 않는다.** 계획 라벨이 달라졌다는 사실과 행동이
같다는 사실만 기술한다. 어떤 축의 영향량으로 환산하지 않는다.

### 4-3. M `plan=,act≠` — 계획층 산출물 전달

```
축                 aligned55  count55(반올림구간)      aligned8  count8
potcontrol           64673      0 – 32    ( 0.0%)      9883       0
aggression           74816      0 – 37    ( 0.0%)     11371       0
bluff                63712      0 – 31    ( 0.0%)      9691       0
thin_value_turn      74822      0 – 37    ( 0.0%)     11374       0
discipline           74511    187 – 260   ( 0.3%)     11320      39
looseness            74771      0 – 37    ( 0.0%)     11365       3
cbet_flop            74822      0 – 37    ( 0.0%)     11374       0
```

### 4-4. `plan≠,act≠` — 혼합. 분해하지 않는다

```
축                 D                       M                       T
potcontrol           0–37  (0.0%) n8=0    98–161 (0.2%) n8=7     98–161 (0.2%) n8=7
aggression           0–37  (0.0%) n8=0   113–187 (0.2%) n8=17   113–187 (0.2%) n8=22
bluff                0–37  (0.0%) n8=0   351–414 (0.6%) n8=71   542–605 (0.9%) n8=88
thin_value_turn      0–37  (0.0%) n8=0     0–37  (0.0%) n8=0      0–37  (0.0%) n8=4
discipline           0–37  (0.0%) n8=0   112–186 (0.2%) n8=15   112–186 (0.2%) n8=15
looseness            0–37  (0.0%) n8=0     0–37  (0.0%) n8=0      0–37  (0.0%) n8=0
cbet_flop            0–37  (0.0%) n8=0     0–37  (0.0%) n8=0      0–37  (0.0%) n8=0
```

계획과 행동이 동시에 달라졌으므로 **해당 관측만으로 어느 층·어느 산출물이
차이를 만들었는지 식별할 수 없다.** D/M/T 중 하나에 귀속시키지 않는다.

### 숫자에서 직접 확인되는 것

- **D 팔의 `plan≠` 두 칸이 7축 전부 0.** 8시드 count 도 정확히 0 이므로
  반올림 문제가 아니다. (구조적 단서는 5-2)
- **M 팔의 `plan=,act≠` 는 `discipline`·`looseness` 에만 있다.** 다른 5축은
  8시드에서 정확히 0. 2절의 산식 예측과 원자료가 맞는다
- `potcontrol` 과 `looseness` 는 D 세 칸이 전부 0 이고, T 가 M 과 모든
  칸·`aligned`·`shifted` 까지 동일하다
- `cbet_flop` 은 M 세 칸이 전부 0 이고 D 에만 `plan=,act≠` 41건이 있다
- `aggression` 의 D `plan=,act≠` 3.5% 가 전 축·전 칸 통틀어 가장 크다
- 8시드와 55시드의 비율이 어긋나지 않는다 (`aggression` D 3.46% vs 3.5%,
  `discipline` D 1.89% vs 1.8%, `bluff` D 1.16% vs 1.3%)

---

## 5. 사전등록 예측 대조

예측 원문은 `CF_DESIGN_LEVEL2.md` 8절이다. **수정하지 않았다.**

| # | 예측 문구 (원문) | 실제 관측값 | 판정 |
|---|---|---|---|
| 1 | `potcontrol D = 0 (구조적으로 확정)` | 세 칸 0.0% · 8시드·2시드 정확히 0 | **일치** (타당성 검사) |
| 2 | `potcontrol M 이 크게 나올 것` | `plan≠,act=` 2.1% — 전 축 최대 · `plan≠,act≠` 0.2% · `plan=,act≠` 0.0% | **방향 일치**, 아래 단서 |
| 3 | `aggression D 가 크고 M 도 0 이 아닐 것` | D 3.5% (전 축·전 칸 최대) / M `plan≠,act=` 0.4%(n8=37) · `plan≠,act≠` 0.2%(n8=17) | **일치** |
| 4 | `bluff D 와 M 이 둘 다 있을 것` | D 1.3%(n8=132) / M 1.7%(n8=150) · 0.6%(n8=71) | **일치** |
| 5 | `rng_shifted potcontrol 에서 가장 높을 것` | potcontrol 13.59% vs **bluff 14.88%** | **불일치** |
| 6 | `cbet_flop M = 0 (구조적으로 확정)` | 세 칸 0.0% · 8시드·2시드 정확히 0 | **일치** (타당성 검사) |
| 7 | `discipline M = 0 (구조적으로 확정)` | — | **무효** (측정 전 철회, 0절) |
| 8 | `thin_value_turn 예측하지 않는다` | — | 대조 대상 아님 |

`looseness` 는 예측 대상이 아니었다. 원 예측 블록에 없고 정정 때 대상으로
추가된 축이다.

**#2 단서.** "크게" 에 사전 정의된 허용 범위가 없다. 원문이 정성 표현이라
서열(전 축 최대)만 확인했다. 그리고 `potcontrol` M 은 `alignment_rate`
86.4% 로 하한이며, `bluff`(85.1%) 와의 서열 비교도 편향 방향을 특정할 수
없다.

**#5 가 틀렸다.** 세 표본 전부 같은 방향이다.

```
              shifted / total            55시드    8시드    2시드
potcontrol    10175/74848 · 1491/11374   13.59%   13.11%   11.93%
bluff         11136/74848 · 1683/11374   14.88%   14.80%   15.36%
```

근거로 적었던 `_allowed×2` 는 `potcontrol` 의 게이트 자리였는데, `bluff` 는
계획층 소비처가 `_allowed`·`line_bluff_prior`·`make_plan`·`river_fix` 넷이라
난수 굴림 자리가 더 많다. **예측을 쓸 때 게이트 성격만 보고 굴림 자리
개수를 세지 않았다.**

---

## 6. 측정 가능성 검증 — 8시드를 부분집합으로 쓸 수 있는가

`looseness` M 이 55시드에서 세 칸 전부 `0.0%` 로 찍혔다. 개입 래퍼가
죽은 것인지 확인했고, 아니었다.

```
축 목록 무관성    looseness 단독 8시드 vs 7축 8시드
                 update_plan 5687 / total 11374 / aligned 11365 / shifted 9
                 세 칸 count (3,4,0) — **전부 동일**
워커 재사용 무관성  시드 5000-5001 을 jobs=1 (한 워커가 두 시드 연속) 과
                 jobs=2 (워커 둘이 한 시드씩) 로 실행
                 23줄 전 칸 동일
```

따라서 시드 5000-5007 의 원자료는 55시드의 부분집합이고, `count8` 은
55시드 count 의 하한이다. `looseness` M `plan≠` 는 **4 이상 37 이하**다.

```
0.0% 의 뜻    count ≤ 37 (38 이면 0.1% 로 표시된다)
8시드 관측    4건 (0.035%) → 55시드 환산 약 26건
```

**표시된 `0.0%` 는 부재가 아니라 출력 정밀도다.** 이후 `tools/cf_axis_l2.py`
출력에 세 칸의 원시 count 를 같이 찍게 했다 (커밋 4a93fd8).

첫 재현 시도에서 `--cap 120` 을 붙여 total 이 10,466 으로 달라졌다. 원본
실행은 cap 없음(기본 3000)이었다. 원본 인자로 다시 돌려 11,374 / 11,365 /
9 가 일치하는 것을 확인한 뒤의 숫자다.

---

## 7. Level 1 교차확인

Level 1 (`CF_RESULT_LEVEL1_EXT.md`) 과 나란히 둔다. **두 층은 서로 다른
개입이므로 합산하거나 비율로 환산하지 않는다.**

```
축                L1 POST flip   L1 응답 flip   L2 D plan=,act≠   L2 M plan≠ 합
aggression            9.2%           5.7%           3.5%             0.6%
discipline            4.3%           1.6%           1.8%             0.7%
bluff                 3.5%           1.4%           1.3%             2.3%
thin_value_turn       2.7%           0.0%           1.1%             0.2%
cbet_flop             1.0%           0.0%           0.4%             0.0%
potcontrol            0.0%           0.0%           0.0%             2.3%
looseness          (해당 없음)         —             0.0%             0.0%
```

`L2 M plan≠ 합` 은 `plan≠,act=` + `plan≠,act≠` 다. 효과 크기가 아니라
계획 라벨이 달라진 빈도다.

**D 팔 서열이 Level 1 서열과 같다.**

```
L1 POST   aggression 9.2 > discipline 4.3 > bluff 3.5 > tvt 2.7 > cbet 1.0 > potcontrol 0.0
L2 D      aggression 3.5 > discipline 1.8 > bluff 1.3 > tvt 1.1 > cbet 0.4 > potcontrol 0.0
```

개입 지점과 분모(31,236 vs 74,822)가 다른데도 순서가 완전히 일치한다.
`potcontrol` 은 양쪽에서 정확히 0 이다.

**두 층의 서열이 뒤집히는 축이 둘 있다.**

```
potcontrol   L1 세 지표 전부 0.0%     L2 M plan≠ 2.3% (전 축 최대 타이)
bluff        L1 POST 3.5% (3위)      L2 M plan≠ 2.3% (전 축 최대 타이)
```

`potcontrol` 이 Level 1 에서 0 이고 Level 2 M 에서만 나타나는 것은
`CF_RESULT_LEVEL1_EXT.md` 3절의 "`potcontrol` — 계획 층 축이다" 와 방향이
같다.

`looseness` 는 양쪽 모두 실행층이 0 이다. Level 1 에서는 프리플랍 층
(`defend_tot` 2.35× / `open_pct` 1.84×)에서만 잡혔다.

**L2 D 가 L1 flip 보다 일관되게 작고 비율이 0.37~0.42 로 비슷하지만
(`aggression` 0.38, `discipline` 0.42, `bluff` 0.37, `thin_value_turn` 0.41,
`cbet_flop` 0.40) 이 비율을 해석하지 않는다.** 분모 정의와 개입 경로가
달라 같은 양을 재고 있다는 근거가 없다.

---

## 8. 이 실험이 말하지 않는 것

- **효과 크기를 말하지 않는다.** `plan≠,act=` 는 계획 라벨이 달라졌고 행동이
  같았다는 기술이지 축의 영향량이 아니다
- **`plan≠,act≠` 를 분해하지 않는다.** 어느 층·어느 산출물이 차이를
  만들었는지 식별되지 않는다
- **T 와 D·M 의 대소를 가산성으로 읽지 않는다**
- **M `plan=,act≠` 19건에서 `rel` 과 `stackoff` 의 개별 기여를 분리하지
  않았다.** `rel` 은 19/19 에서 변했고 `stackoff` 는 5/19 에서 함께 변했다.
  항상 동반하므로 이 측정만으로 분리하면 새로운 식별 문제를 만든다.
  **Level 2 의 목적은 개별 변수의 인과효과 추정이 아니라 사전등록된 구조적
  예측과 실제 관측 패턴의 교차검증이므로, 관측 가능한 단위 그대로 기록한다**
- **`potcontrol`·`bluff` 의 M 수치는 하한이다** (3절)
- **축을 1↔9 로 흔드는 것은 필드 실재 범위를 넘을 수 있다.** Level 1 과
  같은 한계다
- **D 가 계획층과 완전히 독립적이라고 말하지 않는다** (5-2). 구조적 결합은
  존재하고, 계획 라벨 변경만 관측되지 않았다

---

## 도구

```
tools/cf_axis_l2.py     네 팔 반사실 본체. 세 칸 + 원시 count
tools/diag_mleak.py     M 팔 plan=,act≠ 의 반환 state 필드 차이
tools/axis_dataflow.py  축 소비처 지도 (derive·bias·street_concept 경유)
tools/cf_axis.py        Level 1. swap / RecordRandom / ReplayRandom
```

재현:

```
python3 tools/cf_axis_l2.py \
  --axes potcontrol,aggression,bluff,thin_value_turn,discipline,looseness,cbet_flop \
  --seeds 5000-5054 --jobs 4
```
