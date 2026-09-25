# Uncalled excess / contestable pot correction

## Why this precedes effective-all-in

The effective-stack audit found 84 aggressive postflop actions whose executed target
exceeded the deepest live opponent's current-street capacity:

- physical all-in: 41
- non-all-in: 43
- summed unmatched excess in the sampled rows: 1,295,700 chips

This is a betting-round accounting problem, not an effective-all-in threshold problem.

Examples include a 132,400 stack betting 54,000 when the deepest opponent could reach
only 2,600 on that street.  The unmatched 51,400 cannot be won from that opponent.

## Poker semantics represented

Two distinct things are required:

1. **Decision-time contestable view**
   - a short stack's call amount is capped by its remaining stack;
   - current-street contributions above that player's reachable target are excluded from
     the pot amount used for that player's pot-odds / sizing decision.

2. **Round-end uncalled return**
   - when the betting round closes, if one seat is the unique highest contributor,
     the amount above the second-highest actual contribution is returned to that seat;
   - folded contributions still count as matched money already in the pot;
   - a player whose chips are returned is removed from the physical-all-in set if chips
     remain.

The declared action log is left intact.  This keeps replay/action provenance while the
state carried to the next street uses only called/matched contributions.

## Scope

Production changes are limited to:

- `runner.Round.to_call`
- new `runner.Round.contestable_contrib`
- new `runner.Round.settle_uncalled`
- session decision-visible pot wiring
- one settlement call at the end of preflop and each postflop betting round

No effective-all-in percentage/SPR threshold is added.
No intentional 1BB leave-behind behavior is added.
No plan probabilities or sizing coefficients change.

## Verification

Run:

```
python3 tools/verify_uncalled_excess.py
python3 -m py_compile runner.py session.py
python3 tools/regress.py check --baseline current
```

A frozen regression mismatch is expected because this is an intentional engine-accounting
correction; do not update the baseline yet.  After targeted verification, rerun the
near-all-in/effective-stack audit before designing effective-all-in execution modes.


## Verification result so far

Targeted verifier passed all five locked cases:

- heads-up overbet versus short-stack call
- legitimate multiway side pot with no refund
- raise then fold with uncalled return
- short-stack multiway contestable-pot view
- tied top contributions with no refund

Fresh-process regression A/B then isolated this accounting change from the earlier
planned-allin preservation fix.  Both arms used the same current branch; the OLD arm
monkeypatched out only the new `to_call`, contestable-pot, and uncalled-return
semantics.

Result:

```
changed seeds: []
old stats: {'flop': 80, 'hands': 180, 'n': 1390, 'pfr': 158, 'vpip': 265}
new stats: {'flop': 80, 'hands': 180, 'n': 1390, 'pfr': 158, 'vpip': 265}
```

Therefore the frozen regression's seed-3001 mismatch is inherited from the earlier
planned-allin preservation change, not introduced by the uncalled-excess accounting
correction.  The frozen baseline remains unchanged pending completion of the whole
near-all-in/effective-all-in workstream.


## Regression isolation result

Fresh-process A/B on the frozen regression fixture:

- OLD = current branch with only the uncalled-excess semantics monkeypatched out
- NEW = current branch as implemented
- changed seeds: none
- all six seed fingerprints identical
- aggregate stats identical

Therefore the frozen regression mismatch at seed 3001 is entirely inherited from the
earlier planned-allin preservation change.  The uncalled-excess accounting correction
introduces no additional divergence in that fixture.
