# BRANCH_POLICY — branch hygiene

브랜치는 작업 부산물이 아니라 **명시적 수명주기를 가진 작업 단위**로 관리한다.

## Active branches

원칙적으로 동시에 유지하는 활성선은 두 개다.

1. `chatgpt/decision-architecture-audit-20260926`
   - 엔진/판단 구조의 source of truth
   - 현재 F7-B1D 포함 구조 감사 진행
   - balance tuning 전까지 엔진 주 작업선

2. `chatgpt/ui-recovery-20260927`
   - UI 복구/통합 전용
   - 과거 UI 브랜치에서 검증된 UI 변경만 현재 엔진 위로 이식
   - 엔진 판단 로직은 여기서 임의 수정하지 않음

## Do not create branches casually

새 브랜치는 아래 중 하나일 때만 만든다.

- 현재 active branch에서 수행하면 결과가 섞여 attribution이 깨지는 대규모 실험;
- UI와 엔진처럼 서로 다른 배포/검증 수명주기가 필요한 경우;
- 위험한 migration처럼 rollback 단위가 반드시 분리돼야 하는 경우.

단순 진단, verifier, 문서, 소규모 구조 수정은 새 브랜치를 만들지 않고 현재 작업선에서 커밋한다.

## Temporary branch lifecycle

임시 브랜치를 만들었다면 생성 시점에 반드시 문서에 적는다.

- 목적
- 기준 commit
- 종료 조건
- 최종 처리: merge / cherry-pick / abandon

종료 조건을 만족한 뒤에는 더 이상 새 커밋을 쌓지 않는다.

## Historical branches

과거 브랜치는 source of truth가 아니다.

- `chatgpt/fix-side-seat-overlay-20260924`
- `integration/ui-v49-money-jump-20260920`
- `chatgpt/fix-newgame-fn-20260924`
- `codex/hanok-9max-visuals-20260924`
- 기타 `claude/*`, 과거 `chatgpt/*` 실험선

필요한 변경은 commit 단위로 읽어서 active branch에 이식한다.
과거 브랜치를 통째로 merge해 최신 엔진을 되돌리지 않는다.

## Cleanup checkpoint

각 큰 단계가 끝날 때 branch cleanup을 같은 완료 조건에 넣는다.

1. verifier/regression 통과
2. 결과 문서 갱신
3. active branch에 필요한 commit 반영
4. 임시 branch가 더 필요한지 판정
5. 불필요한 branch 목록을 삭제 후보로 기록
6. 삭제 전 merge/cherry-pick 누락 여부 확인

즉 **기능 완료 = 코드 완료 + 검증 완료 + 문서 완료 + branch 정리 완료**다.

## Planned cleanup

현재는 안전을 위해 기존 브랜치를 즉시 삭제하지 않는다.
먼저 UI recovery가 끝난 뒤 과거 UI 브랜치들의 누락 commit이 없는지 확인하고 삭제 후보를 확정한다.

엔진 구조 감사가 끝나면 과거 audit/experiment 브랜치도 같은 방식으로 정리한다.

GitHub 원격 브랜치를 실제 삭제할 때는 삭제 후보 목록을 사용자에게 보여준 뒤 한 번에 정리한다.
