# 배선 추적 — `refresh` / `update_plan` (턴·리버 계획 갱신)

읽기 전용이다. `plan.py` 를 고치지 않았다.
`refresh` 를 건너뛴 변종은 실행 중인 소스에서 그 호출만 뺀 `update_plan` 을
메모리에 만들어 쓴다(`inspect.getsource` → 문자열 제거 → `exec`).

재현: `python3 tools/cf_refresh.py --n 350`
위약 축(`tilt_swing`/`tilt_stack`) 바닥값 **0.0%**.

---

## 결론 먼저

| | 판정 |
|---|---|
| 호출 구조 | **정상.** 진입점이 하나고 순서가 한 곳에 정의돼 있다 |
| 계획 갱신 자체 | **작동한다.** 우회하면 7.1% 의 계획이 달라진다 |
| 성향 연결 | **`make_plan` 과 똑같이 좁다.** `bluff`/`potcontrol`/`semibluff` 뿐 |
| 강등·승격 사다리 | **성향이 전혀 없다.** `rel`/`made` 고정 임계값 |
| 플랍 성향의 생존 | **절반이 턴에서 지워진다** (49%) |

**구조적 문제**로 분류한다. 다만 `make_plan` 에서 이미 확인된 것과
**같은 성질**이라 새로운 종류의 결함은 아니다.

---

## 1. 호출 구조 — 진입점은 하나다

```
session.py:436   PL.update_plan(...)            ← 유일한 호출부
   first=(key not in h.plans or street == 'flop')

update_plan (plan.py:1423)
  ├ first 또는 state None → make_plan          (플랍마다 새로)
  └ 아니면              → runner.revise_plan   (board_changed 일 때만 make_plan 재호출)
  ↓
  if _first or _range_moved → refresh(...)      (스트리트 첫 갱신, 또는 상대 레인지가 바뀌면)
  ↓
  river_fix → _allowed → attach_intent
```

`update_plan` docstring 이 그 이유를 적어놨다 — 예전에는 session 이 다섯
함수를 직접 순서대로 불러 이력이 중간에 사라졌다. **지금은 순서가 한 곳에
정의돼 있다. 이 부분은 정상이다.**

갱신 조건도 근거가 기록돼 있다: `_rsig`(상대 레인지 내용 서명)로
**같은 스트리트 안에서도 레인지가 실제로 바뀌면 다시 갱신**한다.
내 레인지를 서명에서 뺀 이유까지 주석에 있다.

## 2. 계획을 유지하는 경우 vs 새로 계산하는 경우

상황 350개:

| | 건수 | 비율 |
|---|---|---|
| 플랍 → 턴에 라벨이 바뀜 | 70 | **20.0%** |
| 턴 → 리버에 바뀜 | 82 | **23.4%** |
| 플랍과 리버가 다름 | 114 | 32.6% |

**스트리트당 약 80% 는 라벨이 그대로 간다.** 값(`rel`·`eq`·`outs`·`made`·
`nut_adv`·`range_adv`)은 매번 갱신되고 라벨만 유지된다.

## 3. 무엇이 계획을 바꾸는가 — 사다리에 성향이 없다

`refresh` 의 강등·승격 사다리(plan.py:1730-1800)는 전부 `rel`/`made`/`outs`
고정 임계값이다.

```python
old in ('value_3street','value_2street') and rel < ctrl_thr and made <= 1   → giveup/pot_control
old == 'value_3street' and rel < 0.62                                       → value_2street
old == 'semibluff' and outs < 6                                             → value_2street/giveup
old == 'giveup' and (rel >= 0.55 or made >= 2)                              → value_2street/showdown
old in ('pot_control','block','showdown') and rel >= 0.70                   → value_2street/3street
old == 'bluff_2street' and rel >= 0.75                                      → value_2street
```

`0.62` · `0.55` · `0.70` · `0.88` · `0.75` · `6아웃` — **성향이 하나도
들어가지 않는다.**

성향이 닿는 곳은 넷뿐이다.

| 경로 | 실효성 |
|---|---|
| `rel = perceived_rel(profile, ...)` | `PS.bias` 중앙값 0.00 → 필드 절반은 보정 0 (`TRACE_PLAN.md` 5절) |
| `give_thr`/`ctrl_thr` ← `read_opponent` | `opp_est` 필요. 실측 이동 폭 작음 |
| `_bt = sk('board_texture')/7` | 턴 카드 효과 배수. 아래 측정에서 0.9% |
| **`_allowed(profile, plan, rng)`** | **실제로 거의 전부** |

## 4. 성향 반사실 — 플랍 계획을 고정하고 턴 갱신만 (n=350)

| 축 | 뒤집힘 | 가장 흔한 전환 | |
|---|---|---|---|
| `bluff` | **14.0%** | `giveup → bluff_2street` ×47/49 | ● |
| `potcontrol` | **12.9%** | `showdown → pot_control` ×43/45 | ● |
| `semibluff` | **7.4%** | `giveup → semibluff` ×13 | ● |
| `range_read` | 3.4% | `showdown → giveup` | △ |
| `discipline` | 2.3% | | △ |
| `outs` | 1.7% | | △ |
| `board_texture` | 0.9% | | △ |
| **`aggression`** | **0.6%** | | △ |
| **`looseness`** | **0.0%** | | ○ |
| **`trap`** | **0.0%** | | ○ |
| 위약 2축 | **0.0%** | | |

**`make_plan` 과 정확히 같은 세 축이고, 전환 방향까지 같다.**

전환이 `giveup → bluff_2street` 와 `showdown → pot_control` 에 몰린 것은
우연이 아니다. `_allowed` 의 강등표가 바로 그 짝이다:

```python
_down = {'bluff_2street':'giveup', 'semibluff':'showdown',
         'pot_control':'showdown', 'trap':'value_3street',
         'block':'value_2street', ...}
```

**즉 `refresh` 에서 성향이 하는 일은 사실상 `_allowed` 게이트 하나다.**
개념이 1.5 미만이면 강등, 3.5 미만이면 확률 강등. 그 위로는 아무 차이가
없다. `CF_PROFILE.md` 3절에서 잰 게이트 통과율(`bluff` 78%,
`potcontrol` 86%, `semibluff` 99%)이 그대로 여기에도 적용된다.

## 5. `refresh` 를 통째로 건너뛰면 (턴, n=350)

계획이 달라진 상황 **25 / 350 = 7.1%**

```
giveup → showdown              12
showdown → value_3street        4
giveup → value_2street          3
pot_control → value_2street     2
value_3street → value_2street   1
```

**`refresh` 는 무의미한 단계가 아니다.** 가장 많은 것이
`giveup → showdown`/`value_2street` — 즉 *"포기했으나 강도 상승"* 승격
분기가 실제로 일하고 있다. 그 분기의 도입 주석이 적어놓은
*"포기에서 나오는 길이 없었다"* 는 문제를 실제로 해결하고 있다.

다만 **7.1% 는 계획 라벨 기준**이다. 값 갱신(`nut_adv`/`range_adv`/`rel`/
`eq`)은 우회 여부와 무관하게 `decide_size`·`overbet_frac`·`bluff_mode` 가
소비하므로, 행동 영향은 이보다 클 수 있다. 여기서는 재지 않았다.

## 6. 플랍 성향이 턴 갱신에서 살아남나

`bluff` 를 1↔9 로 바꿔 **플랍 계획이 갈린** 82건을, 그다음 턴은
**같은 기준 프로필**로 갱신했다.

```
플랍에서 갈림                 82건
턴 갱신 뒤에도 계획이 다름     42건 (51%)
턴에서 같은 계획으로 수렴      40건 (49%)
```

**절반이 지워진다.** 사다리가 `old`(플랍 라벨)를 보긴 하지만, 서로 다른
`old` 가 같은 `rel` 구간에서 같은 새 라벨로 떨어지면 수렴한다.
그리고 `_allowed` 가 턴에서 다시 강등하면 `bluff_2street` 이 `giveup` 으로
되돌아간다.

**해석 주의.** 이 테스트는 턴 갱신에 기준 프로필을 썼다. 즉
"그 사람이 실제로는 기준 개념값이었다면 플랍의 다른 라벨이 살아남는가"를
물은 것이다. 실전에서는 같은 사람이 같은 개념값을 계속 갖고 있으므로
`_allowed` 재강등은 일어나지 않는다. **따라서 49% 전부를 '누수'로 읽으면
안 된다** — 사다리 수렴과 게이트 재적용이 섞여 있다.

## 7. 알려진 결함 두 개 (코드 주석이 이미 적어놓음)

**(a) `made` 승격 항이 죽어 있다** (plan.py:1777-1790 주석)

```python
elif old in ('pot_control','block','showdown') and (
        rel >= 0.70 or made >= max(2, st.get('made', 0) + 1)):
```

`st.update` 가 위에서 `st['made']` 를 새 값으로 덮어쓴 뒤라
`made >= made+1` 이 되어 **모든 값에서 거짓**이다. 실질 조건은
`rel >= 0.70` 단독이다. 주석이 이걸 알고 있고, `_prev_made` 로 고쳤다가
**되돌린 이유**(페어 보드에서 rel 0.00 짜리가 밸류로 승격)까지 적혀 있다.
`known issue E` 로 남아 있다.

**(b) `refresh` 의 `outs` 는 날것이다**

```python
outs = draw_strength(hero, board)          # refresh
outs = outs_true * PS.calc_noise(profile, 'outs', rng)   # make_plan
```

CLAUDE.md '기타 확인된 이슈' 에 이미 기록돼 있다 —
*"`refresh`의 outs 는 `draw_strength` 날것, `make_plan`의 outs 는
`calc_noise`를 거친 체감값. 불일치 (rel 은 이미 고쳤으나 outs 는 누락)"*.
이번 추적에서 그대로 확인했다. `outs` 축 반사실이 1.7% 로 낮은 것과
일관된다 — 턴 갱신에서 `outs` 개념이 체감값에 안 닿는다.

---

## 8. 최종 판정

| 항목 | 판정 |
|---|---|
| 호출 구조·순서 | **정상** |
| `_rsig` 재갱신 조건 | **정상** (근거 기록 있음) |
| 계획 갱신의 실효성 | **작동** (우회 시 7.1% 차이) |
| **강등·승격 임계값에 성향 없음** | **구조적 문제** — `make_plan` 과 동일 성질 |
| **성향이 `_allowed` 게이트 하나로 수렴** | **구조적 문제** — 게이트 통과율 78~99% |
| `made` 승격 항 (죽은 조건) | **알려진 문제.** 고쳤다 되돌린 기록 있음 → **설계 판단 필요** |
| `refresh` 의 `outs` 날것 | **불일치 확정.** CLAUDE.md 기존 기록과 일치 |
| 플랍 성향의 49% 수렴 | **영향은 있으나 설계 문제인지 판단 불가** (측정 설계상 섞임) |

## 9. 전체 판단 시스템에서의 비중

```
포스트플랍 계획 라벨이 정해지는 곳
  플랍          make_plan        (매 핸드 1회)
  턴·리버       refresh 사다리    라벨 변경률 20.0% / 23.4%

성향이 라벨을 바꾸는 폭
  make_plan     bluff 18.0% · potcontrol 16.5% · semibluff 3.5%  (CF_PROFILE)
  refresh       bluff 14.0% · potcontrol 12.9% · semibluff 7.4%  (여기)

refresh 를 통째로 빼면        계획의 7.1% 가 달라진다
```

**`refresh` 는 `make_plan` 의 축소판이다.** 같은 세 개념만 통하고,
같은 게이트(`_allowed`)로 통하고, 같은 방향(`giveup`/`showdown` 탈출)으로
움직인다. 새로운 결함이 아니라 **같은 결함이 한 번 더 있는 것**이다.

## 한계

- 상황이 합성이다. 플랍→턴→리버를 한 번에 돌리므로 실제 대국의 액션
  경로(벳·콜에 따른 레인지 축소)가 반영되지 않는다.
- **행동(폴드/콜/레이즈)이 아니라 계획 라벨만 쟀다.** `refresh` 가 갱신하는
  값들(`nut_adv`/`range_adv`)은 `decide_size`·`overbet_frac` 이 소비하므로
  사이즈 영향은 별도 측정이 필요하다.
- 6절의 49% 수렴은 측정 설계상 사다리 수렴과 `_allowed` 재적용이 섞여 있다.
