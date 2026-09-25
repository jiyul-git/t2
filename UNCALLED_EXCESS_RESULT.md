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


## Full 6000-6007 audit after correction

- field hands: 1,608
- aggressive postflop actions: 1,467
- engine errors: 0
- physical all-in/clamped: 118
- non-all-in >=95% own-stack commit: 6

Observed round-end uncalled returns:

- total: 2,283 returns / 24,363,500 chips
- preflop: 1,657 / 18,125,400
- flop: 221 / 1,808,400
- turn: 232 / 2,506,700
- river: 173 / 1,923,000

This total is intentionally broader than the earlier 1,295,700-chip
"target beyond deepest opponent cap" diagnostic.  It also includes ordinary
uncalled wagers after folds, so the two totals are not directly comparable.

The own-stack near-all-in tail is essentially unchanged by the accounting correction:
>=95% non-all-in remains 6, <=1BB residual remains 3, <=2BB remains 5.
That is expected: the correction changes contestable/returned money, not the
near-all-in execution policy.

Next population for effective-all-in design: **actor-effective only**.  Opponent-effective
cases must not be used to decide whether the actor should physically shove.

No effective-all-in threshold and no intentional leave-behind rule is implemented yet.
