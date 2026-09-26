# UI CURRENT STATUS — READ THIS FIRST

UI는 엔진 감사와 별도 최신선으로 관리한다.

## Canonical refs

- Engine / architecture source of truth:
  `chatgpt/decision-architecture-audit-20260926`
- **Only active UI line / current playable UI:**
  `chatgpt/ui-bot-pipeline-20260927`
- Current verified UI head at this checkpoint:
  `9230929`

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

## Side-seat checkpoint

Current active values after the latest user-visible adjustment:

- 9 o'clock chip lane: `x=22%, y=51%`;
- 3 o'clock chip lane: `x=78%, y=51%`;
- side action bubbles retain their dedicated side-seat vertical rule;
- bubble triangle tail overlaps the body by 1px more than before to avoid a visible gap.

Further chip/bubble movement should be based on an actual frame where the relevant
3/9 o'clock action is visible. Do not infer action bubbles from seat labels or stack text.

## Current streamed-play additions

The active UI line additionally includes server-driven bot-action streaming and playback hardening. Bot calculation overlaps the existing 1.5s action pacing; board transitions can render before the next bot finishes computing; short presentation pauses are UI-only and do not sleep the engine.

## Historical UI branches — deletion candidates

- `chatgpt/ui-recovery-20260927` — fully contained in `ui-bot-pipeline`
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
- Active UI line: `chatgpt/ui-recovery-20260927`
- Branch cleanup is part of phase closure.
- Historical branches are not to be used as runtime source-of-truth.
