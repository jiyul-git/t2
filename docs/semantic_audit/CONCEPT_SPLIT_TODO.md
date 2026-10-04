# CONCEPT_SPLIT_TODO

기준: 2026-10-05 `test`

현재 Human Model에서 **서로 다른 판단 능력이 하나의 숙련치/개념을 공유하는 문제**를 따로 추적한다.
이 문서는 구현 지시가 아니라 분리 필요성 메모다. 새 수치나 새 prior는 근거 확보 전 만들지 않는다.

## 분리 필요 항목

1. `checkraise_late` — **PHASE 1 DONE**
   - 의미 경계: 턴은 `checkraise_turn`, 리버는 `checkraise_river`로 분리
   - 기존 생성 프로필: 두 새 키가 없으면 모두 `checkraise_late`로 fallback하여 행동 보존
   - 새 prior/loading/base/spread: 아직 만들지 않음
   - 다음 단계: 실제 모집단에서 turn/river를 독립 생성할 근거와 난이도/분포를 정한 뒤 compatibility fallback 제거 검토
   - 이유: 턴은 세미블러프/드로우가 존재하지만 리버는 드로우가 끝난 별도 판단

2. `bluffcatch_early` — **PHASE 1 DONE**
   - 의미 경계: 플랍은 `bluffcatch_flop`, 턴은 `bluffcatch_turn`, 리버는 기존 `bluffcatch_river`
   - 기존 생성 프로필: 새 두 키가 없으면 모두 `bluffcatch_early`로 fallback하여 행동 보존
   - 새 prior/loading/base/spread: 아직 만들지 않음
   - 다음 단계: 실제 모집단에서 flop/turn을 독립 생성할 근거와 난이도/분포를 정한 뒤 compatibility fallback 제거 검토
   - 이유: 남은 스트리트 수, 미래 액션, 실현 가능성이 다름

3. 플랍 thin value
   - 현재: 독립 숙련치 없이 `range_merge`를 proxy로 사용
   - 필요: flop thin-value ability 분리 검토

4. 프리플랍 3-bet
   - 현재: 독립 3-bet 숙련치/prior 없이 `pf_defend`를 proxy로 사용
   - 필요: 3-bet 판단 능력과 기준 prior 분리

5. limp / iso
   - 현재: RFI 숙련/폭을 차용
   - 필요: limp와 isolation raise를 독립 능력/지식으로 분리

6. `range_read`
   - 현재 하나의 숙련치가 다음 세 기능을 함께 담당
     - 상대 레인지 복원
     - 상대 액션/라인 해석
     - 해석 결과를 실제 의사결정에 반영
   - 필요: reconstruction / interpretation / application 3경계 분리 검토

## 원칙

- 기존 행동을 먼저 보존한 채 의미 경계부터 분리한다.
- 새 숙련치의 loading/base/spread는 근거 없이 임의 생성하지 않는다.
- 분리 후에는 same-state counterfactual + frozen regression으로 영향 측정한다.
- GTO/reference 브랜치 정리와 이 작업은 분리한다.
