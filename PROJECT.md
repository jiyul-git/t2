# t2 PROJECT — status, handoff, branch policy

Last consolidated: 2026-09-28 KST

이 파일이 새 세션의 첫 번째 기준 문서다. 프로젝트 전체를 다시 읽지 말고 이 파일에서 현재 작업을 확인한 뒤 필요한 통합 문서만 추가로 읽는다.

## 1. 목표

t2는 9-max NLH 토너먼트 봇을 인간의 의사결정처럼 모델링하는 프로젝트다.

핵심 원칙:
- 판단(JUDGMENT)과 계획(PLAN)과 집행(ACTION)을 분리한다.
- 상대 읽기, 성향, ICM, money-jump, 레인지, 멀티웨이 의미론을 한 계수에 섞지 않는다.
- 구조 감사가 끝나기 전에는 VPIP/PFR/bluff/personality 계수를 전역 튜닝하지 않는다.
- 실험은 사전등록, 고정 시드, 명시적 모집단, 회귀검증을 우선한다.
- 구현 완료에는 코드 + 검증 + canonical 반영 + 문서 + branch cleanup이 모두 포함된다.

## 2. 현재 branch topology

Repository: `jiyul-git/t2`

Stable canonical:
- `chatgpt/decision-architecture-audit-20260926`
- 마지막 architecture code checkpoint: `9330c4f7fc5acb09775f39f7f9174183299cc7fc`
- 이후 canonical 변경은 문서 정리만 포함한다.

Documentation consolidation:
- root Markdown **125 -> 10**
- consolidation commit: `f6da7936a8e6b2afde01a0d839c598a9d94162b8`
- compare 검증상 non-Markdown 변경: **0**
- `chatgpt/docs-consolidation-20260928`은 canonical 반영 완료 후 deletion candidate다.

Active engine / live hand-review line:
- `chatgpt/logic-tuning-20260927`
- last code checkpoint: `6d2a663460acd2ed296741d828a960f4d9b3c557`
- 최근 엔진 수정: board-danger connectivity 보정, duplicate preflop defend-call cliff 제거.

GTO reference line:
- `chatgpt/gto-reference-20260928`
- last code checkpoint: `2897def3543bc61f080252f234709af7f2deb499`
- GTO workflow 규칙은 이 문서 10절에 통합했고, 상황별 데이터는 `data/gto_scenarios.jsonl`에 보존.

Mini-CFR / vendored solver line:
- `chatgpt/mini-cfr-solver-20260928`
- last code checkpoint: `80026c02326e54694ce40ee27c87e521d2098708`
- logic-tuning 및 GTO reference와 diverged 상태이므로 이름만 보고 merge/delete 금지.

`integration/latest-20260927`은 이름과 달리 최신선이 아니다.

## 3. 현재 작업

Primary workstream:
- 실제 핸드 리뷰를 한 테이블/한 상황씩 진행.
- GTO는 중립 기준선으로만 사용.
- solver 결과는 채팅에만 남기지 않고 `data/gto_scenarios.jsonl`에 저장.

Immediate state:
- board-danger의 0/과소탐지 문제가 실제로 있었고 `logic-tuning`에서 수정됨.
- 이 신호의 영향을 받던 베팅/액션 확률은 **수정 후 엔진으로 다시 측정**해야 한다.
- 이전 캡처를 수정 전 확률로 그대로 해석하면 안 된다.
- solver가 진행 중이어도 핸드 리뷰 자체를 중단하지 않고, 상황/입력/출력을 기록해 이어간다.

Next actions:
1. 현재 리뷰 spot을 post-fix `logic-tuning`으로 다시 계산.
2. T2 확률과 대응 GTO 빈도를 같은 상황 row로 저장.
3. logic-tuning-only commits와 solver/GTO branch의 unique commits를 containment 기준으로 확인.
4. 그 뒤 merge/cherry-pick/abandon 결정.

## 4. 구조 상태

CLOSED / verified:
- Preflop P1-P6 구조 경로.
- Postflop F1-F7 구조 경로.
- F7-B1A multiway joint relative strength.
- F7-B1B1 multiway range advantage.
- F7-B1C blocker-effect judgment lifecycle.
- F7-B1D defend-likelihood rewire.
- weighted range W0-W4.
- TDA dead-button position/blind engine.
- parallel table round.
- final-table ICM fast path + motion-gated UI action pipeline.
- effective-all-in v1.
- uncalled-excess accounting.

OPEN / logic barrier:
- P7 cold-facing re-raise dedicated strategy.
- F7-B nut semantics.
- F7-B2 multi-opponent read/stack aggregation.
- F7-C emotion/tilt boundary activation.
- F7-D execution/sizing boundary activation/refactor.
- F8 side-pot / ICM decision semantics.
- W5 non-uniform posterior production.
- street-concept granularity/taxonomy.
- final dead-code cleanup.

## 5. Regression checkpoint

`tools/regress.py check --baseline current` is the normal production safety gate.

Current canonical fingerprints:
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

Intentional strategy promotions can move the current fingerprint only after attribution. Historical frozen baselines are read-only evidence.

## 6. 문서 지도

평소에는 이 파일만 먼저 읽는다.

작업별 추가 문서:
- 판단 구조/상황/P·F 감사: `DECISION_SYSTEM.md`
- 개념 사전·배선·taxonomy: `CONCEPT_SYSTEM.md`
- weighted range + multiway range semantics: `RANGE_MODEL.md`
- side pot / uncalled / effective-all-in: `POT_ALLIN_MODEL.md`
- money-jump: `MONEY_JUMP_MODEL.md`
- TDA/9max/parallel/UI runtime: `TOURNAMENT_RUNTIME.md`
- personality/axis/prior 연구: `PERSONA_RESEARCH.md`
- counterfactual 연구: `CF_RESEARCH.md`
- 과거 진단/버그 근거: `DIAGNOSTICS_HISTORY.md`

세부 원문이 필요하면 Git history에서 consolidation 이전 commit `4cfbfc3c88578a4e862e44496a5a6d7b173a50da`의 개별 Markdown을 연다.

## 7. 새 채팅 운영

새 채팅 시작:
1. 이 파일을 읽는다.
2. remote branch HEAD를 확인한다. branch 이름만으로 최신성을 판단하지 않는다.
3. 현재 작업에 필요한 통합 문서 **하나만** 추가로 읽는다.
4. 과거 개별 Markdown을 무더기로 로드하지 않는다.

한 채팅은 가능하면 하나의 workstream만 다룬다:
- engine / decision logic
- live hand review + GTO
- solver/CFR
- UI/runtime
- experiments/calibration

세션 종료 전 이 파일의 현재 작업 부분에 다음을 반영한다:
- branch + exact HEAD
- 완료 작업
- 검증/측정 결과
- 미해결 문제
- 정확한 다음 행동

## 8. Branch policy

새 branch는 다음처럼 코드 이력상 분리 이유가 있을 때만 만든다:
- attribution-sensitive 실험
- 위험한 migration/rollback boundary
- 대규모 solver/vendor 작업
- 독립 검증이 필요한 변경

단순 진단, verifier, 문서, 소규모 수정 때문에 새 branch를 만들지 않는다.

Temporary branch 종료 조건:
1. verifier/regression 통과
2. 결과 문서 갱신
3. canonical 반영
4. containment proof
5. runtime source가 canonical을 추적하는지 확인
6. 그 뒤 deletion candidate로 전환

절대 금지:
- branch 이름만 보고 old/new 판단
- 코드가 현재 branch에 안 보인다는 이유로 “미구현” 판정
- historical branch를 통째로 merge해 최신 엔진을 되돌리기
- runtime 폴더를 source of truth로 취급

## 9. 현재 튜닝 상태

**NOT TUNING YET.**

구조/의미론 audit가 닫히기 전에는 광역 VPIP/PFR/bluff/personality 보정을 시작하지 않는다.

## 10. GTO reference workflow

GTO는 production personality/exploit을 튜닝하기 전의 **중립 기준선**으로 사용한다.

Reference scope:
- Hold'em tournament preflop 우선
- table size 2-9
- effective stack 1-600bb
- main validation zone 5-300bb
- 300-600bb는 ultra-deep tag로 별도 해석
- postflop은 실제 리뷰 spot 기준으로 case-by-case 추가

모든 reference row는 최소 다음을 보존한다:
1. players / positions
2. effective stacks
3. blinds / ante
4. action history
5. allowed sizes
6. source 또는 calculation method
7. raise/call/fold frequencies
8. source condition exact match 여부
9. current T2 output
10. discrepancy + decision

Status labels:
- `exact`: 조건 일치
- `near`: 작은 mismatch, comparison only
- `pending`: 미검증
- `rejected`: tuning target으로 부적합

단일 chart나 조건이 다른 solver 결과 하나로 production constant를 조정하지 않는다.
실제 hand-review에서 얻은 reference는 `data/gto_scenarios.jsonl`에 저장한다.
Mini-CFR/solver tooling이 존재하더라도 이 기록 규칙은 동일하다.
