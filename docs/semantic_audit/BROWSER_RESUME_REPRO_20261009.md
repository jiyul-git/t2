# Browser resume reproduction, 2026-10-09 KST

## Actual UI observation

Baseline: test3 d1ff356 engine in a disposable preview, real backend,
44 bots plus HERO, turbo 9-max, timing enabled and async calculation enabled.
This reproduces closing the game tab, not Android force-stop or Android's
possible suspension/termination of a local server process.

- Late-registered in the event starting 07:15 KST. Observed initial admission
  waiting and then entered HAND 18. Manually folded Qd7c in SB against an open.
- Closed the only game tab at 2026-10-08T22:18:53.139Z (07:18:53.139 KST).
- Kept the server running with no game tab/HTTP presence. Read-only state-file
  observations confirmed offscreen=false and busted=false. No test action
  was posted while the tab was closed.
- Reopened /play. Return observation timestamp was 315.455 seconds after close.
  The table displayed HAND 25 without an admission synchronization sheet.
  Subsequent observation showed actual flop actions and '관전 중…'.
- The durable snapshot still had offscreen=false, busted=false and no pending
  virtual-clock settlement. The absent seat had lost blinds as play continued.

The reported repeat admission synchronization was NOT reproduced in this
continuously running server / direct /play return case. This does not establish
that the user's phone exhibited no problem: app shutdown, server suspension,
server restart, different installed code and the exact waiting text remain
unverified. Do not equate this negative result with a diagnosis of the phone.

## Separate confirmed bug and fix

The lobby's /api/enter endpoint unconditionally cleared _last, the worker and
the speculative clock buffer even for the same currently active, seated,
playing event. A handler-level regression exercising the real production
method failed before the change with ['worker', 'clock'] reset calls.

For that same live seat only, /api/enter now resumes without activation,
entry-request mutation, decision invalidation or calculation-buffer reset.
Initial/unseated admissions and offscreen takeovers retain their original reset
path. Different-event switching restrictions are unchanged. This removes a
confirmed source of unnecessary recalculation; it is not claimed to prove the
cause of the user's direct browser-return synchronization.

## Verification

- ui/tools/verify_same_event_resume.py: preserves the exact decision object,
  future and queued event coverage on live return; genuine admissions reset.
- Extended ui/tools/verify_scheduled_ui.py: real HTTP /api/enter followed by
  /api/state preserves token and the original armed action deadline.
- Updated scheduled HTTP verifier passed including absence, timeout,
  install/update/restart recovery, wallet persistence and offline bust/reentry.
- tools/verify_scheduled_tournaments.py: 38 tests pass.
- ui/tools/verify_play_review.py and verify_action_clock_js.js: pass.
- Python compilation and git diff --check: pass.
