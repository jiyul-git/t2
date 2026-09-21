# Money-open sizing — 9-max preregistration

Status: **locked before 9-max measurement**.

Behavior baseline: `7e40ba0` (verified 9-max regression baseline).
Counterfactual harness hardening: `19438e6`.

Production state remains:
- RANGE = LIVE
- SIZING = SHADOW
- LIMP = SHADOW

The earlier 92100..92119 structural run and 92200..92219 behavioral run were
8-max measurements.  They are retained as engineering/history evidence only
and are not confirmatory evidence for the 9-max target.

## Fixed game configuration

- entries: 100
- format: standard
- standard seats: 9
- rounds: maximum 260
- stop when remaining <= 8
- population: near-ladder unopened preflop non-all-in baseline raises with an
  actual applied baseline size
- stages: approach / bubble / itm / final9, using the existing tool definition
- production strategy is never changed by these measurements

## Phase S — structural 9-max revalidation

Fresh seeds: **93000..93019** inclusive.

Tool: `tools/money_sizing_batch.py`.

Required mechanical conditions:
1. zero engine errors / child failures;
2. at least one qualifying row;
3. shadow target >= 2 BB;
4. shadow target <= applied baseline target;
5. logged shadow target matches the registered formula within the existing
   tolerance;
6. same-state open-size skill 9 never produces a larger shadow target than
   skill 1;
7. output must include at least one UTG+2 qualifying row, proving that the
   measured population actually contains the 9-max-only early position.

This phase can invalidate the measurement harness but cannot promote sizing.

## Phase P — harness/runtime pilot

Fresh seeds: **93050..93053** inclusive.

Tool: `tools/money_sizing_cf_batch.py`.

The pilot is inspected freely and is **excluded from the primary behavioral
sample**.  Its purposes are only:
- prove the hardened paired harness executes on 9-max;
- check row yield and runtime;
- catch engine/harness failures before the confirmatory run.

Required harness conditions on every changed row:
1. same preflop log prefix before intervention;
2. same baseline proposed raise-to target;
3. same RNG state immediately before the intercepted apply;
4. identical dealt cards / hand hash in baseline and counterfactual;
5. intervention pinned to the original preflop Round only;
6. interception used exactly once;
7. counterfactual log records exactly the registered raise-to target;
8. table chips conserved in baseline and counterfactual;
9. no duplicate qualifying row for the same seed/hand/table;
10. zero engine/counterfactual exceptions.

If the pilot fails, the confirmatory seeds remain untouched until the harness is
fixed and independently reviewed.

## Phase C — primary behavioral paired counterfactual

Fresh untouched seeds: **93100..93139** inclusive (40 seed clusters).

The pilot seeds and all previous 8-max seeds are excluded.

Intervention:

    cf_target_chips =
        round(max(2 * BB, base_target_chips * size_factor_shadow))

Only the first qualifying unopened preflop raise target of the observed opener
is replaced.  All later decisions are recalculated naturally from the changed
betting state.  The baseline tournament continues unchanged and the
counterfactual hand is discarded.

Zero interventions (rounded target equals baseline) remain in the primary
population with paired delta 0.  Therefore the primary estimand remains
intention-to-treat over qualifying rows, not treatment-on-the-treated.

Primary outcome:

    paired_chip_delta_bb =
        CF opener final-stack change
        - baseline opener final-stack change

Uncertainty:
- cluster unit = tournament seed;
- use the tool's fixed 10,000-replicate seed-level percentile bootstrap;
- report the number of seed clusters and the interval.

Interpretation is locked:
- interval wholly below 0: evidence against sizing promotion;
- interval wholly above 0: chip-EV evidence supporting promotion;
- interval overlapping 0: **INCONCLUSIVE**, not evidence of no effect.

Forty seed clusters are used because the previous 20-cluster 8-max run produced
a wide interval and was not sufficiently discriminating.

Secondary outcomes remain descriptive only:
- changed-size count/rate;
- opponent calls;
- 3-bet/all-in response;
- downstream action/amount path changes;
- flop pot and opener flop SPR;
- winner-path changes;
- stage and position summaries, including UTG+2.

No secondary cutoff may be invented after observing Phase C.

## What this experiment does not establish

This is chip EV, not prize EV.  It does not justify a final promotion by itself
if prize-value evidence is still required.

The next independent stage, if warranted, is a final9-only exact-ICM paired
measurement using `icm.icm_equity` on the **entire remaining field stack
vector**, never `table_bf` on a partial table.

No 10+ player $EV proxy formula will be invented.
