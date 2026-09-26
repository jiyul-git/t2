# UI CURRENT STATUS — READ THIS FIRST

UI는 엔진 감사와 별도 최신선으로 관리한다.

## Canonical refs

- Engine / architecture source of truth:
  `chatgpt/decision-architecture-audit-20260926`
- UI recovery / integration branch:
  `chatgpt/ui-recovery-20260927`
- Richest historical UI lineage to recover from:
  `chatgpt/fix-side-seat-overlay-20260924` @ `18e68ce`
- Earlier visual integration:
  `integration/ui-v49-money-jump-20260920`
- Old snapshot only:
  `ui-v33-snapshot-20260920`

Do **not** treat the historical UI branch as the engine source of truth.
It contains older engine/session commits. UI changes must be ported onto the current engine branch.

## Current UI already present on engine branch

- play-only local server at `http://127.0.0.1:8765`
- no play key / no watch mode
- current action/history/gameplay fixes on the audit branch
- hanok background
- teal felt / changsal card-back visual layer
- 9 portrait atlas
- portrait gaze
- hero portrait
- recursive web asset copy into the run directory

## Historical UI changes still missing or needing reconciliation

### A. Side-seat/table layout — RECOVER

Historical commits include:

- `98c1ea7` separate side-seat chips from board cards
- `9c43c1c` keep side-seat action bubbles clear of cards
- `7860961` move bot seats onto outside rail
- `4ad5516` / `7a99aa7` refine side-seat chip placement
- `eaa8a3f` shrink table inward along marked arrows

These are user-visible layout fixes and must be checked against the current 9-max screen before porting.

### B. Header/history/table viewport — RECOVER / VERIFY

- `9f49e43` fold history controls into top bar
- `cf234ca` remove log strip and use dynamic viewport height
- `eac1a95` compact top status bar
- `002676e` compact top controls
- final asset/layout bumps through `c2c7939`

Current branch still has older top/log layout, so this lineage is not fully integrated.

### C. Lobby / tournament selection — SEPARATE FEATURE SET

- `66aaca8` lobby route and tournament catalog API
- `777e221` lobby shell
- `b4bd8b9` / `d7bdc7f` tournament lobby and selection
- `1be3df7` return-to-lobby action

This changes routing/server behavior and must be recovered separately from table-only visual fixes.

### D. Profile / deck / theme preferences — SEPARATE FEATURE SET

- profile/settings lineage: `239705d` through `6be1ee5`
- card-back themes: `5a0dfa1`, `8687239`
- airport day/night themes: `4f7b62a`, `b0b14c2`, `eb12698`
- portrait crop/eye fixes: `b3e594e`, `50bb142`

The current branch restored the earlier 9-portrait layer but not all later corrections/preferences.

### E. Fullscreen — DO NOT RECOVER

- `aa64cb6` added fullscreen
- `932d93e` removed fullscreen

The historical lineage ends with fullscreen removed. Do not resurrect it.

### F. New-game hotfix — ENGINE/API, VERIFY BEFORE PORT

- `89a46a4` avoids undefined function in new-game sidecar backup

This is not a pure visual change. Compare against current `live2.py` before deciding whether it is still needed.

## Recovery order

1. lock current engine HEAD;
2. recover table-only layout fixes A+B on the UI recovery branch;
3. visual regression / mobile 9-max check;
4. recover portrait corrections and preference features D;
5. decide separately whether lobby C is still desired;
6. verify new-game hotfix F against current engine;
7. only after UI verification, port the verified UI commit(s) back to the engine branch.

## Rule

A UI commit is not "latest" merely because its branch name is newer.
`UI_CURRENT_STATUS.md` + `chatgpt/ui-recovery-20260927` define the current UI integration line.
