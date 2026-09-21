# Money-open sizing — 9-max Phase C result

Status: **SEALED — INCONCLUSIVE**

## Provenance

Preregistered design:
- `MONEY_SIZING_9MAX_PREREG.md`
- Phase C seeds: `93100..93139` inclusive
- 40 tournament-seed clusters
- primary estimand: row-equal-weight ITT mean over qualifying rows
- zero-intervention rows retained with paired delta 0
- uncertainty: 10,000-replicate whole-seed-cluster percentile bootstrap
- bootstrap RNG seed: `922002026`

Pre-confirmatory implementation correction:
- original commit `e60250a`
- integrated as `7f131ff`
- Amendment A1 original commit `504a23c`
- integrated as `c2c02e1`

Amendment A1 was recorded before any `93100..93139` confirmatory seed was run.

The completed Phase C run was executed in the prior execution environment.
Its raw scratchpad artifact is not present in this Termux checkout, so its raw
file hash cannot be independently recomputed here. The numerical record below
is therefore the sealed completion record from that run and must not be
misrepresented as a fresh rerun from this checkout.

## Validity

Completed seeds: **40 / 40**

- child return code failures: 0
- engine errors: 0
- global harness errors: 0
- row-level harness errors: 0
- duplicate qualifying keys: 0
- structural harness verdict: PASS

The confirmatory run is valid under the preregistered validity gate.

## Primary result

- qualifying rows: **2046**
- changed-size rows: **1594**
- seed clusters: **40**
- cluster-size range: min **26**, median **51**, max **73**
- primary row-level ITT mean: **+0.042653 BB**
- rounded primary output: **+0.0427 BB**
- cluster bootstrap 95% interval: **-0.0106 .. +0.0969 BB**

Zero-intervention rows:
- count: **452**
- all paired deltas: exactly **0**
- retained in the ITT population as preregistered

### Locked interpretation

**INCONCLUSIVE — the preregistered bootstrap interval overlaps zero.**

This is not evidence of no effect.

The result does not provide the preregistered evidence required to promote the
money-open sizing change. It also does not constitute evidence against the
change under the locked rule.

Production money-open sizing therefore remains unchanged.

## Secondary descriptive outcomes

These are descriptive only and have no promotion cutoff.

- downstream action changed: 56 / 2046 = 2.7%
- winner path changed: 37 / 2046 = 1.8%
- 3-bet rate change: approximately +0.05 percentage points
- opponent calls mean delta: +0.020
- flop pot mean delta: -0.265 BB
- opener flop SPR mean delta: +0.280

The directions are consistent with the mechanical consequences expected from a
smaller opening size, but they are not independent promotion criteria.

Stage/position summaries are descriptive only. In particular, the observed
UTG+2 subgroup (`n=52`, mean approximately `+0.398 BB`) is a thin subgroup and
must not be used as promotion evidence.

## Decision

Do not:
- extend confirmatory seeds post hoc until significance appears;
- promote from a favorable subgroup;
- alter the acceptance threshold after observing this result;
- reinterpret the overlapping interval as evidence of zero effect.

Phase C is closed as **INCONCLUSIVE**.

Any future test of money-open sizing must be a separately designed experiment
with a new preregistration and fresh data.
