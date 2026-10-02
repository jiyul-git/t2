# STAGE9_TRIAGE — 9단계 semantic-only refactor 잔여 분류

원 계획 9단계(행동 보존 SPLIT/MERGE/RENAME)의 잔여를 ledger 전 항목(149)에서 분류했다. 생성: `python docs/semantic_audit/stage9/build_triage.py`.

| 분류 | 수 | 뜻 |
|---|---|---|
| DONE | 39 | 행동 보존 처리 완료(이번 9단계 batch 완료분 포함) |
| PARTIAL | 4 | 일부 완료, 남은 행동 보존 부분은 batch 에 배정 |
| NOW | 58 | 이번 9단계에서 행동 보존으로 처리 |
| LATER | 18 | 행동 변화가 필요 — 9단계 대상 아님(판단 개선 단계) |
| KEEP | 30 | 의도적으로 유지 |

## batch

| batch | 범위 | 배정 항목 수 | 상태 |
|---|---|---|---|
| B1 | preflop (preflop.py, gto.py 이름, persona preflop 공급) | 17 | 완료 |
| B2 | ranges / reads / persona 읽기 / money_pressure | 7 | 완료 |
| B3 | plan 포스트플랍 (make_plan, decide_aggression, decide_size, decide_response, act_with_plan, checkraise) | 24 | 대기 |
| B4 | persona 개념 scalar 역할 함수 | 20 | 대기 |
| B5 | RENAME 과 REMOVE_COMPAT | 9 | 대기 |
| B6 | bot / texture / depth | 5 | 대기 |

모든 batch 공통 검증:
- pristine 기준 커밋 대비 같은 입력 → 같은 출력 + RNG 상태(바이트 비교 probe)
- baseline sim 지문 = R2 봉인값(시드 11 `e6d8b5e5…`, 12 `c13a5bf4…`)
- 23-gate 통과/실패 집합 동일, completeness 미소유 0, ledger/등록부 갱신

## 항목별

| ID | 개념 | ledger 판정 | 9단계 분류 | 내용 |
|---|---|---|---|---|
| L001 | bluff | SPLIT | NOW:B4 | bluff 를 ability / evidence / temperament 역할 함수로 나누되 같은 scalar 를 공급 |
| L002 | semibluff | SPLIT | NOW:B4 | semibluff 공급 함수에 street 문맥을 이름으로 드러냄(river 비적용 명시) |
| L006 | checkraise_flop | SPLIT | NOW:B4 | checkraise_flop 과 generic trap gate 별칭을 이름으로 분리(값 동일). 별칭 교체 자체는 LATER |
| L007 | checkraise_late | SPLIT | NOW:B4 | checkraise_late 의 turn/river 공급 경로 이름 분리 |
| L008 | bluffcatch_early | SPLIT | NOW:B4 | bluffcatch capability 와 주관 콜 편향 공급 분리(값 동일) |
| L009 | bluffcatch_river | SPLIT | NOW:B4 | 같음(river) |
| L010 | thin_value_turn | KEEP | KEEP | flop 은 range_merge 사용 — 의도된 공급 |
| L012 | blockbet | SPLIT | NOW:B4 | blockbet motive / size 공급 분리 |
| L013 | potcontrol | SPLIT | NOW:B4 | potcontrol motive vs 빈도 scalar 분리 |
| L014 | trap | SPLIT | NOW:B4 | trap no-bite / checkraise gate 공급 분리 |
| L015 | overbet | SPLIT | NOW:B3 | overbet 실행 함수 안의 street 분기를 명명 |
| L016 | probe | SPLIT | NOW:B3 | poker probe 와 bluff_mode 의 probe 크기 모드 이름 분리(L144 와 함께) |
| L018 | equity_denial | KEEP | KEEP | river 미래 equity 없음 — 설명만 |
| L019 | stackoff | SPLIT | NOW:B4 | stackoff ability / investment horizon 공급 분리 |
| L020 | reraise | SPLIT | NOW:B4 | reraise 의 preflop/postflop 소비를 역할 이름으로 분리 |
| L021 | outs | SPLIT | NOW:B4 | outs: raw draw count 와 인지(calc_noise) 경계 명명 |
| L022 | potodds | SPLIT | NOW:B4 | potodds: 계산 정밀도 vs 추론 확신 역할 분리 |
| L023 | spr | SPLIT | NOW:B4 | spr: 비율 / 인지 / 계획 역할 분리 |
| L024 | range_read | SPLIT | PARTIAL | 3·4차에서 복원/해석/적용 경계 분리 완료. 남은 공급 분리는 독립 skill = LATER |
| L025 | blocker | SPLIT | NOW:B4 | blocker: 객관 블로커 vs skill 사용 분리 |
| L026 | icm | SPLIT | NOW:B4 | icm: 수학 BF / 인지 / 계획 역할 분리 |
| L027 | board_texture | SPLIT | NOW:B6 | board_texture: raw facts / street 해석 분리 |
| L028 | sizing_tell | SPLIT | NOW:B4 | sizing_tell: 텔 인지 vs 자기 사이즈 위장 분리 |
| L029 | pf_range | SPLIT | DONE(B1) | pf_range: RFI 기억 vs 림프 추론 역할 분리(L064 와 함께) |
| L030 | positional | SPLIT | DONE(B1) | positional: prior 조건 vs 추론 역할 분리 |
| L033 | pf_defend | SPLIT | DONE(B1) | pf_defend: 지식 / 추론 게이트 / family 역할 분리 |
| L034 | range_merge | SPLIT | NOW:B4 | range_merge: merged-value vs thin-flop 역할 분리 |
| L035 | multiway | SPLIT | PARTIAL | 4차에서 multiway 적용 능력 분리. 남은 pool identity vs 추론 명명은 B4 |
| L036 | fold_equity | SPLIT | NOW:B4 | fold_equity: 확률 추정 vs 활용 분리 |
| L037 | money_jump | KEEP | KEEP | money_jump: preflop 활성, 이후 shadow |
| L047 | aggressive_street_count | MERGE | KEEP | ranges 의 재생 중 누적 수와 canonical 결정 시점 전체 수는 시간 기준이 다른 질문(B2 조사 결과 재분류) |
| L049 | preflop_public_roles | SPLIT | LATER | _was_3bettor 는 원시 로그의 raise/allin(올인 콜 포함)을 세고 canonical 역할은 full raise 만 센다 — 교체하면 행동 변화(B1 조사 결과 재분류) |
| L054 | called_aggression_ownership | SPLIT | DONE | line_owned_by_live_aggressor 추출(재감사) |
| L055 | rfi_width_prior | KEEP | KEEP | RFI 폭 prior — 지식 항목 |
| L056 | defend_width_prior | RENAME | DONE(B1) | RENAME: mdf 는 정확한 MDF 가 아니라 폭 보정 대용 |
| L057 | threebet_width_prior | SPLIT | DONE(B1) | 3벳 prior 층 분리(R2 S2). 독립 차트는 MISSING_KNOWLEDGE |
| L058 | chart_memory_accuracy | SPLIT | DONE(B1) | acc 가 차트 기억 정확도이자 기질 이탈 상한 — 두 역할 함수로 분리(값 동일) |
| L059 | studied_condition_match | KEEP | KEEP | OPT-IN, 기본 꺼짐 |
| L060 | preflop_condition_reasoning | KEEP | KEEP | OPT-IN, 기본 꺼짐 |
| L061 | legacy_preflop_ordering | SPLIT | DONE | 1차 legacy 이름 + R2 A 소비처별 역할 판정 + B1 에서 블로커/posterior/fallback 순서 역할 명명 |
| L063 | rfi_personality_deviation | SPLIT | DONE(B1) | L058 과 같은 분리(RFI 쪽) |
| L064 | limp_entry_motive | SPLIT | DONE(B1) | rfi skill 을 림프 지식으로 재사용하는 공급을 역할 함수로 명명 |
| L067 | unopened_decision | SPLIT | DONE(B1) | open_decision 의 판단 / 계획 / 형태를 함수 경계로 분리 |
| L068 | isolation_decision | SPLIT | DONE(B1) | iso 폭 산출을 명명(독립 prior 는 MISSING_KNOWLEDGE) |
| L069 | defend_attack_continue_widths | SPLIT | DONE | 2차 디펜스 폭 경계 + B1 3벳/4벳 층 분리(후보/증거/prior/4벳 MISSING_KNOWLEDGE 명시) |
| L071 | sample_defend_action | RENAME | KEEP | "3bet" 액션 라벨은 하위 소비처가 읽는다 — 라벨 변경은 행동 변화. 의미는 문서/주석으로만(B1 조사 결과) |
| L072 | reraise_sizing_form | SPLIT | DONE(B1) | raise_form: 동기 vs 스택 커밋 기하 분리 |
| L073 | reshove_opportunity | SPLIT | DONE(B1) | 리쇼브 후보 / legacy 폭 / legacy 확률 분리(R2 S3) |
| L075 | preflop_card_removal | SPLIT | DONE(B1) | 블로커 몫: PCT 순서 vs 관측 질량 분리 |
| L077 | legacy_calloff_threshold | SPLIT | DONE(B1) | legacy 콜오프 폭 소비 경로 명명(R2 S1) |
| L078 | layer_calloff_judgment | SPLIT | DONE(B1) | layer 콜오프: 수학 vs skill 게이트 경계 명명 |
| L079 | calloff_comparison_shadow | KEEP | KEEP | SHADOW |
| L082 | range_identity_signature | SPLIT | DONE(B2) | 캐시 시그니처 계약별 이름 분리 |
| L083 | preflop_posterior_order | SPLIT | DONE(B1) | posterior 순서: support-count rank vs 누적 질량 명명 |
| L087 | range_reconstruction_grasp | MERGE | DONE | blend_action_range_by_grasp 통합(1차), reconstruction 함수(3차) |
| L089 | bet_range_partition | SPLIT | DONE(B2) | bet range 분할: flop/turn 드로우 지원 vs river 블로커 전용 분리 |
| L090 | continue_range_partition | MERGE | DONE | continuation_support_fraction 통합(1차) |
| L093 | raise_range_posterior | SPLIT | LATER | forward raise 정책과 posterior 불일치 — 행동 변화 |
| L095 | hero_made_contribution | RENAME | NOW:B5 | RENAME: made_strength = hero 기여 카테고리(정의 교정은 LATER, L-RA09) |
| L097 | current_board_not_behind | RENAME | NOW:B5 | RENAME: rel 은 equity 가 아님(joint/union fallback 명시) |
| L099 | unconditioned_equity | KEEP | KEEP | FALLBACK |
| L102 | strong_region_advantage | RENAME | NOW:B5 | RENAME: nut_advantage 는 문자 그대로의 넛이 아님 |
| L103 | strong_support_blocker | SPLIT | DONE(B2) | blocker_score: support 분위 vs 질량 분위 분리 |
| L105 | relative_strength_perception | SPLIT | NOW:B3 | perceived_rel: true rel 과 perceived rel 경계 명명 |
| L107 | depth_perception | SPLIT | NOW:B6 | depth: 객관 깊이 vs 주관 추정 경계 명명 |
| L109 | board_completion_danger | SPLIT | NOW:B6 | board_danger raw vs skill-scaled state.danger 명명(계약 통일은 LATER, L-RA06) |
| L111 | street_texture_sizing | SPLIT | NOW:B6 | texture sizing: 보드 사실 / 학습 prior / 인지 잡음 분리 |
| L112 | turn_card_range_shift | SPLIT | NOW:B6 | river 호출을 실제 질문 이름으로(값 동일). 턴 카드 반영은 LATER(L-RA07) |
| L114 | calculation_error | SPLIT | NOW:B4 | calc_noise 의 계산 종류별 진입점 명명 |
| L115 | value_line_selection | SPLIT | NOW:B3 | make_plan 의 긴 inline 판단을 등록부 개념 단위 함수로 추출 |
| L116 | vulnerable_paired_flush | SPLIT | NOW:B3 | 같은 이름 다른 문턱 — 문맥별 함수로 분리(합치지 않음) |
| L118 | deep_one_pair_caution | SPLIT | NOW:B3 | 같음 |
| L119 | continue_range_value | SPLIT | NOW:B3 | continue-range value 판정의 street 별 게이트 분리 |
| L120 | semibluff_line_selection | SPLIT | NOW:B3 | semibluff 선택: flop 두 드로우 / turn 한 드로우 / river 전환 분리 |
| L121 | pure_bluff_line_selection | SPLIT | NOW:B3 | 순수 블러프: 동기 / 증거 / 능력 / 위장 분리 |
| L122 | potcontrol_motive | SPLIT | NOW:B3 | potcontrol 라벨과 빈도 분리 |
| L123 | potcontrol_bet_propensity | SPLIT | NOW:B3 | potcontrol 벳 성향: continuation vs caller stab 분리 |
| L124 | blockbet_motive | SPLIT | NOW:B3 | blockbet 동기: flop 비이니셔티브 동크 중첩 분리 |
| L125 | trap_induction | SPLIT | LATER | trap 의 latent.study 직접 사용 — 공급 변경 |
| L127 | draw_completion_value_gate | MERGE | DONE | draw_completion_supports_value(1차) |
| L129 | missed_draw_river_conversion | SPLIT | DONE | river_semibluff_resolution(1차) |
| L131 | flop_cbet_plan | SPLIT | DONE | cbet_flop_frequency(1차) |
| L132 | turn_barrel_plan | SPLIT | DONE | barrel_turn_frequency(1차) |
| L133 | river_barrel_plan | SPLIT | DONE | barrel_river_frequency(1차) |
| L134 | probe_after_checkthrough | SPLIT | NOW:B3 | probe: turn 드로우 의존 / river 무드로우 분리 |
| L138 | planned_bet_sizing | SPLIT | NOW:B3 | decide_size: 강도 질문 vs 실행 사이즈 분리 |
| L139 | turn_overbet | SPLIT | NOW:B3 | overbet_frac turn 분기 분리 |
| L140 | river_overbet | SPLIT | NOW:B3 | overbet_frac river 분기 분리(union range 사용은 LATER, L-RA10) |
| L142 | target_investment_fraction | SPLIT | NOW:B3 | target_commit 의 쓰이지 않는 인자 명시(고정 horizon 교정은 LATER) |
| L143 | stackoff_spread_horizon | SPLIT | LATER | stackoff 고정 3스트리트 기하 — remaining streets 로 바꾸면 행동 변화 |
| L144 | bluff_sizing_camouflage | RENAME | NOW:B3 | RENAME: bluff_mode 의 probe = 사이즈 모드 |
| L145 | calldown_required_share | SPLIT | NOW:B3 | calldown_need: 객관 가격 vs 주관 콜 문턱 분리(쓰이지 않는 read 인자 명시) |
| L146 | nonvalue_raise_ev_gate | SPLIT | NOW:B3 | nonvalue raise EV 게이트의 적용 범위 명명(트리 확장은 LATER) |
| L147 | response_plan | SPLIT | NOW:B3 | decide_response: 판단 vs 계획 기록 분리 |
| L148 | call_bias_reapplication | SPLIT | LATER | call bias 이중 반영 제거 = 행동 변화 |
| L149 | checkraise_flop_decision | SPLIT | PARTIAL | checkraise_draw_street_probability(1차). flop 결정 함수 경계는 B3 |
| L150 | checkraise_turn_decision | SPLIT | DONE | flop/turn 공유 확률 함수(1차) |
| L151 | checkraise_river_decision | SPLIT | DONE | checkraise_river_probability(1차). river_bluff 라벨 누락은 LATER |
| L152 | checkraise_sizing | SPLIT | NOW:B3 | checkraise_size: street 기준과 절대/추가 단위 분리 |
| L153 | action_adapter_with_reasoning | SPLIT | NOW:B3 | act_with_plan: 추론 vs 실행 분리 |
| L154 | human_planned_size_shape | RENAME | NOW:B5 | RENAME: shape_size 는 표시용이 아님 |
| L156 | plan_revision_lifecycle | SPLIT | LATER | replan 의 bb/tilt/문맥 전달 보완 = 행동 변화(경계 명명만 B3) |
| L157 | plan_concept_permission | SPLIT | NOW:B3 | _allowed 의 generic checkraise 별칭 분리(별칭 교체는 LATER) |
| L161 | opponent_behavior_memory | SPLIT | LATER | bot 테이블이 Book 을 매 핸드 새로 만듦 — 기억 지속은 행동 변화 |
| L163 | showdown_strength_observation | SPLIT | LATER | 쇼다운 관측 가시성 + PCT 를 쇼다운 강도로 사용 |
| L164 | opponent_estimation | SPLIT | DONE(B2) | estimate: 믿음 불확실성 vs exploit 강도 분리 |
| L166 | style_belief_reference | KEEP | KEEP | SHADOW |
| L167 | recency_window | KEEP | KEEP | OPT-IN |
| L168 | exploit_read_permission | SPLIT | DONE(B2) | legacy exploit_weight vs read_opponent 가중치 경계 명명(v3 통합은 opt-in 유지) |
| L169 | opponent_sizing_normalization | SPLIT | DONE(B2) | size read: 물리 팟오즈 vs 인지 분리 |
| L170 | shown_hand_range_adjustment | SPLIT | LATER | 쇼다운 히스토리 확장 — 상대 적응 경로(baseline 고정 대상) |
| L172 | accumulation_variance_drive | SPLIT | KEEP | 분산 추구 = 의도된 인간 성향(D). 설명만 |
| L174 | icm_bubble_factor | SPLIT | KEEP | BF 단순화 — 지식 항목 |
| L175 | field_icm_proxy | REMOVE_COMPAT | NOW:B5 | REMOVE_COMPAT: 덮어쓰인 옛 field_bf 와 그 전용 표 |
| L177 | icm_required_equity_reference | KEEP | KEEP | FALLBACK, 다른 pot 규약 — 합치지 않음 |
| L184 | stack_cover_pressure | SPLIT | DONE(B2) | stack cover pressure 하위 질문 명명 |
| L185 | money_commitment_budget | KEEP | KEEP | SHADOW |
| L187 | money_open_form_shadow | KEEP | KEEP | SHADOW |
| L189 | layer_expected_share | RENAME | NOW:B5 | RENAME: _diagnostic_layer_equities 는 일부 ACTIVE |
| L194 | showdown_visibility | SPLIT | LATER | 쇼다운 가시성 이전 기록 — 행동 변화 |
| L198 | emotion_profile_view | SPLIT | LATER | axes view 의 전면 reroute — 행동 변화 |
| L199 | persona_population_generation | SPLIT | KEEP | 생성 latent vs runtime — 설명만 |
| L200 | display_skill_summary | KEEP | KEEP | SHADOW |
| L206 | legacy_tournament_progress | KEEP | KEEP | FALLBACK |
| L207 | telemetry_observation_only | KEEP | KEEP | SHADOW |
| L208 | legacy_betting_range | KEEP | KEEP | FALLBACK(조용히 합치지 않음). 순서표 중복은 R2-A3 |
| L209 | legacy_arch_types | KEEP | KEEP | FALLBACK |
| L210 | legacy_sidepot_helper | KEEP | NOW:B5 | REMOVE_COMPAT 후보: table.Table.sidepots — 참조 확인 후 |
| L211 | legacy_icm_overridden | KEEP | NOW:B5 | REMOVE_COMPAT: icm.field_bf 첫 정의(덮어쓰임) |
| L212 | dead_generic_error_rate | KEEP | KEEP | persona.error_rate — tools/audit_error_rate_v3 가 읽음. DEAD 표시만 |
| L213 | placeholder_gto_adaptation | KEEP | KEEP | gto.adapt_mult — 1.0 상수 placeholder 이지만 persona.open_pct 가 호출. 설명만 |
| L-RA01 | called_aggression_ownership | RENAME | DONE | 등록부 의미 정정, 추출 |
| L-RA02 | lead_into_aggressor_policy | MERGE | LATER | 세 메커니즘 통합 = 행동 변화 |
| L-RA03 | value_when_called_strength | MERGE | LATER | 네 producer 통합 = 행동 변화 |
| L-RA04 | showdown_value_predicate | MERGE | PARTIAL | 식 통합 완료. equity 기준 통일은 LATER |
| L-RA05 | players_behind_risk_premium | MERGE | DONE | players_behind_required_equity_premium |
| L-RA06 | perceived_board_danger | SPLIT | LATER | danger 계약 통일 = 행동 변화(명명은 B6) |
| L-RA07 | turn_card_range_shift | SPLIT | LATER | 턴 카드 반영 = 행동 변화(명명은 B6) |
| L-RA08 | medium_strength_merge_value | REROUTE | LATER | skill 공급 변경 |
| L-RA09 | giveup_reentry_on_improvement | SPLIT | LATER | made_strength 정의 교정(명명은 B5) |
| L-RA10 | multiway_representative_union_range | REROUTE | LATER | union → seat pool reroute |
| L-RA11 | opponent_unconsumed_estimates | KEEP | KEEP | SHADOW(exploit 단계) |
| L-RA12 | opener_position_attack_table | SPLIT | DONE(B1) | OPENER_MULT 두 용도에 각각 이름(값 공유). 분리값은 LATER |
| L-RA13 | defend_width_prior | KEEP | KEEP | 지식 공백(R2 MISSING_KNOWLEDGE) |
| L-RA14 | dead_strategy_tables | REMOVE_COMPAT | NOW:B5 | REMOVE_COMPAT: 읽히지 않는 전략 상수 표 4개 |
| L-RA15 | response_equity_basis | KEEP | KEEP | FALLBACK |
| L-RA16 | plan_revision_lifecycle | RENAME | DONE | 주석 갱신 |
| L-RA17 | self_hand_overconfidence_bias / perceived_player_edge | KEEP | KEEP | 설명만 |
| L-RA18 | opponent_concept_inference (range_profile) | KEEP | KEEP | baseline 하네스로 고정 |
