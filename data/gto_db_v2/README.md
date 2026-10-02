# T2 GTO DB v2 (canonical spot_key)

Lookup key for every T2 GTO result = `spot_key(canonical_state(...))` from `tools/gto_db_v2/spot_key.py`.
File paths, solver run directories, legacy `spot_id` strings and other arbitrary ids are never lookup keys.

- `solutions.jsonl` (created on first add): append-only, schema `gto_solution_v2`
  (`spot_key`, `canonical_state`, `spot_label` (display only), `quality`, `source`, `strategy`, `solution_id` = sha256 of content, `added_at`).
- Legacy `data/gto_db/preflop_9max_pushfold_v1.jsonl` (616 rows, branch `chatgpt/gto-reference-20260928`) is not modified or moved.
  `tools/gto_db_v2/index.py` reads it in place when present, otherwise from its pinned git blob
  `003078a5edc81bc45cbe157c824a66799e15055e`; bytes must match sha256 `bacf94e9…16c87`. Each row is mapped to its canonical spot_key
  (616 distinct keys, tier 4 external approximation) and queried together with v2.
- Skip: `need_compute(state)` is false when any solution (legacy or v2) exists for the spot, unless the target quality is strictly higher.
- Upgrade: `add_solution` appends a strictly better solution; nothing is deleted or rewritten; `lookup` returns the best, `all` returns every one.
- Quality order: tier (1 exact full tree converged, 2 converged abstracted tree, 3 approximate / capped, 4 external reference),
  then exploitability (% pot), then earlier `added_at`. Multiway research approximations are tier 3 at best and never labelled GTO.
- The key encodes the game state only (players, positions, blinds, ante model, stacks, ICM, rake, full preflop history incl. folds, hero).
  Action menu / abstraction / convergence live in `quality` and `source`.

No A4c / research result is exported here until its verdict is confirmed.

## Decisions (2026-10-03)

- `tools/gto_db_v2/spot_key.py` (sk1) is the only canonical spot address for the T2 GTO DB. The Termux-era
  `tools/gto_db_schema.py` sha256 address (branch `chatgpt/gto-db-worker-v1-20261003`) is deprecated; it is used only to
  verify and read old files during migration.
- Legacy 616 stays a pinned, read-only source (no move to or from `chatgpt/gto-reference-20260928`).
- Termux worker spots (30bb x44 now; 25/40/20bb in progress) are imported with `tools/gto_db_v2/migrate_termux_v1.py` after the
  worker finishes: strategies verbatim (no re-solve), old address checked, canonical history checked, expected count per stack,
  duplicate sk1 keys abort the run, appends only through `Index.add_solution`, round trip verified value by value.
  Old `data/gto_db/spots` files are not deleted or changed before the migration is verified.
- `Index.need_compute(state, target_quality)` requires the target quality; workers must pass the quality they will produce.
- T2 `gto.py` runtime lookup is a separate later step, after migration and lookup parity.
