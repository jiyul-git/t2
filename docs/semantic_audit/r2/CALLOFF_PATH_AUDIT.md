# B. CALLOFF_PATH_AUDIT — 올인 대면 콜 판단의 경로별 판단량

기준 `test` `d284a9e`. 읽기 전용이며 행동은 바꾸지 않았다.

비교 기준은 계산이 끝난 9-max GTO DB spot 이다(`chatgpt/gto-reference-20260928:data/gto_db/preflop_9max_pushfold_v1.jsonl`).
- HoldemMath 9-max push/fold, 0.1bb×9 안테, 칩 EV, single-caller 근사.
- T2 1bb BBA 와는 near 조건이다.

## 0. 판단량이 쓰이는 곳

| 판단량 | 계산 위치 | 소비처 |
|---|---|---|
| pf_rank 백분위 cap | `preflop.calloff_cap`: 디펜스 총량 `tot` × `CALLOFF_TIGHTEN[level+1]` × 2.6 × (1 − 0.18·feel) ÷ **객관** bf (exploit 있으면 배수) | `calloff_decision`(`r <= cap`) ← `defend_action_likelihoods` 의 calloff 분기 |
| 상대 레인지 | 관찰자 복원 `session._preflop_perceived_range` → `_preflop_story_range` → `ranges.preflop_range` | 순수 콜오프 shadow(`_pf_call_ev_shadow`), multiway/cold 판단, 뒤 좌석의 판단 |
| hero equity | `_diagnostic_layer_equities`(팟 층별, 800 sims) / `bot.equity_vs_combos`(multiway 900 sims) | `calloff_layer_judgment`, `multiway_reraise_decision` |
| 가격(필요 equity) | `icm.required_equity(pot, cost, bf)` / multiway 는 `cost·bf/(pot+cost)` | 같음 |
| ICM/BF | 객관 `h.bf(s)` → 개인 인지 `PS.icm_bf(prof, bf)` | layer·multiway 는 인지 bf. **legacy cap 은 객관 bf 로 직접 나눈다**(인지 단계 없음) |
| 계산 오차 | `PS.calc_noise(prof,'potodds')`(0.65~1.55 clip) | layer·multiway |
| 실행 게이트 | `PS.gate(prof,'pf_defend')` = (skill/5)^0.85 | layer 판단만. 통과하지 못하면 legacy 행동이 남는다 |
| 뒤 좌석 위험 | `icm.players_behind_required_equity_premium` | multiway/cold 만 쓴다. 순수 콜오프 layer 와 일반 디펜스는 쓰지 않는다 |

## 1. 경로별 실제 소비 (baseline 시드 11·12, 1,149핸드, 올인 관련 결정 182건)

수집:
- `tools/r2_baseline_sim.py` 에 읽기 전용 래퍼를 하나 더 씌워 `pf_calloff_consumer` 등 dict 필드를 기록했다(scratch).
- 핸드 수와 결정 수는 봉인값과 같다(583/566, 5,147/5,010).
- 래퍼가 한 겹 더 들어가 기존 래퍼의 프레임 조회(`hash`, `seat`)가 비게 되고, 그래서 sha 는 봉인값과 다르다. 행동 기록은 비교하지 않았다.

| 경로 | 조건 | 건수 | 행동을 정하는 것 | legacy cap 의 역할 |
|---|---|---|---|---|
| **P1 순수 콜오프** | 상대 올인, 나는 레이즈 불가, 콜 가격 > 0, 상대 레인지 있음 | 42 | `calloff_layer_judgment`(인지 bf, 계산 오차, equity ≥ 필요 equity). max-skill 게이트 1.80 → 항상 통과 | **우회됨.** `defend_decision` 이 먼저 legacy 행동을 계산하지만 RNG 를 쓰지 않는 경로이고, 통과하면 덮어쓴다. 42건 중 19건(45%)이 legacy 와 다른 행동 |
| **P2 올인 대면, 뒤 좌석 때문에 레이즈 가능, 첫 오픈 대면** | `opener_allin` 이고 `can_raise`, raise_level 1, 쇼브 < 내 스택×0.92 | **102** | 일반 vs-open 혼합 정책(`defend_action_likelihoods`: `tot`/`tp` 로지스틱. `open_bb` 에 쇼브 크기가 들어감) | 쓰지 않는다. 대신 **vs-open 디펜스 폭**이 판단량이다. 가격도 equity 도 보지 않는다 |
| P3 올인 대면, cold/multiway | raise_level ≥ 2 이고 cold 문맥 또는 2개 이상 레인지 | 28 | `multiway_reraise_decision`(equity, 가격, 뒤 좌석, locked 가격 게이트) | 기본 확률에만 섞이고, 콜/폴드는 증거로 교체 |
| **P4 내 스택 거의 전부를 거는 콜** (`_hero_calloff`, 순수 콜오프 아님) | `open_bb ≥ 내 스택×0.92` 이고 (상대 비올인 또는 레이즈 가능) | 10 | **legacy cap**(`r <= cap`). 공격(리쇼브) 선택지 0 | **행동을 직접 정한다** |
| **P5 낮은 숙련 순수 콜오프** | P1 과 같고 `pf_defend` < 5 | (baseline 은 전원 max-skill 이라 0) | 확률 (1 − gate) 로 legacy 행동 | **행동을 직접 정한다.** 필드 생성기 기준 평균 legacy 유지 확률: field_quality 0.45 → 0.36, 0.6 → 0.27, 0.9 → 0.14 |
| **P6 상대 레인지 복원: 쇼브한 사람** | 첫 진입 올인 → 액션 라벨 `'open'`(`_pf_range_action`: shove + role open → open) | 모든 올인 대면 판단의 입력 | `preflop_range(...,'open', stack)` = **RFI 폭 상위 슬라이스** | cap 은 아니다. 다만 같은 pf_rank 순서로 **쇼브 레인지를 오픈 레인지로** 대신한다 |
| **P7 상대 레인지 복원: 쇼브에 콜한 사람** | 라벨 `'call'` → `_defend_likelihood_range` → `defend_action_likelihoods(..., opener_allin=False, can_raise=True)` | 뒤 좌석·다음 결정의 입력 | 쇼브 ≥ 콜러 스택×0.92 이면 **legacy cap**. 그보다 깊은 콜러면 **vs-open 플랫 콜 구간** | 깊은 콜러는 "오픈에 플랫한 레인지"가 된다(아래 3.3) |

## 2. 완료된 9-max spot 과의 비교

### 2.1 P1·P4·P5 — 콜 판단 규칙 세 가지 (`calloff_paths_vs_db.json`)

`tools/r2_calloff_paths.py`.
- 대상: 10/15/20bb, 콜러 BB/SB/BTN, 쇼버는 앞 좌석 전부. 63 spot.
- 일치율: 핸드 클래스별로 규칙의 콜/폴드가 DB 와 같은 콤보 비율.

| 규칙 | 판단량 | DB 콜 집합과 일치율 평균 (최소) | 평균 콜 폭 (DB 0.402) |
|---|---|---|---|
| legacy | pf_rank ≤ cap | 0.779 | 0.199 |
| math_db | equity(핸드 vs **DB 의 첫 진입 쇼브 레인지**) ≥ 필요 equity | **0.940 (0.879)** | 0.436 |
| t2_obs | equity(핸드 vs **T2 관찰자가 복원한 쇼브 레인지**) ≥ 필요 equity (= 현재 max-skill P1 의 방식) | 0.771 | 0.175 |

스택·콜러별:

| 스택 | 콜러 | DB 콜 | legacy | math_db | t2_obs | DB 쇼브 폭 | T2 복원 쇼브 폭 |
|---|---|---|---|---|---|---|---|
| 10 | BB | 0.557 | 0.278 | 0.602 | 0.242 | 0.739 | 0.248 |
| 10 | SB | 0.513 | 0.178 | 0.565 | 0.217 | 0.777 | 0.245 |
| 10 | BTN | 0.429 | 0.131 | 0.527 | 0.173 | 0.780 | 0.225 |
| 15 | BB | 0.407 | 0.269 | 0.414 | 0.170 | 0.624 | 0.228 |
| 15 | SB | 0.395 | 0.172 | 0.414 | 0.153 | 0.658 | 0.225 |
| 15 | BTN | 0.345 | 0.126 | 0.384 | 0.133 | 0.654 | 0.205 |
| 20 | BB | 0.327 | 0.271 | 0.342 | 0.172 | 0.540 | 0.248 |
| 20 | SB | 0.326 | 0.175 | 0.341 | 0.158 | 0.570 | 0.245 |
| 20 | BTN | 0.285 | 0.127 | 0.318 | 0.137 | 0.563 | 0.223 |

해석:
- **질문에 맞는 판단량은 "상대 쇼브 레인지 대비 equity ≥ 가격"이다.**
  - 그 레인지를 정확히 주면 DB 와 94% 일치한다.
  - 남는 차이(조금 넓게 콜함)는 뒤 좌석 위험을 넣지 않은 탓으로 보인다. SB·BTN 콜러에서 더 넓고, DB 는 single-caller 근사로 뒤 좌석을 반영한다.
- **현재 max-skill 의 P1 은 판단량은 맞지만 입력 레인지가 틀렸다.**
  - T2 는 첫 진입 쇼브를 `'open'` 으로 읽어 RFI 폭(0.21~0.25)으로 복원한다. DB 쇼브 폭은 0.54~0.78 이다.
  - 그 결과 일치율이 legacy 와 같은 수준(0.77)으로 떨어진다.
  - 오차의 원인은 콜 계산이 아니라 **레인지 복원(P6)**이다.
- 단서: DB 쇼브 레인지는 push/fold 전용 모델(레이즈 선택지 없음)의 균형값이다. T2 쇼버는 `open_form` 으로 레이즈와 쇼브를 섞는다. 그래서 "T2 쇼버의 실제 레인지"와 DB 쇼브 레인지는 같지 않다. 관찰자가 가질 **지식 prior** 로서 DB 쇼브 차트가 오픈 레인지보다 맞는 질문이라는 뜻이고, 수치가 같다는 뜻은 아니다.

### 2.2 P2 — 커버하는 스택이 쇼브를 맞음 (`covering_stack_vs_shove.json`)

max-skill, 40bb 스택, 쇼브 10/15/20bb, 뒤 좌석 있음. DB 비교는 유효 스택이 같은 call-vs-shove spot 이다(칩 EV 판단은 유효 스택만 본다).

| 쇼버 → 콜러 | 쇼브 10bb: DB 콜 / T2 계속 | 15bb | 20bb |
|---|---|---|---|
| UTG → BTN | 0.433 / 0.135 | 0.342 / 0.135 | 0.278 / 0.135 |
| CO → BTN | 0.421 / 0.193 | 0.351 / 0.193 | 0.287 / 0.193 |
| UTG → SB | 0.517 / 0.177 | 0.397 / 0.177 | 0.318 / 0.177 |
| BTN → SB | 0.493 / 0.289 | 0.397 / 0.289 | 0.342 / 0.289 |
| HJ → CO | 0.430 / 0.129 | 0.351 / 0.129 | 0.287 / 0.129 |

- T2 의 계속 빈도는 **쇼브 크기와 무관하게 같다.** `mdf(open_bb)` 표가 6bb 에서 고정되고, 그 밖에 가격을 보는 항이 없다.
- 쇼브가 작아질수록(가격이 좋아질수록) DB 는 넓어지는데 T2 는 그대로다.
- baseline 102건 중 89건이 폴드다. 4bb 이하 작은 올인 10건 중 6건이 폴드였다(예: 150bb 스택 Q4o/J5o 가 3bb 올인 폴드, BB J9o 가 2.2bb 올인 폴드). 일부는 다인원이라 폴드가 맞을 수 있다. 다만 판단식에 가격 항이 없다는 것이 구조적 문제다.
- 판정: **WRONG_QUANTITY**. 쇼브에 콜할지를 오픈 디펜스 폭으로 판단한다.

## 3. 세 경로에 같은 cap 을 써야 하는가

### 3.1 질문이 다르다

| 경로 | 실제 질문 | 맞는 판단량 | DB 근거 |
|---|---|---|---|
| P1 순수 콜오프(계산하는 사람) | 이 쇼브 레인지를 상대로 이 가격에 콜이 +EV 인가 | equity(상대 쇼브 레인지) vs 필요 equity(인지 bf) | 있음(2.1, 94%) |
| P4 내 스택 거의 전부(상대 비올인 또는 레이즈 가능) | 콜 / **리쇼브** / 폴드 중 무엇인가 | 콜: equity vs 가격. 리쇼브: 폴드 에쿼티 + 콜당했을 때 equity | 콜 부분은 같은 수학. 리쇼브 빈도는 비올인 오픈 대상 DB spot 없음 → MISSING_KNOWLEDGE |
| P5 계산하지 않는 사람 | 기억하는 콜 차트가 무엇인가 | 기억된 **call-vs-shove 차트**(GTO 지식) × 기억 정확도 | DB call-vs-shove 차트가 바로 그 지식이다(10~20bb, near). 20bb 초과는 없음 |
| P2 커버 스택, 뒤 좌석 있음 | P1 과 같은 질문 + 뒤 좌석 위험 + 아이솔레이션 선택지 | equity vs 가격 + `players_behind_required_equity_premium`(기존 단일 producer) | 콜 부분 있음. 아이솔레이션 빈도 MISSING_KNOWLEDGE |
| P6 쇼버 레인지 복원 | 이 자리·스택에서 첫 진입 쇼브하는 레인지는 무엇인가 | 쇼브 레인지 prior(쇼브 전용) | DB first-in jam 차트 4~20bb(near). 20bb 초과 MISSING_KNOWLEDGE |
| P7 쇼브 콜러 레인지 복원 | 이 사람이 쇼브에 콜하는 레인지는 무엇인가 | P1/P5 와 같은 콜 정책을 관찰자 입장에서 적용 | P1/P5 와 같다 |

### 3.2 판정

- 하나의 cap 을 다섯 질문에 쓰는 것은 **WRONG_QUANTITY** 다. 질문별로 나눈다.
- 현재 cap 은 디펜스 총량(9-max 출처 미상)에서 파생된 값이다. 완료된 DB 대비 콜 폭이 절반이고(0.199 vs 0.402), 스택이 줄어도 넓어지지 않는다. 어느 경로의 정답으로도 근거가 없다.
- legacy cap 은 객관 bf 로 나눈다. 다른 경로는 인지 bf 를 쓴다. 같은 사람이 경로에 따라 ICM 을 다르게 인지하는 셈이다.

### 3.3 P7 결함: 쇼브에 콜한 깊은 스택의 레인지에 프리미엄이 거의 없다

관찰자 복원(max-skill 관찰자, baseline 빈 Book), BB 가 BTN 20bb 쇼브에 콜한 경우의 클래스 질량(만점 = 콤보 수):

| 콜러 스택 | AA | KK | QQ | AKo | A9o | 76s | 전체 질량 |
|---|---|---|---|---|---|---|---|
| 21bb (cap 경로) | 6/6 | 6/6 | 6/6 | 12/12 | 12/12 | 0 | 426 콤보 |
| **60bb** (vs-open 플랫 구간) | **0.57/6** | **0.63/6** | 0.70/6 | 10.2/12 | 11.4/12 | 2.5/4 | 495 콤보 |

60bb 콜러는 vs-open 정책으로 복원된다. 그 정책에서 AA·KK 는 "3벳"할 핸드라 콜 가중치가 작다(`can_raise=True` 기본값). 하지만 올인에 대한 콜에는 3벳 선택지가 없다. 이 레인지는 다음 좌석의 equity 계산과 사이드팟 층 equity 에 들어간다. 판정: **WRONG_QUANTITY**(레인지 복원 의미 결함).
