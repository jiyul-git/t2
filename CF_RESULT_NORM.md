# ⑥-3-1 결과 — L1 ↔ L2 정규화와 잔여 차이 분해

`CF_DESIGN_ORDER.md` 3-1 의 분모 분해를 실제로 수행한 결과다.

**`CF_RESULT_LEVEL2.md`(기준점 `8be8b4e`)의 숫자는 이 문서에서 하나도
바뀌지 않는다.** 여기서 하는 것은 같은 측정을 L1 과 비교 가능한 단위·정의로
다시 읽는 일이다.

```
측정 조건   entries=24 hpl=12 stack=30000  시드 5000-5054 (55개)
            L1 과 동일하다
원자료      rows55b.jsonl.gz  261,968행 (37,424 호출 × 7축)
도구        tools/cf_axis_l2.py --rows  /  tools/l2_recount.py
```

---

## 0. 왜 기존 비교가 폐기되는가

처음에 L1 POST flip 과 L2 D 의 `plan=,act≠` 를 나란히 놓고 비율 0.37~0.42
를 얻었다. **그 비교는 성립하지 않는다.** 두 층이 다른 것을 세고 있었다.

```
분모   L1  포스트플랍 결정 31,189        (결정당 1)
       L2  update_plan 호출 × 2 = 74,848 (결정당 2, 반복 호출 포함)

정의   L1  act_lo != act_hi              (cf_axis.py:354)
       L2  각 tag 를 O 와 비교            (cf_axis_l2.py:303)
```

정의가 같은 사건을 다르게 센다. `O=fold, lo=call, hi=call` 이면 L2 는
flip 2건, L1 은 0건이다.

**0.37~0.42 는 폐기한다.** 축의 성질이 아니라 계수 규약의 차이였다.

---

## 1. 분모 정규화 — ① → ② → ③

```
①  L2 전체 update_plan            37,424      (× 2 = 74,848 비교쌍)
②  action-decision 대응 단위        31,189     ← attach_intent 가 실행된 호출
①→② 반복 호출 제거                 6,235
③  L1 대응 decision unit           31,189
```

`②` 의 기준은 `attached_O` — `plan.py:1521` 의 `intent_of(st, street) is None`
게이트가 열렸다는 직접 관측이다. 원자료에서 `attached_O == True` 가
218,323행, 7축이므로 **축당 31,189** 다. `CF_RESULT_LEVEL1.md` 의 결정 수와
같다.

**`31,236` 을 이 문서의 L2 decision unit 으로 쓰지 않는다.** 그 수는
`CF_RESULT_LEVEL1_EXT.md` 의 다른 실행에서 나온 값이고, 31,189 와의 47 차이는
아직 미검증 항목이다(7절). 원자료가 직접 센 값은 31,189 다.

**반복 호출은 행동 뒤집힘 분자에 기여하지 않는다.** `l2_recount.py` 의
`①flip` 과 `②flip` count 가 21칸 전부 정확히 같다. 소스에서 도출한 것이
원자료에서 확인됐다 — `idx>0` 에서는 `attach_intent` 가 양쪽 팔 모두
건너뛰어 `act` 가 승계된 같은 값이 된다.

---

## 2. 정의 정규화 — 같은 분모에서 정의만 바꾼 효과

```
축            팔    tag↔O (기존)   lo↔hi (L1 정의)
aggression    D        3.524%          6.862%
discipline    D        1.828%          3.603%
bluff         D        1.311%          2.617%
```

약 2배다. 기존 정의는 결정당 2회 비교를 분모로 써서 같은 사건을 절반
비율로 표시하고 있었다.

---

## 3. 정규화 후 L1 과의 대조

**단위와 flip 정의를 동일하게 맞췄다. 분모는 아직 완전히 같지 않다.**
L2 쪽에서 정렬·불변량 조건으로 13쌍이 제외돼 비교 분모가 **31,176** 이 된다
(L1 의 결정 수는 31,189).

```
축                L1 (31,189)   L2 D ② (31,176)      차
aggression           9.2%          8.234%          −0.97%p
discipline           4.3%          4.324%          +0.02%p
bluff                3.5%          3.140%          −0.36%p
thin_value_turn      2.7%          2.669%          −0.03%p
cbet_flop            1.0%          0.982%          −0.02%p
potcontrol           0.0%          0.000%           0.00%p
```

네 축은 거의 겹친다. `aggression` 과 `bluff` 에만 차가 남았다.

### 3-1. 세 숫자의 정밀도가 서로 다르다

```
L1 발표값      소수 첫째 자리 반올림값이다 (9.2%, 3.5%, …)
L1등가         같은 실행 원자료에서 센 raw count 다
L2실제         같은 실행 원자료에서 센 raw count 다
```

**`+0.02%p` 같은 차를 수치적 차이로 해석하지 않는다.** L1 의 raw count 를
같은 집합에 대입하지 않은 상태다.

---

## 4. 잔여 차이 분해 — 같은 실행 안에서

`p`(= `decide_aggression` 반환)·`size`(= `decide_size` 반환)·`src`(= intent
사유)를 팔·tag 별로 기록해 **같은 실행 안에서 L1 등가 판정을 재구성**했다.

```
crossed      roll < p 였는가.  src 로 복원한다
               act == 'bet'             → True   (size > 0)
               src == '사이즈 0 → 체크'   → True   (size == 0)
               그 외                     → False
L1등가_act   'bet' if crossed else 'check'     ← size 단계 적용 전
L2실제_act   intent 의 act                      ← size 단계 적용 후
```

`roll` 을 따로 기록하지 않았다. 필요한 것은 값이 아니라 `roll < p` 판정이고
`src` 로 정확히 복원된다.

### 4-1. ② 분모(31,176) 위에서

```
축                팔         ②쌍  L1등가flip  L2실제flip        차
potcontrol       D      31176         0         0       +0
                 M      22667       198       101      +97
aggression       D      31176      2876      2567     +309
                 M      31170       110       117        −7
                 T      31170      2960      2663     +297
bluff            D      31176      1090       979     +111
                 M      22778       257       170      +87
                 T      22778       729       608     +121
thin_value_turn  D      31176       832       832       +0
                 M      31176         0         0       +0
discipline       D      31176      1348      1348       +0
                 M      30911       378       369       +9
looseness        D      31176         0         0       +0
                 M      31130        34        25       +9
cbet_flop        D      31176       306       306       +0
                 M      31176         0         0       +0
```

**`차` 는 순효과다.** `D` 팔에서는 뒤의 2×2 가 `cx=·act≠` 를 전 축 0 으로
보여주므로 순차가 곧 "지운 건수" 지만, `M`·`T` 팔에서는 두 방향의 차다.

### 4-1-1. 2×2 — `crossed` 판정 × 최종 act

```
축                팔          쌍  cx≠·act≠  cx≠·act=  cx=·act≠   cx=·act=     L1등가   L2실제
potcontrol       D      31176         0         0         0      31176         0        0
                 M      22667        39       159        62      22407       198      101
aggression       D      31176      2567       309         0      28300      2876     2567
                 M      31170       107         3        10      31050       110      117
                 T      31170      2657       303         6      28204      2960     2663
bluff            D      31176       979       111         0      30086      1090      979
                 M      22778       160        97        10      22511       257      170
                 T      22778       600       129         8      22041       729      608
thin_value_turn  D      31176       832         0         0      30344       832      832
discipline       D      31176      1348         0         0      29828      1348     1348
                 M      30911       348        30        21      30512       378      369
                 T      30911      1687        30        21      29173      1717     1708
looseness        M      31130        24        10         1      31095        34       25
cbet_flop        D      31176       306         0         0      30870       306      306
```

```
cx≠·act=   size 단계가 flip 을 지운 것
cx=·act≠   size 단계가 flip 을 만든 것
L1등가 = cx≠ 합 (xx+xe)   ·   L2실제 = act≠ 합 (xx+ex)
```

**2×2 합계는 (b)(c) 와 전 칸 일치한다** (`l2_recount.py` 가 자체 검사한다).

**`2,876 → 2,567` 을 "중간에서 309개가 사라졌다" 로만 읽으면 안 된다.**
D 팔에서는 맞지만, `aggression` M 은 지운 것 3 · 만든 것 10 이라 순차가
−7 이고, `potcontrol` M 은 지운 것 159 · 만든 것 62 라 순차가 +97 이다.

### 4-2. 잔여 차이와의 대조

```
축            L1 발표    L1등가flip(L2 내)    L2실제flip
aggression     9.2%      2876 → 9.225%      2567 → 8.234%
bluff          3.5%      1090 → 3.496%       979 → 3.140%

축            L1 − L2실제    L1등가 − L2실제      L1 − L1등가
aggression     −0.97%p       −0.991%p (309건)    +0.02%p
bluff          −0.36%p       −0.356%p (111건)    +0.00%p
```

**건수까지 맞는다.**

### 4-3. 제외된 13쌍과 L1 발표값의 반올림 구간

`p`·`src` 는 정렬 실패 쌍에서도 기록된다. 그래서 L1등가 flip 을 **31,189
전체**에서도 셀 수 있다 — L1 의 결정 수와 같은 분모다.

```
축                L1 발표   반올림 구간(count)   L1등가(31,189)   (31,176)   구간 안
aggression         9.2%     2,854 – 2,884          2,879          2,876      예
discipline         4.3%     1,326 – 1,356          1,350          1,348      예
bluff              3.5%     1,077 – 1,107          1,090          1,090      예
thin_value_turn    2.7%       827 –   857            832            832      예
cbet_flop          1.0%       297 –   327            306            306      예
potcontrol         0.0%         0 –    15              0              0      예
```

**6축 전부 L1 발표값의 반올림 구간 안에 들어간다.** 제외된 13쌍이 담고 있던
L1등가 flip 은 `aggression` 3건, `discipline` 2건, 나머지 4축 0건이다.

```
D 팔 L1등가 비율 (분모 31,189)
  aggression 9.231%   discipline 4.328%   bluff 3.495%
  thin_value_turn 2.668%   cbet_flop 0.981%   potcontrol 0.000%
```

**한계.** L1 의 발표 백분율은 L1 자신의 `aligned` 부분집합을 분모로 쓴다
(`cf_axis.py:364`). 그 크기가 문서에 없어 31,189 와 같은지 알 수 없다.
위 반올림 구간은 분모를 31,189 로 가정해 만든 것이다.

---

## 5. 이 결과의 정확한 진술

> L1 의 flip 정의와 L2 의 `aggression`·`bluff` `crossed` 판정을 동일 실행에서
> 비교했을 때 결과가 거의 일치한다. L2 의 최종 action 은 이후 `size` 단계의
> 영향을 받으며, 이 단계에서 `aggression` D 는 309건, `bluff` D 는 111건의
> flip 차이가 발생한다. 따라서 기존 L1↔L2 의 −0.97%p / −0.36%p 잔여 차이는
> 동일 실행 내에서 관측된 `size` 단계 전후의 action 변환과 수치적으로
> 일치한다.

**"`size` 가 flip 을 제거하는 원인이다" 라고 쓰지 않는다.** 코드 구조
전체의 인과를 선언하는 것이 아니라, 동일 실행에서 `size` 적용 전후의 차이가
정확히 그 잔여 차이를 구성한다는 관측을 기록한다.

### 5-1. `size` 단계는 양방향이다

`aggression` M 에서 차가 **−7** 로 음수다.

```
aggression M   L1등가flip 110   L2실제flip 117   차 −7
```

`crossed` 판정에서는 flip 이 아니었는데 `size` 결과 때문에 최종 action 이
갈려 실제 flip 이 된 경우다.

> `size` 단계는 `crossed` 여부와 최종 action 사이에 추가 변환을 일으키며,
> 그 결과 flip 을 제거하는 경우와 새로 만드는 경우가 **모두** 존재한다.

4-1-1 의 2×2 가 두 방향을 각각 센다. `aggression` M 은 지운 것 3 · 만든 것
10, `potcontrol` M 은 159 · 62 다. **D 팔에서만 `cx=·act≠` 가 전 축 0 이라
순차를 "지운 건수" 로 읽을 수 있다.**

### 5-2. 축마다 다르다

`discipline`·`thin_value_turn`·`cbet_flop` 의 D 팔은 `L1등가flip ==
L2실제flip` 이다. 전 축에 일괄로 걸리는 현상이 아니다.

---

## 6. `potcontrol` M 의 `crossed≠` 198건 — 해소됐다

처음에 이것을 미해결 이상 징후로 적었다. **그 서술이 틀렸다.**

```
p 차 중앙 0.0000   ← aligned 22,667쌍 **전체**의 중앙값. 대부분 p 가 안 움직인다
198건             ← crossed 가 갈린 **부분집합**
```

두 수가 서로 다른 집합의 값인데 나란히 놓고 모순이라고 읽었다. 198건만
따로 보면 **전부 `|p_hi − p_lo| >= 0.001`** 이다.

### 실제 기전

198건이 전부 같은 한 가지다.

```
plan_M_lo → plan_M_hi     showdown → pot_control    198 / 198
스트리트                   turn 170 · river 28
p_M_lo == 0.0             151 / 198
```

`potcontrol` 은 `plan.py:504` 에서 계획 라벨을 가른다.

```python
if has_sd and sk('potcontrol') >= 1 and rng.random() < 0.72:
    plan = 'pot_control'
elif has_sd:
    plan = 'showdown'
```

축 1 → 게이트 미통과 → `showdown` → `decide_aggression` 의 `giveup/showdown`
분기 → `p = 0.0`.
축 9 → 게이트 통과 → `pot_control` → `p = 0.18 + 0.035·a` ≈ 0.31~0.51.

사례:

```
turn  seed5000 h42 t1 pid4
   plan   O=pot_control   lo=showdown   hi=pot_control
   p      O=0.5055        lo=0.0        hi=0.5055
   act    O=check         lo=check      hi=check
   src    lo=포기 계획 + 이니셔티브 없음 → 체크
          hi=사이즈 0 → 체크
```

**`crossed` 가 갈린 것은 `p` 가 갈렸기 때문이고, `p` 가 갈린 것은 계획
라벨이 갈렸기 때문이다.** M 팔이 하도록 설계된 그대로다.

`potcontrol` 에 실행층 소비처가 없다는 것과 모순되지 않는다 — 축이 실행층
에서 읽힌 것이 아니라, 계획 라벨이 바뀌어 `decide_aggression` 의 **분기**가
달라진 것이다.

## 7. 미검증으로 남기는 것

```
L1 harness 의 trace 40 상한(plan.py:_trace)이 31,236 을 깎았는지
CF_RESULT_LEVEL1.md 31,189 vs _EXT.md 31,236 의 47 차이 (서로 다른 실행)
두 harness 가 핸드별 1:1 동일한 시퀀스를 만드는지 (소스 구조로만 추론)
L1 은 decide_aggression 하나, L2 D 는 실행층 아홉 함수를 개입시킨다는
  개입 범위 차이가 남은 +0.02%p 를 만드는지
L1 의 raw flip count 를 31,176 공통집합에 제한해 재집계하는 것 —
  tools/cf_axis.py 가 rows 를 저장하지 않아(파일 출력 0회) 기존 산출물로는
  불가능하다. --rows 추가와 재실행이 필요하다. 이번에는 하지 않았다
L1 이 백분율 분모로 쓴 aligned 부분집합의 크기 — 문서에 없다
```

## 8. 재현

```
python3 tools/cf_axis_l2.py \
  --axes potcontrol,aggression,bluff,thin_value_turn,discipline,looseness,cbet_flop \
  --seeds 5000-5054 --jobs 4 --rows rows55b.jsonl.gz
python3 tools/l2_recount.py rows55b.jsonl.gz
```

진단 계측을 넣은 실행의 집계표는 넣기 전 실행과 **21행 바이트 단위로
일치한다.** 계측이 측정을 바꾸지 않았다.
