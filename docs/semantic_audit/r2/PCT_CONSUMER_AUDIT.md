# A. PCT_CONSUMER_AUDIT — pf_rank/PCT 소비처 전수 감사 (R2-A)

기준 `test` `46a2070`. 이 문서는 판정만 한다. production 숫자, 순서, 행동은 바꾸지 않았다.

정정(2026-10-02): `NEEDS_SOLVER_DATA` 를 `MISSING_KNOWLEDGE` 로 바꿨다. 9-max 비교는 계산이 끝난 GTO DB spot(`chatgpt/gto-reference-20260928`)과 신뢰할 수 있는 공개 자료만 쓴다. 1절의 8-max 측정은 순서의 *모양*에 관한 것이라 유지한다.

## 0. 대상과 찾은 방법

- 직접 소비: `preflop.PCT`, `preflop.legacy_preflop_order_percentile`, `preflop.pct`.
- 파생 소비:
  - `ranges._SORTED`(PCT 순서로 정렬한 1326 콤보)
  - 위 값을 인자로 받는 `hand_pct` / `r` 지역변수
- 두 번째 순서표: `bot._pf_score` → `bot._SCORED` / `bot.range_combos`.

검색 방법:
- `grep -n "pf_rank|PCT|legacy_preflop_order_percentile|\bpct(|_SORTED|hand_pct|range_combos("`
- 재감사 등록부(293행)에서 pf_rank/percentile 을 언급하는 13행과 대조했다.
- `tools/`, `legacy/`, `audit.py`, 테스트는 production 이 아니어서 제외했다.

### pf_rank.json 의 정체

169개 핸드 클래스에 누적 콤보 백분위(0~1)가 들어 있다. AA = 6/1326 = 0.0045 이다.

- **출처:** 커밋 기록상 출처가 없다. 최초 커밋 `39bbc966` 에 이미 있었다.
- **특이한 순서:**
  - 66, QTs, KTs 가 AKo 보다 위(AKo 0.071)
  - K9s 가 AQo 보다 위
  - 22 가 ATo 보다 위
  - 이 순서는 HU all-in equity 순서도, 공개 RFI 순서도 아니다(4절 측정).

## 1. 정량 근거: "순서"가 맞는가, "양"이 맞는가

`tools/r2_ordering_fidelity.py`(결과 `ordering_fidelity.json`)로 측정했다.

방법:
- 공개 8-max MTT 차트(C 문서의 출처와 같음)의 각 액션 집합(오픈, 계속, 3벳, 올인, 콜)을 기준으로 삼았다.
- 코드가 실제로 하는 것처럼 같은 질량의 "상위 k% 슬라이스"를 잘랐다. 콜은 (tp, tot] 구간이다.
- 그 슬라이스 안에 기준 액션 질량이 몇 %나 들어오는지(agreement)를 쟀다.
- 비교군으로 "HU all-in equity vs 랜덤 핸드" 순서(`eq_vs_random_169.json`, 6000 sims, 고정 seed)도 같은 방식으로 쟀다.

차트 노드 15~100bb 를 평균한 결과:

| 결정 family | 노드 수 | pf_rank 평균 (최소) | equity 순서 평균 (최소) | 뜻 |
|---|---|---|---|---|
| RFI 오픈 집합 | 36 | **0.90** (0.82) | 0.84 (0.75) | 순서로 충분하다. pf_rank 가 오히려 낫다 |
| vs-open 계속(콜+3벳) 집합 | 50 | **0.90** (0.77) | 0.84 (0.71) | 순서로 충분하다 |
| vs-open 3벳 집합 | 50 | 0.61 (0.33) | 0.65 (0.43) | 상위 슬라이스는 3벳 집합의 모양이 아니다 |
| vs-open 올인 집합 | 29 | 0.53 (0.00) | 0.57 (0.00) | 같음 |
| vs-open 콜 집합 (tp,tot] | 50 | 0.61 (0.00) | 0.53 (0.00) | 3벳을 위에서 잘라내니 콜 구간도 어긋난다 |
| vs-3bet 계속 (오프너 레인지 조건부) | 18 | 0.85 (0.62) | 0.80 (0.56) | 순서로는 대체로 맞다 |
| vs-3bet 4벳 집합 | 18 | **0.41** (0.00) | 0.47 (0.00) | 상위 슬라이스와 크게 다르다 |
| cold 4벳 집합 | 6 | 0.59 (0.49) | 0.71 (0.60) | 같음 |

판정:
- "어떤 핸드가 계속하는가"를 묻는 곳(오픈, 계속 집합)에서는 **pf_rank 순서가 문제가 아니다**(ORDERING_OK).
- "어떤 핸드로 공격하는가"(3벳, 4벳, 올인)를 같은 순서의 상위 슬라이스로 정하는 것은 **양(모양)이 틀린다**(WRONG_QUANTITY).
  - 순서표를 equity 순서로 바꿔도 0.41~0.71 수준이다. 그러니 순위표 교체로는 고쳐지지 않는다.
  - 공격 집합은 블로커, 폴라라이즈, 플레이어빌리티를 포함한 별도 지식이 필요하다.
- 이 측정은 8-max 차트 기준이다. 순서의 *모양*에 관한 결론이고, 9-max 빈도 값의 근거로는 쓰지 않는다.

## 2. 소비처 표

질문 = 그 함수가 실제로 알고 싶은 것. 필요한 양: O = 순서만, W = range 폭(prior 빈도), E = 상대 레인지 대비 equity, P = 가격(필요 equity), F = 폴드 에쿼티, B = 블로커/카드 제거, V = 액션별 EV, S = solver prior 빈도.

| # | 소비처 (파일:줄) | 실제 질문 | 지금 쓰는 양 | 필요한 양 | 판정 | 근거 / 메모 |
|---|---|---|---|---|---|---|
| 1 | RFI `preflop.open_decision` `r <= thr` (preflop.py:336, 358) | 이 핸드가 이 자리·스택의 오픈 레인지에 드는가 | O(pf_rank) + W(`gto.rfi`) | O + W | **ORDERING_OK** | 오픈 집합 agreement 0.90. 폭은 R2-B 와 별개(RFI 는 8-max 교정, 9-max UTG `RFI_BY_BEHIND[8]` 은 교정 밖) |
| 2 | 오픈 형태 `open_form` 손 대역 0.06/0.55, 성향항 0.10/0.25 (preflop.py:252-263) | 레이즈로 열까 올인으로 열까 | O 의 계단 대역 | F + E(콜당했을 때) + V(쇼브 vs 레이즈) | **WRONG_QUANTITY** | 형태 결정은 EV 비교 질문이다. 9-max GTO DB 에 첫 진입 쇼브 spot(4~20bb, near)이 있어 비교할 수 있다(이번 단계에서는 미실시) |
| 3 | 림프 `limp_p` 대역 0.03/0.30, 0.05/0.12/0.25 (preflop.py:194-202) | 이론형: 20bb 이하에서 림프가 레이즈보다 나은 손인가. 습관형: 사람의 림프 습관 | O 의 계단 대역 | 이론형 S(숏스택 림프 빈도), 습관형은 D(의도된 인간 오류)라 O 로 충분 | 이론형 **MISSING_KNOWLEDGE**, 습관형 **APPROXIMATION_ACCEPTABLE** | 이론형 레인지(22-88, A2s-A8s)가 pf_rank 대역 0.03~0.30 과 실제로 겹치는지 미검증 |
| 4 | iso `iso_decision` `r <= thr`, 오버림프 `r <= thr×2.2` (preflop.py:1228-1240) | 림퍼 상대 아이솔레이트 레인지에 드는가 | O + W(오픈 폭 × iso) | O + W(iso prior) | **ORDERING_OK**(순서) / 폭은 **UNSUPPORTED_PRIOR** | iso 폭은 오픈 폭에서 파생된 것이고 독립 prior 가 없다. 기준 자료가 없다 |
| 5 | vs-open 계속 `defend_action_likelihoods` `w_cont` (preflop.py:787) | 이 핸드로 계속하는가 | O + W(`tot`) | O + W(디펜스 prior) | 순서 **ORDERING_OK** / 폭은 R2-B | 계속 집합 agreement 0.90. 폭 문제는 C 문서 |
| 6 | vs-open 3벳 `w_raise` 로지스틱 + `(0.35+0.65(1-r/tp))` (preflop.py:768-770) | 이 핸드로 3벳하는가 | O 상위 슬라이스 (0, tp] | S(3벳 집합) + B + 폴라라이즈 | **WRONG_QUANTITY** | 3벳 agreement 0.61. 추가로 `tp` 폭의 약 절반만 실제 3벳 빈도가 된다(C 문서 3.3) |
| 7 | 콜 구간 (tp, tot] | 플랫할 핸드인가 | O 중간 슬라이스 | S(콜 집합) | **WRONG_QUANTITY**(파생) | 6의 결과로 생긴다. 콜 agreement 0.61 |
| 8 | 프리미엄/슬로플레이 `r <= 0.03` 폴드 금지, `r <= 0.015/0.04` 콜 축소, `_pf_slow` premium `(0.10-r)/0.10` (preflop.py:772-800) | 최상단 핸드인가 | O 최상단 | O | **ORDERING_OK** | 상위 3% = AA-TT, AKs. 최상단 동일성은 두 순서 모두 같다. 슬로플레이 혼합 비율 자체는 별도(D 판정은 R2 범위 밖) |
| 9 | 핫존 리쇼브 `p_hot` `r <= rs`, `depth = 1-r/rs` (preflop.py:756-761) | 이 스택에서 3벳 올인이 +EV 인가 | O + 휴리스틱 폭 `reshove_range` (OPENER_MULT, 공격성) | F + E(콜 레인지 대비) + P, 또는 S(리쇼브 차트) | **WRONG_QUANTITY** + **MISSING_KNOWLEDGE** | 올인 집합 agreement 0.53. `reshove_range` 폭은 출처가 없다. 9-max GTO DB 에 비올인 오픈 대상 리쇼브 spot 이 없다. `OPENER_MULT` 과적재는 L-RA12 |
| 10 | vs-3bet (오프너가 HU 3벳을 맞음) `defend_decision(def_pos=오프너, opener_pos=3벳터, raise_level=2)` (plan.py:2733 → preflop.py:843) | 내 오픈 레인지 중 무엇으로 계속/4벳하는가 | O + **vs-open 디펜스 prior 를 위치만 바꿔서** × LEVEL_TIGHTEN[3]=0.34 | S(vs-3bet prior, 오프너 레인지 조건부) + P | **MISSING_KNOWLEDGE** | `gto.defend_pct(LJ, BTN)` 은 "LJ 가 BTN 오픈을 디펜스"하는 값이다. 3벳터가 BB 면 `rfi(BB)=0` 이라 `DEF_A` 만 남는다. 계속률: 코드 7~25% vs 기준 43~89%. baseline sim(시드 11·12) `opener_backaction` 비올인 87회 중 73회 폴드(84%) |
| 11 | 4벳/cold 4벳 `multiway_reraise_decision` / `cold_reraise_decision` 기본 확률 (preflop.py:1047 → `defend_action_likelihoods`) | 다인원/콜드 상황에서 재재레이즈할까 | O + LEVEL_TIGHTEN + equity 증거(eq vs fair, locked 가격 게이트) | S(cold 4벳 prior) + E + P + B | **MISSING_KNOWLEDGE**(prior) / 증거층은 E·P 를 이미 씀 | cold 4벳 agreement 0.59. 기본 확률은 #10 과 같은 swap 구조 |
| 12 | 콜오프 `calloff_cap`/`calloff_decision` `r <= cap`, `cap = tot×CALLOFF_TIGHTEN×2.6×…` (preflop.py:1247-1398) | 올인을 콜할 equity 가 가격(ICM 포함)을 넘는가 | O + 디펜스 폭에서 파생한 cap | E(쇼버 레인지 대비) + P(ICM) | **WRONG_QUANTITY** | 9-max GTO DB(HoldemMath 쇼브 대면 콜 144 spot) 대비 cap 이 평균 0.17~0.33 좁다(`9MAX_DEFEND_PRIOR_PROVENANCE.md` 3절). 순수 콜오프(상대 올인 + 레이즈 불가)는 `calloff_layer_judgment`(E+P)가 pf_defend 게이트 통과 시 대체한다(plan.py:2757). 남은 경로: `defend_action_likelihoods` 의 `_hero_calloff`(open ≥ 스택×0.92, 상대 비올인)는 여전히 percentile 이다 |
| 13 | 오픈쇼브 판단 깊이 `open_form` `_pos_depth = OPENER_MULT` | 뒤 인원 대비 쇼브 위험 | 리쇼브 표 재사용 | F(뒤 좌석 콜 확률) | (pf_rank 직접 소비 아님) L-RA12 과적재 | R2 범위에서 R2-B 리쇼브 지식과 함께 다룬다 |
| 14 | 상대 레인지 구성 `ranges.preflop_range` open `hi=base` / limp `hi=base×2.6` / 기본 3벳 `t['threebet']×3` / polar 3벳 밴드 (ranges.py:328-378) | 관찰된 액션으로 상대 레인지 추정 | O 슬라이스 | 액션별 S(상대 모델) | open **ORDERING_OK** / limp·polar·opener 없는 3벳 **UNSUPPORTED_PRIOR** | call/3bet(opener 있음)은 `_defend_likelihood_range` 로 #5~7 과 같은 정책을 공유한다. 행동 지식과 관찰 모델이 같은 오류를 공유한다 |
| 15 | 4벳+ 사후 레인지 `ranges.preflop_reraise_posterior` `exp(-q/rate)` (ranges.py:250) | 4벳한 상대의 레인지 | O 분위 가중 + wheel-A 블로커 채널 | S(4벳 레인지 모양) + B | **WRONG_QUANTITY**(모양) | 4벳 집합 agreement 0.41. 단조 감소 가중은 폴라 구조(A5s 류 외)를 표현하지 못한다 |
| 16 | 블로커 몫 `preflop_blocker_share` 최상단 20% 정의 (preflop.py:937) | 내 카드가 상대 최상단 밸류를 지우는가 | O 최상단 | O(최상단 정의) + B | **ORDERING_OK** | 최상단 20% 정의에만 쓴다 |
| 17 | 쇼다운 기반 레인지 확장 `runner.adjust_range_by_history` 중앙값 > 0.55 → cap = max×1.5 (runner.py:332-345) | 이 사람이 예상보다 넓게 치는가 | O 분위 | 관찰 빈도(VPIP 등) | **APPROXIMATION_ACCEPTABLE** | 상대 적응 경로다(L-RA18). baseline 고정 대상이고 R2 행동 수정 대상이 아니다 |
| 18 | 쇼다운 관찰 `reads.Book.observe_showdown` `hand_pct > 0.45 & aggressor → sd_weak`, `< 0.20 → sd_strong` (reads.py:355-362, session.py:2705) | 상대가 약한 핸드로 공격했는가 | 프리플랍 분위 | 쇼다운 시점의 핸드 강도/라인 | **WRONG_QUANTITY** | 72o 로 풀하우스를 만든 공격도 "weak" 로 센다. exploit 경로라 baseline 에서 중립이다. 기록만 남긴다 |
| 19 | 머니점프 반사실 `money_open` (preflop.py:351-357) | 머니점프가 진입을 바꿨는가 | #1 과 같은 r, thr | 같음 | **ORDERING_OK** (기록) | 행동은 #1 의 thr 경로다 |
| 20 | 기록 전용 `plan.preflop_plan` `pf_hand_pct`, `calloff_ev_comparison`, `defend_action_likelihoods` 반환 `hand_pct` | 텔레메트리 | O | — | nonsemantic | 행동 영향 없음 |
| 21 | 두 번째 순서표 `bot._pf_score` → `range_combos(0.35)` (bot.py:139-151, plan.py:424/462/2268) | 상대 레인지가 비었을 때 기본 레인지 | **별도 공식 순서**(하이카드×2 + 페어/수티드/갭 보너스) | O(하나의 순서) | **WRONG_QUANTITY**(중복 순서) | 같은 질문("프리플랍 핸드 순서")에 순서가 둘이다. fallback 전용이라 빈도는 낮다 |
| 22 | `ranges._SORTED` 반복 순서 (ranges.py:302, 319) | 클래스 대표 선택, 출력 순서 | O 정렬 | — | nonsemantic(순서 의존) | 행동 값과는 무관하다. 다만 리스트 레인지의 원소 순서와 tie-break 이 PCT 순서를 따른다. 순서를 바꾸면 tie 처리나 표본 순서로 행동이 바뀔 수 있다(D 문서 1절의 동결 근거) |

hotzone 의 `in_hotzone`, `reshove_weight`, `hotzone_pressure` 는 스택만 본다. PCT 는 #9 경로로만 들어온다.

## 3. 요약 판정

- **순서로 남길 것 (ORDERING_OK):**
  - #1 RFI 진입
  - #4 iso 진입 순서
  - #5 계속 집합
  - #8 프리미엄
  - #14 open 레인지
  - #16 블로커 최상단
  - #19 머니점프 기록
- **양이 틀린 것 (WRONG_QUANTITY):**
  - #2 오픈 형태
  - #6·#7 3벳/콜 분할
  - #9 리쇼브
  - #12 남은 percentile 콜오프
  - #15 4벳 사후 모양
  - #18 쇼다운 관찰
  - #21 중복 순서
- **지식이 없는 것 (MISSING_KNOWLEDGE):** #10 vs-3bet, #11 4벳·cold 4벳 prior
- **근거 없는 prior (UNSUPPORTED_PRIOR):**
  - #4 iso 폭
  - #14 limp, polar 3벳 레인지 모델
- **9-max 완료 spot 이 없는 것 (MISSING_KNOWLEDGE):** #3 이론형 림프, #9 리쇼브 폭(비올인 오픈 대상)

전역적으로 pf_rank 를 equity 로 바꾸는 것은 근거가 없다(1절). equity 순서도 공격 집합을 재현하지 못한다.
