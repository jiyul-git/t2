# CURRENT STATUS — READ THIS FIRST

이 파일이 현재 작업 상태의 **첫 번째 기준 문서**다.

## Source of truth

- Repository: `jiyul-git/t2`
- **Single unified canonical branch:** `chatgpt/decision-architecture-audit-20260926`
- Unified engine+UI merge: PR #11 / `0b919b62`
- 엔진/배선 감사 원본: `~/t2`
- UI 소스 원본: `~/t2_ui_src`
- 실제 플레이 실행본: `~/t2_ui_beta`

엔진과 UI는 더 이상 별도 최신선으로 운영하지 않는다.
`~/t2`와 `~/t2_ui_src` 모두 같은 unified canonical branch를 추적한다.
`chatgpt/ui-bot-pipeline-20260927`은 local 전환을 위한 임시 호환 ref이며 새 작업을 하지 않는다.
플레이 실행본은 unified source에서 `ui/tools/setup_run_dir.sh "$HOME/t2_ui_beta"`로 갱신한다.

## Architecture audit

### CLOSED / production verified

- Preflop P1-P6 structural routes
- Postflop F1-F7 structural routes
- F7-B1A multiway relative-strength consumer
- F7-B1B1 multiway range-advantage consumer
- F7-B1C12 blocker-effect judgment lifecycle
- F8 side-pot plumbing stages already marked closed in their audit docs

### F7-B1D — CLOSED

B1D7-A likelihood shadow passed locally:
- probability invariants 97,344
- scripted branch checks 164,444
- mismatches 0

B1D7-B production rewire exact parity also passed locally against checkpoint `5eb848c`:
- exact checks 92,883
- hotzone checks 1,611
- calloff checks 13,050
- attack outputs 2,124
- action_or_rng_mismatches 0

Defend execution now shares the likelihood helper without changing action, sizing, or RNG state.

**Next architecture step: weighted-range representation + legacy adapter.**
Production ranges are still unweighted until that step begins.

### OPEN after B1D

- F7-B nut semantics
- F7-B2 single-main-opponent aggregation
- F7-C emotion/tilt boundary
- F7-D execution/sizing boundary
- P7 / cold-reraise completeness revisit
- F8-ICM semantic closure
- final dead-code cleanup

## Weighted-range migration — W0 implemented / local gate pending

The post-TDA architecture work has resumed.

W0 is now implemented on the canonical engine line:

- canonical representation: `{combo: relative_mass}`;
- legacy lists map to unit mass per occurrence;
- duplicate legacy occurrences aggregate mass rather than disappearing;
- `legacy_range()` refuses to flatten non-uniform weighted input;
- stable weighted iteration, total mass, per-combo mass and weight-preserving filter helpers added;
- no production decision consumer has been switched to non-uniform weights yet.

Design source: `WEIGHTED_RANGE_DESIGN.md`

Local W0 gates:

- `python3 -m py_compile ranges.py tools/verify_weighted_range_adapter.py`
- `python3 tools/verify_weighted_range_adapter.py`
- `python3 tools/regress.py check --baseline current`

W0 exit condition is exact existing regression behavior plus adapter contract PASS. Then W1 converts weighted sampling consumers one family at a time.

## Balance status

**NOT TUNING YET.**

VPIP/PFR/bluff/personality ratios and strategic coefficients remain untouched until the architecture/wiring audit closes.
When that phase begins it must be announced explicitly as: **“이제부터 튜닝 단계.”**

## Documents

- Current structural map: `DECISION_ARCHITECTURE_AUDIT.md`
- Current F7-B work: `F7B_MULTIWAY_DOWNSTREAM_AUDIT.md`
- Dead/duplicate ledger: `AUDIT_LEDGER.md`
- UI current guide: `ui/README.md` (play-only; no watch mode / no play key)
- Tool classification: `tools/README.md`

Historical result/design markdown files remain for evidence. Their presence does **not** mean they are current work.


## Branch hygiene

Branch lifecycle is part of the project plan, not an afterthought.

- **Only active canonical line:** `chatgpt/decision-architecture-audit-20260926`
- PR #11에서 최신 엔진과 최신 playable UI를 한 history로 통합했다.
- `chatgpt/ui-bot-pipeline-20260927`은 호환 ref / 삭제 후보이며 새 커밋 금지.
- TDA temporary branches는 이미 merge/deletion 완료.
- 새 temporary branch는 명시적 이유와 종료 조건이 있을 때만 만든다.
- 기능 완료에는 verification + canonical 반영 + cleanup이 포함된다.

See `BRANCH_POLICY.md`.


## Tournament position / blind system — CLOSED / promoted

The earlier physical-button-only hotfix was insufficient. The tournament position layer was redesigned around the 2026 Poker TDA dead-button model and locally verified, then merged to the canonical engine line in PR #9 / merge `4b601b8b`.

Implemented:
- physical BTN/SB/BB anchors; BTN and SB may be dead/empty;
- BB obligation is the rotation axis;
- BB bust => old BB physical seat becomes dead SB, old UTG becomes BB;
- SB bust => dead BTN as required;
- TDA Rule 36-B vacant-seat BTN advance while preserving blind progression;
- 3-handed → HU transition and HU BTN=SB / no consecutive BB;
- broken-table Rule 11 seat restrictions and RNG assignment;
- balance Rule 12-A: next-BB player moves, destination is worst position, never SB;
- no-bet showdown order from physical first seat left of BTN;
- split-pot odd chips from first winner left of BTN;
- live-state schema persists `button_seat/sb_seat/bb_seat` with one-time legacy migration;
- bot-only tables and HERO tables use the same explicit hand layout.

Design source: `TDA_POSITION_DESIGN.md`

Promotion gates passed locally on 2026-09-27:
- `tools/verify_tda_dead_button.py`: 16 checks PASS
- `tools/verify_tda_live_integration.py`: PASS
- `tools/verify_button_rotation.py`: PASS
- changed Python modules compile cleanly

Containment proof after merge: canonical is ahead of `chatgpt/tda-position-engine-20260927` with temp behind=0. The temp branch is now deletion-only.

## Latest playable checkpoint

As of 2026-09-27 engine and playable UI share the same unified history:

```
chatgpt/decision-architecture-audit-20260926 @ 0b919b62
```

This contains:
- B1D defend rewire and current architecture-audit engine;
- W0 weighted-range representation foundation;
- lobby/profile/history and approved visual layer;
- bot-action streaming and playback hardening;
- parallel HERO/OTHER round settlement;
- TDA dead-button position/blind system;
- tournament-info menu and right-swipe full standings.

The old UI-only branch name is no longer a separate source of truth.
