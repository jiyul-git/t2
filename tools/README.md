# tools/ — classification

도구 파일이 많기 때문에 이름만 보고 현재 작업이라고 판단하지 않는다.

## 1. CURRENT — 지금 진행 중

F7-B1D empty/partial opponent-range audit:

- `measure_f7b_partial_pools.py`
- `measure_f7b_empty_hu_range.py`
- `measure_f7b_empty_hu_pipeline.py`
- `measure_f7b_empty_range_overlap_candidate.py`

현재 단계의 결과는 `F7B_MULTIWAY_DOWNSTREAM_AUDIT.md`와 `CURRENT_STATUS.md`에 기록한다.

## 2. ACTIVE VERIFIERS — 현재 production 보호용

핵심:

- `regress.py`
- `audit_f7b_multiway.py`
- `verify_f7b_blocker_activation.py`
- `verify_preflop_closure.py`
- `verify_f1_free_action.py` ~ `verify_f7_street_closure.py`
- `audit_f8_sidepot.py`
- `verify_ui.py`는 `ui/tools/`에 있음

`baseline_9max*.json`은 동결 증거다. 기존 baseline을 새 행동에 맞춰 덮어쓰지 않는다.

## 3. HISTORICAL DIAGNOSTICS — 완료된 감사의 증거

예:

- `measure_f7b_blocker_*.py`
- `measure_f7b_joint_rel.py`
- `measure_f7b_range_nut.py`
- `attribute_f7b_*.py`
- `cf_*.py`
- 과거 money / axis / replan 측정 도구

삭제하지 않는 이유는 이미 내린 구조 판정의 재현 증거이기 때문이다. **현재 단계에서 임의 실행하지 않는다.**

## 4. Naming rule for new tools

- `verify_*.py` — pass/fail 계약 검증
- `measure_*.py` — production 무변경 관측/계측
- `attribute_*.py` — 행동 변화의 직접 귀속
- `cf_*.py` — 반사실 실험
- `*_audit.py` — 넓은 구조 감사

새 임시 root-level `tools_*.py`는 만들지 않는다. 새 도구는 모두 `tools/`에 둔다.

## 5. Legacy/dead code

`AUDIT_LEDGER.md`에서 `CLEANUP_LATER` 또는 dead로 판정된 코드/도구는 최종 구조 감사 후 제거한다.
지금은 이름을 보고 production 코드로 사용하지 않는다.
