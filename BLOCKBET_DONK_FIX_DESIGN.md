# Blockbet / donk no-aggressor correction

Base evidence: `BLOCKBET_DONK_AUDIT_RESULT.md`.

## Locked semantic rule

Two concepts require a **known aggressor**.

### Blockbet

A blockbet is a price-setting bet made before a known aggressor can bet.

Eligible positional condition:

```
oop_vs_aggr is True
```

If `oop_vs_aggr is None`, there is no valid aggressor-relative ordering and the action
must not gain blockbet eligibility from absolute seat position.

### Donk suppression

Donk suppression applies only when leading into a known aggressor.

Eligible positional condition:

```
oop_vs_aggr is True
```

No-aggressor OOP leads are not donks.  A limped/check-around pot may later deserve a
separate stab/lead concept, but it must not inherit donk suppression by accident.

## Production change

Only two consumer lines in `plan.py` change from a legacy fallback:

```
oop_vs_aggr if oop_vs_aggr is not None else bool(oop_legacy_abs)
```

to:

```
oop_vs_aggr is True
```

No coefficients, thresholds, RNG draws, ICM logic, field-relative OOP logic, or plan
labels are otherwise changed.

`oop_legacy_abs` remains in the call contract and provenance so historical comparison
and diagnostics are still possible.

## Post-change checks

1. compile `plan.py` and the audit tool;
2. rerun seeds 6300-6315 with the exact same audit;
3. require engine errors = 0;
4. expect:
   - legacy fallback calls may still be observed as context;
   - block membership changed by toggling legacy = 0;
   - no-aggressor aggression probability changed by toggling legacy = 0;
5. run frozen regression without updating the baseline;
6. any regression mismatch is treated as expected only after tracing it to one of these
   two corrected semantic paths.
