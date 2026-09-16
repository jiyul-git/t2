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
②  action-decision 대응 단위        31,236     ← attach_intent 가 실행된 호출
①→② 반복 호출 제거                 6,188      (16.53%)
③  L1 대응 decision unit           31,236
```

`②` 의 기준은 `attached_O` — `plan.py:1521` 의 `intent_of(st, street) is None`
게이트가 열렸다는 직접 관측이다. 원자료에서 `attached_O` 총계가
**31,189** 로 나왔고 `CF_RESULT_LEVEL1.md` 의 결정 수와 같다. 정렬·불변량
탈락 13쌍을 빼면 비교 분모는 **31,176** 이다.

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

단위·정의·분모가 모두 같아진 상태다.

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

### 5-2. 축마다 다르다

`discipline`·`thin_value_turn`·`cbet_flop` 의 D 팔은 `L1등가flip ==
L2실제flip` 이다. 전 축에 일괄로 걸리는 현상이 아니다.

---

## 6. 미해결 관찰 (이 문서의 결론에 섞지 않는다)

**`potcontrol` M 의 `crossed≠` 198건, `p` 차 중앙 0.0000 / 95% 0.0007.**

`potcontrol` 은 실행층 소비처가 없어(`CF_DESIGN_ORDER.md` 4-1) M 팔에서
`p` 가 거의 움직이지 않는데 `crossed` 가 198건 갈렸다. `p` 가 아닌 다른
경로에서 온 것이다. 원인 미확인. **다음 검증 대상으로 남긴다.**

## 7. 미검증으로 남기는 것

```
L1 harness 의 trace 40 상한(plan.py:_trace)이 31,236 을 깎았는지
CF_RESULT_LEVEL1.md 31,189 vs _EXT.md 31,236 의 47 차이 (서로 다른 실행)
두 harness 가 핸드별 1:1 동일한 시퀀스를 만드는지 (소스 구조로만 추론)
L1 은 decide_aggression 하나, L2 D 는 실행층 아홉 함수를 개입시킨다는
  개입 범위 차이가 남은 +0.02%p 를 만드는지
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
