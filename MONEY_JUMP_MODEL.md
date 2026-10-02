# MONEY-JUMP MODEL — architecture + measurement status

## 2026-10-02 코드 재감사 동기화

현재 unopened range_factor만 전략 소비한다. size_factor_shadow/limp_pull_shadow 및 postflop money signals는 shadow다. 이번 작업에서 money 계수/빈도/Phase C 판정 변경 없음.

현재 근거: [전체 구조](docs/semantic_audit/CURRENT_ARCHITECTURE_AUDIT.md), [개념→함수](docs/semantic_audit/CONCEPT_FUNCTION_REGISTRY.md), [문서 차이](docs/semantic_audit/DOCUMENT_DRIFT.md), [리팩터링·검증](docs/semantic_audit/REFACTOR_AND_VERIFICATION.md). 아래 과거 실험/commit별 증거는 그 시점 기록이며 현재 배포 인증이 아니다.

Money-jump는 ICM의 다른 이름이 아니다.
ICM/BF가 payout-risk의 객관적 구조를 제공한다면 money-jump는 “다음 상금 구간까지의 상대적 위치와 pressure opportunity를 플레이어가 어떻게 활용하는가”를 별도 모델링한다.

## 1. Architecture

세 output을 분리한다.

### self_preservation
현재 stack을 보존하려는 압력.

### pressure_opportunity(target)
특정 opponent에게 tournament leverage를 행사할 기회.

### urgency
기다릴 수 없는 상황의 counter-force.
short stack/forced costs 때문에 무조건 보존만 하는 오류를 막는다.

또한:
- structural pressure와 exploit realization을 분리.
- objective context와 personality를 분리.
- stack-below count/ladder buffer/waiting feasibility를 구조 입력으로 취급.
- table position과 seat topology를 입력으로 둔다.
- BF/ICM와 같은 risk를 이중 계산하지 않는다.

## 2. Current production wiring

현재 intentionally:
- unopened range factor: **LIVE**
- open-size money factor: **SHADOW ONLY**
- limp-form pull: **SHADOW ONLY**
- postflop money-jump observation: observation/provenance 중심

이는 missing wire가 아니라 측정 후 보류한 설계다.

## 3. Open-size shadow result

Corrected 6400-6415 sample:
- field hands 3,370
- unopened observations 17,029
- legal unopened raises 3,347
- numerical change 2,174 = 65.0%
- newly pulled to exact 2BB: 143
- changed-row reduction median 0.029BB
- q75 0.083BB
- max 1.036BB

Approach region:
- changed 170/215 = 79.1%
- median 2.30 -> 2.00BB
- newly exact 2BB 71/215 = 33.0%

이 2BB pile-up은 preregistered promotion condition을 통과하지 못했다.
**open-size remains shadow-only.**

## 4. Limp-form shadow result

Same sample:
- eligible 3,487
- add-limp 23 = 0.66%
- base-limp 155
- unchanged raise 3,309
- SB 9/23 candidates

SB open-limp semantic change와 얽혀 있으므로 **limp-form remains shadow-only**.
결과를 본 뒤 SB만 제외하고 나머지를 promote하는 것도 금지.

## 5. 9-max confirmatory sizing experiment

Phase C:
- seeds 93100..93139, 40 clusters
- qualifying rows 2,046
- changed-size rows 1,594
- row-level ITT mean **+0.042653 BB**
- bootstrap 95% interval **-0.0106 .. +0.0969 BB**
- zero-intervention rows 452, paired delta exactly 0

Locked interpretation:
**INCONCLUSIVE** — interval overlaps zero.

Secondary descriptive:
- downstream action changed 56/2046 = 2.7%
- winner path changed 37/2046 = 1.8%
- 3-bet rate about +0.05%p
- opponent calls mean delta +0.020
- flop pot mean delta -0.265BB
- opener flop SPR mean delta +0.280

따라서 production open sizing은 변경하지 않는다.

## 6. Future test rule

money sizing/limp를 다시 볼 경우:
- 새 preregistration
- fresh seeds
- 기존 sample의 favorable subgroup로 promotion 금지
- significance가 나올 때까지 seed를 사후 증대 금지
- open-size mechanism 자체를 재설계한 뒤 측정

## 7. Historical sources

- `MONEY_JUMP_DESIGN.md`
- `MONEY_JUMP_OBS_RESULT.md`
- `MONEY_JUMP_STRATEGY.md`
- `MONEY_OPEN_SHADOW_AUDIT_DESIGN.md`
- `MONEY_OPEN_SHADOW_AUDIT_RESULT.md`
- `MONEY_SIZING_PROMOTION.md`
- `MONEY_SIZING_CF_DESIGN.md`
- `MONEY_SIZING_9MAX_PREREG.md`
- `MONEY_SIZING_9MAX_RESULT.md`
