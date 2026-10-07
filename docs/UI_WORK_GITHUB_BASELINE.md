# UI Work GitHub Baseline

Updated: 2026-10-07

This document is the starting assumption for any ChatGPT Work / UI task on T2.

## Repository and branch

- Repository: `jiyul-git/t2`
- Default GitHub branch is `master`, but **UI/integration work must use `test` unless the user explicitly says otherwise**.
- Do not silently switch to `master`, `test2`, `test3`, or `test-online`.
- At the time this document was written, `test` contains `master` and is substantially ahead of it. Other test branches have diverged and are for separate experiments.
- Before editing, always verify the active branch and HEAD.

## GitHub search limitation

The GitHub connector currently reports `is_code_search_indexed=false` for `jiyul-git/t2`.

Therefore:
- A failed/empty GitHub code-search result does **not** mean a file/function is absent.
- Prefer direct file reads when paths are known.
- In a cloned workspace, use `git grep`, `find`, or direct paths instead of depending on GitHub code search.
- Never create replacement files just because code search returned no results.

## Current UI entry points

The main mobile table UI is under:
- `ui/web/index.html`
- `ui/web/style.css`
- `ui/web/theme.css`
- `ui/web/app.js`
- `ui/web/visuals.js`
- `ui/web/assets/`

Current visual theme is still the Hanok layer. The next visual direction is an **airport gate / boarding waiting-area atmosphere**, not a premium airport lounge.

## Change isolation

For visual redesign:
- Prefer `theme.css`, HTML presentation markup, `visuals.js`, and assets.
- Treat `app.js` as gameplay/state behavior. Do not change it for purely visual work unless unavoidable.
- Do not reimplement poker rules or infer state in the frontend. The latest server JSON remains the UI source of truth.
- Preserve existing action clocks, tournament clocks, legal-action behavior, replay timing, table movement, and state synchronization unless the user explicitly asks to change those behaviors.

## Character direction

- Keep the existing stable portrait allocation behavior.
- Static character art is acceptable first.
- The intended character style should gain depth/volume while remaining illustration-like rather than becoming realistic 3D.
- Do not add hair animation.
- Subtle cheek/breathing motion may be added later; it is not required for the first static pass.

## Validation

The `test` branch UI smoke workflow runs:
- Python compile of `fieldsim.py`, `live2.py`, and `ui/server/ui_server.py`
- `ui/tools/verify_action_timeout.py`
- `ui/tools/verify_clock_ui.py`
- `ui/tools/verify_vclock_finish_ownership.py`
- `ui/tools/verify_async_refill.py`
- `ui/tools/verify_vclock_session.py`
- `ui/tools/verify_ui.py`

Run the same checks locally when possible before treating GitHub Actions as the only source of truth.

The workflow itself has a 15-minute timeout. A run that never obtained a runner / never executed test steps is infrastructure evidence, not evidence that the code is wrong. Do not edit code merely to react to a non-executed CI run.

## Work session protocol

1. Open/clone `jiyul-git/t2`.
2. Checkout `test`.
3. Verify branch + HEAD + clean/known working tree.
4. Read this file.
5. Inspect the actual target UI files directly.
6. Make the smallest visual change that satisfies the requested screen.
7. Preview the UI at mobile widths first (360–412 px).
8. Run local UI verification.
9. Commit only the intended UI files.
10. Report exact commit SHA and changed files.

Do not spend the session rediscovering repository access or guessing which branch is current.
