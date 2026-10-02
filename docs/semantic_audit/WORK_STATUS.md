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
