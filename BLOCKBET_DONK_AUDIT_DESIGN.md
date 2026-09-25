# Blockbet / donk semantic audit design

Status: read-only audit.  No production behavior changes.

## Question

The current engine has two different poker concepts sharing the same positional fallback:

- **blockbet**: an OOP player sets a price before a known aggressor can bet;
- **donk lead**: a player leads into the previous/current aggressor.

When an aggressor is not identified, both paths currently fall back to
`oop_legacy_abs`, an old absolute-position boolean.  The code explicitly marks this
boundary unresolved.

The audit asks:

1. how often does the no-aggressor legacy fallback activate?
2. does it actually change plan selection into/out of `block`?
3. does it materially suppress bluff/semibluff aggression as if a true donk spot existed?
4. how large is that effect compared with true `oop_vs_aggr=True` donk contexts?

## Counterfactuals

No thresholds are invented.

### Block-plan counterfactual

For calls to `make_plan` where:

```
oop_vs_aggr is None
oop_legacy_abs is True
```

replay the same call with only:

```
oop_legacy_abs = False
```

The function owns its RNG from the supplied seed, so this replay does not alter the live
random stream.

Report whether the final plan changes, especially whether `block` appears/disappears.

### Donk-suppression counterfactual

For `decide_aggression` calls with no identified aggressor but legacy OOP fallback,
save the incoming RNG state, execute production once, then evaluate a second copy of the
same state with:

```
oop_legacy_abs = False
```

The counterfactual uses a separate RNG object restored to the pre-call state, so it cannot
move the production RNG stream.

Report `p_actual - p_no_legacy` for bluff-family plans.

## Population

First confirmatory sample:

- seeds 6300-6315
- entries 24
- standard format
- same field simulator used by the prior sizing audits

This seed range is not used to tune a correction.

## Interpretation

Possible outcomes:

- fallback almost never occurs / has zero material effect -> document and defer cleanup;
- fallback changes block plans but not donk aggression -> isolate block semantics;
- fallback suppresses bluff aggression materially -> no-aggressor leads are being treated
  as true donks and require semantic separation;
- both effects occur -> split the concepts before balance calibration.

No production edit is made from static reasoning alone.
