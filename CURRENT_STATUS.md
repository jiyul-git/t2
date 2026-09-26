# CURRENT STATUS — READ THIS FIRST

이 파일이 현재 작업 상태의 **첫 번째 기준 문서**다.

## Source of truth

- Repository: `jiyul-git/t2`
- Active branch: `chatgpt/decision-architecture-audit-20260926`
- 엔진/배선 감사 원본: `~/t2`
- UI 소스 원본: `~/t2_ui_src`
- 실제 플레이 실행본: `~/t2_ui_beta`
- 임시 clone(`~/t2_ui_stream_test`, `~/t2_play_src` 등)은 사용하지 않는다.

브랜치 역할을 섞지 않는다.
`~/t2`는 엔진 감사 브랜치에 고정하고, UI 작업은 `~/t2_ui_src`에서만 한다.
플레이할 때는 UI 소스에서 `ui/tools/setup_run_dir.sh "$HOME/t2_ui_beta"`로 실행본을 갱신한다.

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
- B1D5 proved the percentile-bin overlap fallback is **not behavior-preserving**:
  3/6 preregistered target hands changed directly on identical pre-hand state;
- B1D6 posterior audit: 11/11 observed actions had positive model-implied posterior mass;
- 9/11 cannot be represented exactly by a unique unweighted combo list;
- the other 2/11 are one-class AA posteriors, but the overlap fallback still has the wrong support;
- overlap fallback was exact in **0/11** cases and omitted as much as **89.813%** of posterior mass.

Conclusion: another hard-slice/bin patch cannot close B1D. B1D7 is active.
Step A (RNG-free defend-action likelihood shadow) passed locally with 164,444 scripted branch checks and 0 mismatches.
Step B rewires production defend execution to that shared helper while preserving the legacy RNG order;
exact action+sizing+RNG-state parity against checkpoint 5eb848c is pending.
Weighted-range representation/consumer migration starts only after Step B passes. Production ranges remain unweighted for now.

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


## Branch hygiene

Branch lifecycle is part of the project plan, not an afterthought.

- Engine active line: `chatgpt/decision-architecture-audit-20260926`
- UI active line: `chatgpt/ui-bot-pipeline-20260927`
- New branches require an explicit reason and exit condition.
- Temporary branches must be merged/cherry-picked/abandoned and then cleaned up.
- Every major phase closes with code + verification + docs + branch cleanup.

See `BRANCH_POLICY.md`.


## Tournament button / blind rotation hotfix — pending local verification

User observed consecutive SB in HAND 50 -> HAND 51 without evidence of a full table break.

Source audit found a real structural defect in the live field path:

- `fieldsim.Table.button` was stored as an index into a compressed alive-player list;
- table busts / balancing can change that list between hands;
- the same integer index can therefore point at a different physical seat on the next hand;
- `_play_table` also used `tb.players` append order while the hero path used physical-seat order,
  so the same button index had inconsistent meaning after player movement.

Fix on the active engine branch:

- persist a physical `button_seat` while retaining legacy `button` index for old saves;
- order live players by fixed seat;
- advance dealer by physical seat, not compressed-array index;
- use the same physical dealer in `live2` build/finish;
- choose the balancing source mover from physical button order;
- regression tool: `tools/verify_button_rotation.py`.

Production promotion is pending the local verifier result.


## Latest playable checkpoint

As of 2026-09-27 the canonical playable/UI line is:

```
chatgpt/ui-bot-pipeline-20260927 @ f9a4ed2
```

It contains the full `ui-recovery` lineage plus:

- new-game sidecar backup `fn` hotfix;
- physical dealer/button-seat persistence used by the live UI;
- side-seat chip/bubble fixes;
- bot-action server streaming;
- streamed transport/error hardening;
- new-street board reveal while the next bot computes;
- 1.5s action pacing overlap;
- short hero-action/new-street breathing pauses.

`chatgpt/ui-recovery-20260927` is fully contained in this line and is obsolete.
