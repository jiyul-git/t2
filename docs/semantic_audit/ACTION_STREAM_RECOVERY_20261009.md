# Action stream delay recovery (UI v85)

## Observed report and scope

The supplied 15.666567-second Samsung Browser recording shows a river board,
pot 2,400, and no subsequent table action while the tournament clock advances.
The corresponding production standard-event timing record was not available
in this session. The recording alone does not establish whether that entire
interval was computation, intended bot time, or buffered transport.

Three concrete defects were found in the current test3 code:

* `callStepStream` waited only for the NDJSON transport. A proxy retaining
  headers/chunks could hide already-computed actions and the final result
  indefinitely. There was no independent progress recovery.
* A delayed `stream_start.server_now_ms` was treated as current time when
  received. Buffering could rewind the UI clock and extend absolute waits.
* `/api/step-stream` was absent from `PLAY_PATHS`, so its long-running request
  did not protect the player-presence predicate.

## Change

The client submits each action once with a random request ID. A short-lived,
bounded in-memory mailbox publishes the same public start/action/final
messages before socket writes. `/api/step-progress` reads that mailbox without
the gameplay lock or engine execution. The client polls during the outstanding
action and merges both transports by action sequence number. Polling never
reposts the action. Either transport can finish the request; the blocked stream
is aborted when replay finishes. Bot absolute action deadlines remain intact.

Old streamed timestamps no longer set the current clock. Fresh readiness and
progress responses supply time. JSON responses disallow caching. The stream
and its progress reads now count as play presence.

No strategy, bot thinking-time distribution, hand IDs, tournament clocks,
table movement rules, wallet, or archived hand data were changed.

## Verification

`verify_step_progress_js.js` executes the actual client caller with a stream
whose headers never arrive. Before the patch, it fails with
`stream remained blocked`; after the patch, the final frame appears using
progress, with one action POST and one application of the bet/result.
It also checks late duplicate delivery and the old start timestamp.

`verify_step_progress.py` exercises the actual HTTP handlers with a controlled
engine paused while holding the gameplay lock and a failed stream socket.
The concurrent progress endpoint responds, retains both actions and final,
protects presence, and respects retention bounds.

Existing resume UI, fresh resume snapshot, zero-bank action clock,
continuous tournament clock, and same-event reentry verifiers pass.
`verify_action_clock_js.js` needed two missing no-op timing stubs for its
existing apply-handler fixture; its production assertions are unchanged.

Operating-server deployment is pending. The browser rejected administrator
access because permission was declined; no alternate access path was used.
This patch does not establish that all production CPU/calculation delays or
initial admission synchronization are resolved.
