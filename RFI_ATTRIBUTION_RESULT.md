# RFI 계수 변경 attribution — 결과

기준일 2026-09-28. 분석 브랜치 `tmp/claude-rfi-attribution-20260928` (test `1a23123` 에서 분기).
**production / test 코드 무수정.** 추가한 것은 `tools/rfi_*.py`, `tools/draw_rfi_attr.py`,
이 문서, `docs/RFI_ATTR_V1.png` 뿐이다.

그림: `docs/RFI_ATTR_V1.png` (`python3 tools/draw_rfi_attr.py --repo <ca418d2 worktree>`)

---

## 0. 결론 먼저

1. **regression 격차(VPIP 20.7→23.0, flop 47.2→56.1)의 대부분은 RFI 변경이 만든 것이 아니다.**
   RFI 커밋 `ca418d2` 가 단독으로 만든 변화는 VPIP **+2건/1380**(+0.13%p), PFR **0**,
   flop **+1핸드/180**(+0.56%p)이다. 나머지 VPIP +32건 · flop +15핸드 · PFR +2건은
   동결 기준 `0962cb2` 와 RFI 직전 `e17be45` 사이(first-parent 179커밋)에 이미 있었다.
2. **PFR 이 그대로인 것은 우연한 상쇄라기보다 구조적 상쇄다.** 이 레시피의 결정은 전부
   `ante=False` 이고 유효스택 90~343bb 이다. 새 표는 이 조건에서 100~170bb 오픈을 넓히고
   170bb 이상을 좁힌다. unopened 결정의 59% 가 130~160bb 에 몰려 있다. 짝지은 기대 오픈 수
   변화는 결정 745건에서 Σ = **+0.78**(100–170bb +2.61, ≥170bb −1.82)이다.
   실측 1차 뒤집힘도 3건 늘고 3건 줄었다.
3. **RFI 변경이 행동을 바꾸는 통로는 둘이다.** `OPEN_DEC`(오픈/아이소 결정의 `_open`)와
   `POST_RANGE`(포스트플랍마다 다시 만드는 프리플랍 레인지 모델)다. 디펜스 결정·프리플랍
   레인지 모델·관찰(rfi_exp) 채널은 단독으로는 지문을 하나도 바꾸지 않았다.
4. **seed 3000/3001/3002/3004 의 최초 divergence 는 포스트플랍이다.** 원인은 `POST_RANGE` 이고
   RNG 밀림이 아니다. 새 표에서 `my_r`/`opp_r` 크기가 바뀌면 `nut_adv`·`range_adv`·`eq` 가
   바뀌고, 결국 계획 라벨이나 벳 사이즈가 바뀐다.
5. **VPIP +2 / PFR 0 / flop +1 은 전부 `OPEN_DEC` 1차 뒤집힘이 있는 핸드에서 나왔다.**
   오픈이 새로 생기면 원래 열던 뒷사람이 콜러로 바뀐다(VPIP +1, PFR ±0).
   오픈이 사라지면 림프/컴플리트가 생긴다(PFR −1, VPIP ±0, flop +1).

---

## 1. 대상 커밋과 레시피

`tmp/rfi-coeff-shadow-20260928` 은 원격에 없다(`git ls-remote` 로 확인). test 에서 RFI 변경은
`ca418d2 calibration: update RFI base depth and ante coefficients` 하나이고, 그 뒤 두 커밋은
이 레시피에서 동작이 없다.

| 커밋 | 변경 | 레시피 지문 |
|---|---|---|
| `e17be45` | (RFI 직전) | 기준 |
| `ca418d2` | `gto.py` 데이터 표 넷: `RFI_BY_BEHIND`(7~2), `_DEPTH_EARLY`, `_DEPTH_LATE`(75→70 매듭 포함), `ANTE_MULT[False]` 0.90→0.762 | 6/6 변화 |
| `ce5c118` | `gto._use_mtt8_ante_defense` 게이트 (`gto.py:180`) | `ca418d2` 와 6/6 동일 |
| `1a23123` | `preflop.defend_thresholds` `_finish_widths` (`preflop.py:532-543`) | `ca418d2` 와 6/6 동일 |

`ce5c118`·`1a23123` 은 `ante=True and seats==8` 에서만 작동한다. 레시피 결정 1,427건은 전부
`ante=False` 다(9맥스 1,166 / 8맥스 261).

레시피는 `tools/regress.py` 와 같다: `Tournament(entries=100, start_stack=30000, hero_seat=7,
seed=sd, hands_per_level=200)`, seeds 3000–3005, 30핸드, 히어로 전부 폴드. VPIP/PFR 는 비히어로
각 플레이어의 첫 프리플랍 액션 기준이다. `tools/rfi_ladder.py` 로 `0962cb2` 를 돌리면
`tools/baseline_9max_post_f8.json` 의 per-seed 지문 6개가 **정확히** 재현된다.

| rev | VPIP | PFR | flop | 비고 |
|---|---|---|---|---|
| `0962cb2` | 283/1368 = 20.69% | 165 = 12.06% | 85/180 = 47.22% | 동결 기준 |
| `e17be45` | 315/1379 = 22.84% | 167 = 12.11% | 100/180 = 55.56% | RFI 직전 |
| `ca418d2` = `ce5c118` = `1a23123` | 317/1380 = 22.97% | 167 = 12.10% | 101/180 = 56.11% | RFI 후 |
| **RFI 단독 (ca418d2 − e17be45)** | **+2** | **0** | **+1** | |
| RFI 이전 누적 (e17be45 − 0962cb2) | +32 | +2 | +15 | 이번 범위 밖 |

---

## 2. 실행 경로 — `gto.rfi` 를 읽는 곳 전수

`ca418d2` 는 표만 바꿨다. 그 표를 읽는 함수는 `gto.rfi`(`gto.py:98-106`, `depth_mult` `gto.py:74-77`)
하나다. seed 3000 전수 호출 스택 결과(`tools/rfi_channel_split.py` 분류, 미분류 2건은 아래):

| 채널 | 호출 경로 (ca418d2 줄번호) | 소비처 |
|---|---|---|
| OPEN_DEC | `plan.preflop_plan:2216/2229` → `preflop.open_decision:298` / `iso_decision:821` → `preflop._open:31` → `persona.open_pct:398`(+`avg_rfi` :409) | 오픈/아이소 역치 `thr` |
| DEF_DEC | `plan.preflop_plan:2241` → `preflop.defend_decision:752` → `defend_action_likelihoods:626` → `defend_thresholds:530/531` → `gto.defend_pct`(`DEF_A + DEF_B·rfi(opener)`) | 디펜스 `(tp, tot)` |
| PF_RANGE | `session._run:1270` → `session._preflop_perceived_range:1120` → `ranges.preflop_range` | `_pf_call_ev_shadow` (`strategy_consumer: False`) |
| POST_RANGE | `session._run:1607`(my_r) / `:1650`(orange) / `_locked_postflop_range:1172` → `ranges.preflop_range:236` (`_base_open = pf._open`, **`ranges.py:228` import 시점 바인딩**) · `:249` (`_def_thresholds`) | `session.py:1806` `PL.update_plan(..., my_r, opp_r, ...)` |
| OBS | `session.py:1467` `_GTO.rfi(...)` → `book.observe_preflop(rfi_exp)` → `reads.py:305-310` `rfi_rel` → `persona.py:943` `open_gap` | `preflop.table_pressure:272` 등 |
| (미분류) | `plan.preflop_plan:2257` → `preflop.calloff_cap:875` → `defend_thresholds` | F8-D6-D1 legacy 비교 기록. 모든 arm 에서 옛 표를 받았는데도 ALL_NEW 가 `ca418d2` 지문을 재현했으므로 무영향 |

test HEAD(`1a23123`)에서는 `preflop.py` 줄번호만 +12 밀린다: iso 역치 821→833,
`defend_action_likelihoods` 626→638, `calloff_cap` 875→887. 다른 파일은 `ca418d2` 와 같다.

**측정 공백이 하나 있었다.** 앞 단계의 `tools/rfi_decision_cf.py` 는 결정 745건만 가로챘는데,
`gto.rfi` 호출 census 는 `persona.py:398` 호출을 3,215건 셌다. 원인은 위 표의 POST_RANGE 다.
`ranges.py:228` 이 `pf._open` 을 import 시점에 바인딩하므로 `preflop._open` 패치에 안 걸리고,
포스트플랍 레인지를 만들 때마다 `open_pct` 가 불린다(seed 3000: `_open` 125회, `open_pct` 772회).

---

## 3. 채널 녹아웃 (`tools/rfi_channel_split.py`)

`gto.rfi` 를 감싸고 호출 스택 기준으로 채널을 가른다. 채널마다 새 표와 옛 표 중 하나를 준다.
arm 마다 별도 프로세스로 돌렸다(`persona._TILT_VIEW_CACHE` 대회 간 오염).
N = `ca418d2` 지문, O = `e17be45` 지문, x = 둘 다 아님.

| arm | 3000 | 3001 | 3002 | 3003 | 3004 | 3005 | VPIP | PFR | flop |
|---|---|---|---|---|---|---|---|---|---|
| ALL_OLD (대조) | O | O | O | O | O | O | 315/1379 | 167 | 100 |
| ALL_NEW (대조) | N | N | N | N | N | N | 317/1380 | 167 | 101 |
| ONLY_OPEN_DEC | x | x | O | x | x | x | 314/1379 | 167 | 99 |
| ONLY_DEF_DEC | O | O | O | O | O | O | 315/1379 | 167 | 100 |
| ONLY_PF_RANGE | O | O | O | O | O | O | 315/1379 | 167 | 100 |
| ONLY_POST_RANGE | x | x | **N** | x | x | O | 316/1373 | 167 | 101 |
| ONLY_OBS | O | O | O | O | O | O | 315/1379 | 167 | 100 |
| DROP_OPEN_DEC | x | x | N | x | x | O | 315/1373 | 167 | 100 |
| DROP_DEF_DEC | N | N | N | N | N | N | 317/1380 | 167 | 101 |
| DROP_PF_RANGE | N | N | N | N | N | N | 317/1380 | 167 | 101 |
| DROP_POST_RANGE | x | x | O | x | x | x | 315/1379 | 167 | 100 |
| DROP_OBS | N | N | N | N | N | x | 316/1380 | 167 | 100 |

- 대조 두 개가 성립한다. 그래서 채널 분리를 믿는다.
- **DEF_DEC · PF_RANGE · OBS 는 단독으로 0 이다** (ONLY 6/6 = O, DROP_DEF_DEC·DROP_PF_RANGE 6/6 = N).
- seed 3002 는 **POST_RANGE 하나로** 완전히 설명된다(ONLY_POST_RANGE = N).
- seed 3005 는 OPEN_DEC · POST_RANGE · OBS 가 모두 있어야 새 지문이 된다. OBS 는 단독 효과는 0 이지만
  OPEN_DEC 가 오픈을 바꾼 **뒤에** `rfi_did/rfi_exp` 가 달라지는 상호작용으로만 작동한다.
- 나머지 네 시드는 OPEN_DEC 와 POST_RANGE 가 둘 다 있어야 한다. 효과는 가산적이지 않다
  (ONLY 두 개의 합 ≠ ALL_NEW).

---

## 4. 1차 결정 효과 — 짝지은 반사실 (`tools/rfi_preflop_cf.py`)

프리플랍 결정은 전부 `session.py:1357` `PL.preflop_plan(...)` 한 곳을 지난다. 그 호출을 감싸
**같은 상태**에서 표 넷만 반대쪽으로 바꿔 한 번 더 부른다. `h.rng` 는 스냅샷 후 복원하고,
dict/list 인자는 복사본을 넘긴다. 감싼 실행의 지문이 양쪽 궤적 모두 원래 지문과 **6/6 같다.**
짝 호출이 게임에 부작용을 남기지 않았다는 뜻이다.

두 궤적에서 모두 쟀다.
- 신궤적 = `ca418d2` 실행, 반사실 = 옛 표 (결정 1,427)
- 옛궤적 = `e17be45` 실행, 반사실 = 새 표 (결정 1,427)

### 항목 1·2·5 — unopened (오픈 / 림프 / 쇼브)

| | 결정 | 옛 표 행동 | 새 표 행동 | 뒤집힘 |
|---|---|---|---|---|
| 신궤적 | 657 | raise 119 · limp 35 · shove 4 · fold 499 | raise 119 · limp 34 · shove 3 · fold 501 | 8 |
| 옛궤적 | 653 | raise 121 · limp 35 · shove 1 · fold 496 | raise 120 · limp 34 · shove 1 · fold 498 | 6 |

뒤집힘 전부 (신궤적 기준, 비율 = 그 자리의 새 RFI / 옛 RFI):

| seed h | 좌석 | 스택 | 핸드 (pct) | 옛 → 새 | RFI 비율 |
|---|---|---|---|---|---|
| 3001 h11 | HJ | 139.0bb | K6s (.216) | fold → raise | ×1.027 |
| 3001 h14 | UTG+2 | 90.5bb | QJo (.198) | fold → raise | ×1.095 |
| 3005 h14 | UTG+1 (8max) | 114.0bb | KQo (.103) | fold → raise | ×1.095 |
| 3000 h27 | UTG | 239.5bb | K7s (.154) | raise → fold | ×0.862 |
| 3004 h25 | UTG+1 | 297.5bb | AQo (.094) | raise → fold | ×0.877 |
| 3005 h20 | BTN (8max) | 202.0bb | A7o (.333) | raise → fold | ×0.932 |
| 3003 h15 | UTG+1 | 343.0bb | QTo (.172) | limp → fold | ×0.877 |
| 3000 h22 | BTN | 31.5bb | K3o (.517) | shove → fold | ×0.894 |

- 넓힘은 전부 90~146bb, 좁힘은 전부 ≥202bb 또는 31.5bb 다. **방향이 전부 RFI 비율의 부호와 맞는다.**
- 옛궤적의 6건은 신궤적 8건 중 6건과 같은 자리·같은 핸드다(3000 h27 은 스택만 262bb).
  3000 h22 쇼브와 3001 h14 는 신궤적에만 있다. 그 자리의 스택이 이미 달라져 있었기 때문이다.
  3000 h22 seat9 는 옛궤적 113bb / 신궤적 31.5bb, 3001 h14 seat2 는 옛궤적 147bb / 신궤적 90.5bb 다.
  옛궤적에서는 같은 핸드가 새 표로도 fold 였다. 즉 이 두 건은 **2차 상태 변화 위에 얹힌 1차 뒤집힘**이다(6절).

### 항목 3 — 상대가 먼저 연 뒤 (vs_open)

| | 결정 | call | 3bet | fold | 뒤집힘 |
|---|---|---|---|---|---|
| 신궤적 | 618 | 111 | 19 | 488 | **0** |
| 옛궤적 | 610 | 108 | 19 | 483 | **0** |

디펜스 역치는 실제로 움직였다. `gto.defend_pct` 가 `DEF_A + DEF_B·rfi(opener)`(`gto.py:199`)이므로
605/618 결정에서 `(tp, tot)` 가 달라졌다. 하지만 크기가 작다. Σ|Δtot| = 1.293, 최대 |Δtot| = 0.021,
ΣΔtot = +0.318 이다. 옛 역치와 새 역치 **사이에 hand_pct 가 끼는 결정은 0건**이었다.
균등 핸드 가정의 기대 뒤집힘이 ~1.3건이므로, 0건 관측은 표본 안에서 이상하지 않다.

### 항목 4 — opener back-action (내가 연 뒤 3벳을 받음)

신궤적 21 / 옛궤적 22 결정, 뒤집힘 **0**. 역치는 12/21 결정에서 움직였지만
Σ|Δtot| = 0.003, 최대 0.0005 다. cold 3벳 대면(vs_3bet_cold) 43건도 뒤집힘 0이다
(Σ|Δtot| 0.032). 역치 이동이 왜 vs_open 보다 두 자릿수 작은지는 따라가지 않았다.

### 아이소 (vs_limp)

신궤적 88건 중 1건: 3005 h19 LJ 145.5bb 33 fold → raise (×1.049).
옛궤적 99건 중 1건: 3000 h23 HJ 248bb T9o raise → fold.

---

## 5. 항목 10 — PFR 은 상쇄된 것인가, 원래 안 변한 것인가

**둘 다지만, 주된 것은 구조적 무변화다.**

결정마다 `_open` 을 새 표와 옛 표로 짝 계산했다(`open_new_old`). Σ(새 − 옛)은 균등 핸드 가정에서
오픈 범위에 들어오는 핸드 수의 기대 변화다(`table_pressure` 등 곱하기 전).

| 구간 | 신궤적 n | ΣΔ_open | 옛궤적 n | ΣΔ_open |
|---|---|---|---|---|
| 전체 (unopened+vs_limp) | 745 | **+0.78** | 752 | **+0.91** |
| <100bb | 51 | −0.01 | 32 | −0.09 |
| 100–170bb | 553 | **+2.61** | 595 | **+2.77** |
| ≥170bb | 141 | **−1.82** | 125 | **−1.77** |

- 같은 레시피를 무한히 돌려도 기대 오픈 수 변화는 결정 750건당 약 +0.8~0.9건이다.
  **표 변경 자체가 이 스택 분포에서는 거의 0 이다.**
- 원인은 표의 모양이다. `_DEPTH_EARLY`/`_DEPTH_LATE` 의 250bb 매듭(0.72/0.78)은 그대로다.
  반면 50–100bb 매듭은 올라갔고(예: LATE 100bb 0.82→1.023), `ANTE_MULT[False]` 는 모든 호출에서
  0.90→0.762(−15.3%)로 내려갔다. 그래서 ante=False 에서 새/옛 비율이 ~150–170bb 부근에서
  1 을 가로지른다(그림 (b)).
- 실현값은 1차 뒤집힘 +3/−3(오픈), shove −1, limp −1, 아이소 +1 이다. 기대값 +0.8 과 모순되지 않는다.

**실현 PFR 구성**(첫 액션 기준, 두 궤적의 실제 실행):

| 상황 | e17be45 | ca418d2 | Δ |
|---|---|---|---|
| unopened raise | 121 | 119 | −2 |
| unopened shove | 1 | 3 | +2 |
| vs_limp raise(아이소) | 24 | 24 | 0 |
| vs_open 3bet | 19 | 19 | 0 |
| vs_3bet_cold 3bet | 2 | 2 | 0 |
| **PFR 합** | **167** | **167** | **0** |

unopened raise −2 를 shove +2 가 메웠다. 이 shove +2 는 1차 효과가 아니다.
seed 3000 좌석 9 한 사람의 스택이 바뀐 **2차 효과**다(6절). 즉 실현 PFR 0 은
"구조적으로 거의 0" 위에 "2차 효과의 우연한 상쇄 ±2" 가 얹힌 결과다.

---

## 6. 인과 경로 — 최초 divergence 부터

`tools/rfi_first_divergence.py` 로 두 리비전의 full_log 를 핸드 단위로 비교했다.

| seed | 최초 갈림 | 지점 | 원인 채널 |
|---|---|---|---|
| 3000 | h6 | flop seat4 bet 1000 → 1300 | POST_RANGE |
| 3001 | h5 | flop seat8 fold → call 900 | POST_RANGE |
| 3002 | h16 | turn seat5 bet 4600 → 4400 | POST_RANGE (단독으로 새 지문 재현) |
| 3003 | h15 | preflop seat9 limp → fold | OPEN_DEC (UTG+1 343bb QTo, ×0.877) |
| 3004 | h21 | turn seat9 bet 3500 → 3600 | POST_RANGE |
| 3005 | h14 | preflop seat2 fold → raise | OPEN_DEC (UTG+1 114bb KQo, ×1.095) |

### POST_RANGE 의 결정 단위 경로 (`tools/rfi_postflop_trace.py`)

ALL_OLD 와 ALL_NEW 에서 `update_plan` 호출을 같은 순서로 맞대면, 게임이 갈라지기 전까지 결정이
1:1로 정렬된다.

| seed | 정렬 결정 | 레인지 다름 | 계획 필드 다름 | plan 라벨 다름 |
|---|---|---|---|---|
| 3000 | 154 | 39 | 41 | 4 |
| 3001 | 49 | 7 | 7 | 0 |
| 3002 | 63 | 46 | 48 | 1 |
| 3003 | 115 | 56 | 58 | 3 |
| 3004 | 93 | 45 | 47 | 2 |
| 3005 | 95 | 27 | 27 | 0 |

(`_rsig`·`_opps_sig` 는 파이썬 `hash()` 기반 프로세스 내 서명(`plan.py:343`)이라 비교에서 뺐다.)

예 — seed 3000:
```
h0 flop   my_r 664 → 697 콤보 (프리플랍 역할 레인지가 넓어짐)
          nut_adv .42 → .50 · range_adv .25 → .23           ← 첫 계획 필드 차이. 행동은 같다
   ...    (39개 결정에서 레인지 다름, 행동은 그대로)
h6 flop   hero AsTh, board Td3d8s, opp_r 188 → 192
          plan pot_control → value_3street                  ← 첫 라벨 차이
          full_log: seat4 bet 1000 → 1300, turn 3000 → 4000, river 6500 → 7400 (seat8 모두 콜)
```
seed 3004 는 h0 flop 부터 `range_adv .13 → .01` 이 되고, h5 flop 에서 `giveup → pot_control` 이 된다.

**연쇄 (seed 3000):**
```
RFI 표 변경
 → ranges.preflop_range:236 의 _open 폭 변화 (ranges.py:228 바인딩, POST_RANGE)
 → session.py:1607/1650 my_r·opp_r 크기 변화
 → plan.update_plan (session.py:1806) nut_adv / range_adv / eq 변화
 → h6 plan pot_control → value_3street → 벳 사이즈 1000/3000/6500 → 1300/4000/7400
 → seat4·seat8 스택 차이 → h7·h15·h16·h20 연쇄 갈림
 → h20 seat9 turn check → bet 8300, seat2 raise 24800 에 콜 → seat9 스택 35,600 → 6,400
 → seat9 가 숏스택(20~41bb)이 되어 h24 HJ AJo shove, h27 UTG+1 QJo shove
   (h27 은 UTG 가 OPEN_DEC 로 K7s 오픈을 접은 뒤 첫 오픈 자리가 된 것)
 → unopened shove +2 / raise −2 → PFR 합계 불변
```

### VPIP / flop 변화가 나온 핸드 전수

두 리비전의 핸드별 (Δn, ΔVPIP, ΔPFR, Δflop) 을 모두 셌다. 0이 아닌 핸드는 7개뿐이고, 합이 정확히
+1 / +2 / 0 / +1 이다.

| seed h | 1차 뒤집힘 (OPEN_DEC) | 연쇄 | ΔVPIP | ΔPFR | Δflop |
|---|---|---|---|---|---|
| 3001 h11 | HJ K6s fold→raise | 원래 오프너(seat3)가 raise→call | +1 | 0 | +1 |
| 3001 h14 | UTG+2 QJo fold→raise (스택 147→90.5bb 로 바뀐 뒤) | seat6 raise→call, seat8 계속 call | +1 | 0 | 0 |
| 3005 h19 | LJ 33 아이소 fold→raise | seat4 raise→call | +1 | 0 | +1 |
| 3003 h15 | UTG+1 QTo limp→fold | BB 체크 팟 소멸 | −1 | 0 | −1 |
| 3005 h14 | UTG+1 KQo fold→raise | seat5 limp→fold, 팟 즉시 종료 | 0 | +1 | −1 |
| 3005 h20 | BTN A7o raise→fold | SB 컴플리트, BB 체크 → 플랍 | 0 | −1 | +1 |
| 3001 h29 | (없음) | 좌석1 생존 여부 차이 → 결정 1개 추가 | 0 (Δn +1) | 0 | 0 |
| **합** | | | **+2** | **0** | **+1** |

3000 h27(UTG raise→fold 후 seat9 shove)과 3004 h25(UTG+1 raise→fold 후 seat8 raise·seat9 call)는
행동이 바뀌었지만, 다른 오프너가 자리를 대신해 집계 변화는 0 이다.

**요약 경로:**
```
RFI 표 → OPEN_DEC 역치 이동 → 경계 핸드 오픈 추가/삭제 (±3)
       → 오픈 추가: 원래 오프너가 콜러로 대체 → VPIP +1, PFR 0, 플랍 +1
       → 오픈 삭제: 림프/컴플리트가 대체 → VPIP 0, PFR −1, 플랍 +1
RFI 표 → POST_RANGE 레인지 모델 → 포스트플랍 사이즈·라벨 → 스택/생존 → 뒤 핸드의 자리·스택 이동 (2차)
```

---

## 7. 항목별 답

| # | 항목 | 결과 |
|---|---|---|
| 1 | unopened RFI raise | 1차: 신궤적 119→119 (+3/−3), 옛궤적 121→120. 실현: 121→119 |
| 2 | open limp | 1차: 35→34 (3003 h15 QTo 343bb 1건). 실현 35→34 |
| 3 | 상대 오픈 뒤 call/fold/3bet | 1차 뒤집힘 0/618 (역치는 605건에서 움직였지만 Σ\|Δtot\| 1.29). 실현 call 107→110 은 **새 오픈이 만든 새 콜 기회**(3001 h11·h14, 3005 h19) |
| 4 | opener back-action | 1차 0/21 (옛궤적 0/22). Σ\|Δtot\| 0.003 |
| 5 | all-in/shove | 1차: 신궤적 4→3 (3000 h22 BTN 31.5bb K3o). 실현 1→3 은 seed 3000 seat9 스택 붕괴의 2차 효과 |
| 6 | 포지션별 | 넓힘: HJ·UTG+2·UTG+1·LJ(iso). 좁힘: UTG·UTG+1×2·BTN×2. ΣΔ_open 은 CO +0.51, LJ +0.35, UTG+2 +0.32, UTG −0.24, BTN −0.16 (신궤적) |
| 7 | 스택 깊이별 | 100–170bb ΣΔ +2.61 (n 553), ≥170bb −1.82 (n 141), <100bb −0.01 (n 51). 뒤집힘 방향이 비율 부호와 전부 일치 |
| 8 | 핸드 클래스별 | 1차 뒤집힘은 전부 경계 핸드: hand_pct 0.094~0.333 (top10%~top35%). 예외 하나는 31.5bb 쇼브 K3o (.517) |
| 9 | RNG/액션 순서 2차 효과 | 같은 행동인데 RNG 소비만 다른 결정이 양 궤적 각 3건. 전부 `iso_decision` 의 단락평가 `r <= min(0.95, thr*2.2) and rng.random() < _lp`(ca418d2 `preflop.py:854`, HEAD :866). 3000 h8 은 로그가 두 리비전에서 같다. 나머지 둘(3003 h25, 옛궤적 3000 h25)은 그 시드의 최초 갈림 이후라 따로 귀속할 수 없다. 핸드 rng 는 매 핸드 `tourney.py:121` 에서 새로 시드되므로 핸드 밖으로 새지 않는다. **최초 divergence 6건 중 RNG 로 시작한 것은 0건.** 2차 효과의 실체는 RNG 가 아니라 스택·생존 변화(6절)다 |
| 10 | PFR 상쇄 vs 무변화 | 구조적 무변화(기대 +0.8/745) + 실현 ±2 의 2차 상쇄. 5절 |

---

## 8. 한계

- 30핸드 × 6시드다. 1차 뒤집힘이 신궤적 9건(오픈 8 + 아이소 1)뿐이라 포지션·핸드 클래스
  분포는 서술 이상으로 읽으면 안 된다. 기대값(ΣΔ_open)은 결정 전수 기반이라 더 안정적이다.
- ΣΔ_open 은 `thr` 에 곱해지는 `table_pressure`·`hotzone_pressure`(`preflop.py:298`) 이전 값이다.
  raise/limp 분할(`open_form`)도 반영하지 않는다.
- POST_RANGE 가 포스트플랍 행동을 바꾼 **최초 행동** 지점은 3000 h6 만 라벨까지 확인했다. 3001 h5
  (fold→call), 3002 h16, 3004 h21 은 정렬 추적에서 레인지·계획 필드 차이를 확인했지만,
  응답 함수(`decide_response`) 안의 어느 분기가 뒤집혔는지는 따라가지 않았다.
- 3000 h20 seat9 의 turn check→bet 은 앞선 갈림 4핸드 뒤에 일어났다. POST_RANGE 직접 효과인지,
  book/스택 이월 효과인지는 분리하지 않았다.
- **RFI 이전 누적 격차(VPIP +32, flop +15, PFR +2)의 원인은 이번 범위 밖이다.**

---

## 9. 재현

```
W=<scratch>; git worktree add $W/wt/e17be45 e17be45; git worktree add $W/wt/ca418d2 ca418d2
python3 tools/rfi_ladder.py --repo $W/wt/<rev>                                  # 1절
python3 tools/rfi_channel_split.py --repo $W/wt/ca418d2 --arm <ARM>             # 3절, arm 마다 별도 프로세스
python3 tools/rfi_preflop_cf.py --repo $W/wt/ca418d2 --out new.json             # 4·5절 신궤적
python3 tools/rfi_preflop_cf.py --repo $W/wt/e17be45 --cf-rev ca418d2 --out old.json   # 옛궤적
python3 tools/rfi_first_divergence.py --dump ... / --diff A B                   # 6절
python3 tools/rfi_postflop_trace.py --repo $W/wt/ca418d2 --arm ALL_OLD --out a.json   # 6절
python3 tools/rfi_postflop_trace.py --diff a.json b.json
python3 tools/draw_rfi_attr.py --repo $W/wt/ca418d2 --out docs/RFI_ATTR_V1.png
```

이전 단계 도구 `tools/rfi_decision_cf.py`(open/iso 만), `tools/rfi_channel_knockout.py`(직접 호출 줄
기준 채널)는 2절의 측정 공백과 채널 혼합이 있다. 기록용으로 남겨 두었다. 결론은 위의
`rfi_preflop_cf.py`·`rfi_channel_split.py` 결과를 쓴다.
