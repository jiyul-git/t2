# t2 PROJECT — current status and branch contract

## 2026-10-02 코드 재감사 동기화

master `8614f32d` / test 감사 기준 `4b9d33d`. remote 6개, test ahead 544 / behind 8; master ancestor 아님. 재개 확인 때 terminal-census만 `5d9fa389`로 전진했다. 이번 작업은 test semantic-only이며 merge/master promotion/branch cleanup 없음.

현재 근거: [전체 구조](docs/semantic_audit/CURRENT_ARCHITECTURE_AUDIT.md), [개념→함수](docs/semantic_audit/CONCEPT_FUNCTION_REGISTRY.md), [문서 차이](docs/semantic_audit/DOCUMENT_DRIFT.md), [리팩터링·검증](docs/semantic_audit/REFACTOR_AND_VERIFICATION.md). 아래 과거 실험/commit별 증거는 그 시점 기록이며 현재 배포 인증이 아니다.

Last updated: 2026-09-28 KST

이 파일이 새 세션의 첫 번째 기준 문서다. 전체 저장소나 과거 채팅을 다시 읽지 말고, 이 파일에서 현재 branch/workstream을 확인한 뒤 필요한 통합 문서만 추가로 읽는다.

## 1. Project goal

t2는 9-max NLH 토너먼트 봇을 인간의 의사결정처럼 모델링하는 프로젝트다.

핵심 원칙:
- JUDGMENT -> PLAN -> ACTION을 분리한다.
- **GTO를 공부해 얻은 learned prior/memory와 실제 테이블의 human reasoning을 동시에 구현한다. 둘 중 하나로 다른 하나를 대체하지 않는다.**
- GTO reference와 T2의 차이는 먼저 `reasoning error / human approximation / intentional exploit`로 분류한 뒤 수정 여부를 결정한다.
- 상대 읽기, 성향, ICM, money-jump, range, multiway semantics를 한 계수에 섞지 않는다.
- 구조/의미론이 닫히기 전에는 VPIP/PFR/bluff/personality 계수를 광역 튜닝하지 않는다.
- 실험은 고정 시드, 명시적 모집단, 사전등록, regression/attribution을 우선한다.
- 완료는 code + verification + master promotion + documentation + branch cleanup까지 포함한다.

## 2. Branch contract — final

### master — CORE / official

- GitHub default branch이며 **유일한 정식 코어 브랜치**다.
- 현재 안정 code checkpoint: `9330c4f7fc5acb09775f39f7f9174183299cc7fc`.
- 이후 master의 변경은 현재까지 문서 통합/운영 정리뿐이다.
- 검증되지 않은 전략/로직을 master에서 직접 실험하지 않는다.

### test — sole non-GTO development line

- **일반 엔진/UI/판단 로직 시험은 전부 test 하나에서 진행한다.**
- 기존 `chatgpt/logic-tuning-20260927`의 실제 작업선을 test로 승계했다.
- 현재 logic code checkpoint: `6d2a663460acd2ed296741d828a960f4d9b3c557`.
- 여기에는 board-danger local straight connectivity 수정과 duplicate preflop defend-call cliff 제거가 포함된다.
- 과거 diverged 실험 36개는 `2520cb2a975d1492513608ccdd2a747cdf94fed4`에서 **history-only**로 연결했다. 이 commit은 파일 트리를 전혀 바꾸지 않았다.
- `2f5c7cb8f978da711b5b60c418068bad3f64ce15`에서 master 이력도 test에 연결했다. 역시 test 파일 트리는 바뀌지 않았다.
- 당시에는 master ancestry를 연결했다. 현재 remote 관계는 위 재감사 상태를 따른다.

### GTO exception — ongoing, do not clean yet

다음 두 브랜치는 현재 GTO 작업이 진행 중이므로 이번 일반 branch cleanup에서 제외한다.

- `chatgpt/gto-reference-20260928`
- `chatgpt/mini-cfr-solver-20260928`

GTO 작업이 끝나기 전에는 master/test 정리 규칙으로 강제 merge/delete하지 않는다.

상황별 reference data는 `data/gto_scenarios.jsonl`에 보존한다.

### telemetry/live — operational data only

- `telemetry/live`는 코드 개발 브랜치가 아니라 runtime telemetry 기록용이다.
- master/test로 코드를 merge하는 source로 취급하지 않는다.
- telemetry 수집을 중단할 때 별도로 정리한다.

## 3. Branch cleanup status — COMPLETE

2026-09-28 전수 비교 및 정리 완료:

- GTO 2개와 `telemetry/live`를 제외한 모든 과거 작업 브랜치는 **master 또는 test 이력에 완전히 포함**됨을 확인했다.
- 삭제 전 독립 고유 commit은 0개였다.
- 과거 diverged experiment의 코드는 test working tree에 적용하지 않았고 history만 보존했다.
- `ui-bot-pipeline`의 ancestry는 갈라져 있었지만 현재 master에 motion ACK, ThreadingHTTPServer, final-table ICM verifier, `app.js?v=67` 등 실제 기능이 존재함을 재확인했다.
- 검증된 obsolete branch ref **61개를 실제 삭제 완료**했다.
- branch 삭제에 사용한 one-shot GitHub Actions workflow는 실행 성공 후 저장소 working tree에서 즉시 제거했다.

이전 cleanup 직후 branch snapshot은 다음 5개였다(현재 6개는 재감사 표 참조):
1. `master`
2. `test`
3. `chatgpt/gto-reference-20260928`
4. `chatgpt/mini-cfr-solver-20260928`
5. `telemetry/live`

위 목록은 당시 snapshot이다. 현재 terminal-census branch도 존재하며 이번에 정리하지 않는다.


### 2026-10-01 cleanup addendum

이전 5-branch contract를 다시 적용했다.

- `test`를 Human Model 최신 작업선(`70008d9c...`)까지 fast-forward했다.
- 과거 non-GTO 임시 브랜치의 고유 이력은 working tree를 바꾸지 않는 history-only merge로 `test`에 보존했다.
- GTO 감사/성능/terminal-census 임시 브랜치의 고유 이력도 working tree를 바꾸지 않는 history-only merge로 `chatgpt/mini-cfr-solver-20260928`에 보존했다.
- `chatgpt/human-model-v3-20260929`를 포함한 obsolete ref 13개를 삭제했다.
- 따라서 Human Model을 포함한 일반 비-GTO 개발의 source of truth는 다시 `test` 하나다.
- 오래된 master에서 분기됐던 `ccr-9a10123b-0lyye0`의 고유 commit은 **코드를 적용하지 않는 history-only merge**로 `test` 이력에 보존한 뒤 ref를 삭제했다.
- 따라서 원격 branch는 다시 정확히 5개(`master`, `test`, GTO 2개, `telemetry/live`)만 남는다. Human Model을 포함한 일반 비-GTO 개발은 `test` 하나에서만 계속한다.


### 2026-10-01 cleanup addendum

이전 5-branch contract를 다시 적용했다.

- `test`를 Human Model 최신 작업선(`70008d9c...`)까지 fast-forward했다.
- 과거 non-GTO 임시 브랜치의 고유 이력은 working tree를 바꾸지 않는 history-only merge로 `test`에 보존했다.
- GTO 감사/성능/terminal-census 임시 브랜치의 고유 이력도 working tree를 바꾸지 않는 history-only merge로 `chatgpt/mini-cfr-solver-20260928`에 보존했다.
- `chatgpt/human-model-v3-20260929`를 포함한 obsolete ref 13개를 삭제했다.
- 따라서 Human Model을 포함한 일반 비-GTO 개발의 source of truth는 다시 `test` 하나다.
- 오래된 master에서 분기됐던 `ccr-9a10123b-0lyye0`의 고유 commit은 **코드를 적용하지 않는 history-only merge**로 `test` 이력에 보존한 뒤 ref를 삭제했다.
- 따라서 원격 branch는 다시 정확히 5개(`master`, `test`, GTO 2개, `telemetry/live`)만 남는다. Human Model을 포함한 일반 비-GTO 개발은 `test` 하나에서만 계속한다.

## 4. Promotion workflow

일반 개발은 다음 한 경로만 쓴다.

```
master
  |
  v
test
  |
  +-- 구현 / audit / hand review / targeted experiment
  +-- verifier
  +-- regression
  +-- intentional behavior change attribution
  |
  v
master promotion
```

승격 조건:
1. 목표와 변경 범위가 명확함
2. targeted verifier PASS
3. regression 결과 확인
4. 행동 변화가 있으면 원인 attribution 완료
5. 관련 통합 문서 갱신
6. master에 반영
7. test를 새 master 기준으로 계속 사용

2026-10-03 사용자 결정 — 변경 종류별 승격:
- 버그 수정·개념 연결/구현: test 에서 검증(같은 상태 귀속, 23-gate, completeness)이 끝나고 문제가 없으면 **바로 master 로 승격**한다.
- 계수 조정: **test 에서만** 한다. 표본을 뽑아 포커적으로 검토한 뒤, master 승격 전에 사용자에게 한 번 더 확인한다.
- 플레이(UI)는 master 로 한다: `T2_UI_REF=master sh ui/tools/setup_run_dir.sh ~/t2_play`.

새 비-GTO branch를 관성적으로 만들지 않는다.
정말 독립 이력이 필요한 예외 작업도 먼저 test에서 가능한지 확인하고, 별도 branch가 필요하면 같은 phase 안에서 merge/drop까지 닫는다.

## 5. Current work

### Non-GTO / test

**2026-10-06 KST 대회 간격/입장 동기화 후속 (test)**: 최신 시간 시스템 `3d48f9b` 위에서
기본 일정을 2시간에 한 대회로 줄였다. 레이트 참가를 영구 접수하고 요청 시각 이후의
완료 핸드에 자동 입장하도록 수정했다. 선택한 입장 대기를 우선 처리하며, 등록이 끝난
미참가 대회는 작업 큐에서 제외한다. 기존 참가/취소 영수증·원장·규칙은 유지한다.
동기화 중 자연 마감된 대회의 미착석 참가비는 한 번만 환불한다. `T2_UI_DEFER=0`에서
정산이 영원히 대기하던 경로도 동기 계산으로 복구했다. 경제 검증 37개, 개인 설치 23개,
11명/2테이블 실제 HTTP 레이트 참가(DEFER=0, 시간 시스템 ON) 및 예약 참가(DEFER=1, OFF),
오프라인 탈락 복구/재참가를 확인했다. 근거: [후속 검증 기록](docs/semantic_audit/evidence/SCHEDULED_ADMISSION_FIX.json).

**2026-10-05 예약 대회/개인 칩 V1 (test 검증본)**: 수동 새 게임 대신 시간대별 대회,
영구 지갑, 예약 바이인/취소, 레이트 등록, 탈락 후 리엔트리, 한 번만 상금 지급을 구현했다.
미접속 중 실제 시간대로 진행하며 체크/폴드·블라인드를 적용한다. 작업 시작 기준은 `cd2ee646`이고
기존 test의 개념 분리 변경을 보존했다. 운영값은 임시이며 정식 서버/master에는 아직 반영하지 않았다.
근거: [예약 대회 V1](docs/semantic_audit/SCHEDULED_TOURNAMENTS_V1.md).

**2026-10-05 개인 지갑 설치/업데이트 분리 (test 후속)**: 예약 대회 V1 위에서 최초 설치는
`system` + `personal` 생성, 업데이트는 `system`만 복사하도록 분리했다. 지갑 DB는 패키지에
넣지 않고 최초 설치 시 로컬에서 한 번 생성한다. 시스템 폴더 전체 삭제 후 복원에도 지갑·원장·
참가·대회 상태를 유지한다. 기존 지갑/연결 정보를 잃거나 손상된 경우 새 초기 지급으로 넘어가지
않고 중단하며, 과거 `userdata`는 명시적인 이전만 허용한다. 실제 ZIP 설치 검증 23개와
경제 검증 27개를 통과했다. test 검증본이며 정식 master/운영 서버 배포는 아직 하지 않았다.
실행/업데이트 명령: [UI 설치 안내](ui/README.md#개인-지갑을-분리한-설치와-업데이트-test-2026-10-05).

**2026-10-05 최신 test 통합**: 원격 `d235743a`의 인간모델 분리/시간 설계 5개 커밋 위에
예약 대회(`4bc1d34`)와 개인 설치 분리(`28818d3`)를 통합했다. 원격용 개인 설치
커밋은 이전 로컬 `aef0dbb`/리베이스 후 `bfe2fb4`와 파일 내용이 같다. 원격에서 추가된 15개 파일은 바이트 단위로
그대로 유지했다. 설치 23개, 경제 27개, 인간모델 분리 검증 4개, 18명/6핸드 UI smoke와
2테이블 실제 HTTP 검증을 다시 통과했다. 시간 설계 후보를 운영 타이머 코드로 적용한 변경은 없다.
통합 검증 기록: [PERSONAL_INSTALLATION_V1.json](docs/semantic_audit/evidence/PERSONAL_INSTALLATION_V1.json).

**2026-10-03 master 승격**: 인간형 모델 감사·통합 Stage 0~11 과 베타 전 버그 수정 3건을 master 로 승격했다. 이 시점이 새 본체 기준선이다.
- 본체 + Human Model 2차/3차가 하나의 실행 경로로 통합됐다. GTO 의존 두 플래그(`T2_GTO_MEMORY_V2`, `T2_PREFLOP_REASONING_V3`)는 production OFF 이고 BLOCKED_BY_GTO_REFERENCE_VALIDATION 이다.
- 안테: 참가자 균등 분담. 게시 순서는 ante → SB → BB.
- 검증: 23-gate 23/23, tier-all REGRESSION 0, completeness 미소유 0. 기준선 시드 11 `d6c70b87…`, 시드 12 `f0620c61…`.
- 상세: `docs/semantic_audit/WORK_STATUS.md`, `REFACTOR_AND_VERIFICATION.md`.
- 다음: 베타(판단 → 계획 → 실행 층 추적 + 포커 타당성 검토). 이후 `docs/semantic_audit/CONCEPT_GAPS_NEXT.md` 순서로 개념·지식을 보강한다. 미판정 FOLLOWUP 은 ledger 'Stage 11' 절에 있다.

이전 메모: live hand-review를 한 table/spot씩 진행한다.

Immediate state:
- board-danger 0/under-detection 문제가 실제로 있었고 test의 logic line에서 수정됐다.
- 이 신호 영향을 받는 betting/action probability는 **post-fix test engine으로 다시 측정**한다.
- 수정 전 capture를 수정 후 확률처럼 해석하지 않는다.
- hand-review에서 발견한 로직 문제는 먼저 현재 구현 의도를 확인한 뒤 수정한다.

### GTO

- GTO는 중립 reference baseline으로 사용한다.
- GTO 데이터는 solver clone을 만들기 위한 production 정답표가 아니라 **학습된 prior/reference layer의 기준점**으로 사용한다.
- 높은 GTO-study skill은 matched spot의 prior 신뢰도를 높이고, 조건 mismatch가 커질수록 human reasoning 비중이 커지는 구조를 목표로 한다.
- 향후 구현은 두 workstream을 모두 닫아야 한다: **(A) GTO knowledge/memory/prior + condition matching/interpolation**, **(B) human reasoning + reads/exploit/ICM + bounded mistakes**.
- 실제 spot과 조건이 맞는 frequency만 비교한다.
- solver/reference 결과는 chat에만 두지 않고 dataset에 저장한다.
- GTO branch 정리는 현재 진행 중인 GTO 작업이 끝난 뒤 별도로 한다.

## 6. Architecture status

CLOSED / verified:
- Preflop P1-P6 structural routes
- Postflop F1-F7 structural routes
- F7-B1A joint relative strength
- F7-B1B1 multiway range advantage
- F7-B1C blocker-effect lifecycle
- F7-B1D defend-likelihood rewire
- weighted range W0-W4
- TDA dead-button position/blind engine
- parallel table round
- final-table ICM fast path + motion-gated UI pipeline
- effective-all-in v1
- uncalled-excess accounting

OPEN / logic barrier:
- P7 dedicated strategy/observation ACTIVE; 독립 solver prior 및 완전 action EV OPEN
- F7-B joint strong-region producer ACTIVE; literal nuts 의미는 OPEN
- F7-B2 purpose별 read/stack selector ACTIVE; 일반 joint response model OPEN
- F7-C emotion/tilt consumer boundary
- F7-D execution/sizing semantic closure
- F8 side-pot / ICM decision semantics
- W5 non-uniform likelihood/posterior ACTIVE; 전체 관측 의미 검증 OPEN
- street-concept granularity/taxonomy
- final dead-code cleanup
- dual-source strategy integration: GTO learned prior/memory ↔ human reasoning weighting
- GTO-study knowledge/confidence/mismatch decay representation
- human approximation/error vs intentional exploit discrepancy classification in verification

## 7. Regression checkpoint

Normal core safety gate:

`tools/regress.py check --baseline current`

Historical checkpoint fingerprints (현재 test와 이미 불일치):
- 3000 `12c2daefd7c87cbb`
- 3001 `8b83f668c038d002`
- 3002 `0badaa6a21474fd3`
- 3003 `3aebdd1942b57229`
- 3004 `d4295da0aace11ca`
- 3005 `2c50d0b71bd16614`

Fixture totals:
- 180 hands
- 1,368 preflop decisions
- 283 VPIP
- 165 PFR
- 85 flop-seen

Intentional strategy promotion은 fingerprint가 움직일 수 있다.
그 경우 baseline을 먼저 덮지 말고 attribution을 끝낸 뒤 새 checkpoint를 선택한다.

## 8. Documentation — 10 canonical files

Root Markdown은 125개에서 **10개**로 통합했다.

1. `PROJECT.md` — 현재 상태, branch contract, handoff
2. `DECISION_SYSTEM.md` — judgment/plan/action + P/F audit
3. `CONCEPT_SYSTEM.md` — concept glossary/wiring/taxonomy
4. `RANGE_MODEL.md` — weighted range + multiway semantics
5. `POT_ALLIN_MODEL.md` — pot/side-pot/uncalled/effective-allin
6. `MONEY_JUMP_MODEL.md`
7. `TOURNAMENT_RUNTIME.md` — 9max/TDA/parallel/UI runtime
8. `PERSONA_RESEARCH.md`
9. `CF_RESEARCH.md`
10. `DIAGNOSTICS_HISTORY.md`

과거 개별 설계/중간결과 Markdown은 Git history에 보존한다.
현재 판단의 source of truth로 직접 로드하지 않는다.

## 9. New-chat rule

새 채팅 시작 순서:
1. 현재 작업 branch를 확인한다: 일반 작업은 `test`, 안정판 검증은 `master`, GTO는 해당 GTO branch.
2. 이 `PROJECT.md`를 읽는다.
3. 현재 작업에 필요한 통합 문서 **하나만** 추가로 읽는다.
4. 과거 chats/Markdown 전체를 다시 로드하지 않는다.

세션 종료 시 기록할 것:
- branch + code checkpoint
- 완료한 변경
- verifier/regression 결과
- 미해결 문제
- 다음 정확한 action

## 10. GTO reference rule

GTO row에는 최소 다음을 보존한다:
1. players / positions
2. effective stacks
3. blinds / ante
4. action history
5. allowed sizes
6. source/calculation method
7. raise/call/fold frequencies
8. exact condition match 여부
9. current T2 output
10. discrepancy + decision

Status:
- `exact`
- `near`
- `pending`
- `rejected`

단일 chart나 조건이 다른 solver 결과 하나로 production constant를 조정하지 않는다.

## 11. Tuning state

**NOT GLOBAL TUNING YET.**

구조/의미론의 열린 항목을 닫기 전에는 광역 VPIP/PFR/bluff/personality calibration을 시작하지 않는다.
