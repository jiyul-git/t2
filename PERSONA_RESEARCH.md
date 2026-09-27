# PERSONA / AXIS / PRIOR RESEARCH — consolidated history

이 문서는 personality axis와 concept prior를 검증하던 연구 흐름의 최종 결론을 보존한다. 현재 production source of truth가 아니라 calibration 근거다.

## 1. 연구 원칙

과거 반복된 오류 때문에 순서를 고정했다:
1. code path 추적
2. metric 정의
3. 측정 조건 calibration
4. sample size preregistration
5. 본 측정
6. split-half / permutation / control
7. counterfactual로 causal layer 확인

단순 상관을 “축이 검증됐다”로 읽지 않는다.

## 2. Main observational fixture

기본 조건:
- entries 24
- hpl 12
- start stack 30,000
- 본 측정 seed 55개
- eligible 기본 기준 >=3

`hpl=12`은 정의된 format 영역과 교란 최소화를 고려해 채택.
시드 수는 결과를 본 뒤 늘리지 않고 power 설계로 고정.

## 3. Axis measurement conclusion

본 측정의 정확한 결론:
> 사전 정의한 7개 행동 연관 가설 모두가 본 측정에서 재현 가능한 방향성을 보였다.

이것은 “7개 concept/axis가 독립적·인과적으로 검증됨”을 뜻하지 않는다.

과정에서 수정한 대표 측정 오류:
- profile identity 추적 실패
- 서로 다른 모집단에서 correlation/r 계산
- denominator mismatch
- degenerate derived metric
- split-half statistic 정의 오류
- inventory eligibility mismatch

## 4. Accuracy/frequency findings

- perception accuracy 축은 action flip만으로 평가하면 안 됨.
- `sizing_tell`은 초기 구현에서 실제 size 읽기보다 overwrite gate처럼 작동했던 역사적 문제가 있었음.
- frequency axis는 domain 밖에서는 구조적으로 무반응.
- `potcontrol`은 단순 빈도 scalar보다 switch/gate 성격.
- `aggression` 등 일부 축은 plan/execution 여러 층에 걸쳐 있어 layer별 측정 필요.

## 5. Concept prior audit

Realized distribution은 nominal base/spread의 직접 복사본이 아니다.

영향:
- latent loadings
- clamping
- overall-skill rejection
- generator correlation

따라서 calibration은 **realized distribution**을 대상으로 해야 한다.

Sensitivity audit:
- base perturbation이 realized median에 미치는 local slope를 측정.
- spread가 width를 늘리는지 clamp saturation만 늘리는지 분리.
- 이 audit 자체는 새 production prior를 선택하지 않았다.

## 6. Calibration blocker

Concept taxonomy가 아직 완전히 고정되지 않았다.
특히 street concept granularity가 열린 상태이므로 LOADING/SPREAD global calibration은 보류.

현재 관련 기준은 `CONCEPT_SYSTEM.md`.

## 7. Counterfactual link

Observational result의 인과 해석은 별도 CF 실험으로 이동했다.
세부는 `CF_RESEARCH.md`.

## 8. Historical sources

- `ANALYSIS_PLAN.md`
- `AXIS_INVENTORY.md`
- `AXIS_FREQ_PLAN.md`
- `CALIB_COND.md`
- `F_TRACE_RESULT.md`
- `OBS_AXIS_PLAN.md`
- `RESULT_AXIS.md`
- `SEED_DECISION.md`
- `TRACE_AXIS_ACC.md`
- `TRACE_AXIS_FREQ.md`
- `CF_PROFILE.md`
- concept prior/sensitivity design/result 문서들
