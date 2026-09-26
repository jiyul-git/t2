# CURRENT STATUS — READ THIS FIRST

이 파일이 현재 작업 상태의 **첫 번째 기준 문서**다.

## Source of truth

- Repository: `jiyul-git/t2`
- Active branch: `chatgpt/decision-architecture-audit-20260926`
- 개발 원본 폴더: `~/t2`
- 실제 플레이 실행폴더: `~/t2_play`
- `~/t2_play_src` 같은 추가 clone은 사용하지 않는다.

Git 커밋 해시는 계속 바뀌므로 **브랜치 HEAD가 최신 원본**이다. 플레이할 때는 `~/t2`를 pull한 뒤
`ui/tools/setup_run_dir.sh ~/t2_play`로 실행폴더만 갱신한다.

## Architecture audit

### CLOSED / production verified

- Preflop P1-P6 structural routes
- Postflop F1-F7 structural routes
- F7-B1A multiway relative-strength consumer
- F7-B1B1 multiway range-advantage consumer
- F7-B1C12 blocker-effect judgment lifecycle
- F8 side-pot plumbing stages already marked closed in their audit docs

### IN PROGRESS — do not call complete

**F7-B1D: empty/partial opponent-range semantics**

Current finding:

- live incomplete examples observed so far were heads-up, not true multiway partial pools;
- 11/11 HU empty-seat cases originated at `preflop_range`;
- all 11 were reconstructed as 3bet;
- continuous 3bet interval was positive but narrower than the discrete AA percentile bin;
- current downstream fallback can replace missing opponent union with hero's own range;
- `tools/measure_f7b_empty_range_overlap_candidate.py` is the current shadow experiment.

Separate open question: actual `defend_decision` uses stochastic mixed action probabilities while
`ranges.preflop_range` reconstructs a hard slice. That posterior-semantics mismatch is **not closed** by the bin-overlap shadow.

### OPEN after B1D

- F7-B nut semantics
- F7-B2 single-main-opponent aggregation
- F7-C emotion/tilt boundary
- F7-D execution/sizing boundary
- P7 / cold-reraise completeness revisit
- F8-ICM semantic closure
- final dead-code cleanup

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
