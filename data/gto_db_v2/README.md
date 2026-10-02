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
