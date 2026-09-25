# Blockbet / donk semantic audit — result

Sample: seeds 6300-6315, 24 entries, standard format.

## Sanity

- tournaments: 16
- field hands: 3,375
- engine errors: 0

## No-aggressor blockbet fallback

Calls with:

```
oop_vs_aggr is None
oop_legacy_abs is True
```

observed: 1,075.

Counterfactual intervention: keep the exact same state/seed and set only
`oop_legacy_abs=False`.

Results:

- final plan changed: 3
- block membership changed: 3
- `block -> pot_control`: 2
- `block -> value_2street`: 1

Therefore the legacy absolute-position fallback creates real blockbet plans even when
there is no identified aggressor.

## No-aggressor donk suppression

Bluff-family aggression contexts:

- true donk: 127
- no-aggressor + legacy fallback: 22
- other: 394

For all 22 no-aggressor fallback rows, removing only the legacy fallback changed the
aggression probability.

```
delta = p_actual - p_no_legacy
min  = -0.4920
mean = -0.3514
max  = -0.1855
```

- suppressed rows: 22 / 22
- increased rows: 0 / 22

This is a large, one-directional effect.  The engine is treating a no-aggressor OOP lead
as if it were a true donk and suppressing bluff/semibluff execution by roughly 0.19-0.49
absolute probability in this sample.

## Semantic conclusion

The legacy fallback is behaviorally material and semantically wrong for these two
consumers.

- blockbet requires a known aggressor whose future bet price is being pre-empted;
- donk suppression requires leading into a known aggressor;
- no-aggressor OOP position alone is insufficient for either concept.

A checked-around limped pot is a different strategic object (stab/lead), not a donk by
definition.  It must not inherit donk suppression merely because the actor sits early in
the absolute postflop order.

## Correction scope

The correction should be surgical:

```
_oop_a = (oop_vs_aggr is True)
```

for the blockbet-selection and donk-suppression consumers only.

Do not change:

- field-relative OOP used by c-bet logic;
- `oop_legacy_abs` logging/provenance yet;
- initiative semantics;
- probe semantics when a real known aggressor exists;
- plan probabilities or concept coefficients.

After correction, rerun this same audit and the frozen regression.  The expected semantic
result is zero legacy-caused block membership and zero no-aggressor donk suppression.
