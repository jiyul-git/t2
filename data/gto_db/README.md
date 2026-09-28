# T2 GTO Knowledge Database

This directory is the canonical **9-max MTT reference knowledge layer** for T2.

It is deliberately separate from:
- player-specific learned GTO memory,
- human reasoning,
- persona/style,
- opponent reads/exploit adjustments.

The database answers: **what reference strategy do we currently know for this spot, and how trustworthy/matched is it?**

It does not answer: **what will this particular T2 player do?**

## Current inventory

### `preflop_9max_pushfold_v1.jsonl`
Licensed short-stack reference imported from HoldemMath:
- 9-max
- 4/6/8/10/12/15/20bb
- no-ante and 0.1bb-per-player ante variants
- 616 spot records
- all 169 hand classes per spot
- first-in jam and call-vs-jam nodes
- CC BY 4.0 attribution preserved

This source is **near**, not exact for T2's 1BB big-blind ante.

### Solver-generated mid-stack data
Generated 9-max 20/25/30/40bb raise-tree spots will be added only after an independent public cross-check. Solver assumptions and convergence must travel with every record.

## Canonical matching order

1. exact 9-max MTT + 1BB BBA + matching stack/action tree,
2. exact 9-max MTT with documented but different ante,
3. validated 9-max solver output,
4. nearby public reference,
5. 8-max/cash/HU auxiliary evidence.

Never silently promote level 4/5 to level 1.

## Human-model interface

Future player memory should reference spot IDs from this DB and add player-side fields such as:
- studied/not studied,
- recall confidence,
- condition-match confidence,
- interpolation confidence,
- remembered strategy error.

Reference rows themselves remain immutable evidence.

See:
- `PRIORITY_9MAX_MTT.md`
- `SOURCES_9MAX.md`
- `index_9max_v1.json`
