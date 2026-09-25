# Uncalled-excess verification result

## Targeted rules

`tools/verify_uncalled_excess.py` passed all five targeted cases:

- HU overbet vs short-stack call: short call capped, unmatched excess returned
- legitimate multiway side pot: no false return
- raise then fold: folded matched money stays, unmatched raise excess returned
- multiway contestable-pot view: short stack sees only contestable current-street money
- tied top contributions: no false return

## Frozen regression isolation

The ordinary frozen regression still reports seed 3001 as changed.  That mismatch already
existed after the earlier planned-allin preservation fix.

Fresh-process A/B on the current branch compared:

- OLD: planned-allin fix retained, only uncalled-excess semantics monkeypatched out
- NEW: current uncalled-excess implementation

Result:

- seeds 3000-3005: all fingerprints identical OLD vs NEW
- changed seeds: []
- aggregate stats identical

Therefore the new uncalled-excess accounting change adds no further divergence in the
frozen regression fixture.  The remaining frozen-baseline seed-3001 mismatch belongs to
the earlier planned-allin behavior change, not this accounting correction.

The next validation is the same 6000-6007 near-allin/effective-stack audit with explicit
round-end uncalled-return totals.
