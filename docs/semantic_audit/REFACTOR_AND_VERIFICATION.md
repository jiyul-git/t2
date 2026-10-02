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

## 3차 semantic cleanup: range_read 소비 경계

기준 `33df2ee`. [소비 경계 상세](RANGE_READ_CONSUMER_BOUNDARIES.md). range 복원 계산·관측치 해석 dict 생성·bluff 위협 해석·legacy 적용 가중치·콜 문턱 적용의 본문을 분리했다. 기존 값 공급/early return/threshold/RNG 호출은 보존했다.

- syntax/import PASS. 직접 비교 1,308건 및 입력 경계 검사 4건 PASS.
- 기존 semantic verifier 4,638건, defend verifier 4,752건 PASS.
- 6 seeds × 30 hands = 180 hands: 직전 단계 evidence/defend_stage2_SEED.json과 전체 JSON 6/6 일치. action/statistics/RNG 호출 수·반환 순서 digest·최종 상태 digest 동일.
- 이번에는 live2와 기존 40개 verifier를 재실행하지 않았다. 기존 실패를 해결하거나 새 통과로 계산하지 않는다.
- evidence/range_read_stage3_*에 결과 보존. `python tools/verify_range_read_semantics.py`로 직접 비교를 재현한다.
- 적용 경계 분리는 전체 raise consumer의 독립 application skill 도입을 뜻하지 않는다. 관측 품질·self-edge·multiway·money pressure 소비는 후속 목록에 남긴다.

## 4차 semantic cleanup: 추가 read 소비 경계

기준 `b486969`. reads.observation_accuracy_from_capabilities, money_pressure.pressure_application_capacity, preflop.multiway_evidence_application_capacity, preflop.apply_multiway_call_evidence로 계산 본문을 분리했다. profile/actor 공급과 기존 상수·확률·RNG는 유지했다.

- syntax/import PASS. 실제 이전 consumer 비교 362건, 경계 검사 5건 PASS. controlled equity multiway 72건과 실제 equity multiway 4건은 action·진단 dict·RNG 상태를 함께 비교했다.
- 이전 verifier: range_read 1,308건+경계 4건, defend 4,752건, semantic 4,638건 PASS.
- 6 seeds × 30 hands = 180 hands: 직전 range_read_stage3 증거와 action·통계·RNG 호출 수·반환 순서 digest·최종 상태 digest 포함 전체 JSON 6/6 일치.
- evidence/read_stage4_*에 raw 결과와 함수 입력 목록 보존. 재현: python tools/verify_remaining_read_semantics.py.
- 이번 단계에서 기존 40개 verifier 및 live2를 재실행하지 않았다. 이전 실패/timeout은 미해결이다.
- pressure helper는 기존 mean01 능력 혼합을 드러낸 것으로, 모든 압박 단계의 knowledge/reasoning 분리가 끝났다는 의미는 아니다. multiway attack 억제는 원래 위치를 유지했다.

## 5차(재감사) — completeness 대조 + semantic-only 추출 3건

기준 `63bd82d`. 행동 수정(R2/R1b/OOP 체크레이즈)은 포함하지 않는다.

| 추출 | 이전 위치 | 보존한 경계 |
| --- | --- | --- |
| `icm.players_behind_required_equity_premium(base_need, n)` | `plan.calldown_need`(need, call_need 두 번), `preflop.multiway_reraise_decision` | 같은 식 `(1-base)*min(0.18, 0.06*n)`, 같은 연산 순서 |
| `plan.has_showdown_value(made, equity, mw)` | `make_plan` 의 `_sd_here`(eq), `has_sd`(eq_current) | 각 호출부가 기존 equity 기준을 그대로 넘김 |
| `plan.line_owned_by_live_aggressor(plan_state, street, initiative, oop_vs_aggr)` | `decide_aggression` inline | 턴/리버 콜 이력 + 플랍 프리플랍 어그레서 규칙, 순수 함수 |
| refresh 주석 | "made 항은 죽어 있다" | 주석만 현재 코드에 맞춤 |

검증:
- `tools/verify_reaudit_semantic_extraction.py HEAD`: pristine HEAD 체크아웃과 작업 트리에서 같은 결정적 probe를 돌려 바이트 비교 — calldown_need 400, decide_aggression 1,500, make_plan 전체 상태 500, cold re-raise 120건 **동일**(RNG 상태 포함). 변이 테스트(0.06→0.061, 0.42→0.50, 플랍 소유 규칙 삭제)로 네 probe 모두 차이를 잡는 것을 확인.
- 기존 parity verifier 4종(semantic_cleanup 4,638 / defend 4,752 / range_read 1,308+경계 / remaining 362+경계) PASS.
- baseline sim(tilt 0·exploit 중립·max-skill, 시드 11/12, 1,149핸드): 이전 `test`와 핸드 로그·판단 기록 전체·프리플랍 seed **바이트 동일**.
- 23-gate: 통과/실패 집합 동일(17/23).
- 전체 verifier 71개: `CANONICAL_VERIFIER_MANIFEST.md` (pristine HEAD vs 작업 트리).
- `tools/check_semantic_completeness.py`: site 1,136 / 함수 548 / 상수 표 84 / 등록부 참조 전부 소유, 미소유 0.

## 6차 — 9단계 B1 (preflop semantic-only refactor)

기준 `e6de033`. 잔여 분류는 [stage9/STAGE9_TRIAGE.md](stage9/STAGE9_TRIAGE.md), 항목별 상태는 ledger 의 "9단계 B1" 절.

| 추출/명명 | 이전 위치 | 질문 |
| --- | --- | --- |
| `persona.positional_chart_flattening` | open_pct inline | 좌석 조건 인식이 차트를 평균 쪽으로 누르는 몫 |
| `persona.chart_deviation_room` | open_pct / preflop_reasoned_width / defend_thresholds 의 `(1-acc)` | acc 의 이탈 상한 역할 |
| `gto.open_size_defend_scale` | defend_pct 두 경로의 `mdf(open)/mdf(3)` | 오픈 사이즈 폭 보정 대용 |
| `preflop.limp_theory_knowledge` | limp_p inline | 림프 이론 지식 공급(RFI 기억 공유) |
| `preflop.open_entry_threshold` / `apply_money_open_threshold` | open_decision inline | RFI 진입 폭 / 머니점프 반사실 기록 |
| `preflop.iso_entry_threshold` | iso_decision inline | iso 폭(오픈 폭 파생) |
| `preflop.raise_commit_geometry` / `shove_form_pressure` | raise_form inline | 기하 커밋 / 올인 형태 동기 |
| `preflop.legacy_calloff_likelihoods` | defend_action_likelihoods 분기 | legacy 콜오프 cap 경로 |
| `preflop.apply_defend_exploit_evidence` | defend_action_likelihoods inline | 3벳/4벳 동기·증거 층 |
| `preflop.hot_reshove_probability` | defend_action_likelihoods inline | 리쇼브 후보·legacy 폭·legacy 확률 |
| `preflop.attack_candidate_weight` / `_defend_logistic` / `preflop_slowplay_share` | defend_action_likelihoods inline | 공격 후보 순서 / 로지스틱 / 슬로플레이 기질 |
| `preflop.top_value_class_order` | preflop_blocker_share inline | 블로커 최상단 정의 순서 |
| `preflop.pf_defend_exact_calc_gate` / `calloff_by_price` | calloff_layer_judgment inline | 추론 게이트 / 가격 판단 |
| `ranges.support_rank_quantiles` | preflop_reraise_posterior inline | 개수 기준 분위 |
| `RESHOVE_OPENER_ATTACK` / `OPEN_SHOVE_BEHIND_PROXY` | `OPENER_MULT` 두 소비처 | 같은 표, 질문별 이름(L-RA12) |
| 문서만 | `tighten_defend_widths_for_raise_level`, `bot.range_combos`, session 레인지 메타 | 4벳 prior MISSING_KNOWLEDGE / fallback 순서 / 첫 진입 올인 기록 |

검증:
- `tools/verify_stage9_semantic.py e6de033`: pristine e6de033 대 작업 트리 비교.
  - 6,460건(폭 V2·V3, 디펜스 likelihood+결정+RNG, 오픈/iso+money_open 기록+RNG, raise_form+RNG, 콜오프 layer/cap, multiway+블로커+4벳 posterior+fallback range)이 바이트 동일하다.
- 뮤테이션 테스트: 추출한 각 함수에 의미 있는 변경 13개를 넣었고, 모두 검출했다.
  - 0.75 → 0.76(raise_commit_geometry)은 검출되지 않았다. 이 조건이 다른 조건에 가려지기 때문이다(ledger L-S9-01).
- baseline sim(tilt 0, exploit 중립, max-skill, 시드 11/12, 1,149핸드): 지문이 R2 봉인값과 같다.
  - 시드 11 `e6d8b5e5…`, 시드 12 `c13a5bf4…`
  - 지문은 프리플랍 결정 10,157건 전체와 핸드 로그, 최종 스택을 덮는다. RNG 상태는 함수 단위 probe 에서 따로 비교했다.
- `tools/check_semantic_completeness.py`: site 1,135 / 함수 566 / 상수 표 84, 미소유 0. 새 함수는 SPAN_MAP 에서 기존 개념이 소유한다.
- 23-gate: 통과·실패 집합이 기준(46a2070/e6de033)과 같다. 17 통과, 기존 실패 6 의 마지막 출력 줄도 같다.

## 7차 — 9단계 B2 (ranges / reads semantic-only refactor)

기준 `59650db`. 항목별 상태는 ledger 의 "9단계 B2" 절.

| 추출/명명 | 이전 위치 | 질문 |
| --- | --- | --- |
| `ranges.bet_value_support_fraction` | `_bet_range` inline | 벳 레인지에서 밸류로 남기는 support 비율 |
| `bot.bluff_barrel_continuation` / `bot.bluff_nut_blocking` | `pick_bluffs.score` | 다음 street 배럴 근거(flop/turn) / 넛 블로킹(모든 street) |
| `ranges.strong_support_region` / `ranges.blocked_mass_share` | `blocker_score` inline | 강한 구간 선택(support 분위) / 질량 가중 블로커 몫 |
| `reads.observed_record_rates` | `estimate` inline | 관찰 기록의 원시 빈도(FACT) — PERCEPTION 층과 분리 |
| `persona.read_evidence_amount` | `_exploit_base_weight`, `opponent_read_application_weight` 중복 식 | 상대 정보 증거의 양(MERGE, 값 동일) |
| `plan.perceived_facing_price` | `calldown_need` inline | 마주한 벳의 사실 → 인지 사이즈/콜 금액 |
| 문서만 | `plan._opp_ranges_signature`, `money_pressure.pressure_opportunity`, `ranges.narrow_by_actions` 주석 | 서명 계약 / 압박 층 / 누적 공격 수(KEEP) |

검증:
- `tools/verify_stage9_semantic.py 59650db --probe b2`: 6,200건이 출력과 RNG 상태까지 바이트 동일.
  - ranges 3,500: 벳 레인지, 블로커(hero 카드 포함/제외 레인지), 블러프 선택, 액션 재생 posterior
  - reads 1,500: 가중치 3종, 채운 Book 기록의 estimate + RNG, read_opponent
  - 가격/압박 1,200: calldown_need + RNG, pressure_opportunity
- `--probe b1` 도 59650db 대비 동일하다(persona/ranges 변경이 preflop 경로를 바꾸지 않음).
- 뮤테이션: 새 경계 11개에 의미 있는 변경을 넣었고, 11/11 검출했다.
  - 처음 실행에서 probe 결함 둘을 찾아 고쳤다. (1) `calldown_need` 에 상대 추정치를 `read` 자리로 넘겨 사이즈 정규화 경로가 실행되지 않았다. (2) 압박 상태에 상금 점프 키가 없어 구조 압박이 늘 0 이었다.
  - 뮤테이션 구분자를 `|||` 로 바꿨다(코드 안의 콜론과 충돌).
- `tools/check_semantic_completeness.py`: site 1,136 / 함수 574 / 상수 표 84, 미소유 0.
- baseline sim(시드 11/12, 1,149핸드): 지문이 R2 봉인값과 같다(`e6d8b5e5…`, `c13a5bf4…`).
- 23-gate: 통과·실패 집합(17/6)과 각 게이트의 마지막 출력 줄이 기준과 같다.

## 8차 — 9단계 B3 (plan 포스트플랍 semantic-only refactor)

기준 `ea07ec4`. 항목별 상태는 ledger 의 "9단계 B3" 절. 전략 계수, 임계값, 행동 의미는 바꾸지 않았다. RNG 를 소비하는 단락 평가(`... and rng.random() < p`)는 호출부에 그대로 두고, 확률값 계산만 함수로 뺐다.

| 추출/명명 | 이전 위치 | 질문 |
| --- | --- | --- |
| `self_strength_bias_shift` | `perceived_rel` | 자기 패 과신 편향 가산(L105) |
| `potcontrol_disposition`, `medium_potcontrol_probability` | make_plan | 팟컨트롤 성향 / 중간강도 자리 확률(L122) |
| `continue_range_commit_strength` | make_plan | 커밋 목표를 continue range 대비 강도로 재측정(L119) |
| `continue_range_call_equity` | `river_value_reassessment` + `refresh` 중복 블록 | continue range 대비 equity(MERGE, 값 동일, L119) |
| `multiway_value_thresholds`, `read_value_threshold_shift`, `relative_strength_value_threshold_shift` | make_plan | 밸류 사다리 문턱의 세 보정(L115) |
| `deep_one_pair_vulnerability`, `middle_value_two_street_context/probability` | make_plan | 깊은 원페어 취약 / 중간 밸류 2스트리트 선택(L116/L118) |
| `pure_bluff_evidence`, `pure_bluff_attempt_probability` | make_plan | 블러프 증거 / 실행 확률(L121) |
| `blockbet_probability` | make_plan | OOP 블락벳(L124) |
| `semibluff_line_probability`, `semibluff_barrel_sizing` | make_plan | 세미블러프 라인 / 배럴 사이즈(L120) |
| `bluff_donk_suppression`, `potcontrol_bet_probability` | decide_aggression | 동크 억제·체크스루 프로브(L134) / 팟컨트롤 벳(L123) |
| `planned_size_base` | decide_size | 계획 → 기준 사이즈(L138) |
| `overbet_value_continue_rel`, `overbet_line_polarization`, `overbet_selection_base`, `overbet_size` | overbet_frac | 오버벳 네 단계(L015/L139/L140) |
| `perceived_call_price_share` | calldown_need | 사실 가격 → 인지 가격 몫(L145) |
| `paired_board_flush_raise_damp`, `monster_raise_probability`, `value_raise_size_mult`, `value_raise_probability`, `value_raise_qualification`, `semibluff_raise_probability`, `semibluff_implied_odds_credit` | decide_response | 응답 판단 조각(L147/L116/L120) |
| `response_equity`, `response_raise_target`, `intent_chip_amount` | act_with_plan | 응답 equity 3단계 / 레이즈 target / intent 칩 환산(L153) |
| `checkraise_street_skill`, `checkraise_street_multiplier`, `checkraise_target_amount` | checkraise_decision / checkraise_size | street 별 능력(L149) / 배수 / 칩 target(L152) |
| `PLAN_REQUIRED_CONCEPT`, `PLAN_DOWNGRADE` | `_allowed` 내부 dict | 계획별 필요 개념 / 강등(L157) |
| 문서만 | `bluff_mode`, `target_commit`, `_nonvalue_raise_ev_gate`, `_eq_current` | 'probe'=사이즈 모드 / 미사용 인자 / 범위 / 실제 소비처 |

검증(구조분리 기준점):
- `tools/verify_stage9_semantic.py ea07ec4 --probe b3`: 12개 구역의 출력과 RNG 상태가 바이트 동일하다.
  - 일반 구역: make_plan 450 / aggr·size·overbet·checkraise 3,150 / 응답 1,350 / refresh 250 / 다음 street(river_fix, refresh) 450
  - 경계 sweep 구역: make_plan 240 스팟 × 200 u / 고공격 블락벳 150 × 200 / 응답 270 × 200 / 오버벳 140 × 400 / 커밋 문턱 120 × 21 / 밸류 레이즈 0.5 경계 300 / 체크레이즈 600
  - sweep 은 모든 `rng.random()` 이 같은 값 u 를 내도록 하고 비싼 equity 를 해시 stub 으로 바꾼다. stub 은 BASE 와 작업 트리에 똑같이 적용한다. 확률 gate 의 경계가 u 축에서 직접 보인다.
  - `--base-cache` 를 추가했다. BASE 출력은 (기준 커밋, probe 본문)에만 의존하므로 캐시해서 다시 쓴다.
- `--probe b1`, `--probe b2` 도 ea07ec4 대비 동일하다.
- 뮤테이션 40/40 검출.
  - 1차 실행에서 확률 gate 와 좁은 문턱의 0.01 변경 7개를 놓쳤다(무작위 450건에서는 거의 닿지 않음). 표적 구역을 추가한 뒤 모두 검출했다. 앞 구역은 그대로 두고 뒤에 붙였으므로 앞서 검출한 33개의 결과는 유효하다.
- completeness: site 1,135 / 함수 611 / 상수 표 86, 미소유 0. ea07ec4 는 1,136 / 574 / 84.
- 봉인 sim(시드 11/12, 1,149핸드): 최종 코드 지문이 `e6d8b5e5…` / `c13a5bf4…` 로 같다.
- 23-gate: 통과·실패 집합(17/6)과 출력 줄이 기준과 같다.
- L-S9-02 측정은 `tools/l_s9_02_measure.py`. 측정 실행 지문도 봉인값과 같다.

## 9차 — 9단계 B3 통합 (의도한 행동 변화 포함)

기준 `20e206f7`. 항목별 판정과 근거는 ledger 의 "9단계 B3 통합" 절.

코드 변경:
- `ranges.range_mass_live`
- `plan.VALUE_WHEN_CALLED_EQ`, `ahead_when_called`, `continue_range_strength`
- `continue_range_commit_strength` 와 `overbet_value_continue_rel` 이 공용 함수를 쓰도록 변경
- overbet 경로에 n_opp / opp_ranges / seed 전달
- bluff_mode 라벨 `low_cost`
- `_allowed(street=)`
- trap 읽기 단일 경로

검증:
- 같은 상태 쌍 비교(`tools/b3_integration_attribution.py`, 시드 11/12): 측정 실행 지문 = 일반 sim 지문.
  - fold_p 판정 뒤집힘: 각 1
  - 밸류 판정 뒤집힘: 2 (시드 11 레이즈 eq = 0.50 경계, 시드 12 개선된 블러프 eq 0.531)
  - 멀티웨이 오버벳 rel 하향: 17/143. HU 는 0
- 새 baseline: 시드 11 `e6d8b5e5…`(불변), 시드 12 `8c33ece5…`.
- L-S9-07 / trap 읽기는 최대 숙련, exploit 중립 baseline 에서 드러나지 않는다. 그래서 필드 프로필로 따로 측정했다(ledger).
- completeness: site 1,135 / 함수 614 / 상수 표 87, 미소유 0.
- 23-gate: 통과·실패 집합(17/6)과 출력 줄이 기준과 같다.

## 10차 — 9단계 B4 통합 (persona / concept 역할)

기준 `217bb4c0`. 판정은 ledger "9단계 B4 통합" 절.

코드 변경:
- `persona.call_bias` 가 hero_call 을 포함하는 유일한 콜 문턱 편향 적용 지점이 됐다.
- `plan.apply_response_biases_to_call_threshold` 와 decide_response 의 재적용을 삭제했다.
- `persona.bias('hero_call')` 의 숙련 방향을 바꿨다.
- `calc_noise` 와 `preflop_temper_direction` 을 3차 경로로 단일화하고 플래그 2개를 퇴역했다.

검증기 갱신:
- `verify_calc_noise_v3`, `verify_preflop_temper_direction_v3`: legacy 는 검증기 안의 참조식으로만 남긴다.
- `verify_range_read_semantics`: 의도된 변경은 명시적으로 제외하고 새 계약을 검사한다.
- `verify_human_model_v3_integration`: 퇴역 플래그를 목록에서 제외했다.

검증:
- 같은 상태 쌍 비교: 마지막 콜/폴드 분기 514회 중 8회 콜 → 폴드.
- 새 baseline: 시드 11 `7ce1561d…`, 시드 12 `ef73996c…`.
- completeness: site 1,132 / 함수 613 / 상수 표 87, 미소유 0.
- 23-gate: 통과·실패 집합(17/6)과 출력 줄이 기준과 같다.
