# 9-max baseline migration

The target baseline for the main development and money-jump experiments is
9-max.

## Why this migration was required

The engine position ladder already supported 9 players, but the field simulator
used a module-level `MAXSEAT = 8` for table creation and balancing.  The
standard format also declared 8 seats.  Therefore the money-sizing measurements
on seeds 92100..92119 and 92200..92219 were 8-max measurements.

Those measurements remain useful for harness/mechanics validation, but their
frequencies, positional distributions, and EV estimates are not final evidence
for the 9-max target and must be remeasured after this migration.

A second defect existed after tables became short-handed: `table.orders(n)`
had explicit ladders only for 2 and 6..9 players.  Three-, four-, and
five-handed tables silently fell back to the 8-max position labels.  The action
order happened to remain usable, but labels and therefore RFI/defend/range
logic were wrong.

## Migration rules

- `table.orders(2..9)` now has an explicit ladder for every player count.
- `fieldsim.Field` gets table capacity from `fmt['seats']`.
- `standard` is the project's default 9-max format.
- Existing alternate 8-max formats remain 8-max unless their format definition
  is intentionally changed later.
- live-state dumps store `max_seat`; legacy dumps infer it from their saved
  seat-slot arrays so an in-progress old 8-max game is not silently converted.
- UI decision views receive the actual table capacity instead of a hard-coded
  eight slots.
- inferred defend ranges and all-in calloff thresholds receive the actual
  table size and ante state.

## Validation before expensive reruns

Run `tools/verify_9max.py` first.  Only after it passes should money-sizing
structural and behavioral counterfactual measurements be rerun on 9-max.


## Tool policy

Current-baseline tools follow the selected format seat count.  With the default
standard format they therefore run 9-max.  Historical preregistered
counterfactual tools whose published results were produced at 8-max remain
explicitly locked to 8 seats for reproducibility; their outputs are not used as
new 9-max evidence.

The old regression baseline remains in `tools/baseline.json`.  New baseline
fingerprints use `tools/baseline_9max.json` so the intentional 9-max migration
does not overwrite the historical 8-max reference.

## Initial table balance

Field construction performs one balance pass before the first hand.  This
prevents cases such as 100 entries at 9-max from producing an initial
9x11 + 1 layout in which the lone player would otherwise skip the first hand.


## Initial balance scope

The pre-first-hand balance pass applies to every format, not only 9-max.
Its purpose is format-independent: a remainder table with one player must not
skip the first hand.  Therefore alternate 8-max formats can also have a
different initial table distribution than the historical behavior (for example,
17 entries no longer start as 8/8/1).  This is intentional and should be treated
as a behavioral baseline change for those formats as well.

Initial equalisation is setup, not an in-tournament table move.  It must not
increment `hero_moves` or emit a table-move note.
