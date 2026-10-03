# T2 GTO value extractor — final goal (user, 2026-10-03)

T2 looks up a concrete situation (example: 9-max, UTG 30 bb opens 2 bb, everyone folds, BB 50 bb to act) and immediately gets the
action-frequency table (and EV where available) for that spot.

- Frequent spots are computed in advance and stored in the GTO DB (sk1 spot key, `tools/gto_db_v2`).
- Spots that are not stored are computed quickly on demand and returned (with their quality / status labels).
- Everything else (research panels, outer loops, audits) serves this: the calculator must produce trustworthy frequencies first.

## Consequences for the design
1. **Unequal stacks.** Real lookups have different stacks per seat (e.g. 30 bb opener vs 50 bb BB). sk1 already keys per-seat
   stacks; the GTOpen preflop engine v1 assumes equal stacks. Needed: either an effective-stack mapping with a declared near-match
   label, or unequal-stack support in the solver.
2. **Fast fallback.** A full 9-max preflop solve takes about an hour (100 iterations). On-demand answers need a subgame solve from the
   looked-up spot (upstream ranges taken from the DB) or a nearest stored spot returned as a labelled approximation.
3. **What to precompute.** Order the precomputation by how often each spot occurs in real T2 play (spot-frequency census from T2 logs).
4. **Trust first.** The 30 bb 9-max audit showed the current preflop terminal model is not trustworthy for hand-level frequencies; the
   continuation-model pilot (S) checks the fix before any bulk DB filling.
