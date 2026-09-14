# 배선 추적 — `decide_response` (상대 벳에 대한 응답)

읽기 전용이다. `plan.py` 를 수정하지 않았다.
`decide_response`(plan.py:676-818), `calldown_need`(591-675),
호출부 `act_with_plan`(1212-1290) 을 읽었다.

재현:
```
python3 tools/cf_response.py --n 400
python3 tools/cf_response.py --n 400 --street river
python3 tools/cf_response.py --n 400 --read --reads
```

---

## 결론 먼저

1. **응답 단계는 계획 단계보다 성향이 훨씬 살아 있다.** 방향도 전부 맞다.
   `make_plan` 에서 `aggression` 0.5% / `looseness` 0.0% 였던 것이,
   응답에서는 `aggression` 6.8~13.0% / `looseness` 6.2~6.8% 다.
2. **아카이브에서 단조성이 안 보였던 것은 표본 때문이다.** 효과가 5%p 인데
   그 구간의 표준오차가 12.7%p 다. 원리적으로 안 보인다.
3. **새 발견 — `need` 덮어쓰기.** 상대 추정치가 있으면 84% 의 경우
   `calldown_need` 가 마지막에 `need` 를 **통째로 다시 계산해서**
   그 앞의 성향 보정을 전부 버린다. 발동 조건은 사이즈 오차 **1%** 다.
4. **새 발견 — 편향 이중 적용.** `station`·`bluff_fear` 가
   `calldown_need` 와 `decide_response` 양쪽에 **같은 계수로 두 번** 들어간다.
   단 일부 계획에서만.
5. `CF_PROFILE.md` 의 "`sizing_tell` 0.0%" 를 **정정한다.** 그건 계획 라벨
   얘기였다. 응답에서는 조건만 맞으면 **가장 큰 축(21.2%)** 이다.

---

## 1. 구조 — 계획 라벨이 분기를 가른다

`decide_response` 는 `plan` 으로 분기한다. 아카이브 120건이 실제로 탄 분기
(`trace` 의 `kind='response'` 에서 역추적):

| 분기 | 건수 | 비율 | 성향이 들어가는 자리 |
|---|---|---|---|
| 포기/블러프 + 팟오즈 미달 → 폴드 | 41 | 34.2% | 분기 자체엔 없음 (`eq < need`) |
| **편향 적용** (`need_seen`) | 39 | 32.5% | `station`·`bluff_fear`·`hero_call` |
| 밸류 레이즈 | 13 | 10.8% | `reraise`·`stackoff`·`aggr` |
| 밸류이나 콜 (굴림 실패) | 12 | 10.0% | 같은 굴림의 반대편 |
| 포기인데 팟오즈 맞아 콜 | 9 | 7.5% | 분기 자체엔 없음 |
| 블러프 레이즈 | 3 | 2.5% | `reraise`×`bluff` |
| 넛급 레이즈 | 2 | 1.7% | `aggr`·`gamble`·`reraise` |
| 세미블러프 내재오즈 | 1 | 0.8% | `outs`·`potodds` |

"분기 자체엔 없음" 이 41.7% 지만, 그 분기가 비교하는 `need` 는
`calldown_need` 에서 성향을 잔뜩 받는다. **성향이 `need` 하나로 압축되어
들어가는 구조다.**

---

## 2. 반사실 — 성향은 응답을 실제로 뒤집는다

`tools/cf_response.py`. 계획 라벨을 **고정**하고(기준 프로필로 만든
`plan_state` 를 그대로 재사용) 축만 1.0 ↔ 9.0 으로 바꿔
`act_with_plan` 을 부른다. 위약 바닥값 **0.0%** (네 조건 모두).

### 플랍 (n=400, 읽기 없음)

| 축 | 뒤집힘 | 폴드율차 | 레이즈율차 | |
|---|---|---|---|---|
| `range_read` | 12.5% | **+10.5%p** | −1.5%p | ● |
| `potodds` | 11.8% | −1.2%p | 0.0%p | ● |
| `reraise` | 9.5% | −4.0%p | **+9.0%p** | ● |
| `aggression` | 6.8% | −5.0%p | +2.5%p | ● |
| `looseness` | 6.2% | −6.2%p | 0.0%p | ● |
| `discipline` | 5.2% | **+5.0%p** | −0.2%p | ● |
| `gamble` | 4.5% | −4.5%p | 0.0%p | △ |
| `bluffcatch_river` | 4.2% | −4.2%p | 0.0%p | △ |
| `bluff` | 3.5% | −3.5%p | +3.0%p | △ |
| `sizing_tell`·`icm`·`potcontrol` | 0.0% | 0 | 0 | ○ |

### 리버 (n=400, 읽기 없음)

| 축 | 뒤집힘 | 폴드율차 | 레이즈율차 | |
|---|---|---|---|---|
| `range_read` | **25.8%** | **+24.2%p** | −4.2%p | ● |
| `aggression` | 13.0% | −7.2%p | +6.0%p | ● |
| `reraise` | 10.0% | −2.2%p | +9.8%p | ● |
| `potodds` | 8.8% | +0.2%p | +2.2%p | ● |
| `bluffcatch_river` | 7.8% | −7.0%p | +1.0%p | ● |
| `looseness` | 6.8% | −6.0%p | +0.8%p | ● |
| `gamble` | 6.8% | −4.2%p | +2.5%p | ● |
| `discipline` | 4.8% | +3.8%p | −1.0%p | △ |

**방향이 전부 맞다.**

```
discipline ↑ → 폴드 ↑          looseness ↑ → 폴드 ↓
aggression ↑ → 폴드 ↓, 레이즈 ↑  reraise ↑ → 레이즈 ↑
gamble ↑ → 폴드 ↓              bluffcatch ↑ → 폴드 ↓
range_read ↑ → 폴드 ↑  (벳한 상대의 레인지를 세게 읽는다)
```

지금까지 본 층 중 **가장 건강하다.**

### 리딩(`read`)과 상대 추정치(`opp_est`)를 넣으면 판이 바뀐다

| 축 | 플랍 (없음) | 플랍 (있음) | 리버 (없음) | 리버 (있음) |
|---|---|---|---|---|
| `sizing_tell` | 0.0% | **21.2%** | 0.0% | 0.8% |
| `range_read` | 12.5% | 13.8% | 25.8% | **40.8%** |
| `reraise` | 9.5% | 10.8% | 10.0% | 13.2% |
| `looseness` | 6.2% | **0.8%** | 6.8% | **2.2%** |
| `discipline` | 5.2% | **1.2%** | 4.8% | **1.2%** |
| `potodds` | 11.8% | **2.8%** | 8.8% | **1.5%** |

**읽기 축이 기질 축을 밀어낸다.** 원인은 4절이다.

---

## 3. 아카이브에서 단조성이 안 보인 이유는 표본이다

`REVIEW_2.md` 1절에서 응답 단계를 이렇게 적었다:

```
aggression 2~4  n=36  레이즈 11%  콜 44%  폴드 44%
aggression 4~6  n=33  레이즈 24%  콜 27%  폴드 48%
aggression 8~10 n=27  레이즈 11%  콜 33%  폴드 56%
→ 단조성 없음
```

반사실이 예측하는 폴드율 차이는 **−2.2 ~ −7.2%p** 다.
그 표본의 표준오차는

```
SE = sqrt(0.5·0.5·(1/36 + 1/27)) ≈ 12.7%p
```

**효과의 두 배가 표준오차다.** 이 표본으로는 원리적으로 볼 수 없다.
"단조성이 없다" 는 관측은 **배선 문제의 증거가 아니었다.**

---

## 4. 새 발견 — `need` 덮어쓰기 (`calldown_need` 끝)

```python
# plan.py:665-672
need *= PS.call_bias(profile, street, _sz_seen, made_now, bot.draw_strength(...))
# 오독한 사이즈로 팟오즈를 다시 계산한다 (인식이 곧 판단 근거다)
if abs(_sz_seen - _sz_true) > 1e-9:
    _p0 = float(pot) - tocall
    need = (_sz_seen*_p0)/max(1.0, _p0 + 2*_sz_seen*_p0)     # ← 통째로 덮어쓴다
```

`need` 에 **대입**이다. 곱이 아니다. 발동하면 그 앞의 전부가 버려진다:

- `potodds` 계산 오차 (`calc_noise`)
- `to_act_behind` 가산
- 배팅라인 리딩 `trust` (`range_read`·`bluffcatch_*`·`sizing_tell`·`aggr`)
- 상·하한 클램프
- 바로 윗줄의 `call_bias` (`station`·`bluff_fear`·`draw_love`·`sticky`)

### 얼마나 자주 발동하나 (표본 3,000)

| `opp_est` | 발동률 | 사이즈 오차 중앙 |
|---|---|---|
| 없음 | **0.0%** | — |
| 있음 | **84.1%** | **1%** |

`_sz_seen` 은 `opp_size_norm`(상대 기준 정규화) → `size_read`(내 인식 한계)
를 거친다. `size_read` 는 2팟 이하면 그대로 돌려주므로, 실전 사이즈에서는
**`opp_size_norm` 하나가 발동 여부를 정한다.** 상대 추정치가 있으면
정규화가 거의 항상 값을 조금 바꾸고, 그 "조금"이 **1%** 여도
`> 1e-9` 를 통과한다.

**사이즈를 1% 다르게 인식한 것이 성향 보정 전체를 지우는 근거가 된다.**

이것이 3절 표의 "읽기 축이 기질 축을 밀어낸다"의 정체다.
`opp_est` 가 들어오는 순간 `looseness`·`discipline`·`potodds` 가
6.2/5.2/11.8% → 0.8/1.2/2.8% 로 내려앉는다.

**정정 — `TRACE_NEEDPATH.md` 에서 방향이 뒤집혔다.**
후속 조사 결과 덮어쓰기 식 `sz/(1+2sz)` 이 **교과서 팟오즈와 완전히 같고**,
그 앞의 `need_true = tocall/pot_live` 가 분모에서 내 콜을 빼먹어
`(1+sz)` 배 과대평가하고 있었다. 즉 **덮어쓰기가 틀린 산수를 우연히
고치는 중**이고, 대가로 성향 체인을 버린다. 자세한 것은
`TRACE_NEEDPATH.md` 1~2절.

---

## 5. 새 발견 — 편향 이중 적용

`station` 과 `bluff_fear` 가 두 곳에서 **같은 계수로** 적용된다.

```python
# persona.call_bias (calldown_need 에서 호출) — 모든 계획에 적용
m *= 1.0 - 0.22*max(0.0, bias(prof,'station'))
m *= 1.0 + 0.30*bf*w*min(1.5, max(0.5, size_frac/0.6))       # bluff_fear

# plan.decide_response 마지막 블록 — 폴백 계획에만 적용
need_seen *= max(0.55, 1.0 - 0.22*max(0.0, PS.bias(profile,'station')))
need_seen *= 1.0 + 0.30*max(0.0, PS.bias(profile,'bluff_fear'))*_bf_w
```

`0.22` 와 `0.30` 이 그대로 같다.

**폴백 계획**(`pot_control`·`showdown`·`block` 등, 아카이브 32.5%)은
두 번 받고, `giveup`·`bluff_2street`·`semibluff`·밸류 계획은 한 번만 받는다.
`station` 편향 1.0 인 사람이라면 폴백에서 `0.78 × 0.78 = 0.61`,
다른 계획에서 `0.78` 이다.

계획에 따라 같은 사람의 콜 성향이 **1.28배 차이난다.**

---

## 6. `CF_PROFILE.md` 정정

거기서 `sizing_tell` 을 "라벨에 영향 0 — 계획을 하나도 바꾸지 않는다"고
썼다. **계획 라벨 얘기로는 맞다.** 하지만 응답에서는 다르다.

- 리딩(`read`)을 안 넘기면 0.0%
- 넘기면 플랍에서 **21.2%, 폴드율 −13.2%p** 로 가장 큰 축

`calldown_need` 의 `trust` 블록 전체가 `if read is not None` 안에 있어서,
`read` 없이 부르면 `range_read`·`bluffcatch_*`·`sizing_tell` 이 통째로
꺼진다. **반사실에서 `read` 를 안 넘긴 것은 내 설계 실수였다.**
`tools/cf_response.py --read` 로 켠다.

---

## 7. 아직 안 본 것

- 4절 덮어쓰기가 **행동을 얼마나 바꾸는지**는 안 쟀다. 발동률과 버려지는
  항목까지만 확인했다. 재려면 `plan.py` 를 고쳐야 하는데 baseline 지문이
  깨지므로 별도 브랜치가 필요하다.
- 5절 이중 적용도 같은 이유로 크기는 미측정이다.
- `refresh`/`update_plan`(턴·리버 계획의 37%)은 여전히 미추적.
- 이 조사는 `decide_response` 만 봤다. `mdf` 반응 정확도와 BB 혼합층은
  건드리지 않았다.
