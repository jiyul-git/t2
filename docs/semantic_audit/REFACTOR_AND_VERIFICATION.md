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

## 11차 — 9단계 B5 통합 (호환 / 이름 / 옛 경로 제거)

기준은 clean 안테 기준선 `60c7d615`(코드 `58900603`)이다. B5 는 안테 변경과 섞이지 않게 stash 로 분리해 두었다가, 기준선을 봉인한 뒤 복원했다. 판정은 ledger "9단계 B5 통합" 절.

코드 변경:
- `icm.field_bf` 의 덮인 첫 정의와 그 전용 표 삭제
- 읽히지 않던 표 4개 삭제
- `Table.sidepots` 삭제
- `runner.shape_size` 래퍼 삭제
- `session._diagnostic_layer_equities` → `layer_equities_by_pot_layer`(docstring 정정)
- EXPLOIT_WEIGHT_V3 / `exploit_weight` / `opponent_read_application_weight` 퇴역
- `act_with_plan` 의 response_kind=None 호환 분기와 `checked_before` 삭제
- `bias()` 가 bluff_fear/hero_call 에 street 를 요구
- CI 의 퇴역 플래그 env 정리
- docstring 정의 명시: `relative_strength`, `nut_advantage`

검증(clean 안테 기준선 대비):
- 시드 11 `b6425e83…`, 시드 12 `a769e1e0…`: 기준선과 **동일**. B5 의 행동 차이는 0 이다.
- 23-gate: 안테 기준선의 결과 파일과 동일하다.
- `verify_uniform_ante` 6/6 통과(B5 위에서도).
- completeness: site 1,122 / 함수 612 / 상수 표 76, 미소유 0. 안테 함수 3개를 forced_bet_posting 으로 소유시켰다.
- 갱신한 검증기(새 계약): `verify_core_sizing_ownership`, `verify_human_model_v3`(E1/E2 단일 가중치), `verify_human_model_v2`, `audit_human_v3_live_attribution`, `verify_range_read_semantics`, `verify_f3`/`verify_f5` fixture(canonical response_kind).
- B5 이전부터 실패하던 검증기: `verify_f5_backaction`, `verify_prelogic_execution_boundary`, `verify_f3_checkraise_response`(23-gate 의 기존 실패 6개 중 하나).

## 12차 — 9단계 B6 통합 (bot / texture / depth)

기준 `5acda39d`. 판정은 ledger "9단계 B6 통합" 절.

코드 변경:
- `texture.turn_card_effect` → `new_card_effect(prior_board, new_card)`. 리버도 직전 보드 전체 대비로 잰다.
- `plan.perceived_board_danger`, `plan.board_texture_read` 추가.
- `danger` / `danger_raw` 기록을 분리했다.

검증:
- 같은 상태 쌍 비교: 리버 호출 727회 중 252회 값 변화.
- 새 baseline: 시드 11 `b6425e83…`(불변), 시드 12 `b09618b3…`(567핸드, 오류 0).
- 23-gate: 안테 기준선과 동일하다.
- completeness: 미소유 0.

## 13차 — 9단계 B1/B2 closeout 그룹 A (GTO 비의존)

기준 `13c5c0b4`. 판정은 ledger "9단계 B1/B2 closeout" 절.

코드 변경:
- `reads` 최근 핸드 창을 유일 경로로 만들고 READ_RECENCY_V3 를 퇴역했다.
- `persona.traits_of` 의 threebet 숙련 입력을 bluff 에서 pf_defend 로 바꿨다. pf_defend 는 현존 proxy 이고, 독립 3벳 숙련 / prior 는 MISSING 이다.
- `bot.range_combos` 를 PCT 순서(클래스 경계 floor)로 바꾸고 `_pf_score` 를 삭제했다.
- GTO_MEMORY_V2 / PREFLOP_REASONING_V3 에 BLOCKED 상태 주석을 달았다(OFF 유지).

검증:
- 시드 11 `b6425e83…`, 시드 12 `b09618b3…`: B6 기준선과 **동일**.
  - 이 하네스에서는 세 변경 모두 실행되지 않는다. 북이 비어 있고(exploit 중립), 모든 프로필이 pf_defend = bluff = 10 이며, fallback 레인지 호출은 0회다(`tools/closeout_a_attribution.py`).
- 23-gate: 통과·실패 집합은 같다. 출력 한 줄이 바뀌었다 — 기존 실패 게이트 `verify_f3_checkraise_response` 의 fixture(opp_range=None → fallback 레인지)가 raise 800 / eq 0.9833 에서 700 / 0.9783 으로 바뀌었다. A3 순서 통합에 따른 의도된 변화다.
- `verify_human_model_v3_integration` 5/5:
  - I5 는 'flags OFF 면 기록 없음' 에서 '최근 창 단일 경로: 항상 기록, 상한 121' 로 바꿨다.
- `verify_read_recency_v3` 통과(legacy 는 검증기 안의 참조로만 남김).
- `audit_human_v3_live_attribution` 통과.
- 필드 3벳 형질 차이: 평균 0.013, 최대 0.045(1,000명).
- completeness: site 1,116 / 함수 614 / 상수 표 76, 미소유 0.

### 13차 보강 — A2/A3 계약 검증과 문구 정정 (그룹 A 봉인)

문구 정정(주석/문서만):
- A2 의 pf_defend 는 전용 3벳 숙련이 아니라 bluff 보다 적합한 현존 proxy 다. 독립 3벳 숙련과 solved 3벳 prior 는 MISSING_INDEPENDENT_3BET_SKILL/PRIOR 로 남긴다.
- A3 의 `PCT ≤ pct` 는 정확한 상위 pct 가 아니라 클래스 경계 floor 다(0.35 → 458콤보 ≈ 34.54%).

`tools/verify_closeout_a.py` 9/9 통과:
- A2a: aggression/looseness 고정, bluff 만 바꾸면 형질 불변.
- A2b: pf_defend 만 바꾸면 형질이 단조 증가.
- A2c: 최대 숙련에서 퇴역 식과 같다(0.109).
- A3_0: PCT 는 클래스 누적 몫이다(저장 4자리 이내).
- A3a 단조성, A3b 클래스 무결성(dead card 제외 시 부분 절단 없음), A3c 실현 몫 ≤ 요청 pct, A3e 결정적 순서.
- A3d: 요청 대비 부족분 < 경계 클래스 하나(최대 부족 0.00864 < 최대 클래스 몫 0.00905).
- pct 107점 grid × dead-card 13가지(없음, 2/5/7장 무작위)로 검사했다.

`verify_f3_checkraise_response` 는 원래부터 실패하던 게이트라 A3 검증 근거로 쓰지 않는다. Stage 10 에서 따로 판정한다.

그룹 A 를 최종 완료로 봉인한다. GTO_MEMORY_V2 / PREFLOP_REASONING_V3 는 계속 BLOCKED_BY_GTO_REFERENCE_VALIDATION, production OFF.

## 14차 — Stage 10 final regression

기준 `c6805a15`(Stage 9 봉인). 23-gate 의 기존 실패 6개를 '역사적 실패 유지'로 묶지 않고 하나씩 판정했다. B5 이전부터 실패하던 비게이트 검증기 2개도 같이 판정했다.

| 검증기 | 실패 원인 | 판정 | 처리 |
|---|---|---|---|
| `verify_p4_vs_3bet` | pf_open_bb 등의 키를 `HandRun._run` 소스에서 찾음. 소비는 `_preflop_story_range` 로 옮겨졌다(_run 이 호출) | stale test(필드는 실제로 흐름) | 실제 소비 함수 + _run 의 호출을 검사 |
| `verify_f3_checkraise_response` | ① 체크레이즈 금액을 정확히 777(stub)로 기대 — 계획이 사람 사이즈 습관으로 다듬는다(F7-D). ② hero_call 방향을 옛 식(숙련 ↑ → 편향 ↑)으로 기대 | stale test **+ 실제 잠재 결함**: `size_shape_seed` 없이 직접 호출하면 `random.Random(None)` 이라 같은 입력이 다른 금액(700/800)을 냈다 | 코드: seed 가 없으면 `seed` 에서 결정적으로 파생(세션은 항상 넘기므로 production 불변). 테스트: 같은 seed 로 다듬은 금액, B4 방향(hf > hr) |
| `verify_f4_facing_bet` | 삭제된 API `session._observed_postflop_action` | stale test | canonical `action_events.normalized_action` 으로 검사(빈 팟 올인 = bet 포함) |
| `verify_f6_caller_backaction` | 손으로 만든 action_meta 에 엔진의 full_raise_count / post_contrib 가 없어 raise_depth_full 이 0 | stale fixture(실제 Round 로 같은 시나리오를 돌리면 2/3/1 로 정확했다) | fixture 를 실제 `runner.Round` 액션으로 생성 |
| `verify_f7_street_closure` | `_acts_of` 가 dict event 를 반환하는데 3-tuple 로 풀었다. fixture 에 pre_current 가 없어 raise 가 bet 으로 읽혔다 | stale test | dict 필드로 읽고, 실제 Round 메타데이터로 생성 |
| `verify_weighted_boundaries` | 모르는 좌석에 알려진 레인지가 복제되기를 기대 — `eca264f5` 에서 의도적으로 퇴역한 동작 | stale test | 무복제 계약을 검사(모르는 좌석 None) |
| `verify_f5_backaction`(비게이트) | 재레이즈 금액 550 정확 기대(F7-D 다듬기 전 값), 삭제된 `_postflop_facing_contexts` | stale test | 다듬기 전 target(provenance before=550)과 실행 금액(after) 검사, canonical event stream |
| `verify_prelogic_execution_boundary`(비게이트) | source 라벨 'judgment' 와 옛 stage 마커 — `63c6c4c4` 에서 'plan' 으로 바뀌고 식이 여러 줄이 됐다 | stale test | 라벨 'plan', 현재 마커(순서 동일) |
| `verify_human_model_v2` IDENT(rc 는 0, 보고 항목) | flag OFF fixture 지문을 `test@1a23123`/`a148d95` 값과 비교 — 그 뒤 B3(hero 조건 fold 질량), B4(편향 방향), 균등 ante 로 기본 경로가 의도적으로 바뀌었다 | stale pin | 현재 기본 경로 값으로 재고정(2회 실행 동일). 옛 값은 주석으로 보존 |
| completeness 미소유 1 | Stage 10 에서 넣은 `act_with_plan` seed 파생 줄에 소유 span 이 없었다 | 문서 누락(코드 결함 아님) | `human_planned_size_shape` span 추가 → 미소유 0 |

결론: 실패 검증기 8개 중 7개는 코드가 의도적으로 바뀐 뒤 갱신되지 않은 테스트였다. 1개(f3)는 테스트 갱신과 함께 실제 잠재 결함(사이즈 습관 RNG 의 비결정성)이 있어 코드를 고쳤다. 회귀 중 추가로 드러난 2개(HM2 IDENT pin, completeness 미소유 1)는 각각 stale pin, span 누락이며 코드 결함이 아니다.

전체 회귀 1회(코드 고정 상태, md5 확인):
- 시드 11 `b6425e83…`(581핸드), 시드 12 `b09618b3…`(567핸드), 오류 0. B6 기준선과 동일하다(f3 seed 수정은 production 경로에 영향 없음).
- **23-gate: 23/23 통과**(이전 17/6).
- 추가 검증기 rc=0: `verify_f5_backaction`, `verify_prelogic_execution_boundary`, `verify_uniform_ante`, `verify_closeout_a`, `verify_read_recency_v3`, `verify_calc_noise_v3`, `verify_preflop_temper_direction_v3`, `verify_human_model_v2`, `verify_range_read_semantics`, `audit_human_v3_live_attribution`. 단 첫 실행에서 HM2 IDENT=false(위 표, 재고정 후 재실행 결과는 아래).
- HM2 재고정 후 재실행: IDENT true, MATCH/A1/B/D/E/F/G true, rc=0.
- completeness: 첫 실행 미소유 1(위 표) → span 추가 후 미소유 0, rc=0.
- md5: 회귀 시작 전후 *.py 동일(실행 중 코드 변경 없음).

## 15차 — Stage 11 문서 동기화와 봉인

기준 `3c5d56d5`(Stage 10). 목적은 문서와 검증 manifest 를 현재 코드에 맞추는 것이다. **production 판단 코드는 바꾸지 않았다.** Stage 11 전후 production `*.py` 42개 md5 가 같다.

문서 대조:
- 개념→함수 registry: 모든 행의 함수 참조와 `inputs` 시그니처를 `inspect.signature` 로 현재 코드와 대조했다. 처음에는 삭제된 함수 참조 3건, 시그니처 불일치 8건이었고, 정정 후 둘 다 0.
- 퇴역 플래그·API 를 ACTIVE/OPT-IN 으로 적은 행을 정정했다: recency_window, calculation_error, preflop_temperament_direction, exploit_read_permission, legacy_sidepot_helper, turn_card_range_shift, value_when_called_strength, human_planned_size_shape, value_degradation_thresholds. 정정은 `supplement.py` 의 `ROW_UPDATES` 로 기록했다(재생성 가능).
- registry MD 빠른 표는 CSV 에서 자동 생성한다(`_sync_registry_quick_table`). 225행 중 210행은 기존 텍스트와 바이트 동일, 15행은 정정된 행이다.
- 현재 상태 문서에서 삭제·개명된 `모듈.함수` 참조를 0으로 맞췄다: STREET_SEMANTIC_MATRIX, CURRENT_ARCHITECTURE_AUDIT, RANGE_READ_CONSUMER_BOUNDARIES, STRUCTURAL_CONCEPT_REVIEW, README. 남은 2건(`persona.overpair_love` 는 편향 이름, `tourney.next_hand` 는 메서드)은 오탐이다.
- `CONCEPT_SYSTEM.md` 에 Stage 11 현재 플래그 상태 표를 두고, §11~§15 의 opt-in 문구에 현재 상태를 덧붙였다.
- GTO_MEMORY_V2 / PREFLOP_REASONING_V3: 모든 문서에서 production OFF, BLOCKED_BY_GTO_REFERENCE_VALIDATION.
- `size_shape_seed` 계약:
  - production(세션)은 항상 명시 seed 를 넘긴다.
  - `size_shape_seed` 가 없고 `seed` 가 있으면 `crc32('<seed>|size_shape')` 로 결정적으로 파생한다(Stage 10).
  - `seed` 자체가 None 인 임의 직접 호출은 결정성 계약 대상이 아니다. `act_with_plan` 은 원래 `random.Random(seed)` 를 쓴다.

tier-all(74개, HEAD clean worktree, timeout 2400, jobs 3) 판정. 이전 manifest 대비 바뀐 것만 적는다:

| 검증기 | 결과 | 판정 | 처리 |
|---|---|---|---|
| `f1_free_action` | PASS → FAIL | stale test. 가드는 B3 구조분리(20e206f7, 행동 동일)에서 `plan.blockbet_probability` 로 옮겨졌을 뿐 그대로다 | 검사 위치 갱신 + make_plan 경유 확인. 4/4 |
| `oop_semantics` | TIMEOUT → (처음 완주) FAIL B1c 25, C3 2 | stale test model. 옛 팔은 `vs_aggr=None`(살아 있는 어그레서 없음)을 넘긴다. None 은 legacy 로 대체되지 않는다(4b9d33d5 이전부터). 25건 전부 field=legacy=True, vs_aggr=True 였다. 입력이 다른데 '플래그 불변'으로 셌다. 같은 팔 재생 400/400 결정적(비결정성 없음) | 입력 변화 판정에 vs_aggr≠None 포함, C3 는 입력이 같은 쌍만. 재실행 B1c 0 / C3 0, PASS |
| `state_namespace`, `trace_schema` | PASS → FAIL | 환경. 병렬(jobs 3)에서 다른 검증기가 같은 worktree 에 아카이브를 쓴다 | clean worktree 단독 rc=0. manifest 메모에 단독 실행 명시 |
| `audit_order` | (재확인) | 같은 이유. 아카이브 8개가 남은 worktree 에서 D3 FAIL | 새 clean worktree 단독 PASS |
| `human_model_v2` | TIMEOUT → PASS | 900 초를 넘던 것. 2400 초에서 완주 | — |
| `closeout_a`, `uniform_ante`, `stage9_semantic` | NEW → PASS | Stage 9 에서 추가 | — |

최종: **PASS 62 / FAIL 12 / TIMEOUT 0**, REGRESSION 0. 23-gate 23/23(재실행). completeness 미소유 0, rc=0.
- 남은 FAIL 12 는 모두 이전 manifest 에서도 FAIL 이던 역사적 실패다.
  - 3개(`stepothers_timing`, `tilt_divergence`, `tilt_isolation`)는 인자가 필요한 CLI 드라이버다.
  - 나머지 9개(`defer`, `f7b_blocker_activation`, `f7b_defend_rewire`, `forced_blind_allin_showdown`, `replan_contract`, `telemetry_wiring`, `tournament_telemetry`, `ui_tournament_panel`, `weighted_aggregate_transform`)는 23-gate 밖이고 Stage 10 판정 범위 밖이었다. stale/실결함 판정은 하지 않았다(FOLLOWUP-S11-V).
- manifest 는 실행 결과에서 재생성했다. 검증기별 실행 명령, rc, 상태, 목적(계약), verifier blob SHA, source `3c5d56d5` 를 남긴다.

triage LATER 대조: 결론 기록이 없던 항목을 코드와 대조했다.
- 해결됨이 4건이다(L148, L-RA06, L-RA07, L-RA03). L-RA03 은 registry 만 낡아 있었다.
- 미판정 17건은 FOLLOWUP-S11 로 분리했다(ledger 'Stage 11' 절). 행동 변화가 필요하므로 이 단계에서 고치지 않았다.

다음 단계 개념·지식 공백 목록: `CONCEPT_GAPS_NEXT.md`.

## 16차 — 베타 전 버그 수정 3건

기준 `3993c2cd`(Stage 11). 의도된 행동 변화다. 판정과 근거는 ledger 'FOLLOWUP-S11 중 베타 전 버그 수정' 절에 있다.

| 항목 | 내용 |
|---|---|
| 귀속 측정 | `tools/bugfix3_attribution.py`. 계측 실행 지문 = 일반 sim 지문(계측이 진행을 바꾸지 않음) |
| 새 기준선 | 시드 11 `d6c70b87…`(583핸드), 시드 12 `f0620c61…`(567핸드), 오류 0. 이전은 `b6425e83…` / `b09618b3…` |
| 검증 | `verify_bugfix3` 통과, 23-gate 23/23, completeness 미소유 0 |

## 17차 — 베타 A #5: 밸류 계획 승격 버그 2건

기준 `b28009c4`. 의도된 행동 변화다.

| 결함 | 수정 |
|---|---|
| 예산 소진 후 승격이 '직전 스트리트보다 made 상승'을 요구했다. 턴에 강해지고(예산 남음) 리버에 예산이 소진되면 승격 시점이 오지 않았다(플랍 얇은 밸류 → 턴 트립스 rel 0.96 → 리버 '사이즈 0 → 체크') | 계획 채택 시점의 made(`plan_made`)를 기록하고, 그 이후 made 가 올랐는지를 본다 |
| 직전 rel 은 2자리로 반올림 저장되는데 새 rel 원값과 비교했다. 승격 조건 `rel >= prev_rel` 은 0.957 < 0.96 으로 실패했다. `strength_improvement_supports_value` 의 `rel > prev_rel` 은 같은 강도(0.8312 vs 0.83)를 '상승'으로 읽었다 | 두 비교 모두 `round(rel, 2)` 로 같은 정밀도에서 한다 |

| 항목 | 내용 |
|---|---|
| 같은 상태 쌍 비교 | `tools/fix5_attribution.py`(옛 `refresh` 를 1ac21231 판으로 같은 입력에 재계산). 계측 실행 지문 = 일반 sim 지문. refresh 2,622회 중 계획 판정 변화 11회 |
| 변화 내용 | 의도한 리버 승격 1(value_2street → value_3street). 같은 강도인데 '강도 상승'으로 잘못 올리던 pot_control/block → value_2street 10회 제거 |
| 새 기준선 | 시드 11 `7baf5613…`(583핸드), 시드 12 `9ccf72fc…`(566핸드), 오류 0 |
| 검증 | 23-gate 23/23, `verify_bugfix3` 통과, completeness 미소유 0 |

## 18차 — 베타 A #1: 즉흥 사이징 확률을 기질 '일관성'으로 배선

기준 `6e01273d`. 의도된 행동 변화다.

| 항목 | 내용 |
|---|---|
| 충돌 | '계획한 사이즈를 그대로 실행하는가'를 아키타입 라벨 고정값(`SIZING_FAMILY_SIG['odd']`, reg 2%)이 정했다. 기질 축 `consistency` 가 같은 질문(오픈 사이즈 습관)에 이미 쓰이는데 우회했다 |
| 최종 선택 | 개념/기질 프로필: `odd = SIZING_ODD_MAX × (1 − consistency/10)`(`persona.sizing_odd_probability`). 라벨 전용 프로필은 라벨 표를 유지한다. 난수 소비 순서는 같다 |
| 계수 | `SIZING_ODD_MAX = 0.50` 잠정값(사용자 결정). 일관성 10 → 0, 0 → 0.50. 계수 단계에서 재판정 |
| 같은 상태 쌍 비교 | `tools/fix1_attribution.py`(같은 RNG 상태 복제로 옛 규칙 계산). 계측 지문 = 일반 sim 지문. 사이즈 습관 호출 2,209회 중 변화 20회(전부 odd 사이즈 제거) |
| 새 기준선 | 시드 11 `fa55057f…`, 시드 12 `c04d672a…`, 오류 0 |
| 검증 | 23-gate 23/23, completeness 미소유 0, registry 시그니처 불일치 0 |

## 19차 — 베타 A 개념 공백 #2·#3·#4 + 리버 밸류 모순 2건

기준 `8e51f68b`(master). 의도된 행동 변화다. 새 수치는 만들지 않았다(기존 판단을 연결). 확실한 밸류 경계 0.92 는 리버 코드 리터럴에 `CLEAR_VALUE_REL` 이름만 붙였다.

| # | 충돌 | 최종 선택 |
|---|---|---|
| 3 | 리버 쇼다운 계획이 계획 이탈(지속벳) 확률로 벳 — 쇼다운 가치를 블러프로 전환 | 리버 쇼다운 계획은 이탈 벳 없음(체크). 플랍/턴(보호·에쿼티 거부)과 포기 계획(에어)의 리버 블러프는 유지 |
| 4 | 턴 2스트리트 밸류가 '콜당했을 때 앞서는가'를 묻지 않음(KK J♦T♦9♦6♣ rel 0.37 베팅) | `turn_value_reassessment`: rel < 0.92 이면 계획한 턴 사이즈의 콜 레인지 대비 eq < 0.50 일 때 팟 컨트롤. 근거 없으면 유지 |
| 2 | 라인 소유(직전 스트리트 콜 + OOP)에서 넛급도 재리드 4~16% → 체크백으로 밸류 손실 | rel ≥ 0.92 이면 체크 = 트랩이므로 `trap_judgment`(상대 벳 확률·현재 SPR·인원·위험·취향)를 거치고, 트랩이 아니면 리드. 현재 SPR·tilt 를 attach_intent → decide_aggression 으로 전달 |
| 추가 | 리버 '분명한 밸류' 판정 후 2스트리트 예산 소진으로 '사이즈 0 → 체크' | 예산이 소진된 value_2street 의 분명한 밸류는 리버 밸류(value_3street)로 |
| 추가 | 리버 드로우 완성이 '콜당했을 때 앞서는가' 없이 밸류(55 의 5 하이 플러시 rel 0.36) | rel < 0.92 이면 리버 밸류 재평가를 거친다 |

문서 도구: registry `inputs` 시그니처를 생성 시 코드에서 자동으로 맞춘다(`_sync_input_signatures`).

베타 A 재실행(시드 11 `9015f07d…` 582핸드, 시드 12 `ece27229…` 567핸드, 오류 0):

| 지표 | 수정 전 | 수정 후 |
|---|---|---|
| E4 즉흥 사이즈 | 17 | 0(18차) |
| J7 쇼다운 손 이탈 벳 | 17 | 9(전부 플랍/턴, 의도) |
| J5 리버 강한 손 체크 | 15 | 6(트랩 4 = 계수 단계, 쇼다운 판정 2 = 타당) |
| J4 밸류 계획 낮은 rel 벳 | 2 | 0 |
| 층 전이 이상 / 가격 불일치 콜·폴드 | 0 | 0 |

검증: 23-gate 23/23, `verify_bugfix3` 통과, completeness 미소유 0, registry 불일치 0.

계수 단계로 넘긴 것: `trap_judgment` 의 숙련 항(tool)이 커서 최고 숙련은 상한 0.70 에 붙는다 — 상황(상대 벳 확률 등)이 거의 반영되지 않는다.

## 20차 — L161: 봇 테이블 관찰 장부를 대회 내내 유지

기준 `3e64a392`. 버그 수정이다(익스플로잇 설계의 선결 조건).

| 항목 | 내용 |
|---|---|
| 결함 | 봇끼리의 테이블(`fieldsim`)이 핸드마다 `play.Hand` 안에서 새 `Book` 을 만들었다. 봇의 상대 기억이 전혀 쌓이지 않았다. 내 테이블(`live2`)만 `st['book']` 으로 이어졌다 |
| 수정 | 대회 하나에 장부 하나(`Field.book`). 봇 테이블·내 테이블이 같은 장부를 쓴다. 키가 pid 쌍이라 테이블 이동에도 기억이 따라간다. UI 상태는 field 덤프 안에 장부를 저장하고(`st['book']` 은 한 번 이어받은 뒤 제거), 병렬 라운드는 관찰자 소유(비-HERO pid → worker)로 합친다 |
| 크기 | 최근 창 이력을 압축 저장(`reads._append_hand_snapshot`): 최신 스냅숏만 전체, 이전은 다음 스냅숏과 다른 카운터의 그 시점 값만. 복원은 산술 없이 정확. 옛 형식 장부는 그대로 읽고 다음 기록 때 압축한다. 탈락자가 관찰자/대상인 기록은 삭제(`Field._forget_busted`). 텔레메트리는 해당 테이블 사람끼리의 기록만, 이력 제외(`fieldsim.book_view`) |
| 등가 검증 | `tools/verify_book_history_compact.py`: 옛 구현 대비 무작위 관측 195,000 비교 일치, 옛 장부 이어받기 82,500 비교 일치, 이력 크기 7.5% |
| 동작 확인 | 봇 대회 15핸드: 상대 쌍 216개가 평균 14.8핸드 관측. UI 대회(27명, 병렬 모드) 25핸드: 장부 216쌍 평균 22핸드, 저장 3.5MB 중 장부 0.84MB |
| 기준선 | 장부를 고정하는 기준 하네스라 지문 불변: 시드 11 `9015f07d…`, 시드 12 `ece27229…` |
| 검증 | 23-gate 23/23, `verify_read_recency_v3`·`verify_human_model_v3` 통과, completeness 미소유 0. `verify_tournament_telemetry` 는 변경 전과 같은 역사적 실패(2 table hands) |

주의: 봇 대회·UI 대회의 봇 행동은 이제 상대 기억을 쓰므로 달라진다(의도). 기준 하네스 지문은 장부 고정이라 그대로다.

## 21차 — 내 테이블 아카이브의 장부 기록 범위

L161 이후 장부가 대회 전체를 담는데, 내 테이블 아카이브(`live2` 핸드 기록 `book_before`/`book_after`, 텔레메트리 `hero_book_after`)는 핸드마다 장부 전체를 복사했다. 봇 테이블과 같이 그 테이블 사람끼리의 기록만, 이력 제외로 남긴다(`fieldsim.book_view`, `telemetry_sync._hero_table_book`). 판단 경로 변화 없음(기록 전용). UI 27명 대회 6핸드: 아카이브 장부 72쌍(테이블 9명), 대회 장부 216쌍. 23-gate 23/23.

## 22차 — 익스플로잇 관측: 리드·프로브, 후속 반응, 쇼다운 연결

기준 `2cfbe063`. 관측 추가 + 트랩의 상대 역할 연결. 새 수치 없음.

| 항목 | 내용 |
|---|---|
| 정의 | 리드(동크): 이번 스트리트 첫 벳이 아직 없고, 직전 스트리트 공격자가 아닌 사람이 살아서 대응 가능한 공격자보다 먼저 첫 벳. 프로브(스탭): 공격자가 체크했거나 대응할 공격자가 없을 때(없음·폴드·올인) 비공격자의 첫 벳. 공격자 자신의 첫 액션은 기존 c벳/배럴/지연 c벳(`session.line_spot_kind`) |
| 장부 | 스트리트별 기회/실행, 그 벳이 레이즈를 맞았을 때 폴드 여부, 그 라인을 한 핸드에서 공개된 패(강/약 문턱은 기존 쇼다운 관측과 같음). `estimate` 는 원시 비율만 낸다(표본 없으면 None, fold_to_raise 와 같은 방식) |
| 소비 | `opp_bet_prob(opp_role=...)`: 상대가 공격자면 c벳/배럴(기존과 동일), 내가 공격자라 상대가 '체크받으면 칠지'가 문제면 프로브 빈도. 프로브 표본은 같은 질문의 기존 기본값(스트리트별 0.45/0.38/0.30)으로 기존 수축(`reads._shrink`)만큼 당긴다. 예전에는 이 경우에도 상대의 c벳 빈도를 썼다 |
| 검증 | `tools/verify_line_observations.py`: 분류 8사례, 27명 대회 30핸드에서 리드·프로브 기록 일관성(벳 ≤ 기회, 레이즈 반응 ≤ 벳, 강/약 ≤ 공개), 역할별 빈도 선택. 기준 하네스 지문 불변(장부 고정): 시드 11 `9015f07d…`, 시드 12 `ece27229…`. 23-gate 23/23, completeness 미소유 0 |

후속 반응·쇼다운 연결은 기록·노출까지다. 판단 소비(리드 구성이 밸류/블러프 중 어느 쪽인지 해석)는 테이블 기준선·± 편차 설계와 함께 한다.

## 23차 — 멀티웨이 관측: 동크만 기억

사용자 판단(2026-10-03): 멀티웨이에서는 동크벳 외의 포스트플랍 액션을 상대 성향으로 기억하지 않는다. 멀티웨이 c벳/배럴은 대부분 진짜 패이고 멀티웨이 블러프는 드물어서, 헤즈업 성향 통계에 섞으면 오독한다.

| 항목 | 내용 |
|---|---|
| 멀티웨이 정의 | 이번 스트리트 시작 시 팟에 남은 사람 3명 이상 |
| 기록 | 멀티웨이 동크(리드)만 별도 칸(`mw_lead_*`). c벳·배럴·프로브·벳에 대한 폴드·사이즈 관측은 헤즈업에서만. 쇼다운에서 본 패는 그대로 기록 |
| 영향 | c벳·배럴·벳에 대한 폴드 통계가 '헤즈업 빈도'가 된다(실제 대회의 봇 행동 변화, 의도) |
| 검증 | `verify_line_observations` M1 추가(27명 30핸드: 멀티웨이 동크 기회 219, 동크 0 — 봇들이 멀티웨이에서 공격자에게 먼저 치지 않음과 일치). 기준 하네스 지문 불변(시드 11 `9015f07d…`, 시드 12 `ece27229…`), 23-gate 23/23 |

## 24차 — 최고 숙련 쓰레기 오픈 림프 버그

증상(베타 재실행): 최고 숙련 봇이 84o, J2o, Q4o, KK, AQo 등을 오픈 림프. 오픈 림프 12건 중 11건이 정의 밖.

| 항목 | 내용 |
|---|---|
| 원인 | `limp_p` 의 이론형 림프가 핸드가 아닌 백분위 구간(3~30%)으로 판정했고, 구간 밖에서도 0.15 배수가 새어 나왔다. 정의(22-88, A2s-A8s)와 코드가 달랐다 |
| 수정 | `preflop.theory_limp_hand(hand)` 로 정의를 코드화. 정의 밖 핸드는 이론형 림프 0. 두 호출부(`open_decision`, `iso_decision` 오버림프)가 `hand=hand` 전달. 핸드가 없으면 기존 백분위 구간(누수 없이) |
| 결과 | 베타 재실행 오픈 림프 12 → 1(16.5bb 88, 정의 안) |
| 남은 것 | 정의 안 핸드의 림프 비율(9bb 에서 약 33%)은 계수 대기열 |
| 검증 | 23-gate 23/23, completeness 미소유 0(`theory_limp_hand` span 추가, 호출부 앵커 갱신). 새 기준선 시드 11 `e04c7e88…`, 시드 12 `6dc97c62…` |

## 25차 — UI 다음 핸드 대기(다른 테이블 정산) 속도

증상(사용자 Termux 녹화): 한 핸드가 끝난 뒤 "다른 테이블 정산 중…"에서 오래 멈춤.

| 항목 | 내용 |
|---|---|
| 원인 | 비-히어로 테이블 한 라운드(100명, 9테이블) 계산이 서버 기준 약 25초(폰은 몇 배). 프로파일 77초 중 약 67초가 `bot._sample_pool_combo` — 몬테카를로 매 표본마다 가중 레인지 dict 를 다시 정렬·합산했다. 최근 변경의 회귀는 아님(3c5d56d5 도 24.6초) |
| 수정 | `bot.PreparedPool`/`prepare_pool`: 정렬·누적합을 루프 전에 한 번. 같은 RNG 상태에서 같은 콤보(균등 → `rng.choice` 같은 목록, 비균등 → 같은 누적합에서 `bisect_right` = 기존 `x < acc` 첫 위치, 합계는 기존과 같은 `sum`). 호출부 9곳(bot·plan·ranges 의 MC 루프) |
| 결과 | 같은 라운드 25초 → 약 6초 |
| 검증 | 기준 하네스 지문 불변(시드 11 `e04c7e88…`, 시드 12 `6dc97c62…`), 23-gate 23/23, completeness 미소유 0 |
