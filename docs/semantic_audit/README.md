# T2 semantic audit

- [작업 진행 기록](WORK_STATUS.md) — 감사 브랜치·체크포인트·남은 작업
- [기존 개념의 구조 비교](STRUCTURAL_CONCEPT_REVIEW.md) — 재레이즈 외 판단 구조의 공통점과 차이

감사 기준 test `4b9d33d5f951fce4b292f6e6e79caaf141b106d2`. 전략 튜닝/merge/master promotion 없음.

- [CURRENT_ARCHITECTURE_AUDIT](CURRENT_ARCHITECTURE_AUDIT.md)
- [CONCEPT_FUNCTION_REGISTRY](CONCEPT_FUNCTION_REGISTRY.md) — 227행; 전체 세부사항 [CSV](CONCEPT_FUNCTION_REGISTRY.csv), [JSON](CONCEPT_FUNCTION_REGISTRY.json)
- [STREET_SEMANTIC_MATRIX](STREET_SEMANTIC_MATRIX.md)
- [DUPLICATION_AND_OVERLOAD_LEDGER](DUPLICATION_AND_OVERLOAD_LEDGER.md)
- [DOCUMENT_DRIFT](DOCUMENT_DRIFT.md)
- [KNOWLEDGE_COVERAGE_MATRIX](KNOWLEDGE_COVERAGE_MATRIX.md)

SOURCE_MANIFEST / FUNCTION_CALL_CENSUS는 수정 전 코드 증거다. 실행 결과 및 실제 추출 내역은 REFACTOR_AND_VERIFICATION에 추가한다.

- [REFACTOR_AND_VERIFICATION](REFACTOR_AND_VERIFICATION.md) — 실제 함수 추출 및 before/after 검증

- [range_read 소비 경계](RANGE_READ_CONSUMER_BOUNDARIES.md) — 복원·해석·판단 적용 및 남은 소비처

- [재감사 completeness 보고](completeness/COMPLETENESS_REPORT.md) — 검색 방법, 신규 66행, 정정, 추출, 한계
- [CANONICAL_VERIFIER_MANIFEST](CANONICAL_VERIFIER_MANIFEST.md) — 검증 스크립트 71개의 목적·소속·기대 상태·실행 시점
- 코드 위치 소유 맵: [completeness/SPAN_MAP.json](completeness/SPAN_MAP.json) (생성: `completeness/supplement.py`, 검사: `tools/check_semantic_completeness.py`)

R2 (pf_rank/PCT 용도 + 9-max 디펜스 지식, 첫 보고 — production 변경 없음):
- [R2_BEFORE_BASELINE](r2/R2_BEFORE_BASELINE.md) — 46a2070 행동 봉인과 재현 방법
- [A. PCT_CONSUMER_AUDIT](r2/PCT_CONSUMER_AUDIT.md) — 소비처 22개, 질문·현재 양·필요 양·판정, 순서 재현율 측정
- [B. 9MAX_DEFEND_BASELINE_TABLE](r2/9MAX_DEFEND_BASELINE_TABLE.md) — 현재 코드가 내는 9-max 디펜스 값(prior/문턱/실현)
- [C. 9MAX_DEFEND_REFERENCE_COMPARISON](r2/9MAX_DEFEND_REFERENCE_COMPARISON.md) — 근거 자료·신뢰도·차이·판정, 그림 [defend_vs_reference.png](r2/defend_vs_reference.png)
- [R2-B 9-max defend prior 출처·검증 상태](r2/9MAX_DEFEND_PRIOR_PROVENANCE.md) — 값별 출처, 완료된 GTO DB spot 비교, MISSING_KNOWLEDGE 목록
- [D. R2_CHANGE_PLAN](r2/R2_CHANGE_PLAN.md) — 미적용 변경 계획(승인 대기)

R2 다음 단계 (판단량 분리 — 행동 변경 없음):
- [A. R2_QUANTITY_SEPARATION](r2/R2_QUANTITY_SEPARATION.md) — 소비처별 ordering/equity/EV/FE/solver prior, 리쇼브·3벳·4벳 층 분리
- [B. CALLOFF_PATH_AUDIT](r2/CALLOFF_PATH_AUDIT.md) — 올인 대면 콜 경로 7개, 완료된 9-max push/fold DB 대비 측정
- [C. PREFLOP_ORDERING_DUPLICATION](r2/PREFLOP_ORDERING_DUPLICATION.md) — PCT vs bot._pf_score
- [D. R2_IMPLEMENTATION_PLAN](r2/R2_IMPLEMENTATION_PLAN.md) — 구조 분리 / DB 근거 수정안 / 보류
