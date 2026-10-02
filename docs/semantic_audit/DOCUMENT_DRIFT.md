# DOCUMENT_DRIFT

10 canonical 문서를 모두 읽고 실제 test code와 비교했다. MATCH 행도 남겨 검토 누락과 구분한다. 이 표는 감사 기준 checkpoint의 불일치이며 후속 문서 동기화 뒤에도 증거로 보존한다. 문서가 이상적 불변식을 선언한 경우 코드를 옳다고 바꾸어 합리화하지 않는다.

| 문서/항목 | 문서상 설계 | 실제 코드/검증 | 판정 | 처리 |
| --- | --- | --- | --- | --- |
| PROJECT.md | master ancestor, exactly 5 branches | remote diverged 544/8; 6 branches incl terminal-census | STALE | Git 상태를 현재 checkpoint와 날짜로 명시 |
| PROJECT.md | test 고정 HEAD/현재 회귀 checkpoint | test 4b9d33d; current baseline six seeds mismatch before edits | STALE | 역사 baseline과 현재 행동 구분 |
| PROJECT.md | P7/nut/representative/sizing/W5 open 목록 | 일부 dedicated active producers 이미 존재 | STALE | 부분 완료 및 남은 경계 구분 |
| DECISION_SYSTEM.md §6/8 | P7 observation 없음 또는 generic 경로 | cold_reraise context/decision/Book counters/estimates 존재 | STALE | core+observation 배선 현재 상태 표시 |
| DECISION_SYSTEM.md §12 | 존재하지 않는 _postflop_response_context, runner sizing ownership | action_events.response_context, PLAN shape_planned_target | STALE | 실제 함수명으로 교체 |
| DECISION_SYSTEM.md emotion | tilt는 사실 판단에 침투하지 않음 | Hand.axes tilted_view가 make_plan/calc/perception으로 전달 | CODE DESIGN VIOLATION | view API 존재와 routing 미완료 구분; 후속 |
| DECISION_SYSTEM.md ACTION | ACTION은 합법성/rounding만 | act_with_plan 계산/response/raise 판단; effective_allin 정책 | ARCH_MISMATCH | 실제 혼합층 명시; 전략 수정 분리 |
| DECISION_SYSTEM.md later streets | 새 카드와 기존 story 재평가 | river turn_card_effect는 flop slice와 river card 사용 | CODE DESIGN VIOLATION | 후속 semantic-fix |
| CONCEPT_SYSTEM.md latent | latent 생성 전용 | plan.trap_judgment가 latent.study runtime 소비 | CODE DESIGN VIOLATION | 문서를 실제로 표시하고 후속 분리 |
| CONCEPT_SYSTEM.md labels | type은 표시용 | persona.sizing_signature → shape_size active | STALE | display label의 sizing dependence 명시 |
| CONCEPT_SYSTEM.md §5 | thin_value_turn flop fallback | street_concept thin_value flop은 range_merge | STALE | 현재 mapping과 남은 overload 수정 |
| CONCEPT_SYSTEM.md 37 concepts | 전략 concept 목록 | 독립 poker semantic은 37보다 큼 | INCOMPLETE INVENTORY | 225행 registry를 보조 canonical 지도에 연결 |
| CONCEPT_SYSTEM.md v2/v3 | opt-in flags, 미활성 | default OFF 확인; baseline formula remains | MATCH | 역사 실험값은 현재전략 인증으로 쓰지 않음 |
| RANGE_MODEL.md W5 | weighted logic NOT STARTED | defend likelihood weights, reraise posterior ACTIVE | STALE | 표현층 migration과 active likelihood 구현 구분 |
| RANGE_MODEL.md nut OPEN | joint nut core 미완료 인상 | joint_nut_advantage active; semantics strong-region proxy | STALE / NAMING | 배선 완료와 literal nuts 정의 미완료 구분 |
| RANGE_MODEL.md representative | main aggressor/deepest만 | purpose-specific fold/trap selectors active; legacy 대표도 남음 | STALE / PARTIAL | consumer별 판정 |
| RANGE_MODEL.md missing pools | seat fabricate 금지 | complete joint path guarded; legacy _normalize uses fallback .35 | PARTIAL CONTRACT | fallback을 별도 표시; 잠재정보 입력 개선 후속 |
| POT_ALLIN_MODEL.md F8 foundation | geometry/equity shadow 중심 | closing call/pure calloff/river veto ACTIVE | STALE | 부분 active 경계와 일반 tree 미완료 |
| POT_ALLIN_MODEL.md effective-allin | active v1; leave-behind disabled | 같은 조건 및 활성/비활성 확인 | MATCH | threshold 변경 없음 |
| MONEY_JUMP_MODEL.md | unopened range active; size/limp shadow | range_factor consumer active, other outputs shadow | MATCH | 새 튜닝 없음 |
| MONEY_JUMP_MODEL.md Phase C | INCONCLUSIVE historical | 실험은 현재 proof가 아님; outcome 그대로 보존 | MATCH | 기록 수정/재해석 금지 |
| TOURNAMENT_RUNTIME.md memory | 대회 단위 관측 연속성 기대 | hero Book persists; bot-only play.Hand has new Book each hand | CODE GAP | 경계 명시 및 후속 |
| TOURNAMENT_RUNTIME.md physical runtime | 9max TDA/parallel snapshot | live2/fieldsim 실제 연결; regress는 tourney alternate | MATCH / TEST GAP | 검증 런타임 구분 |
| TOURNAMENT_RUNTIME.md runnable copy | setup scripts standalone runtime 구성 | Python telemetry_sync 누락; both action_events 누락 | PACKAGING DESIGN VIOLATION | 기존 producer module 복사 목록 동기화 |
| TOURNAMENT_RUNTIME.md blind format | blind_mult 구조효과 | fieldsim.blinds는 고정 BLINDS, erosion은 mult사용 | PARTIAL SEMANTICS | 실제 blind growth vs perceived erosion 구분 |
| PERSONA_RESEARCH.md | historical experiment evidence | 현재 flag default/commit과 다를 수 있음; 역사 문서라고 명시 | MATCH | 현행 wiring 표로 사용하지 않음 |
| CF_RESEARCH.md | historical CF scope / inconclusive boundaries | 현재 production 연결과 독립한 실험 결과 | MATCH | 현행 registry 링크만 추가 |
| DIAGNOSTICS_HISTORY.md | R3 next; R5b/c revise_plan location | R3 blocker batch1 HEAD active; transitions mostly refresh | STALE | 현재 checkpoint와 함수 명칭 보완 |
| 10 canonical docs 공통 | 독립적 human/solver 지식 공급 설계 | test has authored priors/heuristics; external empirical solver loader absent | IMPLEMENTATION GAP | coverage에서 provenance 검증 여부 분리 |
| context.py SPEC 주석 | money_jump judgment unused | preflop range modifier active | STALE COMMENT | 현재 usage 주석 동기화 |

## 재감사(2026-10-02) 추가

| 문서 | 기록 | 코드 실제 | 판정 |
| --- | --- | --- | --- |
| CONCEPT_FUNCTION_REGISTRY `called_aggression_ownership` | "직전 스트리트 자신의 공격이 콜받은 라인인가", turn/river | 내가 상대 공격을 **콜했는가**; batch 1부터 플랍(프리플랍 어그레서) 포함 | registry stale → 정정 |
| 직전 진행 보고 (range_read) | perceived_edge는 baseline 영향 없음 | `preflop.feel_of` 경유로 baseline 활성(작음) | 보고 오류 → RANGE_READ 5차에 정정 |
| DECISION_SYSTEM P7 행 | players-behind, skill-dependent reasoning | batch 1 이후 올인 상대 가격 게이트와 공격 근거(읽기/블로커)가 추가됨 | 문서 stale → P7 행 갱신 |
| plan.refresh 주석 | "made 항은 죽어 있다" | 항은 audit9에서 제거됨 | 코드 주석 stale → 수정(동작 무관) |
| KNOWLEDGE_COVERAGE vs-open/3bet | GTO prior authored width | 9-max는 MTT8 보정 표를 쓰지 않음 | 문서 불완전 → 보정 섹션 추가 |
