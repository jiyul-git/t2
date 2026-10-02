# 재감사: 개념 등록부 completeness (2026-10-02)

기준: `test` `63bd82d` (semantic-audit 4차까지 fast-forward 된 상태) + 이 작업의 semantic-only 추출 3건.
행동 수정(R2 pf_rank, R1b 플랍 레이즈 레인지, OOP 체크레이즈)은 이번 범위가 아니다.
감사 조건은 baseline(tilt 0, exploit 중립, 동일 max-skill 프로필)이다.

## 1. 검색 방법 — "등록부에 없는 전략 semantic = 0"의 근거

`tools/check_semantic_completeness.py` 가 네 가지를 기계적으로 검사한다. 판단은 `SPAN_MAP.json` 작성 시점에 사람이 했고, 실행 시점에는 규칙만 적용한다.

| 검사 | 대상 | 소유 규칙 | 결과 |
| --- | --- | --- | --- |
| 1. 결정 지점(site) | 22개 production 모듈의 AST: `if/elif/while` 조건, 조건식, 소수 리터럴이 있는 계산·clamp·`random()`, 계산형 `return` 중 포커 도메인 토큰(rel, eq, need, pot, stack, outs, range, bluff, street, rng …)을 포함한 것 | (a) `SPAN_MAP` 코드 구간(가장 좁은 구간 우선) 또는 (b) 등록부가 정확히 한 개념의 producer로 지정한 함수. **여러 의미를 가진 19개 함수(DECOMPOSED)는 함수 단위 소유를 금지**하고 구간 단위로만 소유 | 1,136 / 1,136 소유, 미소유 0 |
| 2. 함수 | 같은 모듈의 모든 함수 548개 (결정 지점이 없는 매핑/조회 함수 포함) | 등록부 이름, 구간, 또는 사유가 적힌 `nonsemantic_functions`(수학 헬퍼·로깅·컨테이너) / `nonsemantic_modules`(UI·필드 런타임) | 미소유 0 |
| 3. 모듈 상수 표 | 16개 전략 모듈의 숫자를 담은 모듈 수준 대입 84개 (SIZING, OPENER_MULT, LEVEL_TIGHTEN, gto 표, icm 표 …) | `tables` 매핑 (개념 또는 `@nonsemantic`) | 미소유 0 |
| 4. 등록부 참조 | 등록부 producer/current_function 이 가리키는 모든 `module.function` | 실제로 존재해야 함 | stale 0 |

`@nonsemantic` 구간은 27개 site로, 전부 기록/provenance 필드 조립 또는 감사 레코드다(사유가 각 구간에 적혀 있다).

### 이 방법이 보장하지 않는 것
- site 추출은 구문 규칙이다. 리터럴도 조건도 없는 의미(예: 집합 멤버십만으로 정해지는 분기)는 2번 함수 검사로만 잡힌다. 그런 의미가 **이미 소유된 단일 의미 함수 안에** 숨어 있으면 걸러지지 않는다. 그래서 site 4개 이상인 비분해 함수 66개는 사람이 단일 의미인지 다시 읽었다(목록은 `SPAN_MAP.json`의 DECOMPOSED 바깥, 판정 근거는 아래 3절).
- "개념이 하나의 함수/구간에 소유된다"는 것이 "그 개념이 올바르다"는 뜻은 아니다. 정확성은 다음 단계(지식 정확성 감사)의 몫이다.
- 정적 검사다. 실행 도달성은 sim/verifier로 따로 본다.

## 2. 무엇이 빠져 있었나 (66개 신규 행)

기존 227행은 긴 함수를 우산 행 하나로 덮었다(`response_plan` = `decide_response` 전체, `value_line_selection` = `make_plan` 전체 등). 우산 안의 독립 질문을 분리 등록했다. 대표:

| 영역 | 새 행 (요지) |
| --- | --- |
| make_plan | perceived_board_danger, perceived_spr, potcontrol_disposition, value_when_called_strength(commit_rel), multiway/read/rel 밸류 문턱 이동 3개, bluff_evidence_composite, showdown_value_predicate, medium_strength_merge_value |
| decide_response | monster_made_hand_raise, value_raise_sizing_from_commit, value_raise_qualification, value_raise_frequency, bluff/semibluff 레이즈 빈도, implied_odds_adjustment, giveup_deviation_raise, price_overrides_giveup_plan |
| decide_aggression / decide_size | giveup_initiative_stab_deviation, bluff_execution_frequency, donk_suppression, value_bet_execution_frequency, value_blocker_size_adjust, deviation_bet_size_fallback, weak_hand_size_shrink, plan_size_band_clamp |
| act_with_plan | response_equity_basis(3단계 fallback), spr_commitment_flag, raise_target_coordinate, intent_chip_conversion |
| refresh | value_degradation_thresholds, semibluff_draw_loss_resolution, giveup_reentry_on_improvement, improved_bluff_rejudgment, value2_budget_exhaustion_upgrade |
| preflop | preflop_decision_routing/class, preflop_read_width_exploit, preflop_premium_slowplay_mix, allin_form_fold_equity_read, short_stack_open_widening, open_size_behind_read_adjust, **locked_allin_price_gate**(사용자 지적 사례), reraise_attack_evidence, iso_limper_read_widening, iso_sizing, players_behind_risk_premium |
| persona / reads / session / 공통 | self_hand_overconfidence_bias, call_threshold_bias, street_concept_alias, preflop_temperament_direction, concept_skill_gate, legacy_trait_adapter, read_polarity_signal, forced_bet_posting, multiway_representative_union_range, primary_opponent_selection, preflop_range_action_label, range_ordering_strength, continuation_bet_frequency_core, overbet_selection_core, checkraise_value_probability_floor |
| 지식/상태 | opponent_unconsumed_estimates(SHADOW), dead_strategy_tables(DEAD), opener_position_attack_table(OVERLOADED) |

전체 필드(의미·street·층·producer→consumer·입력·출력·지식 출처·축·상태·행동 영향·중복/과적재·canonical 이름·parent·코드 구간)는 `CONCEPT_FUNCTION_REGISTRY.csv/json` 의 origin `IMPLICIT_CODE_V2` 행.

## 3. 기존 감사 결과의 정정

| 대상 | 기존 기록 | 실제 코드 |
| --- | --- | --- |
| `called_aggression_ownership` | "직전 스트리트 **자신의 공격이 콜받은** 라인인가", street turn/river | 내가 **상대 공격을 콜했는가**(방향 반대). batch 1부터 플랍도 소비(프리플랍 어그레서 라인) |
| `perceived_edge` (range_read 자기 실력 인식) | 직전 보고에서 "baseline 영향 없음" | `preflop.feel_of → depth.depth_feel` 로 **baseline에서도 소비**된다. max-skill edge 0.40 → 체감 깊이 +0.016 (작지만 0 아님). `variance_seek` 경로만 0 |
| `defend_width_prior` | 지식 출처 K | 보정된 MTT8 디펜스 표는 **seats==8 + ante** 에서만 쓰인다. standard/main/lowbuyin(9-max)은 이전 공식 |
| refresh 승격 주석 | "made 항은 죽어 있다" | 그 항은 audit9에서 제거됐다(주석만 갱신, 동작 무관) |

비분해(단일 소유) 함수 중 site 4개 이상인 66개는 site 목록으로 모두 대조했고, 그중 여러 의미가 섞일 위험이 큰 24개(attach_intent, bluff_mode, _allowed, spread_curve, checkraise_size, apply_layer_bet_ev_judgment, open_pct, opp_size_norm, variance_seek, money_pressure.read_adjustment, open_size_bb, calloff_cap, made_strength, _preflop_story_range, _preflop_perceived_range, _locked_postflop_range, defend_thresholds, _update_pf_state_after_apply, street_outcome, calloff_layer_judgment, trap_judgment, opp_bet_prob, defend_decision, observe_postflop)는 본문까지 다시 읽었다. 모두 단일 질문(입력이 여럿인 한 판단)으로 판정했다. 남긴 메모:
- `bot.made_strength` 가 '보드 카테고리를 넘는 전체 카테고리'를 반환해 포켓페어+보드페어=투페어(2)가 된다 — HAND 63/R5c와 L-RA09의 공통 뿌리.
- `trap_judgment` 의 latent.study 직접 사용(기존 ledger).
- `defend_decision` 과 `multiway_reraise_decision` 의 재레이즈 팟 추정식이 조금 다르다(1.5+open×(1+callers) vs 그 값과 pot_bb 중 큰 값).
- `_locked_postflop_range` 의 3벳 재라벨은 exploit w>0 일 때만 동작(baseline에서는 pf_seed 라벨 사용).

## 4. 중복/과적재 신규 항목

`DUPLICATION_AND_OVERLOAD_LEDGER.md` 의 L-RA01~L-RA17. 행동을 바꾸지 않고 처리한 것은 L-RA05(병합) 하나, 나머지는 판정만 기록했다. 중요한 것:

- **L-RA02** 같은 질문("살아 있는 어그레서 앞에서 먼저 칠까")에 세 메커니즘(블러프 동크 억제 0.03~0.70, pot_control 0.04 고정, 밸류 재리드 0.04~0.16).
- **L-RA03** "콜당했을 때도 앞서는가"를 네 곳이 서로 다른 지표·문턱으로 계산.
- **L-RA07** 리버에서 `turn_card_effect(flop, river card)` — 턴 카드를 무시하고 이름과 다른 질문을 계산.
- **L-RA09** giveup 재진입이 `made>=2`(보드 페어 포함)를 근거로 씀 — HAND 63(R5c)과 같은 원인의 다른 소비처.
- **L-RA10** 다인원에서 equity는 seat 풀, 일부 게이트는 합집합 레인지.
- **L-RA12** audit9 R4에서 내가 `OPENER_MULT`(리쇼브 폭 표)를 오픈쇼브 포지션 깊이 대용으로 재사용 — 과적재를 새로 만든 것.

## 5. semantic-only 추출 (행동 불변)

| 추출 | 이전 | 근거 |
| --- | --- | --- |
| `icm.players_behind_required_equity_premium` | `plan.calldown_need`, `preflop.multiway_reraise_decision` 에 같은 식 | 같은 poker question, 같은 식 → 단일 producer |
| `plan.has_showdown_value(made, equity, mw)` | make_plan 의 두 inline 조건 | 식은 같고 equity 기준(eq vs eq_current)만 다름 → 기준을 호출부 인자로 드러냄 |
| `plan.line_owned_by_live_aggressor` | decide_aggression inline(턴/리버 + 플랍 규칙) | 라인 소유 질문 하나를 명명 |

추가하지 않은 것: overpair_love / see_line 추출(현재 baseline 소비 없음 또는 0으로 clip, 의미 중복 없음 → 기록만), 새 skill, 새 계수, RNG 순서 변경.

검증은 `REFACTOR_AND_VERIFICATION.md` 5차 항목.
