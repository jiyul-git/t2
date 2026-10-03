# 베타 A 보고서 — 최고 숙련 단일 필드

## 판정 요약

기준 `1ac21231`(버그 수정 3건 후). 시드 11/12, 1,150핸드, 프리플랍 결정 10,196, 포스트플랍 결정 4,243.
계측 실행 지문이 기준선과 같다(`d6c70b87…`, `f0620c61…`). 계측이 진행을 바꾸지 않았다.

**층 전이 — 이상 없음**
- 저장 intent → 계산 액션 불일치 0(무저항 2,980건). 계획 없는 액션 0. 계산 → 실행 불일치 0. 사이즈 거부 대체 실행 0.
- 프리플랍 계획 → 엔진 불일치 0. 짝 없는 계획 7건은 한 핸드(데드 SB, 안테 없음, BB 워크 → 팟 0, 'void')로 규칙상 정상이다.
- 상대 베팅 대응 1,263건에서 자기 eq 와 필요 승률에 어긋난 콜/폴드 0.

**판단 — 이상 7종**

| # | 현상 | 건수 | 분류 | 근거 |
|---|---|---|---|---|
| 1 | 사이즈 습관이 계획 금액을 버리고 팟의 0.33/0.5/1/1.5배로 바꿈(예: 블러프 800 → 3000) | 17 / 973 | **수정 완료(REFACTOR 18차)**: 기질 consistency 로 배선, 최고 숙련 0 |
| 2 | 리버 OOP 가 넛급(rel ≥ 0.9)으로 체크, 상대가 체크백해 밸류 손실 | 8 | **개념 공백** | "직전 스트리트 상대 공격 콜 + OOP → 상대에게 액션 우선(재리드 8~9%)"이 패 강도와 '체크하면 상대가 벳할 확률'을 보지 않는다(L-RA02 계열) |
| 3 | 쇼다운 계획 손이 계획 이탈 확률(3~14%)로 큰 벳 — 콜 레인지 대비 eq 0.04~0.10 | 17 | **개념 공백** | 계획 이탈(지속벳)이 쇼다운 가치 손과 에어를 구분하지 않는다. 쇼다운 가치를 블러프로 바꾼다 |
| 4 | 턴 얇은 밸류가 rel 0.37 로 계속 베팅 | 2 | **개념 공백** | '콜당했을 때 앞서는가' 재평가가 리버에만 있다. 턴은 강등 문턱(rel 0.30)만 본다 |
| 5 | 2스트리트 밸류 계획이 rel 0.96 으로 '사이즈 0 → 체크' | 1 | **버그 — 수정 완료(REFACTOR 17차)** | 승격 기준이 직전 스트리트였고 rel 비교 정밀도가 달랐다. 같은 정밀도 오판으로 생기던 잘못된 밸류 승격 10건도 함께 사라졌다 |
| 6 | 리버 밸류 계획인데 실행 확률 미달로 체크(rel 0.91/0.95) | 2 | 계수 | 밸류 실행 확률 92~96% 의 혼합. 리버 넛급에서도 같은 혼합을 쓴다 |
| 7 | 첫 오픈에 상위 3~5% 손 폴드(AKs, 77, KJs) | 3 / 283 | 계수 | 디펜스 연속 확률 곡선의 위쪽 꼬리. 아래쪽 꼬리는 BB 만(26/378) 넓게 콜해 가격상 타당하다 |

**수정 후 재실행(REFACTOR 19차)**: #1·#3·#4·#5 해결, #2 는 트랩 판단으로 연결(남은 넛 체크 4건은 트랩 상한 = 계수 단계). #6·#7 은 계수 단계.

**문제 아님으로 판정**: 7 7 7 보드 QQ 폴드(eq 0.18 < 필요 0.31, 가격 일관), 스퀴즈에 TT 폴드(9.5bb 콜, 멀티웨이 백액션), 포기 계획 손의 지연·지속벳 이탈 23건(에어로 치는 혼합 블러프).

프리플랍 '순서 역전' 852건은 대부분 경계 구간의 확률 혼합이다(계속 비율이 손 순위에 따라 단조 감소). 위 7번만 판정 대상으로 뽑았다.

---


조건: 모든 봇 최고 숙련, 중립 기질, 틸트 0, 상대 장부 고정(`tools/r2_baseline_sim.py`). 입력: beta_11.json, beta_12.json.
판단 검사는 외부 전략 수치를 쓰지 않는다. 봇 자신의 입력(가격, 자기 밸류 기준, 같은 상황 안의 손 순서)과 결정을 비교한다.

## 규모

| 항목 | 값 |
|---|---|
| hands | 1150 |
| pf_decisions | 10196 |
| post_decisions | 4243 |
| facing_priced | 1263 |
| free_with_intent | 2980 |
| pf_groups_checked | 152 |
| pf_inverted_folds | 852 |
| pf_engine_rows_without_plan | 0 |
| pf_plans_unmatched | 7 |
| pf_raise_clamped_up | 4 |
| pf_intent_without_action | 0 |

## 검사 결과

| 검사 | 층 | 내용 | 건수 |
|---|---|---|---|
| X1_pf_plan_engine_mismatch | 실행 | 프리플랍 계획 액션과 엔진 적용 액션이 다름 | 0 |
| P1_intent_vs_calculated | 계획→실행 | 저항 없는 상황에서 저장 intent 와 계산 액션이 다름 | 0 |
| P2_action_without_plan | 계획 | 계획 없이 실행된 포스트플랍 액션 | 0 |
| E1_execution_fallback | 실행 | 사이즈 거부로 대체 실행(call/check) | 0 |
| E2_calculated_vs_executed | 실행 | 계산 액션과 실행 액션이 다름(올인 변환·재생 제외) | 0 |
| E3_target_drift | 실행 | 사이즈 습관 이후 단계에서 금액이 ×1.5 초과/×0.67 미만으로 바뀜(유효올인·최소레이즈 제외) | 0 |
| E4_odd_size_habit | 계획 | 사이즈 습관이 계획 금액을 ±12% 넘게 바꿈(odd 사이즈) | 17 |
| J1_call_below_price | 판단 | 상대 베팅 레인지 대비 eq 가 필요 승률보다 0.05 넘게 낮은데 콜 | 0 |
| J2_fold_above_price | 판단 | 상대 베팅 레인지 대비 eq 가 필요 승률보다 0.10 넘게 높은데 폴드 | 0 |
| J3_strong_fold | 판단 | rel_true ≥ 0.95 또는 풀하우스 이상으로 폴드 | 1 |
| J4_value_bet_low_rel | 판단 | 밸류 계획으로 베팅했지만 rel < 0.45 | 2 |
| J5_river_check_strong | 판단 | 리버 무저항 상황에서 rel ≥ 0.90 인데 체크 | 15 |
| J6_pf_premium_fold | 판단 | 프리플랍 상위 3% 손을 콜 비용이 스택의 절반 미만인데 폴드 | 1 |
| J7_showdown_value_turned_bluff | 판단 | 쇼다운 계획 손이 계획 이탈 확률로 베팅(쇼다운 가치를 블러프로 전환) | 17 |

## 계획 → 실행 (포스트플랍)

| plan | 상황 | 액션 | 건수 |
|---|---|---|---|
| block | facing | call | 2 |
| block | free | bet | 5 |
| block | free | check | 1 |
| bluff_2street | facing | fold | 127 |
| bluff_2street | facing | call | 43 |
| bluff_2street | free | bet | 185 |
| bluff_2street | free | check | 83 |
| giveup | facing | fold | 286 |
| giveup | facing | call | 32 |
| giveup | free | check | 823 |
| giveup | free | bet | 20 |
| pot_control | facing | call | 147 |
| pot_control | facing | fold | 140 |
| pot_control | free | check | 441 |
| pot_control | free | bet | 49 |
| river_bluff | facing | fold | 7 |
| river_bluff | free | bet | 15 |
| river_bluff | free | check | 5 |
| semibluff | facing | call | 38 |
| semibluff | facing | fold | 15 |
| semibluff | facing | raise | 14 |
| semibluff | free | bet | 85 |
| semibluff | free | check | 21 |
| showdown | facing | fold | 123 |
| showdown | facing | call | 77 |
| showdown | facing | raise | 1 |
| showdown | free | check | 492 |
| showdown | free | bet | 17 |
| thin_river | facing | call | 2 |
| thin_river | free | bet | 13 |
| thin_river | free | check | 4 |
| trap | facing | raise | 3 |
| trap | free | check | 26 |
| value_2street | facing | call | 92 |
| value_2street | facing | raise | 26 |
| value_2street | facing | fold | 2 |
| value_2street | free | bet | 245 |
| value_2street | free | check | 85 |
| value_3street | facing | raise | 44 |
| value_3street | facing | call | 42 |
| value_3street | free | bet | 304 |
| value_3street | free | check | 61 |

## 리버 강한 손(rel ≥ 0.90) 무저항 체크 원인

| 원인 | 건수 |
|---|---|
| OOP 상대에게 액션 우선 | 8 |
| 쇼다운/포기 계획 | 4 |
| 밸류 실행 확률 미달 | 2 |
| 사이즈 0 | 1 |

## 금액 전이 (bet/raise)

| 사이즈 습관 | 최소레이즈 | 유효올인 | 건수 |
|---|---|---|---|
| shape_same | no_clamp | no_eff_allin | 493 |
| shape_changed | no_clamp | no_eff_allin | 492 |
| shape_same | no_clamp | eff_allin | 31 |
| shape_same | minraise_clamped | eff_allin | 4 |
| shape_changed | no_clamp | eff_allin | 3 |
| shape_changed | minraise_clamped | no_eff_allin | 2 |
| shape_same | minraise_clamped | no_eff_allin | 1 |

## 프리플랍 계획 → 엔진

| 계획 | 엔진 | 건수 |
|---|---|---|
| fold | fold | 7841 |
| call | call | 1078 |
| raise | raise | 1041 |
| 3bet | raise | 164 |
| shove | allin | 57 |
| limp | call | 14 |
| check | check | 1 |

## 프리플랍 순서 역전 (같은 상황에서 더 강한 손이 폴드, 더 약한 손이 계속)

상황 = (포지션, 종류, 레벨, 스택 구간, 콜 비용 구간, 멀티웨이). pct 는 손 순위 백분위(낮을수록 강함).

| 상황 | 결정 수 | 가장 넓게 계속한 pct | 가장 강하게 폴드한 pct | 역전 폴드 | 예시 |
|---|---|---|---|---|---|
| LJ / caller_multiway_backaction / 2 / >=80 / <12 / False | 2 | 0.0935 | 0.0226 | 1 | Td Ts(0.023) |
| LJ / face_first_open / 1 / >=80 / <3 / False | 242 | 0.1478 | 0.0302 | 9 | As Ks(0.030), Ah Ks(0.071), 5c 5d(0.075) |
| UTG+1 / face_first_open / 1 / >=80 / <3 / False | 99 | 0.0814 | 0.0392 | 1 | 7c 7s(0.039) |
| CO / caller_multiway_backaction / 2 / <80 / <12 / False | 3 | 0.0513 | 0.0392 | 1 | 7h 7c(0.039) |
| BTN / face_first_open / 1 / >=80 / <3 / False | 395 | 0.3544 | 0.0483 | 45 | Kd Jd(0.048), Ts 9s(0.151), Tc 8c(0.160) |
| LJ / opener_multiway_backaction / 2 / >=80 / <12 / False | 6 | 0.0709 | 0.0558 | 1 | 6c 6d(0.056) |
| HJ / face_first_open / 1 / >=80 / <3 / False | 310 | 0.1599 | 0.0754 | 10 | 5s 5c(0.075), Ad Jh(0.122), Ad 7d(0.136) |
| CO / face_first_open / 1 / >=80 / <3 / False | 392 | 0.2941 | 0.0845 | 30 | 9h Kh(0.085), 4s 4c(0.113), Kc Jh(0.148) |
| UTG+2 / face_first_open / 1 / <80 / <3 / False | 73 | 0.1026 | 0.0845 | 1 | Kc 9c(0.085) |
| CO / face_first_open / 1 / >=80 / <6 / False | 23 | 0.1508 | 0.1026 | 1 | Kc Qs(0.103) |
| CO / opener_backaction / 2 / >=80 / <12 / False | 8 | 0.1086 | 0.1026 | 1 | Qs Kc(0.103) |
| LJ / face_first_open / 1 / <50 / <3 / False | 45 | 0.1599 | 0.1026 | 4 | Qs Kc(0.103), Ad Jh(0.122), Ah 7h(0.136) |
| LJ / face_first_open / 1 / >=80 / <6 / False | 12 | 0.1297 | 0.1056 | 1 | Ac 9c(0.106) |
| UTG / unopened / 1 / >=80 / <1.01 / False | 634 | 0.1599 | 0.1222 | 9 | Jc As(0.122), 9h Qh(0.130), Ah 7h(0.136) |
| UTG+1 / unopened / 1 / >=80 / <1.01 / False | 524 | 0.1976 | 0.1222 | 18 | Jc Ad(0.122), 8d Ad(0.133), Ad 7d(0.136) |
| HJ / face_first_open / 1 / <80 / <3 / False | 177 | 0.1976 | 0.1222 | 10 | As Jc(0.122), Ah Js(0.122), 3c 3s(0.127) |
| LJ / face_first_open / 1 / <80 / <3 / False | 132 | 0.1629 | 0.1222 | 4 | Ah Js(0.122), Ad 7d(0.136), Kc Jd(0.148) |
| UTG+1 / face_first_open / 1 / <80 / <3 / False | 57 | 0.1297 | 0.1267 | 1 | 3s 3h(0.127) |
| CO / face_first_open / 1 / <80 / <3 / False | 205 | 0.2579 | 0.1297 | 11 | Qc 9c(0.130), Tc Qs(0.172), Qd Jc(0.198) |
| UTG+2 / unopened / 1 / >=80 / <1.01 / False | 358 | 0.2127 | 0.1478 | 21 | Jc Ks(0.148), Kh Jd(0.148), Kd Js(0.148) |
| BTN / face_first_open / 1 / <80 / <3 / False | 252 | 0.4208 | 0.1478 | 39 | Jc Kh(0.148), Td As(0.207), 8d Qd(0.210) |
| UTG / unopened / 1 / <50 / <1.01 / False | 125 | 0.1976 | 0.1478 | 2 | Jh Kd(0.148), Tc Qs(0.172) |
| SB / face_first_open / 1 / <80 / <3 / False | 250 | 0.5173 | 0.1508 | 60 | Tc 9c(0.151), Jd Qh(0.198), 9h 8h(0.225) |
| UTG / unopened / 1 / <80 / <1.01 / False | 330 | 0.184 | 0.1508 | 6 | 9d Td(0.151), Td Qs(0.172), Th Qc(0.172) |
| LJ / unopened / 1 / >=80 / <1.01 / False | 363 | 0.2459 | 0.1719 | 11 | Th Qd(0.172), Td Kc(0.184), 2d 2c(0.189) |

## 표시된 결정 예시

### E4_odd_size_habit (17)

- `{"hash": "b20446542991", "seat": 8, "pos": "UTG+2", "hole": "As 8s", "board": "2s 9d 9h Kd 5c", "street": "river", "plan": "bluff_2street", "action": "bet", "amt": 3000, "tocall": 0, "pot": 2000, "rel": 0.33, "rel_true": 0.333727, "eq": 0.347, "made": 0, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["turn: 쇼다운 가치 없음 + 블로커 0.09/넛우위 0.70 → 블러프 계획", "turn: 블러프 세부: low_cost — 도중 포기 위험 100% — 최소 비용 탐색"], "calc_target": 800.0, "shaped_target": 3000.0}`
- `{"hash": "bd28e8394194", "seat": 6, "pos": "HJ", "hole": "Ts 8s", "board": "Ah Ac Jh 6c 3s", "street": "flop", "plan": "bluff_2street", "action": "bet", "amt": 2100, "tocall": 0, "pot": 2100, "rel": 0.02, "rel_true": 0.018349, "eq": 0.159, "made": 0, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 쇼다운 가치 없음 + 블로커 0.07/넛우위 0.45 → 블러프 계획", "flop: 블러프 세부: barrel — 상대가 사이즈를 안 읽음 — 폴드율 52% 역산(팟의 64%, 요구 39%)"], "calc_target": 900.0, "shaped_target": 2100.0}`
- `{"hash": "4912e0656428", "seat": 9, "pos": "UTG+1", "hole": "Qd Jd", "board": "Tc 9c Ts Kh 4s", "street": "flop", "plan": "semibluff", "action": "bet", "amt": 1000, "tocall": 0, "pot": 1900, "rel": 0.03, "rel_true": 0.030642, "eq": 0.43, "made": 0, "outs": 8, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 드로우 8아웃 → 세미블러프", "flop: 세미블러프 사이즈: 폴드율 52% 역산 → 팟의 64%"], "calc_target": 800.0, "shaped_target": 1000.0}`
- `{"hash": "8327a9cb1cd9", "seat": 1, "pos": "UTG+2", "hole": "Qh Ah", "board": "4c As Qc 4s", "street": "turn", "plan": "value_3street", "action": "bet", "amt": 11200, "tocall": 0, "pot": 22300, "rel": 0.94, "rel_true": 0.942675, "eq": 0.858, "made": 2, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": "generic_response", "intent_act": "bet", "calc_act": "bet", "why": ["flop: 강도 최상위 → 3스트리트 밸류"], "calc_target": 15200.0, "shaped_target": 11200.0}`
- `{"hash": "303ecc5a7170", "seat": 3, "pos": "BB", "hole": "4h Qh", "board": "3c 9s 8h 9h 3s", "street": "flop", "plan": "bluff_2street", "action": "bet", "amt": 1400, "tocall": 0, "pot": 2800, "rel": 0.0, "rel_true": 0.0, "eq": 0.18, "made": 0, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 쇼다운 가치 없음 + 블로커 0.10/넛우위 -0.29 → 블러프 계획", "flop: 블러프 세부: barrel — 상대가 사이즈를 안 읽음 — 폴드율 52% 역산(팟의 64%, 요구 39%)"], "calc_target": 1000.0, "shaped_target": 1400.0}`
- `{"hash": "ffad993788c1", "seat": 4, "pos": "BTN", "hole": "2c Kc", "board": "9d 4s 2h 2d", "street": "turn", "plan": "value_3street", "action": "raise", "amt": 2800, "tocall": 1400, "pot": 4700, "rel": 0.97, "rel_true": 0.966102, "eq": 0.925, "made": 3, "outs": 0, "resp_eq": 0.9242, "resp_need": 0.2362, "resp_src": "generic_response", "intent_act": "bet", "calc_act": "raise", "why": ["flop: 중간강도(eq 0.59, rel 0.68) → 팟 컨트롤", "turn: 강도 상승(rel 0.97, made 3) → 밸류 전환"], "calc_target": 10400.0, "shaped_target": 1600.0}`

### J3_strong_fold (1)

- `{"hash": "ef28435c91d2", "seat": 1, "pos": "HJ", "hole": "Qh Qd", "board": "7d 7h 7s 3c 5s", "street": "river", "plan": "showdown", "action": "fold", "amt": 0, "tocall": 10000, "pot": 21500, "rel": 0.19, "rel_true": 0.193659, "eq": 0.187, "made": 6, "outs": 0, "resp_eq": 0.1767, "resp_need": 0.312, "resp_src": "generic_response", "intent_act": "check", "calc_act": "fold", "why": ["flop: 중간 밸류이나 3스트리트 유지(eq 0.76, rel 0.85, p2 0.30)", "프리플랍 3벳+ 팟 → 레인지 우위", "river: 상대강도 0.19 → 3스트리트 철회, 2스트리트", "리버: 전체 rel 0.19지만 콜 레인지 상대 eq 0.05 < 0.50 → 얇은 밸류 아님", "리버: 밸류 계획 재평가 → 얇은 밸류 아님(rel 0.19) → 쇼다운"]}`

### J4_value_bet_low_rel (2)

- `{"hash": "0ccf25146469", "seat": 7, "pos": "LJ", "hole": "Kd Kc", "board": "Jd 9d Td 6c", "street": "turn", "plan": "value_2street", "action": "bet", "amt": 2200, "tocall": 0, "pot": 3300, "rel": 0.37, "rel_true": 0.369213, "eq": 0.495, "made": 1, "outs": 11, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 중간강도(eq 0.58, rel 0.39, 머징 3.0) → 얇은 밸류", "프리플랍 3벳+ 팟 → 레인지 우위"]}`
- `{"hash": "9eeee1e0670e", "seat": 9, "pos": "BB", "hole": "9d 8d", "board": "9s Kh 2c Td Ks", "street": "turn", "plan": "value_2street", "action": "bet", "amt": 5000, "tocall": 0, "pot": 7400, "rel": 0.37, "rel_true": 0.36938, "eq": 0.37, "made": 1, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 중간강도(eq 0.59, rel 0.66, 머징 3.0) → 얇은 밸류"]}`

### J5_river_check_strong (15)

- `{"hash": "a2a63744c3c4", "seat": 4, "pos": "SB", "hole": "Jh Ac", "board": "9h 5s Ad 4c Js", "street": "river", "plan": "showdown", "action": "check", "amt": 0, "tocall": 0, "pot": 3800, "rel": 0.9, "rel_true": 0.89726, "eq": 0.855, "made": 2, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "check", "calc_act": "check", "why": ["flop: 중간강도(eq 0.60, rel 0.71) → 팟 컨트롤", "turn: 강도 상승(rel 0.72, made 1) → 밸류 전환", "리버: 밸류 계획 재평가 → 얇은 밸류 아님(rel 0.90) → 쇼다운"], "cause": "쇼다운/포기 계획", "intent_src": "DEVIATE:포기 계획이나 지속벳(5%)"}`
- `{"hash": "bd28e8394194", "seat": 3, "pos": "UTG+1", "hole": "Jd Ad", "board": "Ah Ac Jh 6c 3s", "street": "river", "plan": "value_3street", "action": "check", "amt": 0, "tocall": 0, "pot": 12300, "rel": 1.0, "rel_true": 1.0, "eq": 0.95, "made": 6, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": "checkraise_declined", "intent_act": "check", "calc_act": "check", "why": ["flop: 강도 최상위 → 3스트리트 밸류"], "cause": "OOP 상대에게 액션 우선", "intent_src": "직전 스트리트 상대 공격 콜 + OOP → 상대에게 액션 우선 (재리드 9%)"}`
- `{"hash": "a973e801d60c", "seat": 3, "pos": "SB", "hole": "8s Ks", "board": "2s 4h 3s Qh 9s", "street": "river", "plan": "value_3street", "action": "check", "amt": 0, "tocall": 0, "pot": 10200, "rel": 0.96, "rel_true": 0.955224, "eq": 0.94, "made": 5, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "check", "calc_act": "check", "why": ["river: 강도 최상위 → 3스트리트 밸류"], "cause": "OOP 상대에게 액션 우선", "intent_src": "직전 스트리트 상대 공격 콜 + OOP → 상대에게 액션 우선 (재리드 9%)"}`
- `{"hash": "def1bdd20c41", "seat": 2, "pos": "UTG", "hole": "Jc Js", "board": "7s Th 8d 9s 6c", "street": "river", "plan": "value_2street", "action": "check", "amt": 0, "tocall": 0, "pot": 15400, "rel": 0.93, "rel_true": 0.926053, "eq": 0.757, "made": 0, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": "checkraise_declined", "intent_act": "check", "calc_act": "check", "why": ["flop: 중간 밸류(eq 0.72, rel 0.79) + 위험 0.40/SPR 7.5/다인원 0 → 2스트리트(p2 0.72)"], "cause": "OOP 상대에게 액션 우선", "intent_src": "직전 스트리트 상대 공격 콜 + OOP → 상대에게 액션 우선 (재리드 8%)"}`
- `{"hash": "1f2ccd47e425", "seat": 1, "pos": "CO", "hole": "Th 8h", "board": "Jh 2h 9c 5c Qd", "street": "river", "plan": "value_3street", "action": "check", "amt": 0, "tocall": 0, "pot": 9200, "rel": 0.99, "rel_true": 0.991145, "eq": 0.98, "made": 4, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": "checkraise_declined", "intent_act": "check", "calc_act": "check", "why": ["flop: 중간강도(eq 0.60, rel 0.03) → 팟 컨트롤", "river: 강도 상승(rel 0.99, made 4) → 밸류 전환"], "cause": "OOP 상대에게 액션 우선", "intent_src": "직전 스트리트 상대 공격 콜 + OOP → 상대에게 액션 우선 (재리드 9%)"}`
- `{"hash": "795ca7ef174d", "seat": 4, "pos": "SB", "hole": "Ac 4c", "board": "9c 5d As Jc 2c", "street": "river", "plan": "value_3street", "action": "check", "amt": 0, "tocall": 0, "pot": 19800, "rel": 1.0, "rel_true": 1.0, "eq": 1.0, "made": 5, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "check", "calc_act": "check", "why": ["river: 강도 최상위 → 3스트리트 밸류"], "cause": "OOP 상대에게 액션 우선", "intent_src": "직전 스트리트 상대 공격 콜 + OOP → 상대에게 액션 우선 (재리드 9%)"}`

### J6_pf_premium_fold (1)

- `{"hash": "ae6c6b9e99b1", "pos": "LJ", "hand": "Td Ts", "pct": 0.0226, "kind": "caller_multiway_backaction", "to_call_bb": 9.5, "stack_bb": 171.9375}`

### J7_showdown_value_turned_bluff (17)

- `{"hash": "f495185cf42d", "seat": 5, "pos": "BB", "hole": "4s Ah", "board": "6c 8d Ad 9c Kh", "street": "river", "plan": "showdown", "action": "bet", "amt": 4400, "tocall": 0, "pot": 5500, "rel": 0.46, "rel_true": 0.455446, "eq": 0.368, "made": 1, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": "checkraise_declined", "intent_act": "bet", "calc_act": "bet", "why": ["flop: 중간강도(eq 0.55, rel 0.63, 머징 3.0) → 얇은 밸류", "리버: 전체 rel 0.46지만 콜 레인지 상대 eq 0.10 < 0.50 → 얇은 밸류 아님", "리버: 밸류 계획 재평가 → 얇은 밸류 아님(rel 0.46) → 쇼다운", "계획이탈: showdown 계획인데 bet (포기 계획이나 지속벳(4%))"], "dev": {"street": "river", "planned": "showdown", "executed": "bet", "why": "포기 계획이나 지속벳(4%)"}}`
- `{"hash": "2b8a77cefda2", "seat": 1, "pos": "LJ", "hole": "As Qs", "board": "Qc Jc 7c 8c Ks", "street": "river", "plan": "showdown", "action": "bet", "amt": 2400, "tocall": 0, "pot": 3500, "rel": 0.32, "rel_true": 0.316535, "eq": 0.265, "made": 1, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["turn: 쇼다운 가치 있음 → 팟 컨트롤", "리버: 전체 rel 0.32지만 콜 레인지 상대 eq 0.04 < 0.50 → 얇은 밸류 아님", "리버: 밸류 계획 재평가 → 얇은 밸류 아님(rel 0.32) → 쇼다운", "계획이탈: showdown 계획인데 bet (포기 계획이나 지속벳(3%))"], "dev": {"street": "river", "planned": "showdown", "executed": "bet", "why": "포기 계획이나 지속벳(3%)"}}`
- `{"hash": "85e19da56f4f", "seat": 6, "pos": "BTN", "hole": "8c Qc", "board": "Ts 9d 8s 2s 9s", "street": "river", "plan": "showdown", "action": "bet", "amt": 2300, "tocall": 0, "pot": 3400, "rel": 0.32, "rel_true": 0.315271, "eq": 0.303, "made": 1, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["turn: 중간강도(eq 0.50, rel 0.56) → 팟 컨트롤", "리버: 전체 rel 0.32지만 콜 레인지 상대 eq 0.00 < 0.50 → 얇은 밸류 아님", "리버: 밸류 계획 재평가 → 얇은 밸류 아님(rel 0.32) → 쇼다운", "계획이탈: showdown 계획인데 bet (포기 계획이나 지속벳(5%))"], "dev": {"street": "river", "planned": "showdown", "executed": "bet", "why": "포기 계획이나 지속벳(5%)"}}`
- `{"hash": "8b18b353f897", "seat": 5, "pos": "BTN", "hole": "Ad 7s", "board": "Js Jh 6c", "street": "flop", "plan": "showdown", "action": "bet", "amt": 1000, "tocall": 0, "pot": 2000, "rel": 0.73, "rel_true": 0.732087, "eq": 0.598, "made": 0, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 중간강도이나 얇은 밸류 조건 미달(rel 0.73, made 0) → showdown", "계획이탈: showdown 계획인데 bet (포기 계획이나 지속벳(14%))"], "dev": {"street": "flop", "planned": "showdown", "executed": "bet", "why": "포기 계획이나 지속벳(14%)"}}`
- `{"hash": "1b1617315fd8", "seat": 1, "pos": "CO", "hole": "2s 2c", "board": "Ts 7h Td 5s Qh", "street": "river", "plan": "showdown", "action": "bet", "amt": 1200, "tocall": 0, "pot": 1800, "rel": 0.57, "rel_true": 0.567227, "eq": 0.607, "made": 1, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 쇼다운 가치 있음 → 팟 컨트롤", "리버: 전체 rel 0.57지만 콜 레인지 상대 eq 0.43 < 0.50 → 얇은 밸류 아님", "리버: 밸류 계획 재평가 → 얇은 밸류 아님(rel 0.57) → 쇼다운", "계획이탈: showdown 계획인데 bet (포기 계획이나 지속벳(14%))"], "dev": {"street": "river", "planned": "showdown", "executed": "bet", "why": "포기 계획이나 지속벳(14%)"}}`
- `{"hash": "32e98457c738", "seat": 5, "pos": "CO", "hole": "Ad Th", "board": "4h Qh 7s", "street": "flop", "plan": "showdown", "action": "bet", "amt": 1000, "tocall": 0, "pot": 1800, "rel": 0.61, "rel_true": 0.614964, "eq": 0.555, "made": 0, "outs": 0, "resp_eq": null, "resp_need": null, "resp_src": null, "intent_act": "bet", "calc_act": "bet", "why": ["flop: 중간강도이나 얇은 밸류 조건 미달(rel 0.61, made 0) → showdown", "계획이탈: showdown 계획인데 bet (포기 계획이나 지속벳(14%))"], "dev": {"street": "flop", "planned": "showdown", "executed": "bet", "why": "포기 계획이나 지속벳(14%)"}}`

