# CANONICAL_VERIFIER_MANIFEST

검증 스크립트 기준을 하나로 정리한다. 스크립트를 합치지 않고 **무엇을 언제 돌리는지**만 통일한다.

## 언제 무엇을 돌리나

| 시점 | 실행 | 통과 기준 |
| --- | --- | --- |
| 모든 코드 변경 직후 | `python tools/run_verifier_manifest.py --tier fast` + `python tools/check_semantic_completeness.py` | fast 전부 PASS, completeness rc 0 |
| 행동 불변 리팩터링 | 위 + 해당 parity verifier(`semantic_cleanup`, `defend_semantic_cleanup`, `range_read_semantics`, `remaining_read_semantics`, `reaudit_semantic_extraction`) + baseline sim action/intent 바이트 비교 | parity PASS, sim 동일 |
| 행동 변경 batch / push 전 | `--tier gate23` (+ baseline sim before/after) | expected 와 동일한 PASS/FAIL 집합 |
| 체크포인트 / 승격 검토 | `--tier all --timeout 900` | 아래 expected 와 동일; REGRESSION 0 |

`expected` 가 FAIL/TIMEOUT 인 스크립트는 pristine HEAD 에서도 같은 상태인 **역사적 실패**다. 억지로 고쳐 PASS로 만들지 않았다. 상태가 바뀌면 원인을 조사하고 이 표를 갱신한다.

요약: PASS 49 / FAIL 20 / TIMEOUT 2 (총 71). REGRESSION: 없음

| verifier | 목적 | subsystem | 23-gate | 40-suite | 40-suite@4b9d33d | pristine HEAD | 현재 | 분류 | 초 | 메모 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 9max | Fast structural verification for the 9-max migration. | tournament runtime |  |  |  | PASS | PASS | pass | 5.3 |  |
| allin_raise_rights | Targeted checks for raise rights once all remaining opponents are all-in. | betting rules/pot |  | Y | PASS | PASS | PASS | pass | 0.0 |  |
| audit_order | audit.py 의 스트리트 액션 순서 검사 D1~D6. | audit tooling |  |  |  | PASS | PASS | pass | 19.5 | environment-dependent: D3/D4 read untracked repo-root *.jsonl archives; PASS in a clean worktree |
| button_rotation | Tournament dealer/blind rotation regression. | tournament runtime |  |  |  | PASS | PASS | pass | 0.0 |  |
| calc_noise_v3 | Verify Human Model v3 concept-specific calc error semantics. | human model v2/v3 |  | Y | PASS | PASS | PASS | pass | 2.5 |  |
| core_joint_nut | Verify seat-keyed multiway nut-advantage semantics. | core plan/range | Y | Y | PASS | PASS | PASS | pass | 0.1 |  |
| core_multiway_reads | Verify seat-aware multiway read/stack selection in the core plan layer. | core plan/range | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| core_p7_cold_reraise | Core P7 cold-vs-reraise verifier. | core plan/range | Y | Y | PASS | PASS | PASS | pass | 2.5 |  |
| core_p7_observation | Verify dedicated P7 cold-reraise observation semantics. | core plan/range | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| core_sizing_ownership | Core F7-D sizing ownership verifier. | core plan/range | Y | Y | PASS | PASS | PASS | pass | 0.1 |  |
| decay_profile | 틸트 감쇠가 **자기 프로필**을 쓰는지 직접 검증한다 (읽기 전용). | tilt/emotion |  |  |  | PASS | PASS | pass | 163.9 |  |
| defend_semantic_cleanup | Compare real pre-checkpoint defend policy with extracted pipeline (9-max first). | semantic audit parity |  |  |  | PASS | PASS | pass | 0.3 |  |
| defer | 안 A(다른 테이블 진행 지연)가 동작을 보존하는지 검증한다. | runtime/parallel |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 862.2 |  |
| effective_allin_v1 | Targeted checks for effective-all-in v1 classifier. | betting rules/pot |  | Y | PASS | PASS | PASS | pass | 0.0 |  |
| f1_free_action | Targeted structural verifier for F1 no-wager fixes. | postflop F-series |  | Y | PASS | PASS | PASS | pass | 0.1 |  |
| f2_checkthrough | Targeted structural verifier for F2 check-through fixes. | postflop F-series |  | Y | PASS | PASS | PASS | pass | 0.1 |  |
| f3_checkraise_response | Targeted structural verifier for F3 check-then-face-bet fixes. | postflop F-series | Y | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.1 |  |
| f4_facing_bet | Targeted structural verifier for F4 direct facing-bet fixes. | postflop F-series | Y | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 | stale API: session._observed_postflop_action removed |
| f5_backaction | Targeted structural verifier for F5 postflop aggressor back-action fixes. | postflop F-series |  | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 |  |
| f6_caller_backaction | Targeted structural verifier for F6 caller back-action. | postflop F-series | Y | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 |  |
| f7_street_closure | Targeted verifier for F7 postflop street-closure carry fixes. | postflop F-series | Y | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.1 | stale tuple shape (expects 3 values) |
| f7b_blocker_activation | Verify production matches preregistered F7-B1C11 blocker structure target. | F7-B range/defend |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 0.1 |  |
| f7b_defend_likelihood | F7-B1D7: verify RNG-free defend likelihoods against live branch semantics. | F7-B range/defend | Y |  |  | PASS | PASS | pass | 7.6 |  |
| f7b_defend_rewire | F7-B1D7: exact behavior/RNG parity for the defend wiring refactor. | F7-B range/defend |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 0.1 |  |
| forced_blind_allin_showdown | SB/BB 강제 올인이 액션 없이도 정상 쇼다운되는지 검증한다. | betting rules/pot |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 | stale test double: fake Book lacks observe_cold_reraise |
| forced_blind_allin_view | 강제 블라인드 올인 좌석이 UI 뷰에서 폴드처럼 사라지지 않는지 검증한다. | betting rules/pot |  |  |  | PASS | PASS | pass | 0.0 |  |
| human_model_v2 | Human Model v2 targeted verifier — GTO memory confidence + invariants A..G. | human model v2/v3 |  | Y | TIMEOUT | TIMEOUT | TIMEOUT | historical (same status on pristine HEAD) | 900.1 | exceeds 900 s |
| human_model_v3 | Targeted verifier for Human Model v3 preflop recall -> reasoning -> temperament. | human model v2/v3 | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| human_model_v3_integration | Combined Human Model v3 integration verifier on canonical 9-max MTT fixtures. | human model v2/v3 | Y | Y | TIMEOUT | PASS | PASS | pass | 776.6 | ~6-10 min: TIMEOUT under the 40-suite 180 s limit, PASS under 900 s |
| human_model_v3_runtime | Human Model v3 runtime / paired-counterfactual verifier. | human model v2/v3 | Y |  |  | PASS | PASS | pass | 409.7 |  |
| icm_fast | Verify the 2..9-player exact-ICM fast path against historical recursion. | money jump / ICM |  | Y | PASS | PASS | PASS | pass | 30.2 |  |
| money_jump_context | 머니점프 문맥 계산의 경계값/동일상금 구간 회귀검사. | money jump / ICM |  |  |  | PASS | PASS | pass | 0.0 |  |
| money_jump_observation | 머니점프 관측 배선: 스택분포/자리/커버관계가 행동과 분리돼 기록되는지 검사. | money jump / ICM |  |  |  | PASS | PASS | pass | 0.1 |  |
| money_pressure_signals | 머니점프 연속 신호의 구조적 단조성 회귀검사. | money jump / ICM |  |  |  | PASS | PASS | pass | 0.0 |  |
| multiway_range_preservation | Targeted verifier for per-opponent postflop range preservation. | weighted range | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| oop_semantics | 포스트플랍 포지션 술어와 그 행동 영향 검증. | position semantics |  |  |  | TIMEOUT | TIMEOUT | historical (same status on pristine HEAD) | 900.1 | exceeds 900 s |
| p2_limped_pot | Targeted verifier for P2 limped-pot fixes. | preflop P-series | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| p3_first_open | Targeted verifier for P3 first-open audit fixes. | preflop P-series | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| p4_vs_3bet | Targeted structural verifier for P4 opener-facing-3bet fixes. | preflop P-series | Y | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.1 |  |
| p5_backaction | Targeted verifier for P5 preflop back-action fixes. | preflop P-series | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| p6_calloff | Targeted structural verifier for P6 all-in/call-off fixes. | preflop P-series | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| parallel_tables | 병렬 테이블 round의 소유권/merge 불변식 검증. | runtime/parallel |  |  |  | PASS | PASS | pass | 0.4 |  |
| postflop_events | Structural verification for canonical postflop action events. | public action events |  | Y | PASS | PASS | PASS | pass | 0.0 |  |
| prefetch_determinism | 프리페치 전제 검증: _load_field → step_others(settle=False) → _dump 가 | runtime/parallel |  |  |  | PASS | PASS | pass | 193.7 |  |
| preflop_closure | Preflop closure verifier for P1 reopen fixes and P7 decision classes. | preflop | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| preflop_temper_direction_v3 | Verify full-scale preflop temperament direction for Human Model v3. | preflop |  | Y | PASS | PASS | PASS | pass | 0.0 |  |
| prelogic_execution_boundary | Behavior-neutral F7-D judgment -> execution boundary gate. | judgment/execution boundary |  | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 18.3 |  |
| prelogic_profile_boundary | Behavior-neutral F7-C pre-logic profile boundary gate. | judgment/execution boundary |  | Y | PASS | PASS | PASS | pass | 0.0 |  |
| range_read_semantics | Compare real checkpoint functions, including RNG and mutated response state. | reads/range_read |  |  |  | PASS | PASS | pass | 1.1 |  |
| read_range_semantics | Regression checks for public preflop range reconstruction and read semantics. | reads/range_read |  | Y | PASS | PASS | PASS | pass | 0.0 |  |
| read_recency_v3 | Verify Human Model v3 opponent-memory recency semantics. | reads/range_read | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| reaudit_semantic_extraction | Behavior-identity check for the re-audit semantic extractions. | semantic audit parity |  |  |  | NEW | PASS | pass | 95.4 | new in re-audit; compares against HEAD (or given base) |
| remaining_read_semantics | Stage4: compare actual old consumers, not duplicated formulas. | reads/range_read |  |  |  | PASS | PASS | pass | 0.4 |  |
| replan_contract | make_plan 입력 계약: 최초 수립 경로 vs 보드변화 재계획 경로. | plan lifecycle |  | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.1 |  |
| semantic_cleanup | Compare extracted semantic boundaries to the actual pre-refactor functions. | semantic audit parity |  |  |  | PASS | PASS | pass | 2.9 |  |
| settle_split | step_others(settle=False) 분리가 동작을 보존하는지 검증한다. | runtime/parallel |  |  |  | PASS | PASS | pass | 697.6 |  |
| state_namespace | 상태별 sidecar namespace 격리 검증 (A9-W). 읽기 전용. | runtime/parallel |  |  |  | PASS | PASS | pass | 155.2 | environment-dependent: repo sidecar invariants; PASS in a clean worktree |
| stepothers_timing | step_others 를 언제 돌리느냐가 결과를 바꾸는지 잰다. | runtime/parallel |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 | CLI driver: requires --mode (not a standalone pass/fail verifier) |
| tda_dead_button | TDA dead-button / heads-up / table-balance position contract. | tournament runtime |  |  |  | PASS | PASS | pass | 0.0 |  |
| tda_live_integration | Integration checks for TDA blind anchors through live2 persistence/HandRun. | tournament runtime |  |  |  | PASS | PASS | pass | 3.4 |  |
| telemetry_wiring | Verify whole-tournament telemetry captures real engine provenance without strategy changes. | telemetry |  | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 2.9 |  |
| tilt_divergence | Tilt pid 격리 수정의 divergence 측정 드라이버 (읽기 전용). | tilt/emotion |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 | CLI driver: requires a command argument |
| tilt_isolation | Tilt 상태의 소유 단위를 좌석에서 사람(pid)으로 바꾼 변경의 검증. | tilt/emotion |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 | CLI driver: requires --mode |
| tournament_telemetry | End-to-end verification for whole-tournament telemetry. | telemetry |  | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 8.1 |  |
| trace_schema | 결정 기록 스키마 계약 검사 (A7). 읽기 전용. | telemetry |  |  |  | PASS | PASS | pass | 8.5 | environment-dependent: repo archive invariants; PASS in a clean worktree |
| ui_tournament_panel | UI tournament-info / standings drawer wiring checks. | UI |  |  |  | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 |  |
| uncalled_excess | Targeted verification for contestable-pot / uncalled-excess semantics. | betting rules/pot |  | Y | PASS | PASS | PASS | pass | 0.0 |  |
| weighted_aggregate_transform | W2/W3 weighted aggregates + transforms. | weighted range |  | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.1 |  |
| weighted_boundaries | W4 weighted range boundaries/signatures/provenance gate. | weighted range | Y | Y | FAIL | FAIL | FAIL | historical (same status on pristine HEAD) | 0.0 |  |
| weighted_range_adapter | W0 weighted-range representation / legacy-adapter contract. | weighted range | Y | Y | PASS | PASS | PASS | pass | 0.0 |  |
| weighted_sampling | W1 weighted sampling consumers: exact legacy parity + weighted direction. | weighted range |  | Y | PASS | PASS | PASS | pass | 0.1 |  |
