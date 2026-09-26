# Parallel table round design

Status: implementation target for `chatgpt/parallel-tables-20260927`.

## Goal

Remove the end-of-hand bottleneck caused by computing all non-HERO tables only after the HERO table finishes.

A tournament hand number is treated as one **round**:

```
round snapshot
├─ HERO table (main process, interactive)
└─ all other tables (one worker process, existing table order)
        ↓
merge the two disjoint table results
        ↓
_collect_busts()
_balance()
        ↓
next round
```

The worker does **not** balance tables and does **not** collect busts. Those remain a single main-process operation after both sides of the round are available.

## Ownership

At round start, record the HERO table id and its pids.

Main/HERO branch owns:
- HERO-table player stacks
- HERO-table button / hand count
- HERO-table pid tilt state
- HERO read book / archive payload / UI result

Other-tables worker owns:
- player stacks for pids seated at every non-HERO table at round start
- button / hand count for every non-HERO table
- tilt state for those non-HERO pids
- bot-table log and worker notes

Shared tournament structure is not taken from the worker. Level, hand number, payouts/format, HERO movement count, and busted order stay on the main branch until final settlement.

## Snapshot semantics

Both branches start from the same field snapshot for the round.

Therefore eliminations, stack changes, ICM/remaining changes, and table balancing produced during this round affect strategy from the **next round**, not another table that is simultaneously playing this round.

The non-HERO tables remain sequential *inside the single worker*. This preserves their existing RNG/table order and avoids a second, unnecessary parallelization.

## Merge

The worker returns a delta-like payload, not an authoritative whole field:

- `base_key`
- `hero_table`
- `players` for non-HERO table pids only
- `tables` for non-HERO tables only
- `tilt` for non-HERO table pids only
- worker notes
- bot log

At HERO hand completion:

1. dump the main field after HERO-table result
2. replace only worker-owned player/table/tilt entries
3. reload the merged field
4. run `_collect_busts()` once
5. run `_balance()` once
6. persist/archive

A mismatched `base_key` is never merged.

## Worker lifetime

The UI server starts the worker as soon as a new round snapshot is saved, before the HERO table continues calculating its first actions.

If the worker is already complete when the HERO table finishes, merge immediately.

If it is still running, return the HERO result without blocking and keep the existing pending/fallback safety path. Before the next round starts, the result must be joined and merged.

After a server restart during an in-progress HERO hand, the current `st['field']` is still the round-start snapshot, so the worker can be restarted. If the HERO hand already ended, `others_base` is persisted specifically for fallback reconstruction.

## Invariants

- Worker never writes the live state file.
- Worker never changes HERO-table stacks/button/hands.
- Main branch never overwrites worker-owned table results during merge.
- Each pid belongs to exactly one side for a round.
- Bust collection and balancing happen only after both sides are merged.
- Chip total is conserved.
- A base-key mismatch fails closed and recomputes from the saved round snapshot.
- Existing `T2_UI_DEFER=0` path remains a synchronous fallback.
