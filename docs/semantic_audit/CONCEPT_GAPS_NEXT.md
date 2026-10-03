# CONCEPT_GAPS_NEXT — 개념 정리에서 드러난, 아직 채우지 않은 개념과 지식

기준 Stage 11(`3c5d56d5` 이후). 사용자 요청으로 남기는 다음 단계(전략 지식 개선)의 출발 목록이다.
개념 정리 단계에서는 검증된 근거 없이 새 수치를 만들지 않는다는 원칙 때문에 **기록만 하고 채우지 않았다**.

## 1. 코드에 있었지만 목록에 없던 개념 — 처리 완료

이름 없이 판단하던 곳을 개념으로 등록했다(선언 능력 37개, 개념→함수 대응표 227행 → 293행).
예: 콜당했을 때도 앞서는가, 뒤에 남은 사람 수만큼 요구 승률 상향, 숙련에 따른 보드 위험 인지, 계획 강등 문턱.
이미 코드에 있던 판단이라 행동 변화는 없다. 정본: `CONCEPT_FUNCTION_REGISTRY.csv`, `completeness/SPAN_MAP.json`(미소유 0).

## 2. 하나의 숙련치가 서로 다른 질문을 떠맡는 곳 — 독립 능력 부재(미해결)

계산 경계는 함수로 나눴지만 숙련치 공급은 하나다. 분리하면 인구 분포와 행동이 바뀌고, 새 숙련치의 분포 근거가 필요하다.

| 지금 | 필요한 독립 능력 | 근거 위치 |
|---|---|---|
| 턴·리버 체크레이즈가 `checkraise_late` 공유 | 턴(세미블러프 중심) / 리버(드로우 없음) | registry `checkraise_late` |
| 플랍·턴 블러프캐치가 `bluffcatch_early` 공유 | 스트리트별 블러프캐치 | registry `bluffcatch_early` |
| 플랍 얇은 밸류가 `range_merge` 를 빌림 | 플랍 얇은 밸류 능력 | registry `medium_strength_merge_value`, L-RA08 |
| 프리플랍 3벳 성향이 `pf_defend` 를 proxy 로 사용 | 독립 3벳 숙련 / solved 3벳 prior | MISSING_INDEPENDENT_3BET_SKILL/PRIOR (closeout A2) |
| 림프·아이솔이 RFI 숙련/폭을 빌림 | 림프·아이솔 능력과 prior | KNOWLEDGE_COVERAGE_MATRIX |
| `range_read` 하나가 레인지 복원 / 액션 해석 / 반영을 모두 공급 | 세 능력으로 분리 | L024, `RANGE_READ_CONSUMER_BOUNDARIES.md` |

## 3. 개념은 있으나 근거 지식이 없는 곳 — 지식 공백(미해결)

독립된 기준 정책 없이 작성된 휴리스틱이나 다른 차트에서 파생한 값으로 동작한다(상세: `KNOWLEDGE_COVERAGE_MATRIX.md`).

- 프리플랍: 림프, 아이솔, vs-3벳, 4벳, 콜드 4벳, 리쇼브, 콜오프.
- 9-max: 디펜스 폭은 8-max(안테) 보정 표뿐이다. 9-max 는 미보정 식이다. GTO 의존 두 플래그(`T2_GTO_MEMORY_V2`, `T2_PREFLOP_REASONING_V3`)는 이 reference 검증 전까지 production OFF(BLOCKED_BY_GTO_REFERENCE_VALIDATION).
- 포스트플랍: c벳, vs c벳, 플랍 레이즈, 턴 배럴·프로브·레이즈, 리버 밸류·블러프·블러프캐치, 멀티웨이 응답 트리. 모두 독립 정책이 없다.
- 계산: 사이드팟 완전 EV, 드로우 콜의 미래 스트리트 EV(내재 오즈).

## 권장 순서

1. 3번 지식 확보 — 9-max 프리플랍(특히 3벳/4벳) 먼저. 근거가 있어야 2번 분리 시 숙련치 수치를 정할 수 있다.
2. 9-max reference 가 검증되면 GTO 의존 두 플래그를 재판정한다.
3. 2번 독립 능력 분리(인구 분포 변화 측정 포함).
4. 포스트플랍 정책 지식(R1b 플랍 레이즈 레인지, OOP 체크레이즈 후속 행동 포함).
