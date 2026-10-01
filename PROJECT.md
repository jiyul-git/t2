# t2 PROJECT — current status and branch contract

Last updated: 2026-09-28 KST

이 파일이 새 세션의 첫 번째 기준 문서다. 전체 저장소나 과거 채팅을 다시 읽지 말고, 이 파일에서 현재 branch/workstream을 확인한 뒤 필요한 통합 문서만 추가로 읽는다.

## 1. Project goal

t2는 9-max NLH 토너먼트 봇을 인간의 의사결정처럼 모델링하는 프로젝트다.

핵심 원칙:
- JUDGMENT -> PLAN -> ACTION을 분리한다.
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
- 현재 master는 test의 ancestor다.

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

현재 존재하는 branch는 정확히 5개다:
1. `master`
2. `test`
3. `chatgpt/gto-reference-20260928`
4. `chatgpt/mini-cfr-solver-20260928`
5. `telemetry/live`

이 다섯 외의 과거 branch 이름은 더 이상 source of truth도, active ref도 아니다.


### 2026-10-01 cleanup addendum

이전 5-branch contract를 다시 적용했다.

- `test`를 Human Model 최신 작업선(`70008d9c...`)까지 fast-forward했다.
- 과거 non-GTO 임시 브랜치의 고유 이력은 working tree를 바꾸지 않는 history-only merge로 `test`에 보존했다.
- GTO 감사/성능/terminal-census 임시 브랜치의 고유 이력도 working tree를 바꾸지 않는 history-only merge로 `chatgpt/mini-cfr-solver-20260928`에 보존했다.
- `chatgpt/human-model-v3-20260929`를 포함한 obsolete ref 13개를 삭제했다.
- 따라서 Human Model을 포함한 일반 비-GTO 개발의 source of truth는 다시 `test` 하나다.
- 현재 `ccr-9a10123b-0lyye0`만 Claude가 진행 중인 임시 scratch branch로 예외 유지한다. 이 branch는 오래된 master에서 분기된 것이므로 production merge source가 아니며, 작업을 최신 `test` 기준으로 옮긴 뒤 삭제한다.
- `ccr-*` 삭제 후 원격 branch는 다시 기존 계약의 5개만 남긴다.

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

새 비-GTO branch를 관성적으로 만들지 않는다.
정말 독립 이력이 필요한 예외 작업도 먼저 test에서 가능한지 확인하고, 별도 branch가 필요하면 같은 phase 안에서 merge/drop까지 닫는다.

## 5. Current work

### Non-GTO / test

현재 live hand-review를 한 table/spot씩 진행한다.

Immediate state:
- board-danger 0/under-detection 문제가 실제로 있었고 test의 logic line에서 수정됐다.
- 이 신호 영향을 받는 betting/action probability는 **post-fix test engine으로 다시 측정**한다.
- 수정 전 capture를 수정 후 확률처럼 해석하지 않는다.
- hand-review에서 발견한 로직 문제는 먼저 현재 구현 의도를 확인한 뒤 수정한다.

### GTO

- GTO는 중립 reference baseline으로 사용한다.
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
- P7 cold-facing re-raise dedicated strategy
- F7-B nut semantics
- F7-B2 multi-opponent read/stack aggregation
- F7-C emotion/tilt consumer boundary
- F7-D execution/sizing semantic closure
- F8 side-pot / ICM decision semantics
- W5 non-uniform posterior production
- street-concept granularity/taxonomy
- final dead-code cleanup

## 7. Regression checkpoint

Normal core safety gate:

`tools/regress.py check --baseline current`

Current stable fingerprints:
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
