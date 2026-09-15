# ⑤ Level 2 설계 — 계획 층 반사실 (실험 명세)

`CF_RESULT_LEVEL1_EXT.md` 가 만든 질문에 답하는 실험이다.
**코드보다 명세를 먼저 고정한다.**

---

## 0. 질문

```
관측 (④)     축 → 행동 연관
Level 1 (⑤)  축 → execution-layer parameter → action     ← 끝났다
Level 2       축 → plan → execution → action              ← 이 실험
```

> **축이 행동을 직접 조절하는가, 아니면 계획을 바꿔서 행동을 바꾸는가?**

Level 1 이 이 질문을 만들었다.

```
potcontrol   실행 층 0.0% (POST·응답 전부) 인데 ④ 라우팅 ρ +0.466
             → 계획 층 축의 강한 후보
aggression   실행 층 9.2% / 5.7% 로 최대
             → 직접 조절의 강한 후보
```

둘을 **같은 실험에서** 비교한다.

---

## 1. 세 팔이 아니라 **네 팔** — 매개 분해

Level 1 과 중복되는 경로를 분리해야 한다. 단순히 "축을 바꾸고 전체를
다시 돌린다"로는 직접 효과와 계획 매개 효과가 섞인다.

```
팔 0  원본                      축 = 원래 값, 모든 지점
팔 D  직접(direct)              축을 decide_aggression/decide_response 에서만 바꾼다
                                → Level 1 이 이미 잰 것
팔 M  매개(plan-mediated)       축을 make_plan 계열에서만 바꾸고
                                실행 층에는 **원래 값**을 넣는다
팔 T  전체(total)               모든 지점에서 바꾼다
```

판정:

```
T ≈ D,  M ≈ 0      축이 행동을 **직접** 조절한다
T ≈ M,  D ≈ 0      축이 **계획을 바꿔서** 행동을 바꾼다
T > D + M          상호작용이 있다 (계획과 실행이 같은 방향으로 겹친다)
T < D + M          상쇄가 있다
```

`T = D + M` 이 성립하지 않을 수 있다는 것을 **미리 적어둔다.**
비선형 경로이므로 가산성을 가정하지 않는다.

---

## 2. 개입 지점 — `make_plan` 계열의 축 소비처

`update_plan`(`plan.py:1444`)이 계획 갱신의 유일한 진입점이다.

```
first or state is None  →  make_plan(seed=seed)
else                    →  runner.revise_plan(...)
        ↓
prev 이력 계승 (intents·deviations·streets·refreshed·bet_streets·plan_since·_rsig)
        ↓
_rsig 비교 → 바뀌었거나 first 면 refresh(...)
        ↓
river_fix(...)
        ↓
_allowed(profile, plan, rng)        ← 축 게이트가 여기 또 있다
        ↓
attach_intent(...)                  ← Level 1 이 덮은 곳
```

**개입 대상**: `make_plan` · `revise_plan` · `refresh` · `river_fix` ·
`_allowed`. 즉 `attach_intent` **직전까지**.

축별로 어느 함수를 타는지는 `tools/axis_sites.py` 로 전수 확인한 뒤
`SITE_L2` 표에 박는다. **Level 1 에서 `aggression → open_pct` 를
빠뜨린 것과 같은 실수를 반복하지 않는다.**

---

## 3. RNG — Level 1 보다 훨씬 어렵다

### 3-1. 단축 평가가 확실히 걸린다

```python
plan.py:447   if sk('blockbet')   >= 1  and rng.random() < block_p:
plan.py:456   if sk('potcontrol') >= 1  and rng.random() < _pc_p:
plan.py:468   elif ... sk('semibluff') >= 0.4 and rng.random() < ...:
```

`sk()` 는 0~3 스케일이라 게이트 `>= 1` 은 `PS.sk >= 3.33` 이다.
**축을 1↔9 로 흔들면 반드시 게이트를 넘나든다** → 난수 소비 횟수가
달라진다. `potcontrol` 은 Level 2 의 주인공인데 정확히 그 축이다.

### 3-2. `_allowed` 도 rng 를 쓴다

```python
plan.py:1634   if rng.random() > (s-1.5)/2.0:  return _down[plan]
```

`PS.sk` 가 1.5~3.5 구간일 때만 굴린다. 축을 바꾸면 이 구간 진입 여부가
바뀌어 또 어긋난다.

### 3-3. 대응 — 기록·재생 + 3그룹, Level 1 과 동일

```
RecordRandom   원본 팔이 뽑은 난수를 순서대로 기록
ReplayRandom   개입 팔에 같은 순서로 먹인다
분류           rng_aligned / rng_shifted / invariant_failed
               **rng_shifted 를 정상 집계에 섞지 않는다**
```

`make_plan` 은 `rng = random.Random(seed)` 를 **내부에서** 만든다
(`plan.py:265`). 밖에서 래퍼를 끼울 수 없으므로 `plan.random` 을
shim 으로 교체해 `Random(seed)` 가 기록·재생 객체를 돌려주게 한다.

**게이트 축은 `rng_shifted` 비율이 높을 것으로 예상한다.** 그 비율 자체를
결과로 보고하고, 정렬된 부분집합에서만 효과를 낸다. 정렬 비율이 너무
낮으면 **그 축은 Level 2 로 측정 불가**라고 기록한다.

---

## 4. 불변량 — Level 2 에서는 실제로 검사해야 한다

Level 1 은 상황 입력을 세 팔에 동일하게 넘겨 **구조적으로** 보장됐다.
Level 2 는 `make_plan` 이 상황 지표를 **내부에서 계산**하므로 검사가
필요하다.

```
공통 불변량 (반환 state 에서 비교)
  eq · eq_current · outs_true · made · board · pot · tocall
  n_opp · oop · initiative · my_range 서명 · opp_range 서명

축별 예외 (인과 경로이므로 변해도 된다)
  draw_love · overpair_love  →  rel        (perceived_rel 이 읽는다)
  outs                       →  outs       (calc_noise 를 탄다)
  board_texture              →  nut_adv · range_adv  (확인 필요)
```

`eq` 는 `equity_vs_combos` 가 **내용에서 crc32 로 시드를 유도**하므로
(CLAUDE.md) 입력이 같으면 같아야 한다. 다르면 오염이다.

**하나라도 깨지면 그 축의 결과를 해석하지 않고 코드에서 원인을 먼저
찾는다.**

---

## 5. 기록할 것 — plan flip 과 action flip 을 **반드시 분리**

```
지표                  의미
plan flip            계획 라벨이 바뀌었는가 (전환 행렬)
action flip          최종 행동이 바뀌었는가 (전환 행렬)
plan≠ & action=      계획은 바뀌었는데 실행 층이 흡수했다
plan= & action≠      계획은 같은데 행동이 바뀌었다 (= 직접 효과)
direction            높은 축이 어느 방향으로
magnitude            f 변화량
rng_aligned          정렬 비율
invariant pass       불변량 통과 비율
```

`plan≠ & action=` 과 `plan= & action≠` 의 **두 칸이 이번 실험의 핵심
출력**이다. 0절 질문에 직접 답한다.

---

## 6. 위약

`_rand_A` / `_rand_B` 를 같은 파이프라인에 태운다.
Level 1 과 같이 **결정론적으로 정확히 0** 이어야 한다.

```
plan flip 0건 · action flip 0건 · 불변량 위반 0건 · rng_shifted 0건
```

`rng_shifted` 가 0 이어야 하는 것이 Level 1 보다 강한 요구다 — 위약은
게이트를 넘나들지 않으므로 난수 소비가 같아야 한다.

---

## 7. 측정 조건

```
entries=24 · hpl=12 · start_stack=30000    ④·⑤ Level 1 과 동일
시드          5000–5054 (55개). 같은 궤적 위에서 개입
개입 값        1 과 9
축            potcontrol · aggression 을 먼저 (0절 질문의 두 후보)
             그 다음 discipline · bluff · thin_value_turn · cbet_flop
             looseness 는 make_plan 소비처가 없으므로 제외 — 확인 후 결정
```

---

## 8. 측정 전 예측 (수정 금지)

Level 1 에서 예측 둘이 다 틀렸다. 그래도 적어둔다 — 적어두지 않으면
결과를 보고 설명을 만들게 된다.

```
potcontrol    D ≈ 0 (Level 1 에서 이미 0), M 이 크게 나올 것
              → "계획을 바꿔서 행동을 바꾼다" 의 사례
aggression    D 가 크고 M 도 0 이 아닐 것
              → make_plan×2 소비처가 있으므로 계획 경로도 있다
cbet_flop     D 작음(1.0%). M 은 모른다 — 예측하지 않는다
rng_shifted   potcontrol 에서 가장 높을 것 (게이트 축)
```

**`cbet_flop` 의 M 은 근거가 없어 예측하지 않는다.** 근거 없는 예측을
적으면 맞아도 우연이고 틀려도 배울 게 없다.

---

## 9. 이 실험이 말하지 않을 것

```
- 하류 전파는 여전히 못 본다. 한 결정의 계획·실행만 본다
- T = D + M 가산성을 가정하지 않는다
- rng_shifted 비율이 높은 축은 효과크기를 신뢰할 수 없다
- 축 1↔9 는 필드 실재 범위를 넘을 수 있다
- entries=24 / hpl=12 / stack=30000 조건이다
```
