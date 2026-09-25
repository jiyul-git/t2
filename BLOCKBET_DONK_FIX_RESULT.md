# Blockbet / donk no-aggressor correction — result

Branch: `chatgpt/fix-blockbet-donk-noaggr-20260926`

## Same-sample post-change audit

Seeds 6300-6315, 24 entries, standard format.

Sanity:

- tournaments: 16
- field hands: 3,335
- engine errors: 0

The total field-hand count changed from the pre-fix audit (3,375 -> 3,335), which is
expected because the production correction changes actions and therefore tournament
trajectories.

### Blockbet semantic check

No-aggressor legacy contexts observed: 1,063.

Counterfactual toggle of `oop_legacy_abs` after the fix:

- final plan changed: 0
- block membership changed: 0

The legacy absolute-position flag no longer creates blockbet plans when no aggressor is
identified.

### Donk-suppression semantic check

Observed bluff-family contexts:

- true donk: 124
- no-aggressor + legacy context: 20
- other: 393

For all 20 no-aggressor legacy rows:

- aggression probability changed by toggling legacy: 0
- min / mean / max delta: 0 / 0 / 0
- suppressed rows: 0
- increased rows: 0

Therefore no-aggressor OOP leads no longer inherit true-donk suppression.

## Result

The locked semantic correction is satisfied on the same audit population:

- known aggressor is required for blockbet eligibility;
- known aggressor is required for donk suppression;
- legacy absolute OOP remains provenance only for these consumers.

The audit itself remains read-only.  The production behavior change is the two-line
semantic correction in `plan.py`.

## Remaining check

Run the frozen regression without updating its baseline.  Any mismatch must be traced to
one of the two corrected semantic paths before acceptance.


## Frozen regression closure

Frozen regression was run without updating the baseline.

```
baseline: VPIP 19.1% / PFR 11.4% / flop 44.4%
current : VPIP 19.1% / PFR 11.4% / flop 44.4%
mismatch seeds: [3001, 3002]
```

This mismatch set is exactly the already-documented inherited set:

- seed 3001: planned-allin preservation change;
- seed 3002: effective-allin v1 change.

`EFFECTIVE_ALLIN_V1_RESULT.md` explicitly isolated v1 fresh A/B to seed 3002 while
seed 3001 remained inherited.  `UNCALLED_EXCESS_RESULT.md` separately documents seed
3001 as pre-existing.

Therefore the blockbet/donk semantic correction adds **no new frozen-fixture mismatch**.
The frozen baseline remains unchanged.

## Closure

Accepted.

The no-aggressor legacy fallback is removed from blockbet eligibility and donk
suppression, while historical provenance remains available.  No further work is required
for this item unless a new semantic failure appears.
