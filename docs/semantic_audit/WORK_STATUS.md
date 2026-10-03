# 감사 작업 진행 기록

## 작업선

- 감사 전용 브랜치: `chatgpt/semantic-audit-20261002`
- 시작 기준: `test` = `4b9d33d5f951fce4b292f6e6e79caaf141b106d2`
- 확인한 `master`: `8614f32d2293ddcc7442447fe569b87ab105c6ea`
- master/test에는 이번 결과를 반영하지 않았다. 앞으로 완료 단위마다 이 감사 브랜치에 checkpoint를 남긴다.

## 완료 체크포인트

| 단계 | 상태 | 증거 |
| --- | --- | --- |
| Git·canonical 10문서·코드 경로 감사 | 완료, 알려진 한계는 보고서 참조 | CURRENT_ARCHITECTURE_AUDIT, DOCUMENT_DRIFT |
| 명시/암묵 개념 inventory | 227행 기록 | CONCEPT_FUNCTION_REGISTRY CSV/JSON |
| street/중복/지식 연결 감사 | 기록 완료; 모든 구조 문제 해결을 뜻하지 않음 | STREET_SEMANTIC_MATRIX, DUPLICATION_AND_OVERLOAD_LEDGER, KNOWLEDGE_COVERAGE_MATRIX |
| 행동 보존 함수 추출 | 제한된 범위 완료 | REFACTOR_AND_VERIFICATION |
| before/after 검증 | 기존 증거 보존 | 4,638 targeted 비교, 6 seeds action/RNG 일치, live2 smoke 일치 |
| 원격 보존 checkpoint 1 | 완료 `968f10ef0c268997463b93b6fdb83abdfa454c45` | remote tree = local tree `339c490f56694fbec80411b368d9ae6f9e5a3e35` |
| 기존 개념 구조 비교 추가 검토 | 이 checkpoint에서 문서화 | STRUCTURAL_CONCEPT_REVIEW |

## 미해결·다음 작업 경계

- 기존 verifier 결과: 26 PASS / 12 FAIL / 2 TIMEOUT. 실패 수정 및 장기 suite 통과를 주장하지 않는다.
- PCT 역할 분리, range_read 독립 능력, danger 계약, river board 전이, remaining-street 투자 계획, 기억 지속·공개패 관측 등은 ledger의 후속 semantic-fix다.
- 수치·확률·RNG·행동이 바뀌는 수정은 현재 semantic-only 작업에 포함하지 않는다.
- 추가 코드 정리가 필요하면 먼저 ledger 항목과 보존할 계약을 지정하고, 작은 단위로 검증한 뒤 checkpoint한다.
- 현재 실행 중인 장기 검증 작업은 없다. 이 파일은 자동 백그라운드 실행을 의미하지 않는다.

## 업로드 장애 처리

이전 tree 불일치의 최초 원인은 확정하지 않았다. 로컬 파일 바이트를 base64 blob으로 다시 올리고, 54개 변경 경로의 원래 mode/SHA와 baseline tree로 새 tree를 구성해 로컬 tree와 정확히 일치함을 확인했다. API 커밋은 로컬 최초 커밋 `804a7a4`와 메타데이터가 달라 SHA가 다르지만 파일 tree는 동일하다. 로컬 감사 브랜치도 원격 checkpoint로 정렬했다.

사용자 보고 원칙: 작업 중 1분 이내 간격으로 완료 항목·막힌 지점·다음 조치를 알리고, 완료 단위마다 이 기록과 원격 checkpoint를 갱신한다.

## 2차 코드 정리 — defend 계산 경계

- 기준 checkpoint: `6feaf56`.
- 완료: prior 정규화·콜러 문맥·짧은 스택·상위 재레이즈 축소를 4개 함수로 추출. `defend_thresholds`는 actor/observer 공통 producer로 유지.
- 직접 비교: threshold 3,600 / likelihood 384 / action+RNG 768건 일치. V3 reasoning OFF/ON 포함.
- 기존 semantic cleanup verifier: 4,638 비교 PASS.
- 4bet 독립 prior, 공유 scalar, 기존 verifier 실패에 대한 수정은 포함하지 않는다.

- 전체 핸드 검증 완료: 6 seeds × 30 hands, stage1 after와 action/RNG 포함 전체 JSON 6/6 일치. evidence/defend_stage2_parity.json 참조.
- 다음 후보: range_read의 인지 역할별 소비 경계. 기존 scalar를 유지하는 함수 추출과 행동을 바꾸는 독립 skill 도입을 구분할 것.

## 3차 코드 정리 — range_read 소비 경계 완료

- 기준 `33df2ee`. 복원·액션 해석·판단 적용 본문과 명시 입력을 분리했다. 세 독립 skill을 생성하지 않았다.
- 직접 비교 1,308건 + 경계 검사 4건 PASS. 기존 verifier 4,638건 및 4,752건 PASS.
- 6 seeds / 180 hands action·RNG 포함 전체 결과 일치. 원시 JSON과 검사 스크립트 보존.
- 신규 함수 연결은 registry current_function 및 RANGE_READ_CONSUMER_BOUNDARIES에 기록했다. 총 227개 상위 의미 단위 수는 바꾸지 않았다.
- 다음 작업: range_read의 남은 multiway/pressure 적용 consumer와 관측 품질 경계를 검토. 공유 값을 새로운 독립 skill로 바꾸거나 레이즈 확률에 새 multiplier를 넣는 것은 별도 전략 변경이다.
- 현재 장기 검증 실행은 종료됐다. master/test 반영 없음.

## 4차 코드 정리 — 관측·멀티웨이·압박 소비 경계

- 기준 `b486969`. 관측 정확도, pressure application capacity, multiway evidence capacity, call/fold evidence 적용의 네 계산을 명시 입력 함수로 추출했다.
- 직접 비교: 관측 30 / pressure 256 / controlled equity multiway 72 / 실제 equity multiway 4 = 362건 PASS. 경계 검사 5건 PASS.
- 이전 verifier: range_read 1,308건 + 경계 4건, defend 4,752건, semantic 4,638건 PASS.
- 의미별 함수·입력·consumer는 registry current_function 및 RANGE_READ_CONSUMER_BOUNDARIES의 4차 항목에 기록했다.
- 독립 skill 도입은 하지 않았다. 자기 패 과신·자기 실력 인식·line visibility·생성/진단 경로는 계속 별도 역할로 추적한다.

- 전체 검증 완료: 6 seeds / 180 hands, 직전 stage3의 전체 action/statistics/RNG JSON 6/6 동일. 실행 중인 검증 작업 없음.
- 다음 검토 대상: range_read의 자기 패 과신·자기 실력 인식 및 line visibility 경계, 이후 street별 의미 과적재 ledger 항목.

## 5차 — 재감사 completeness (Claude, test `63bd82d` 기준)

- 기존 227행을 코드 전체와 기계적으로 대조: 결정 지점 1,136 / 함수 548 / 모듈 상수 표 84 / 등록부 참조 전부를 개념 또는 사유 있는 non-semantic 구간에 소유시킴. 미소유 0 (`tools/check_semantic_completeness.py`).
- 신규 66행(origin `IMPLICIT_CODE_V2`, parent_concept·code_span 포함), 기존 3행 정정(called_aggression_ownership 의미 반전 등), ledger L-RA01~18, street matrix·knowledge coverage·document drift·range_read 5차 갱신.
- semantic-only 추출 3건(players-behind premium 단일 producer, has_showdown_value, line_owned_by_live_aggressor): parity probe·sim 바이트 동일·23-gate 동일.
- 검증 체계: `CANONICAL_VERIFIER_MANIFEST` (71개, 23-gate/40-suite 소속, pristine HEAD 대비 상태).
- 다음(사용자 지정 순서): R2 pf_rank/PCT 지식 정확성 감사 → R1b 플랍 raise-range 지식 → OOP 체크레이즈 후속 행동.

## R2 첫 보고 — pf_rank/PCT 용도(R2-A) + 9-max 디펜스 지식(R2-B) (Claude, test `46a2070` 기준)

- production 계수·표·문턱·액션 변경 없음. 추가는 읽기 전용 측정 도구 `tools/r2_*.py` 와 `docs/semantic_audit/r2/` 문서뿐.
- 46a2070 행동을 R2 before baseline 으로 봉인(`r2/R2_BEFORE_BASELINE.md`).
- 핵심: 9-max 조건 일치 solver 자료가 저장소·공개 자료 모두에 없다 → 9-max 값은 NEEDS_SOLVER_DATA. 자료 없이 확인된 코드 내부 결함 3개(짧은 스택 이중 적용, saturate 증폭, prior→3벳 실현 손실), vs-3bet 지식 부재(오프너 계속률 7~25% vs 기준 43~89%).
- 다음: 사용자 승인 대기(9-max 자료 출처 결정, R2-B2/B4 진행 여부).

### R2-B 정정 — 출처·검증 상태 감사 (사용자 지시 2026-10-02)

- 수치 변경 없음. 미완성 자체 solver 는 기준으로 쓰지 않는다. 비교는 계산이 끝난 GTO DB spot 이나 신뢰할 수 있는 공개 자료로만 한다. 자료가 없으면 MISSING_KNOWLEDGE.
- 정정: 첫 보고의 "9-max GTO DB 없음"은 test 만 검색한 결과였다. `chatgpt/gto-reference-20260928:data/gto_db/` 에 9-max push/fold(HoldemMath) 616 spot 과 RFI 공개 집계가 있다. 올인 아닌 디펜스 spot 은 없다.
- 결과(`r2/9MAX_DEFEND_PRIOR_PROVENANCE.md`):
  - legacy 9-max 디펜스 값(DEF_A/B, DEF_SEAT, TB_SHARE, DEF_VS_SB, MDF 표)은 출처 미상이다.
  - 쇼브 대면 콜 폭(calloff_cap)은 DB 144 spot 대비 평균 0.17~0.33 좁다.
  - 디펜스 식의 입력인 9-max RFI 는 비블라인드 25/28칸이 ±0.024 안이다.

### R2 판단량 분리 보고 (test `d284a9e` 기준, 행동 변경 없음)

- 콜오프:
  - max-skill 순수 콜오프는 legacy cap 을 우회한다(42건 중 45%가 legacy 와 다른 행동).
  - legacy cap 이 행동을 직접 정하는 곳: near-all-in, 낮은 숙련 fallback, 쇼브 콜러 레인지 복원.
  - 가장 큰 경로(쇼브 대면, 뒤 좌석 있음, 102/182건)는 vs-open 디펜스 폭으로 판단한다(가격 무관).
- DB(9-max push/fold) 대비 콜 판단 일치율:
  - legacy 0.78
  - DB 쇼브 레인지 대비 equity·가격 0.94
  - 현재 T2 방식 0.77. 첫 진입 쇼브를 오픈 레인지로 복원하는 것이 원인이다.
- 쇼브에 콜한 깊은 스택의 복원 레인지에서 AA/KK 가 약 10%만 남는다.
- 두 순서표는 같은 질문이다(상위 35% 94% 일치). 통합은 보류.
- 다음: 사용자 승인 대기(S1~S5 구조 분리, C1~C6 콜오프 수정안, DB 파일을 test 로 가져올지).

## 9단계 재개 — semantic-only refactor (R2 행동 수정은 정지)

- 원 계획 순서로 복귀: 재감사(0~8) 완료 → **9단계 semantic-only refactor** → 10단계 최종 regression → 11단계 문서 동기화 → 이후 R2/R1b/OOP.
- 잔여 분류 `stage9/STAGE9_TRIAGE.md`: ledger 149 항목 중 DONE 14 / PARTIAL 5 / NOW 83 / LATER 18 / KEEP 29. batch B1~B6.
- **B1 (preflop) 완료.**
  - 18개 처리, 2개 재분류(L049 → LATER, L071 → KEEP).
  - 행동 동일성: probe 6,460건, 뮤테이션 13/13, 봉인 sim 지문 동일, 23-gate 동일, completeness 0.
  - 새 ledger 항목 L-S9-01(가려진 조건).
- 다음: B2(ranges/reads). B1 이 push 로 봉인된 뒤 시작한다.
- **B2 (ranges/reads) 완료.**
  - DONE 7, KEEP 1(L047 — 재생 중 누적 수와 결정 시점 전체 수는 시간 기준이 다름).
  - 행동 동일성: probe 6,200건(+B1 probe 재통과), 뮤테이션 11/11, 봉인 sim 지문 동일, 23-gate 동일, completeness 0.
  - 기록: L-S9-02(복원 레인지에 hero 카드 콤보가 남음 — blocker_score 계약).
- 다음: B3(plan 포스트플랍). 사용자 지시 전에는 시작하지 않는다.
- **B3 구조분리(행동 보존) 기준점 완료.**
  - 24개 + L149 를 함수 경계로 분리했다.
  - 행동 동일성: probe 12개 구역(경계 sweep 포함), 뮤테이션 40/40, 봉인 sim 지문 동일, 23-gate 동일, completeness 0.
  - L-S9-02 추적: 실제 왜곡은 `_nonvalue_raise_ev_gate` 의 fold_p 한 곳이다(219회 중 2회 판정 뒤집힘). 후속 L-S9-02a~08.
- **목적 변경(사용자 결정):** B3~B6 는 감사와 동시에 본체 / Human Model 2차 / 3차를 하나의 최종 실행 경로로 통합한다.
  - 충돌은 미루지 않는다. R2 의 미검증 9-max 수치 금지는 유지한다.
  - 2차/3차는 이름이 아니라 실제 도입 commit 과 플래그로 식별한다.
    - 2차: `T2_GTO_MEMORY_V2`(22487e9f)
    - 3차: `T2_PREFLOP_REASONING_V3`, `T2_EXPLOIT_WEIGHT_V3`, `T2_CALC_NOISE_V3`, `T2_PREFLOP_TEMPER_DIRECTION_V3`, `T2_READ_RECENCY_V3`(114c846f 이후)
- 다음: B3 통합 — L-S9-02a~07 판정과 B3 범위 플래그 경로(`plan.trap_judgment` 의 EXPLOIT_WEIGHT_V3).
- **B3 통합 완료.**
  - 판정 8건: L-S9-02a, 03(이진/연속), 04, 05, 06(현 경계 확정), 07, HM3 EXPLOIT_WEIGHT_V3(trap) — 미결정 0.
  - 새 baseline: 시드 11 `e6d8b5e5…`, 시드 12 `8c33ece5…`.
- 다음: B4(persona/concept 역할) — GTO_MEMORY_V2, PREFLOP_TEMPER_DIRECTION_V3, CALC_NOISE_V3, PREFLOP_REASONING_V3(persona 쪽)의 판정과 통합.
- **B4 통합 완료.**
  - 판정 4건(L148 이중 편향, L008/L009 hero_call 방향, CALC_NOISE_V3, PREFLOP_TEMPER_DIRECTION_V3).
  - 개념 역할 항목 16개 확인(같은 질문 → 단일 공급자). 미결정 0.
  - GTO_MEMORY_V2 / PREFLOP_REASONING_V3 는 9-max 근거가 필요해 마지막 B1/B2 통합으로 넘겼다(사용자 지시).
  - 새 baseline: 시드 11 `7ce1561d…`, 시드 12 `ef73996c…`.
- 다음: B5(호환 / 이름 / 옛 경로 제거).

## 안테 규칙 변경과 새 기준선 (B5 이전)

- 사용자 결정: BB 안테(BB 가 블라인드 1bb + 안테 1bb)를 **참가 인원 균등 분담 안테**로 바꿨다. BB 는 블라인드 1bb 만 내고, 안테 1bb 는 SB·BB 를 포함한 전원이 나눠 낸다. SB 0.5bb 는 그대로다.
  - `d65a960f`: 균등 분담 도입.
  - `58900603`: 게시 순서를 GTO 검증기와 같게 통일. 안테 → SB → BB 이고, 블라인드는 안테를 낸 뒤의 스택에서 낸다.
  - 정본 함수 `runner.post_forced_bets` 하나를 엔진(`session.HandRun`)과 화면 재생(`live2._opening_raw`)이 같이 쓴다. UI 애니메이션 순서도 같다.
  - 정수 칩이라 `ante // n` 씩 내고, 나머지는 프리플랍 순서 앞자리부터 1칩씩 더 낸다. GTO 의 정확한 1/n 과 좌석당 최대 1칩 차이가 있고, 총액은 같다.
- 검증기 `tools/verify_uniform_ante.py` (6/6 통과):
  - 5~9인 분담 산수
  - 짧은 블라인드(BB 1.05bb → 안테 33, BB 282 올인)
  - 몫보다 짧은 스택
  - 안테 없는 레벨
  - 단일 함수 사용
  - 실제 엔진 2~9인 테이블 78회 게시: 오류 0, 칩 보존
- **새 기준선(B5 이전, clean `58900603`)**:
  - 시드 11 `b6425e83…`(581핸드, 오류 0), 시드 12 `a769e1e0…`(579핸드, 오류 0)
  - 23-gate 통과·실패 집합(17/6)과 출력 줄이 기준과 같다
  - 같은 시드를 다시 돌려도 지문이 같다(재현성)
  - B4 기준선(`7ce1561d…` / `ef73996c…`)과의 차이는 안테 납부자와 스택이 바뀐 데서 오는 **의도된 의미 변화**다. 이전 지문과 같을 것을 요구하지 않는다.
- B5 stash 로 B5 코드가 메모리에 올라간 채 돌던 시뮬/게이트 결과는 폐기했다.
- 다음: B5 stash 복원 → 같은 검증 → 이 기준선 대비 B5 차이만 측정 → B5 커밋 → B6.
- **B5 통합 완료.**
  - 호환 / 옛 경로 / 이름 정리 10건(ledger "9단계 B5 통합").
  - clean 안테 기준선 대비 행동 차이 0: 지문 동일, 23-gate 동일.
- 다음: B6(bot / texture / depth).
- **B6 통합 완료.**
  - 리버 새 카드 효과가 턴 카드를 포함하도록 했다(L-RA07).
  - danger 기록의 의미를 통일했다(L-RA06).
  - board_texture 정규화를 하나로 통일했다(L027).
  - depth / texture sizing 은 현 구조가 최종이다.
  - 새 baseline: 시드 11 `b6425e83…`, 시드 12 `b09618b3…`.
- B1/B2 closeout 은 두 그룹으로 나눴다(사용자 결정).
- **그룹 A(GTO 비의존) 완료.**
  - A1 READ_RECENCY_V3 → 최근 창 유일 경로.
  - A2 3벳 형질 숙련 입력 bluff → pf_defend.
  - A3 fallback 순서표를 PCT 로 통합.
  - B6 기준선 대비 지문 동일. 23-gate 집합 동일(f3 출력 한 줄만 의도된 변화).
- **그룹 B(GTO 의존) 보류: BLOCKED_BY_GTO_REFERENCE_VALIDATION.**
  - GTO_MEMORY_V2 / PREFLOP_REASONING_V3 는 production OFF 유지.
  - GTO continuation S pilot 이후 corrected 9-max reference 가 검증되면 재판정한다. Stage 9 범위 밖이다.
- 그룹 A 봉인: `tools/verify_closeout_a.py` 9/9(A2 proxy 계약, A3 클래스 경계 floor 계약). 문구 정정 반영.
- **Stage 9 완료.** GTO 의존 두 플래그는 별도 blocker 로 남긴다.
- 다음: Stage 10 final regression. 23-gate 의 기존 실패 6개를 하나씩 판정한다(stale test 인지 실제 결함인지).
- **Stage 10 완료.**
  - 23-gate 실패 6개 + 비게이트 2개를 하나씩 판정했다.
    - 7개: stale test(의도된 코드 변경 뒤 갱신 안 됨).
    - f3: stale test + 실제 잠재 결함. 사이즈 습관 RNG 가 seed 없이 비결정적이었다. 코드 수정(production 경로 불변).
  - 회귀 중 드러난 2개: HM2 IDENT stale pin → 재고정. completeness span 누락 → span 추가.
  - 전체 회귀: 시드 11 `b6425e83…`, 시드 12 `b09618b3…`(B6 기준선과 동일), 23-gate 23/23, 추가 검증기 rc=0, completeness 미소유 0.
- 다음: Stage 11 문서 동기화(전체 tier-all 검증기 실행으로 verifier manifest 재생성 포함).
