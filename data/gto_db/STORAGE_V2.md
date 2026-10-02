# T2 GTO DB storage v2

## Fixed rules

1. A file path or sequence number is never a poker-state identity.
2. spot_key = sha256(canonical T2 state) is the address.
3. Canonical state uses T2 semantics: 9-max MTT, street, stack, position, public action history, raise-to BB coordinates, BBA target, ICM/rake state.
4. Solver/source assumptions do not change spot_key; they belong to a solution under the spot.
5. Existing preflop_9max_pushfold_v1.jsonl (616 records) is legacy canonical evidence. Do not rename, split, or rewrite it now.
6. New solver outputs go through tools/gto_db_schema.py and are stored under data/gto_db/spots/<2-char-shard>/<spot_key>.json.
7. Default workers skip an already stored canonical spot. Re-solving/upgrading a spot must be an explicit later operation; never silently overwrite a solution.
8. Multiple solutions may coexist under one spot when provenance/quality differs.
9. T2 lookup must use the same canonical-state builder. Display notation is separate from internal notation.
10. GTO reference data remains separate from human model / reads / tilt / exploit adjustments.

## Termux worker v1

tools/gto_db_worker.py uses the existing vendored GTOpen server. It is not a new solver.

Initial coverage:
- P1 unopened/RFI
- P3 clean single-open defense
- stacks requested by the worker, priority order supplied by the caller

The worker normalizes already-qualified existing pilot rows before solving and then computes only missing canonical spots.

The current GTOpen ante model is still a same-total-dead-money uniform-ante approximation, not exact T2 1BB BBA. This mismatch is retained in each solution's provenance/quality and must never be silently promoted to an exact BBA solution.

## Legacy migration

Do not physically migrate the 616-record legacy file merely for organization. A future unified index/lookup adapter should expose legacy and v2 sources through the same canonical lookup interface. Physical migration may be done later only as a verified, reversible migration.
