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

Locked invocation includes `--require-position UTG+2`; absence of a qualifying
UTG+2 row is therefore a nonzero structural failure, not a manual post-hoc
inspection.

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
4. immutable dealt-card/hash signature captured before replay is unchanged
   through the counterfactual replay;
5. the first betting Round must have the exact expected preflop seat order,
   and intervention is pinned to that Round object only;
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

Uncertainty (see Amendment A1 below):
- the primary point estimate is the equal-weight mean over qualifying rows;
- the tournament seed is the RESAMPLING unit, not the averaging unit;
- use the tool's fixed 10,000-replicate whole-cluster percentile bootstrap:
  each replicate draws N seed clusters with replacement from the N observed
  clusters and keeps every qualifying row inside each drawn cluster, so the
  replicate statistic is the row-level mean of all sampled rows;
- report the number of seed clusters and the interval;
- row-level median / p10 / p90 are descriptive only.

Validity is checked before interpretation.  **Any** engine error, batch child
failure, global harness error, or row-level harness error in Phase C invalidates
the entire confirmatory run.  In that case any printed means or bootstrap
intervals are diagnostic only and must not be interpreted for promotion; the
tool prints `INVALID` and exits nonzero.  The confirmatory seeds may be rerun
only after the harness defect is fixed and independently reviewed.

If and only if the run is valid, interpretation is locked:
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


## Amendment A1 — estimand/uncertainty alignment (before any Phase C seed ran)

Recorded 2026-09-21, before `93100..93139` were touched.  This amendment does
not change any acceptance threshold and was not written after observing a
confirmatory result.

What was found.  At the Phase 4 pre-run integrity gate, using **pilot-only**
data (seeds 93050/93051, which are excluded from the primary sample), the tool
printed a row-equal-weight point estimate next to an interval produced by a
bootstrap over seed **means**.  Those are two different estimands whenever
clusters hold unequal row counts: on that pilot data the row-level mean was
0.041090 while the seed-equal-weight centre was 0.033621.

State of the confirmatory sample.  None of the primary seeds `93100..93139`
had been run; no checkpoint, row file, or output existed for any of them.

What is preserved.  The originally locked estimand stands unchanged: the
primary quantity is the **intention-to-treat mean over qualifying rows**,
with zero-intervention rows retained at paired delta 0.  The point estimate
remains the row-equal-weight mean.

What is corrected.  Only the uncertainty calculation.  The bootstrap now
resamples whole tournament-seed clusters and keeps every qualifying row inside
a drawn cluster (a cluster drawn twice contributes its rows twice), so each
replicate statistic is the row-level mean of the sampled rows -- the same
functional as the observed point estimate.  `reps = 10000` and
`rng_seed = 922002026` are unchanged.  Unequal cluster sizes therefore enter
the interval exactly as they enter the point estimate.

Reporting.  `primary_row_mean`, `seed_clusters` and `bootstrap95` are the
primary line.  Row-level median / p10 / p90 are printed separately and labelled
descriptive only.  `primary_interpretation` uses the cluster-bootstrap interval
and nothing else, after the validity gate.

Why this is a clarification and not a post-hoc rule change.  "cluster unit =
tournament seed" was always a statement about dependence between observations
inside one tournament, i.e. about the resampling unit; it was never a
redefinition of the estimand, which the same document had already locked as
ITT over qualifying rows.  The implementation contradicted that lock, and the
contradiction was fixed before the confirmatory data existed.


## Locked commands

Structural Phase S:

    python3 -u tools/money_sizing_batch.py \
      --entries 100 --rounds 260 --until-remaining 8 --fmt standard \
      --seed-start 93000 --seeds 20 --workers 2 \
      --require-position UTG+2 \
      --workdir money_sizing_9max_struct_93000 \
      --out money_sizing_9max_struct.jsonl

Pilot Phase P uses 93050..93053 only.  Running one pilot seed first is allowed
because all pilot seeds are excluded from Phase C.

Confirmatory Phase C:

    python3 -u tools/money_sizing_cf_batch.py \
      --entries 100 --rounds 260 --until-remaining 8 --fmt standard \
      --seed-start 93100 --seeds 40 --workers 2 \
      --workdir money_sizing_9max_cf_93100 \
      --out money_sizing_9max_cf_all.jsonl
