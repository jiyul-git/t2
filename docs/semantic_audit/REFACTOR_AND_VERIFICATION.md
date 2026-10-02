# REFACTOR_AND_VERIFICATION

감사 baseline: `4b9d33d5f951fce4b292f6e6e79caaf141b106d2`. 감사 6종을 먼저 작성·보고한 뒤 아래 변경을 적용했다. 수치·threshold·probability·skill 분포·GTO 빈도 변경 없음. master promotion/merge/branch 정리 없음.

## 실제 변경

| 개념 | 현재 canonical 함수 | 보존한 경계 |
| --- | --- | --- |
| flop cbet / turn barrel / river barrel | plan.cbet_flop_frequency / barrel_turn_frequency / barrel_river_frequency | 기존 capability와 상수 그대로; 같은 계산 본문은 _continuation_frequency 공유, cbet_freq는 호환 dispatcher |
| draw가 가능한 체크레이즈 | plan.checkraise_draw_street_probability | flop/turn 동일 poker question은 공유. flop/late skill 공급은 기존대로 |
| 리버 체크레이즈 | plan.checkraise_river_probability | semibluff branch 없음; 기존 river_bluff label 누락을 새로 고치지 않음 |
| value 체크레이즈 하한 | plan._checkraise_value_floor_probability | 같은 식 한 producer, RNG 없음 |
| 드로우 완성 근거 | plan.draw_completion_supports_value | made>=4 또는 rel>=.62 그대로. turn/river 결과는 별도 |
| 강도 상승에 따른 value 승격 | plan.strength_improvement_supports_value | .88 또는 .70 이상 실제 증가 조건 보존 |
| 리버 value 재평가 | plan.river_value_reassessment | continue-range equity/skill gate/RNG/why 기록 그대로 |
| 리버 draw 종료 | plan.river_semibluff_resolution | value/SD/미스 bluff/giveup 전환을 별도 질문으로 추출 |
| continue support 폭 | ranges.continuation_support_fraction | call-only/raise불가 inclusive partition은 별도 유지 |
| 부분 range 인지 | ranges.blend_action_range_by_grasp | 3곳 동일 blend 통합; 낮은 skill early exit 및 posterior 생성 시점 보존 |
| PCT ordering | preflop.legacy_preflop_order_percentile | pct compatibility 유지. ordering을 equity/EV로 교체하지 않음 |
| standalone runtime | setup_run_dir.py / .sh | 기존 action_events/telemetry_sync 의존 모듈 복사 누락 복구 |
| canonical 문서 | 10개 모두 현행 주석/링크 및 주요 stale 문장 동기화 | 역사 실험결과와 이상적 설계 불변식은 삭제하지 않음 |

`CONCEPT_FUNCTION_REGISTRY.csv/json`의 `function/evidence`는 before 증거, `current_function`은 현재 연결이다. street matrix에 실제 추출 이름도 연결했다. 공유 scalar의 의미를 분리해서 이름 붙이는 것과 독립적인 새 scalar를 만드는 것은 다르다. 후자는 이번에 하지 않았다.

## 검증

- 전체 Python syntax compile PASS; standalone 새 runtime import PASS.
- targeted verifier: **4,638 비교 PASS**, pristine 실제 함수 본문과 boundary 비교. 리버 호출 후 RNG state 동일.
- 기존 regression의 6 seed × 30 hands: **180 hands**, before/after action fingerprint **6/6 동일**.
- 같은 실행에서 Random 인스턴스 생성, random/getrandbits 호출 수, 순서별 반환값 digest, 각 인스턴스 최종 getstate digest **모두 동일**. Gaussian spare state도 getstate에 포함된다.
- live2 actual field/replay smoke: 18 entrants, standard 9max, seed 9011, 4 hero hands / 8 captured completed hand executions. action+metadata+Book/result hash, final field hash, RNG counts/draw/final-state hash 전부 동일. 병렬 UI worker 자체의 새 full-suite 검증은 아님.
- 기존 verifier 40개: before **26 PASS / 12 FAIL / 2 TIMEOUT**, after **26 PASS / 12 FAIL / 2 TIMEOUT**. 새 실패 없음. timeout은 180초 제한이며 PASS로 세지 않았다.
- 과거 `regress --baseline current`는 수정 전부터 6/6 seed mismatch. frozen baseline 미갱신. 이번 판정은 pristine HEAD와 직접 비교한다.

| seed | before = after action SHA prefix |
| --- | --- |
| 3000 | 16c9afad4c061757 |
| 3001 | dc0e1a4d34ee9c5c |
| 3002 | 07f2421433565171 |
| 3003 | 71e6f3ee18ad2171 |
| 3004 | b94b9086d38600f3 |
| 3005 | 0d63c34dcfb9c118 |

### 기존 실패를 숨기지 않음

f3_checkraise_response, f4_facing_bet, f5_backaction, f6_caller_backaction, f7_street_closure, p4_vs_3bet, weighted_aggregate_transform, weighted_boundaries, replan_contract, prelogic_execution_boundary, telemetry_wiring, tournament_telemetry: 모두 baseline에서도 실패. 세부 assert/exception은 evidence/verifiers_before.json과 after.json에 보존한다. 제거된 API/변경된 sizing 계약을 기대하는 과거 test와 실제 미해결 계약을 일괄적으로 “stale tests”라 단정하지 않는다.

human_model_v2, human_model_v3_integration: before/after 모두 timeout. 개별 opt-in calculation/recency/temper direction 및 v3 구조 verifier는 통과했으나 두 장기 suite 완료를 주장하지 않는다.

## 미해결과 범위

모든 의미 과적재를 제거했다고 주장하지 않는다. 227행 registry에 active/shadow/opt-in/fallback/dead/duplicate/overload를 구분했고, 행동이 바뀌는 scalar 분리·새 지식·오류 교정은 DUPLICATION_AND_OVERLOAD_LEDGER 후속 목록에 남겼다. 현재 diff는 의미를 드러내고 동일식 producer를 통합하는 변경이다. sampled parity는 전 입력공간의 형식 증명이 아니다.

소스 corpus는 baseline 268 Python파일/2,214함수 AST census다. tools/reference까지 census에는 포함했지만 이들을 production 개념으로 오인하지 않았다. 런타임 host 배포/opt-in 환경변수는 원격 기기에서 검증하지 않았다.

## 재현

저장소 루트에서 `python tools/verify_semantic_cleanup.py`.

`tools/measure_semantic_parity.py ROOT OUTPUT --seed 3000 --hands 30`은 해당 ROOT를 import하여 regress action/RNG를 측정한다. pristine `git archive 4b9d33d...` 디렉터리와 candidate를 각각 별도 프로세스에서 실행하고 JSON 전체를 비교한다. `--mode live`는 독립 복사 디렉터리에서만 사용한다(상태·archive를 쓴다). telemetry_config가 있으면 측정을 거부한다. RNG 도구는 wallclock/os.urandom을 비교하지 않으며, 명시 game seed를 사용해 action RNG를 고정한다.

증거는 evidence/의 JSON, 이전 regression log, remote refs, master↔test 코드 diff에 보존했다.

### F5 실패 출력 차이의 원인 추적

기존 F5 fixture는 size_shape_seed를 전달하지 않아 shape_planned_target이 Random(None)을 생성한다. baseline assert 결과 600, candidate 500 차이가 관측되어 별도 추적했다. 같은 20개 size seed를 명시한 paired 재검증은 모두 동일했다(evidence/f5_fixed_seed.json). 기존 verifier를 조용히 수정하거나 이를 새 전략 차이로 오인하지 않았다.

## 2차 semantic cleanup: preflop defend

기준 `6feaf56`. 기존 defend_thresholds의 inline 계산을 normalize_defend_prior_widths, adjust_defend_widths_for_callers, adjust_defend_widths_for_short_stack, tighten_defend_widths_for_raise_level로 추출했다. 상수·연산 순서·기존 producer/consumer·행동 라벨을 유지했다. 공유 4bet prior 문제를 해결했다고 주장하지 않는다.

- syntax/import PASS. 실제 이전 함수 AST와 직접 비교: threshold 3,600 / likelihood 384 / action+RNG 768건 PASS. 9max 중심, 8max 호환 및 PREFLOP_REASONING_V3 OFF/ON 포함.
- 기존 semantic cleanup verifier 4,638 비교 PASS.
- 6 seeds × 30 hands = 180 hands 재실행. 이전 stage1 after 증거와 JSON 전체(행동, 통계, RNG 호출 수·추출 순서 digest·최종 상태 digest) 6/6 정확히 일치. `6feaf56`은 stage1 이후 문서만 변경했으므로 같은 실행 기준이다.
- 기존 40 verifier 및 live2 suite는 이번 단계에서 재실행하지 않았다. 이전 PASS/FAIL/TIMEOUT 결과를 이번 새 통과로 세지 않는다.
- 증거: evidence/defend_stage2_targeted.json, defend_stage2_parity.json, defend_stage2_3000..3005.json. 재현: python tools/verify_defend_semantic_cleanup.py 및 tools/measure_semantic_parity.py.
