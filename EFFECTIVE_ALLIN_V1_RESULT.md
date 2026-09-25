# Effective-all-in v1 result

Branch: `chatgpt/effective-allin-v1-20260925`

## Locked rule

A postflop bet/raise is classified as actor effective-all-in only when:

- actor is the limiting effective stack: `actor_cap <= opp_cap_max`
- final legal target / actor cap >= 0.90
- actor residual / pot after action <= 0.05

v1 execution mode is physical shove.  Intentional leave-behind remains a separate
future execution mode after classification.

## Targeted verification

User-run verification:

- `tools/verify_effective_allin_v1.py`: 6/6 PASS
- `tools/verify_allin_raise_rights.py`: 5/5 PASS

The raise-right verifier was added after seed 3002 exposed a separate HU dead-raise
bug: once the only opponent is all-in, a covering player must not make an uncallable
raise above the call amount.  After the fix, the seed-3002 path changed from

```
OLD: turn seat1 raise 22800 -> seat2 raise 29100 -> seat1 call 24100
NEW: turn seat1 raise 24100 -> seat2 call 24100
```

The v1 promotion that causes the first divergence is exactly the locked population:

- actor cap: 24,100
- final pre-v1 target: 22,800
- commit fraction: 94.61%
- post-action own SPR: 0.04025
- actor-effective: true
- execution: shove to 24,100

Fresh-process regression A/B with only v1 classification disabled in OLD:

- changed seeds: [3002]
- seeds 3000, 3001, 3003, 3004, 3005 identical
- aggregate VPIP/PFR/flop counters identical

Thus seed 3001 remains inherited from the earlier planned-allin preservation change;
seed 3002 is the isolated v1 behavior change in the frozen fixture.

## In-sample 6000-6007

After v1:

- field hands: 1,697
- aggressive postflop actions: 1,460
- engine errors: 0
- actor-effective non-all-in rows: 679
- actor-effective commit >=90%: 3
- actor-effective commit >=95%: 0
- actor-effective commit >=90% AND post-action own SPR <=0.05: 0
- actor-effective commit >=90% AND post-action own SPR <=0.10: 3

The surviving >=90% actor-effective rows sit immediately outside the locked SPR
boundary (about 0.06-0.07), which is evidence that the rule is not simply converting
all 90% commitments to shoves.

## Out-of-sample 6100-6107

Independent seeds not used to choose the threshold:

- field hands: 1,663
- aggressive postflop actions: 1,445
- engine errors: 0
- actor-effective non-all-in rows: 718
- actor-effective commit >=90%: 0
- actor-effective commit >=95%: 0
- actor-effective commit >=90% AND post-action own SPR <=0.05: 0

v1 provenance:

- classifier hits / applied: 77
- already exact/full targets: 62
- actual near-all-in -> shove promotions: 15
- promotion rate: 15 / 1,445 = 1.04% of aggressive postflop actions
- promoted streets: flop 10, turn 5, river 0
- promoted plans: value_3street 13, value_2street 1, trap 1
- promoted pre-v1 commit range: 90.45% to 99.82%
- promoted post-action own SPR range: 0.0013 to 0.0444
- additional chips normalized to shove across those 15 rows: 17,500 total

The nearest surviving actor-effective rows are below the commit floor or above the
SPR ceiling:

- 88.4% / 0.06
- 86.4% / 0.07
- 85.6% / 0.08

Opponent-effective high-commit rows remain intentionally untouched.  For example,
a 90.9% own-stack commitment can survive when the opponent is the shorter effective
stack; actor shove normalization must not be inferred from own-stack percentage alone.

## Conclusion

v1 satisfies the preregistered intent on both the threshold-selection sample and an
independent sample:

- the targeted actor-effective near-all-in tail is removed;
- opponent-effective cases remain separate;
- the boundary immediately outside 0.05 remains populated;
- actual promotions are sparse rather than broad;
- the frozen regression change is isolated and explained;
- targeted rule checks pass.

The `90% commit + 0.05 post-action own SPR + actor-effective` classifier is therefore
accepted as effective-all-in v1.

No intentional leave-behind policy is part of this result.
