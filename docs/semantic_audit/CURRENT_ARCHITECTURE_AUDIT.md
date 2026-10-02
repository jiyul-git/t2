# CURRENT_ARCHITECTURE_AUDIT

기준은 test `4b9d33d5f951fce4b292f6e6e79caaf141b106d2`. master는 정식 코어 `8614f32d2293ddcc7442447fe569b87ab105c6ea`. “production wiring”은 이 Git tree의 기본 실행 경로이며 사용자 기기의 배포 버전/환경변수를 확인했다는 뜻이 아니다.

## Git 증거

초기 checkout clean. master/test 공통조상 `f8357a994fa7e78c241d7345427ba21ae8f74d2a`; test ahead 544 / behind 8. endpoint diff 79 files, +11118/-733. master-only 8 commits는 문서/운영 변경이며 Python core 변경 없음. master는 현재 test의 ancestor가 아니다. merge/promotion/branch cleanup 없음.

| remote branch | 확인한 HEAD |
| --- | --- |
| master | 8614f32d2293ddcc7442447fe569b87ab105c6ea |
| test | 4b9d33d5f951fce4b292f6e6e79caaf141b106d2 |
| chatgpt/gto-reference-20260928 | 1d19561a60faa0eb48a578219195967f4122ed5e |
| chatgpt/mini-cfr-solver-20260928 | 434abfeba5c309e3cb29f5dafb982133dd79d6fb |
| chatgpt/terminal-census-v2-20260930 | 481857efc8ed10b595b35f908d00e1d04b4e7fa0 |
| telemetry/live | 32395ab8c75d596809fb52f6eb2a169372703200 |

전체 tracked Python 268파일/함수 2214개를 AST census로 포함했다. production 의존 모듈과 실제 함수 본문/호출 경로를 읽어 명시 concept 37개 외 독립적인 계산·인지·판단·계획·상태 개념을 추출했다. reference/tool 함수는 production 기능으로 세지 않는다. 정적 호출 목록은 동적 dispatch 전체 도달성 증명이 아니므로 실행 검증을 병행한다.

## 실제 실행 경로

| 단계 | 실제 producer / consumer | 경계와 현재 한계 |
| --- | --- | --- |
| STATE | ui_server._step → live2.step/build_hand → fieldsim.Field.stamp → play.Hand → session.HandRun._run; runner.Round | UI는 live2 물리 필드. tourney는 별도 legacy 필드 runtime |
| PUBLIC STORY | Round.apply 메타 → action_events.postflop_events/response_context/street_outcome; session._preflop_public_action_context/_pf_observation_flags | postflop canonical producer 존재. preflop raw log _was_3bettor는 별도 |
| KNOWLEDGE | gto.rfi/defend_pct/threebet_pct → persona.gto_knowledge/open_pct; preflop.defend_thresholds; texture.* | authored prior/heuristic. 독립 solver combo DB의 production import 없음 |
| PERCEPTION | reads.Book → estimate/perceived_profile/range_profile → persona.read_opponent; perceived_rel; texture.perceived; calc_noise | range_read가 reconstruction·line interpretation·관측 품질 겸함 |
| RANGE | session._preflop_story_range → ranges.preflop_range/_defend_likelihood_range/preflop_reraise_posterior → perceived_range/narrow_by_actions | active/locked seat pools 보존. union fallback과 별도 shown-hand heuristic 존재 |
| CALCULATION | bot.equity_vs_combos/equity_vs_pools; plan.relative_strength/joint_relative_strength; ranges.joint_range_advantage/joint_nut_advantage/joint_blocker_effect; icm.table_bf; session._diagnostic_layer_equities | rel tie=1, equity split ties, made=board 대비 category. 서로 대체 불가 |
| JUDGMENT | plan.make_plan/calldown_need/decide_response/checkraise_decision/river_fix/refresh; preflop.*decision; money_pressure.* | 독립 깨끗한 layer가 아니라 여러 함수 안에 지각·계산·motive·form 혼재 |
| PLAN | make_plan → attach_intent → decide_aggression/decide_size; preflop_plan; record_response_plan; shape_planned_target | street별 intent, budget, stackoff. act_with_plan도 새 판단을 수행함 |
| ACTION | plan.act_with_plan → session.HandRun._run → runner.effective_allin_v1/Round.apply | legal caps/rounding 외 effective-allin 정책도 남음. pure executor라고 단정 불가 |
| OBSERVATION/MEMORY | Book.observe_*; Tilt.*; live2._archive/fieldsim._log_bot_hand → telemetry_sync.emit_round | telemetry는 online learner 아님. bot-only table Book 재생성; shown/muck 판정 전 관측 |

## 중요한 판정

1. `pf_rank/PCT`: RFI/iso/defend/3bet/4bet/reshove/calloff/레인지 ordering·posterior/블로커 class ordering/showdown weak-strong 관측까지 공유. 호환 ordering 이름을 명시할 수 있지만 역할별 equity/EV로 교체하면 행동이 바뀐다.
2. `relative_strength`는 현재 보드 not-behind, `equity`는 runout 포함 split-pot share, `made_strength`는 보드보다 높은 category 기여. `range advantage`는 range-v-range, `nut advantage`는 강한 category 구간 점유율 proxy다.
3. checkraise_late는 turn/river 공유, bluffcatch_early는 flop/turn 공유, range_merge는 flop thin-value skill 대체. 독립 capability 값을 새로 생성하면 RNG/분포가 바뀌므로 이번에는 함수의 질문과 street를 분리하고 기존 수치 공급을 명시한다.
4. F8은 전부 shadow가 아니다. pure preflop calloff, complete closing postflop call, no-raise closing river bet veto는 ACTIVE. 일반 sidepot raise tree/미래 street의 전체 EV는 미완성.
5. default OFF: T2_GTO_MEMORY_V2, T2_PREFLOP_REASONING_V3, T2_EXPLOIT_WEIGHT_V3, T2_CALC_NOISE_V3, T2_PREFLOP_TEMPER_DIRECTION_V3, T2_READ_RECENCY_V3. 코드 존재와 기본 활성화를 구분한다.
6. `gto.threebet_pct`는 실제 연결되지만 defend 폭에서 파생한 share다. 별도 4bet/cold4bet/reshove/postflop solver policy는 test production 경로에 없다. GTO 작업 branch에 산출물이 있다는 사실과 production 연결은 다르다.
7. raw danger와 skill-scaled danger가 같은 state 이름을 쓰고, trap은 latent.study를 runtime에서 직접 쓴다. tilt view도 실제 JUDGMENT consumer로 흐른다. 설계 위반 후보이며 behavior-changing 교정은 분리한다.
8. Python fresh runtime 복사 시 telemetry_sync 누락으로 import 실패를 재현했다. 두 setup 목록에서 action_events도 누락됐다. 기존 모듈 배포 목록만 동기화한다.

## 리팩터링 허용 범위

동일 predicate/weighted blend/continue-width 계산 통합, 실제 inline checkraise street 정책 추출, draw 완료 predicate 및 turn/river 전환 질문 명명, 호환 ordering 의미 명시. 수치/확률/threshold/evaluation 순서/RNG 소비 유지. 공유 skill을 독립적으로 새 샘플링하거나 기존 오류를 전략적으로 고치지 않는다. 미해결은 ledger에 남긴다.

수정 전 기존 regress current는 이미 6/6 seed 불일치. 과거 baseline을 덮어쓰지 않고 pristine HEAD를 이번 before/after 기준으로 사용한다.
