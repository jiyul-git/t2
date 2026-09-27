# BRANCH_POLICY — branch hygiene

브랜치는 작업 부산물이 아니라 **명시적 수명주기를 가진 작업 단위**로 관리한다.

## Active branch

원칙적으로 활성선은 **하나만 유지한다**.

1. `chatgpt/decision-architecture-audit-20260926`
   - 엔진/판단 구조 + 현재 플레이/UI의 단일 source of truth
   - PR #11 `0b919b62`에서 기존 engine/UI 최신선을 통합
   - 구조 감사, UI 수정, 배포 준비 모두 여기서 닫는다.

`chatgpt/ui-bot-pipeline-20260927`은 통합 이후 호환 ref일 뿐이며 새 작업 금지, local clone 전환 후 삭제한다. `integration/latest-20260927`도 final-table/UI 배선 검증을 위해 잠시 만든 뒤 canonical로 fast-forward 완료했으므로 deletion-only다.

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
4. **containment proof** 수행: 임시 branch -> canonical branch 비교에서 canonical이 임시 branch의 모든 commit을 포함하는지 확인
5. diverged면 unique commit을 먼저 열어보고 merge/cherry-pick/보존 중 하나를 결정
6. canonical status 문서에 실제로 합쳐진 기능명과 merge/head commit을 기록
7. 임시 branch를 즉시 deletion candidate로 전환하고 그 branch에는 더 이상 commit하지 않음
8. local/runtime source가 canonical branch만 추적하는지 확인
9. 그 다음에만 local/remote branch 삭제

즉 **기능 완료 = 코드 완료 + 검증 완료 + canonical 반영 확인 + 문서 완료 + branch 정리 완료**다.

### 절대 금지

- branch 이름만 보고 "옛날 것"이라 판단해 삭제하지 않는다.
- current branch에 코드가 안 보인다는 이유만으로 "구현 안 됨"이라고 결론내리지 않는다.
- 이미 구현한 기능을 다시 설계하기 전에 historical branch/commit 검색과 containment 확인을 먼저 한다.
- runtime 폴더(`t2_ui_beta`)를 source-of-truth로 취급하지 않는다.

이번 parallel-table 사례처럼 구현이 side branch에 남은 채 canonical UI가 따로 전진하면,
기능 자체가 사라진 것처럼 보일 수 있다. 그래서 **merge 확인과 old-branch 폐기를 같은 작업으로 묶는다.**

## Planned cleanup

`integration/latest-20260927`은 최신 엔진 `b6cb821` 위에서 final-table/UI 배선을 검증한 임시선이다. CI 성공 후 canonical이 해당 커밋들을 fast-forward로 포함했으므로 새 작업 금지·삭제 대상이다.

`chatgpt/ui-recovery-20260927`은 `ui-bot-pipeline`에 완전히 포함되어 삭제 대상으로 확정했다.
`chatgpt/parallel-tables-20260927`도 merge `13505d64` 이후 `ui-bot-pipeline`에 완전히 포함되어 삭제 대상이다.
과거 UI 전용 브랜치는 더 이상 source of truth로 유지하지 않는다.

엔진 구조 감사가 끝나면 과거 audit/experiment 브랜치도 같은 방식으로 정리한다.

GitHub 원격 브랜치를 실제 삭제할 때는 삭제 후보 목록을 사용자에게 보여준 뒤 한 번에 정리한다.
