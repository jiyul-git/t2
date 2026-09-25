# Street-concept granularity audit design

Status: taxonomy/wiring audit only. No production behavior or prior changes.

## Why this precedes calibration

The prior sensitivity audit is mechanically sound, but calibration is paused because the
concept taxonomy is not yet stable.  Calibrating a shared concept and splitting it later
would invalidate the population work.

This audit separates two questions:

1. **Granularity** — should one skill be shared across streets?
2. **Cross-wiring** — once a motive/plan exists, can it reach every execution mode that
   should be available?

A low-resolution concept and a missing cross-wire are different bugs.

## Known candidates

### Strong split candidate

`checkraise_late` currently represents both turn and river.

This is semantically lossy because:

- turn check-raise can be value, semibluff, draw/equity-denial;
- river check-raise has no future-card equity and is primarily polarized value/bluff;
- river bluff selection already uses `bluff`, `barrel_river`, and blockers.

Candidate taxonomy:

```
checkraise_flop
checkraise_turn
checkraise_river
```

### Medium split candidates

`bluffcatch_early` currently represents flop + turn.

Candidate taxonomy to evaluate:

```
bluffcatch_flop
bluffcatch_turn
bluffcatch_river
```

`thin_value_turn` is currently also the **flop fallback** for
`street_concept('thin_value','flop')`.

Candidate taxonomy to evaluate:

```
thin_value_flop
thin_value_turn
thin_value_river
```

Do not split automatically; first inspect whether the consumer logic actually uses a
different strategic meaning by street.

## Known cross-wiring defect to verify

`river_fix()` can create `plan='river_bluff'` from:

- bluff skill;
- barrel-river skill;
- blocker effect.

But `checkraise_decision()` has explicit base-probability branches for:

- trap;
- semibluff (non-river);
- bluff_2street;

and no explicit `river_bluff` base-probability branch.

Although the read adjustment later labels `river_bluff` as a bluff, multiplying or
blending a zero base probability does not create a river bluff check-raise.

This is a cross-wiring issue, not merely a naming/granularity issue.

## Audit questions

For each street-sensitive concept family:

1. Which streets map to the same skill?
2. Which functions consume that mapped skill?
3. Does the tactical motive materially differ by street?
4. Does the plan/motive layer expose all expected execution modes?
5. Are any branches listed as a strategy class downstream but never given a non-zero
   upstream probability?
6. Would splitting a concept change only player heterogeneity, or also require different
   decision formulas?

## Order after this audit

1. lock final taxonomy;
2. fix missing motive -> execution wires;
3. add/split concepts with backward-compatible migration defaults;
4. targeted counterfactual + frozen regression checks;
5. regenerate realized-prior audit;
6. only then calibrate LOADING/SPREAD.

No prior calibration is accepted before steps 1-4 are closed.
