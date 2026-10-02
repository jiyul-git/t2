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
