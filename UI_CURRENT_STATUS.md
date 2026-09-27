# UI CURRENT STATUS — READ THIS FIRST

UI는 엔진 감사와 별도 최신선으로 관리한다.

## Canonical refs

- Engine / architecture source of truth:
  `chatgpt/decision-architecture-audit-20260926`
- **Only active UI line / current playable UI:**
  `chatgpt/ui-bot-pipeline-20260927`
- Current verified UI merge checkpoint:
  `ac7179e8` (PR #10, TDA positions + tournament info UI)

The user has designated this UI line as the latest version.
Do not recover older UI branches again unless a specific regression requires historical comparison.

## Current UI state

Already integrated on the active UI line:

- lobby/profile/history flow;
- play-only local table UI;
- current new-game flow;
- compact top status controls;
- reduced table viewport;
- 9-max fixed-seat presentation;
- hanok/background/card-back layer;
- approved portrait/character layer;
- side-seat chip separation logic;
- side-seat action-bubble separation logic;
- action-bubble tail connection fix;
- no fullscreen restore;
- no watch-mode restore.

Character/portrait assets and assignment logic remain frozen unless the user explicitly asks to change them.

### TDA tournament/UI checkpoint

Merged and locally verified on 2026-09-27:

- physical BTN/SB/BB anchors from the engine, including dead BTN and dead SB;
- dead BTN shown as `D` on the empty physical seat;
- dead SB shown as `SB · DEAD`;
- top field/ITM/rank text removed from the table chrome and moved into `...` tournament info;
- bot-action interval setting removed; UI pacing is fixed at 1.5s;
- result/auto-progress preference removed; next-hand progression is fixed;
- tournament info shows field, remaining, ITM, chip rank, stack/BB, average, level, blinds/ante, bubble and money-jump data;
- right swipe opens a separate full standings drawer with all bots' chip ranks, stacks, BB, table/seat and current position;
- parallel HERO/OTHER settlement remains intact.

Local gates passed: TDA core/live/button, parallel-table round, UI tournament panel. Cache tags: `style.css?v=49`, `app.js?v=65`.

The temporary branch `chatgpt/tda-position-ui-20260927` is fully contained after PR #10 and is deletion-only.

Character/portrait assets and assignment logic remain frozen unless the user explicitly asks to change them.

## Side-seat checkpoint

Current active values after the latest user-visible adjustment:

- 9 o'clock chip lane: `x=22%, y=51%`;
- 3 o'clock chip lane: `x=78%, y=51%`;
- side action bubbles retain their dedicated side-seat vertical rule;
- bubble triangle tail overlaps the body by 1px more than before to avoid a visible gap.

Further chip/bubble movement should be based on an actual frame where the relevant
3/9 o'clock action is visible. Do not infer action bubbles from seat labels or stack text.

## Current streamed-play additions

The active UI line includes server-driven bot-action streaming and playback hardening. Bot calculation overlaps the existing 1.5s action pacing; board transitions can render before the next bot finishes computing; short presentation pauses are UI-only and do not sleep the engine.

It also includes the **parallel table round** implementation that was previously isolated on `chatgpt/parallel-tables-20260927`:

- HERO table and all non-HERO tables branch from the same round-start snapshot;
- the non-HERO worker starts at round start, not after the river;
- ownership-based merge restores only worker-owned player/table/tilt rows;
- `_collect_busts()` and `_balance()` run once after merge;
- base-key mismatch fails closed;
- side-seat chip fix remains present.

This was merged into the canonical UI line in merge commit `13505d64`. The old parallel branch is no longer an active source.

## Cleanup contract — mandatory phase closure

Branch cleanup is not cosmetic. It prevents an implemented feature from being stranded on a side branch and later mistaken for "never implemented".

For every temporary branch, phase closure requires all of the following:

1. **Containment proof** — compare temporary branch -> canonical branch. Safe deletion requires `behind=0` from the temporary branch's perspective (canonical contains it). If branches diverge, inspect unique commits before doing anything.
2. **Feature checklist update** — write the merged feature into this file on the canonical branch, with the canonical merge/head commit.
3. **Canonical-only continuation** — after merge, no new commits may land on the temporary branch.
4. **Deletion candidate immediately** — mark the old branch for deletion in the same phase; do not leave it around as an ambiguous alternate source.
5. **Runtime provenance** — `~/t2_ui_src` must track only the canonical UI branch. `~/t2_ui_beta` is runtime state, not source-of-truth.
6. **No cleanup by guess** — never delete a branch merely because its name looks old. Prove containment or explicitly preserve its unique commits first.

When starting work after any pause, read this file first and verify the canonical branch/HEAD before inspecting historical branches.

## Historical UI branches — deletion candidates

- `chatgpt/tda-position-ui-20260927` — fully contained after PR #10 / merge `ac7179e8`
- `chatgpt/ui-recovery-20260927` — fully contained in `ui-bot-pipeline`
- `chatgpt/parallel-tables-20260927` — fully contained in `ui-bot-pipeline` after merge `13505d64`
The following branches are no longer active UI sources after the user confirmed
`chatgpt/ui-recovery-20260927` as latest:

- `chatgpt/fix-side-seat-overlay-20260924`
- `chatgpt/lobby-shell-20260924`
- `chatgpt/avatar-layer-system-v1-20260924`
- `chatgpt/fix-newgame-fn-20260924`
- `codex/hanok-9max-visuals-20260924`
- `integration/ui-v49-money-jump-20260920`
- `ui-v33-snapshot-20260920`

Their useful history is already represented by commits and the current recovery line.
Do not create replacement UI branches for small fixes.

## Rule

- Active engine line: `chatgpt/decision-architecture-audit-20260926`
- **Only active UI line:** `chatgpt/ui-bot-pipeline-20260927`
- Branch cleanup is part of phase closure, not a later housekeeping task.
- Historical/temporary branches are never runtime source-of-truth.
- Before saying a feature is missing or reimplementing it, search historical branches/commits and check containment first.
- Character/portrait assets stay frozen unless the user explicitly asks to change them.
