# T2 Online Prototype Handoff

Date: 2026-10-05  
Status: **paused / archived for later**  
Branch: **`test-online`**  
Source snapshot: former `test2` at `0fa0f565acfdfcf660266eb49a81affc3b039156`

> `test` is reserved for Claude's current work and was not modified by this online prototype.

## Goal

The purpose of this branch was to prove that the existing T2 poker engine can be driven from a browser/server boundary, then extend that prototype toward two real human players in the same tournament field.

This is **not yet the production online architecture**. It is a working prototype and resume point.

## 1. Single-player online prototype

Main files:

- `online_server/app.py`
- `online_server/config.py`
- `online_server/auth.py`
- `online_server/registry.py`
- `online_server/engine.py`
- `online_server/play.html`
- `online_server/requirements.txt`
- `online_server/requirements-firebase.txt`
- `online_server/.env.example`
- `online_server/Dockerfile`
- `tools/verify_online_server.py`
- `tools/online_play.py`

Flow:

```text
Chrome / future Android client
        ↓
FastAPI online_server
        ↓
authoritative GameEngine
        ↓
existing live2 / T2 engine
```

Verified on Android Termux:

- FastAPI server starts
- Bearer-token dev auth works
- 9-max game creation works
- T2 engine reaches the first hero decision
- fold / call work
- next hand works
- invalid duplicate/no-decision actions are rejected
- Chrome touch controls work
- browser action buttons are locked while a request is in flight
- stale/no-decision browser state refresh is handled

Verification:

```bash
python3 tools/verify_online_server.py
```

Expected result:

```text
online_server verifier: PASS
```

## 2. Online state isolation

The online engine uses a separate state path instead of the normal local-play state.

Default data directory:

```text
~/.local/share/T2/online
```

`GameEngine` sets `T2_LIVE_STATE` before importing/using `live2`.

Important limitation:

- main online state is isolated
- some existing archive/sidecar files still use the repository-root namespace mechanism
- before production deployment, all persistent online data should be moved under one dedicated server data directory/database

## 3. Single-player prototype limitations

The single-player online path is still prototype-grade.

Known remaining work:

- durable request idempotency, not only stale action-token protection
- clean decision recovery after process restart
- production-safe server-side RNG/CSPRNG policy
- do not allow client-supplied deterministic seeds in production
- `live2` still relies on process-global state
- one uvicorn worker only until the game writer is separated
- production Firebase container/dependency setup still needs cleanup
- WebSocket path was scaffolded but the browser prototype mainly used HTTP
- private-state exposure must be audited again before public deployment

## 4. Two-human tournament prototype

The user clarified that the two humans **do not need to be forced onto the same table**.

Target behavior implemented on this branch:

- up to 2 authenticated human players
- both belong to the same tournament field
- remaining seats are bots
- humans are assigned by the normal field/table seating logic
- they may start on different tables
- they may later meet through normal table balancing
- if both humans are on the same table, `HandRun` pauses on either human-controlled seat
- each human only receives their own hole cards
- server rejects actions when it is not that user's turn
- human identity is tracked by PID rather than physical seat
- human tables are protected from being accidentally advanced again as bot-only tables during round settlement

Core engine changes:

- `play.Hand`
  - added `human_seats`
  - added `is_human(seat)`
  - old single-`hero` callers remain backward compatible
- `session.HandRun`
  - pauses on any `h.is_human(seat)`
  - decision payload includes `actor_seat` and `actor_pid`
- `fieldsim.Field`
  - added `human_pids`
  - added `human_tables()`
  - bot-table advance skips all protected human tables
  - human PID ownership persists through tournament movement
- `live2`
  - serializes/deserializes `human_pids`

## 5. Two-human server prototype

Added:

- `online_server/duo_engine.py`
- `online_server/duo.html`
- `tools/verify_duo_online.py`

HTTP API:

```text
POST /v1/duo/join
GET  /v1/duo/state
POST /v1/duo/action
POST /v1/duo/reset
GET  /duo
```

Current test setup:

- default tournament: 18 entries
- table format: 9-max
- two humans + 16 bots
- local dev identities:
  - base dev token + `.p1`
  - base dev token + `.p2`

The browser UI lets one browser act as p1 and another as p2.

## 6. Two-human round model

The current duo engine uses a simple synchronization barrier:

1. interactive human tables are built from the same field snapshot
2. each human table progresses until its human decisions are resolved
3. once all human-owned tables in that round finish, their results are merged
4. bot-only tables are advanced
5. bust collection / balancing runs
6. the next synchronized round begins

This is intentionally conservative for the prototype.

It is **not yet the final realtime tournament scheduler**. The existing virtual-clock/background-table system can later replace this barrier.

## 7. Two-human verification result

The verifier intentionally finds a deterministic seed where p1 and p2 start on different tables.

Command:

```bash
python3 tools/verify_duo_online.py
```

Verified result on Termux:

```text
duo online verifier: PASS (seed=6, actions=2, round=2)
```

This confirmed:

- two human PIDs were preserved
- humans were on different tables
- both could make decisions
- both interactive tables settled into one tournament round
- total chip count remained conserved
- user-scoped public state did not expose seat hole-card fields for opponents

## 8. Dev-auth note

For the two-browser local test, `online_server/auth.py` accepts:

```text
<base-dev-token>.p1
<base-dev-token>.p2
```

as two distinct dev identities.

This is only for local testing. Production should use real Firebase/other account UIDs.

## 9. Browser prototype routes

Single-user prototype:

```text
/
```

Two-human prototype:

```text
/duo
```

These are test UIs. The intended future direction is to reuse the existing polished `ui/web` lobby/table UI rather than continue building these temporary pages.

## 10. Important unfinished user requirement

Immediately before pausing the online work, the user requested that players **should not have to wait for the other human to be connected**.

Desired future behavior:

- a registered/known human tournament participant should not block the tournament just because their browser is offline
- each player should be able to connect later and resume their own seat
- when a human is disconnected, the server needs an explicit policy for that seat
  - sit-out / auto-fold / timeout behavior
  - this must not be silently replaced with normal bot strategy
- tournament progression should not depend on both browsers being simultaneously online

This requirement is **not implemented yet** in the current duo prototype.

## 11. Production direction if work resumes

Recommended next steps:

1. replace the temporary `/duo` UI with the existing `ui/web` T2 UI
2. implement persistent user/account identity
3. let tournament participation exist independently of browser connection
4. implement reconnect and server-side action timeout/sit-out rules
5. add durable idempotent mutation IDs
6. separate the authoritative game writer from FastAPI request workers
7. move persistent game/account/history data to a production data store
8. deploy to a VPS with HTTPS
9. add Firebase login only after the local multiplayer state model is stable

## 12. Branch handling

Online work is archived under:

```text
test-online
```

Do not merge this branch into `test` while Claude's work there is still active.

If online work is resumed later, start from this document and verify both:

```bash
python3 tools/verify_online_server.py
python3 tools/verify_duo_online.py
```

before making further changes.
