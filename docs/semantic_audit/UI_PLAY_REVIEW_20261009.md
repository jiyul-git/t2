# UI play review, 2026-10-09 KST

Reviewed the working-tree version of test3 published as 42f8261 in the actual
browser UI. Played/observed 9-max turbo HAND 17–21 and inspected their completed
engine archives alongside the UI history and Plan traces. Manual choices included
T5o UTG+1 fold, 84o UTG fold, KTo BB fold against a BTN isolation and SB call,
and AQo BTN call / turn check. Some decisions expired during code inspection;
this is not a five-hand uninterrupted human speed benchmark.

## Confirmed fixes

- Closed ranking drawer was visible outside the centered desktop app. Hidden
  drawers now have hidden visibility and disabled pointer events; opening restores both.
- Hero action clocks now use the same server-time basis as bot replay, and remain
  hidden until the hero action starts. Bot wait is not displayed as hero thinking time.
- Admission's waiting overlay was left on screen after the server supplied a playable
  decision. A non-waiting response dismisses that overlay, without dismissing a
  different sheet the player has opened.
- Waiting-state polling also overwrote the history sheet every three seconds.
  Polling now updates only its own waiting sheet, preserving an open review/settings sheet.
- History's empty result board fell back to the engine's full predetermined board.
  History now follows only the actual result board, like the live result renderer.
  Missing legacy result boards conservatively render empty rather than future cards.
- Scheduled games reused the engine archive, mixing earlier HAND 97–103 into this
  event. New records include tournament_id; history selects the active event.
  Untagged records remain usable for standalone legacy games, but cannot safely be
  attributed to a scheduled event and are excluded there. No old files are rewritten.
- HAND 18 B28 KQs passed the river aggression draw, but its two-street bluff size
  was zero and it checked. A size_veto trace now explicitly explains this resolution.
  The action policy and random draws are unchanged by this recording change.

## Poker observations

HAND 17 (113a7511e456): B7 QJ opened 600 at 100/300, bet 900 on 9h6d7h,
then 2600 on Qd, and checked 5s river. B28 A9 called twice. The line is readable:
flop continuation bluff, turn top-pair value, river showdown. Plan confirms the
turn strength upgrade and the river thin-value rejection.

HAND 18 (12e5937e4693): B28 KQs called a 2800 squeeze, bet 2300 on 7sAd7h
and 4100 on 7c, then checked 2c. This is an ambitious two-street bluff; the
river check is a size-budget decision, not a failed 61% probability draw.
B17 KQo calls used distorted perceived pot odds, not a strong bluff-reading
argument. Do not describe those calls as proven bluff catching.

HAND 19 (7595ca32f61c): B16 HJ 83o limp/called a 4BB BTN isolation, then
checked down. Its pf_range knowledge was 7.6 but the habit-limp branch permits
weak-hand mistakes. This remains a qualitative watch item; a single occurrence
is insufficient to choose a new global coefficient floor or erase a personality.

Across these five hands, bots had 40 preflop opportunities: 12 voluntarily
entered (30%) and 6 raised (15%). This tiny single-table sample does not establish
long-run personality frequencies. No new frequency coefficients were tuned to it.

Cold scheduled admission still requires actual catch-up computation. Correcting
the stale waiting overlay does not remove this work or make the server persistent.

## Validation

- python ui/tools/verify_play_review.py: event isolation, preflop/flop board
  privacy, legacy standalone records, zero-size veto and unchanged RNG.
- node ui/tools/verify_action_clock_js.js: pre-start hiding, server clock boundaries,
  one timeout submission, waiting-sheet cleanup and other-sheet preservation.
- node --check ui/web/app.js; Python compilation of changed modules.
- python tools/verify_trace_schema.py: PASS, including current archive round-trip.
- python tools/verify_review_reasoning.py: PASS, 3600 sizing cases and historical
  HAND 99 replay; corrected B14 opens 1300, isolated B13 5100 target becomes 5500.
- Browser reload visibly verified the closed drawer fix. Re-entered the updated
  server to check event-filtered history; cold-start catch-up remained observable.
