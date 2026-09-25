# Near-all-in first-fix result

## Before

Seeds 6000-6007, standard, 24 entries:

- aggressive postflop actions: 1,439
- actual all-in/clamped: 77 (5.35%)
- non-all-in >=95% commit: 44
- residual <=1BB: 31
- residual <=2BB: 41
- residual <=3BB: 48
- residual <=5BB: 63

## First correction

Commit `931d793` preserves an exact decision-layer full-stack target through
`shape_size`.  It does not add an effective-all-in threshold.

## After

Same seed set / fixture definition:

- aggressive postflop actions: 1,472
- actual all-in/clamped: 122 (8.29%)
- non-all-in >=95% commit: 6
- residual <=1BB: 3
- residual <=2BB: 5
- residual <=3BB: 10
- residual <=5BB: 24

Because action changes alter later tournament trajectories, before/after row counts are not
paired-event differences.  The large collapse of the extreme tail nevertheless matches the
specific mechanism corrected by `931d793`.

The first fix is retained.

## Remaining tail is heterogeneous

At least two distinct mechanisms remain.

### A. Genuine near-stack sizing before legality clamp

Example:

```
seed 6000 H46 river bet
stack=12000 pre=11900 executed=11900
intent_size=.86 pot=13800
residual=100 = 0.2BB
```

Here `13800 * .86 -> 11900`; the decision did not request an exact stack target.
This is a genuine effective-all-in candidate.

### B. Legal minimum-raise clamp can create near-all-in

Example:

```
seed 6002 H53 flop raise
stack=34100 pre=21000 executed=32600
residual=1500 = 2.5BB
```

The final target is much larger than `pre_clamp`, so the legal raise floor, not the
original sizing target, pushed the action close to all-in.

These mechanisms must not be collapsed into one blind percentage rule.

## Conceptual layering

`effective all-in` and intentional `leave-behind` are not opposites.

1. classify whether the legal action is effectively all-in;
2. if yes, choose execution mode:
   - physical shove;
   - intentional leave-behind (future ICM concept);
3. current accidental residue is neither mode and should not be created by downstream
   sizing noise.

No intentional leave-behind concept exists in current production code.
