# t2 PROJECT — current status and branch contract

Last updated: 2026-10-03 KST

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

GTO는 일반 `master/test` 개발선과 분리된 여러 workstream으로 진행 중이다. 아래 브랜치는 현재 source-of-truth 또는 active evidence를 갖고 있으므로 일반 branch cleanup 규칙으로 강제 merge/delete하지 않는다.

- `chatgpt/gto-reference-20260928` — 기존 public/reference registry와 legacy 616 push/fold DB
- `chatgpt/mini-cfr-solver-20260928` — 9-max preflop solver/pilot 원시 결과
- `chatgpt/gto-external-harvest-20261003` — 외부 9-max MTT hand-level reference 수집본
- `chatgpt/terminal-census-v2-20260930` — terminal/postflop A4c 및 확장 연구
- `chatgpt/gto-db-worker-v1-20261003` — Termux canonical-DB worker 결과

그 외 `gto-*` worker/audit 브랜치도 작업이 닫히기 전에는 이름만 보고 삭제하지 않는다. 먼저 해당 branch의 PROJECT/README와 canonical output이 다른 workstream에 승계되었는지 확인한다.

상황별 reference data는 `data/gto_scenarios.jsonl` 및 각 GTO workstream의 documented dataset에 보존한다.

#### GTO data locator rule

"hand-level reference가 없다"고 결론내리기 전에 최소한 다음 위치를 확인한다.

1. `chatgpt/gto-reference-20260928:data/gto_db/` — legacy/canonical reference registry
2. `chatgpt/gto-external-harvest-20261003:data/gto_external/` — harvested external hand-level datasets
3. `chatgpt/mini-cfr-solver-20260928` 및 worker branches — solver-generated outputs

특히 9-max MTT hand-level mixed-frequency reference는
`chatgpt/gto-external-harvest-20261003:data/gto_external/jensbaagaard_9max_mtt/charts/`
에 있다. 5/10/20/40/100bb × 271 scenarios = **1,355 tables**, 각 169 hand classes다. 이 source에는 exact 30bb pack은 없다.

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

2026-09-28 당시의 5-branch 정리는 완료됐지만 이후 GTO 연구/worker/audit 브랜치가 새로 생겼다. 따라서 **브랜치 개수를 고정값으로 문서화하지 않는다.**

현재 원칙:
- 일반 비-GTO 개발 source of truth는 `master/test`.
- `telemetry/live`는 운영 데이터.
- GTO 관련 `chatgpt/gto-*`, `chatgpt/mini-cfr-*`, `chatgpt/terminal-*` 브랜치는 각 workstream 문서와 output provenance를 확인한 뒤 정리한다.
- 과거 브랜치 cleanup 완료 사실은 유지하되, 이후 생성된 GTO 브랜치를 obsolete로 오해하지 않는다.

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

## 10. GTO reference datasets — current inventory

Public/reference data is split across more than one GTO branch. Do not search only the older reference branch.

### 9-max MTT hand-level harvested reference

On `chatgpt/gto-external-harvest-20261003`:

- `data/gto_external/jensbaagaard_9max_mtt/charts/`
  - 9-max MTT hand-level mixed-frequency charts
  - stacks: **5, 10, 20, 40, 100bb**
  - **271 scenarios per stack / 1,355 tables total**
  - all **169 hand classes** per table
  - MIT upstream
  - no exact 30bb pack; 20/40bb are neighboring-stack evidence, not exact 30bb truth
- `data/gto_external/rangemyhand_pushfold_9max/`
  - 9-max push/fold auxiliary source, 1–25bb
- discovery/provenance: `data/gto_external/DISCOVERY_AUDIT_20261003.md`

### Older public/reference layer

Collected on `chatgpt/gto-reference-20260928`:

- `data/gto_public/8max_mtt_matthiola.jsonl`
  - 8-max MTT preflop
  - 202 chart nodes / **34,138 hand-node rows**
  - stacks: 3, 5, 8, 10, 12, 15, 17, 20, 22, 26, 30, 35, 40, 50, 70, 100bb
  - RFI 112 charts + vs-open 90 charts
  - four-action frequencies: raise / call / all-in / fold
  - source pinned to `matthiola0/poker-hand-review@9ef33a4d...`, MIT

- `data/gto_public/amaster_hu_blueprints/`
  - HUNL auxiliary preflop reference only
  - 27 compressed blueprint shards
  - stacks: 20, 30, 40, 60, 80, 100, 150, 175, 200bb
  - antes: 0 / 0.5 / 1.0bb
  - 169 hand classes, 25,000 DCFR iterations per cell
  - source pinned to `amaster97/poker_solver@f78f1b2b...`, MIT
  - do **not** use as direct 8-max ground truth; use for stack-depth/deep-stack trend checks.

- `data/gto_public/mpcaren_100bb_8max.reference.json`
  - index only; source files are not vendored because no repository license was detected
  - 89 public 100bb 8-max reference files: RFI 7 / facing-open 28 / facing-3bet 28 / facing-4bet 26
  - source pinned to `mpcaren/preflop-range-trainer@6606aefc...`
  - query only as an external corroboration source.

Source provenance and license notes: `data/gto_public/SOURCES.md`.
### RFI reverse-calibration audit (2026-09-28)

- Public 8-max MTT RFI population: 112 charts / 18,928 hand-node rows.
- Current T2 non-SB RFI: mean Brier 0.0620, mean absolute aggregate-rate error 3.51%p.
- Same architecture with reverse-fit base/depth coefficients (shadow only): Brier 0.0537, aggregate-rate error 0.64%p.
- Per-chart best hard cutoff: Brier 0.0435; best monotone mixed boundary on current `pf_rank`: 0.0284.
- Therefore order of work is: **ante/depth coefficient recalibration -> re-audit hard cutoff/mixing -> only then inspect `pf_rank` ordering.**
- 100bb cross-source check: public MTT-ante / no-ante RFI ratio averages ~1.312x across UTG-BTN; current T2 ante separation is only 1.111x (`1/0.9`). This is a provisional 100bb anchor, not yet a production constant.
- SB excluded from this coefficient fit because public SB RFI contains substantial limp mixing.
- Evidence files: `data/gto_public/rfi_calibration_test_20260928.{json,md}`, `data/gto_public/rfi_100bb_ante_crosscheck_20260928.{json,md}`.
- **No production constants were changed in this audit.**


Calibration order:
1. use the large 8-max public frequency dataset first;
2. compare current T2 output over whole populations, not single hands;
3. use the HU deep-stack blueprint only as auxiliary evidence for stack trends;
4. use single-spot solver runs for gaps not covered by public data;
5. PokerData remains outside the repository until an API key is provided.

## 11. GTO reference rule

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


### Preflop frequency calibration promotion (2026-09-28)

Promoted on `test`:
- `ca418d229b199a80040d1eb01439819ae24754d4` — RFI base/depth/ante calibration.
- `ce5c118f8cfa078faed3ed09482549df4ca81458` — defense coefficients gated to **8-max + ante + directly supported defender seats (CO/BTN/SB/BB)**.
- `1a23123608c5c8ab625c6314c550f464465e4724` — calibrated defense widths bypass the legacy exponential saturation; all other paths retain legacy saturation.

Evidence:
- RFI non-SB aggregate-rate error: **3.51%p -> ~0.6-1.0%p** in shadow calibration.
- RFI 100bb no-ante cross-source check improved with the new RFI/ante separation.
- 8-max MTT defense threshold audit exposed a separate defense-width problem; MTT-derived coefficients do **not** transfer to no-ante, so they are condition-gated.
- Actual `defend_action_likelihoods()` audit across 60 public MTT charts:
  - old action Brier **0.12169**
  - gated coefficients + preserved calibrated widths **0.08407**
  - continue-rate MAE **15.56%p -> 7.50%p**
  - attack-rate MAE **7.77%p -> 4.55%p**
  - holdout stacks 15/30/100bb show the same improvement.
- Isolation verifier:
  - GTO layer: **3,150 unchanged / 450 intended changed / 0 errors**
  - threshold layer: **2,100 unchanged / 300 intended changed / 0 errors**
  - preflop closure **4/4 PASS**.

Rejected / not promoted:
- A single global defense calibration across ante and no-ante: rejected; 100bb no-ante cross-source error worsened sharply.
- Re-fitting only seat-level `TB_SHARE`: rejected; frequency-optimal values hit extreme bounds and worsened full action fit.
- Linear opener-sensitive 3bet-share function: rejected for now; small attack-frequency gain but worse overall Brier/continue fit and unstable CO identification.
- `pf_rank` ordering remains untouched.

Next calibration target:
- The remaining attack/3bet mismatch is in the **mixed-policy execution shape after tp/tot**, not justified by another global share constant.
- Keep the new RFI/defense reference layer fixed while auditing the `w_raise / w_call / w_fold` mapping.
- Do not broaden the MTT defense override to no-ante, 9-max, or unsupported defender seats without matched public data.

Evidence files:
- `data/gto_public/rfi_coeff_shadow_20260928.{json,md}`
- `data/gto_public/rfi_candidate_same_state_ab_20260928.json`
- `data/gto_public/defend_width_audit_20260928.{json,md}`
- `data/gto_public/defend_100bb_noante_crosscheck_20260928.{json,md}`
- `data/gto_public/defend_policy_frequency_audit_20260928.{json,md}`
- `data/gto_public/defend_saturation_shadow_20260928.{json,md}`
- `data/gto_public/defend_tbshare_shadow_20260928.{json,md}`
- `data/gto_public/defend_tbshare_function_shadow_20260928.{json,md}`


### RFI-only runtime attribution correction (2026-09-28)

Direct A/B of pre-candidate `e17be45` vs the rounded RFI-only candidate shows the candidate effect is small:
- VPIP 315/1379 (22.84%) -> 317/1380 (22.97%), +0.13%p.
- PFR 167/1379 (12.11%) -> 167/1380 (12.10%), effectively unchanged.
- flop reached 100/180 (55.56%) -> 101/180 (56.11%), +0.56%p.
- 12/180 hands had any actual preflop-log change; 5/180 changed flop reach.
- action totals: raise -2, all-in +2, call +2, fold -2.

Therefore the previously observed `20.7 -> 23.0 VPIP` and `47.2 -> 56.1 flop` are **not** attributable to the RFI candidate. Those numbers compared the candidate to the frozen `current` regression baseline at rev `0962cb2`, while the actual parent `e17be45` had already moved to roughly 22.8% VPIP / 55.6% flop.

For intentional strategy attribution, compare the exact parent and candidate directly. Do not interpret a mismatch against the frozen `current` baseline as the candidate's causal effect when intervening behavior-changing commits exist.

Evidence:
- `data/gto_public/rfi_only_attribution_summary_20260928.json`
- `data/gto_public/rfi_only_attribution_20260928.md`

The 6-seed fixture is 9-max at 150bb, outside the directly calibrated public-data envelope (8-max <=100bb), so use it as a side-effect/extrapolation check rather than direct calibration evidence.
