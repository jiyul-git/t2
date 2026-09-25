# Money-open shadow audit — first pass

Sample: seeds 6400-6415, 24 entries, standard format.

## Sanity

- tournaments: 16
- field hands: 3,370
- unopened observations: 17,029
- engine errors: 0

## First-pass global shape

Open-size shadow:

- legal unopened raises: 3,347
- any numerical change: 2,174 (65.0%)
- base size median: 2.400 BB
- shadow size median: 2.331 BB
- reduction among changed rows: median 0.029 BB, q75 0.083 BB, max 1.036 BB
- shadow target equal to 2BB: 1,170 rows (35.0%)

Limp-form shadow:

- eligible same-roll decisions: 3,487
- add-limp: 23
- base-limp: 155
- unchanged-raise: 3,309
- 9 / 23 add-limp rows are SB, whose current action path blocks open-limp.

These global counts are descriptive only; neither shadow is promoted from this pass.

## Audit-tool correction before interpretation

The first-pass stage helper checked `remaining <= 9` before ITM/bubble/approach.
For a 24-entry / roughly 4-paid tournament, those regions overlap, so every late ladder
state was labeled `final9`.  The output therefore cannot distinguish the exact money
region that the feature is supposed to model.

Also, `shadow at 2BB floor` counted both:

1. raises already at 2BB before the shadow; and
2. raises newly pulled down to the 2BB floor.

Those are strategically different.

The audit tool has been corrected to:

- prioritize ITM -> bubble -> approach -> final9 -> pre;
- report rows **newly pulled** from above 2BB to exactly 2BB.

The exact same preregistered seeds must be rerun.  This is an audit-label correction, not
a formula or threshold change, and production behavior remains untouched.

## Provisional interpretation only

Even before the corrected split:

- the sizing signal is broad but typically small, so the raw 65% "changed" rate overstates
  practical movement;
- the limp signal is sparse (23 same-roll additions) and a large share is entangled with
  unresolved SB open-limp semantics.

No production promotion decision is made until the corrected rerun is observed.


## Corrected rerun — seeds 6400-6415

The same preregistered sample was rerun after fixing only the reporting stage labels and
separating pre-existing 2BB raises from newly floor-clamped shadow raises.

Sanity remained identical:

- field hands: 3,370
- unopened observations: 17,029
- engine errors: 0

### Open-size shadow

Global:

- legal unopened raises: 3,347
- any numerical change: 2,174 (65.0%)
- newly pulled from above 2BB to exactly 2BB: 143
  - 4.3% of all raises
  - 6.6% of changed raises
- changed-row reduction: median 0.029BB, q75 0.083BB, max 1.036BB

By stage:

- pre: 1,586 / 2,571 changed (61.7%), median 2.42 -> 2.39BB,
  newly to 2BB = 10
- approach: 170 / 215 changed (79.1%), median 2.30 -> 2.00BB,
  newly to 2BB = 71
- ITM: 233 / 275 changed (84.7%), median 2.50 -> 2.31BB,
  newly to 2BB = 29
- final9 outside approach/bubble/ITM: 185 / 286 changed (64.7%),
  median 2.20 -> 2.06BB, newly to 2BB = 33

The global median movement is small, but the approach region is not merely a broad,
gentle reduction: 71 / 215 approach raises (33.0%) are newly collapsed to the legal
2BB floor and the stage median itself becomes exactly 2.00BB.

That fails the preregistered "broad coherent small reductions without pathological
2BB pile-up" condition for promotion.

**Decision: keep open-size money pressure shadow-only.**

Do not tune the current formula from this sample.  If revisited, redesign/preregister
the mechanism on fresh data rather than adding an after-the-fact threshold.

### Limp-form shadow

Same-roll counterfactual:

- eligible decisions: 3,487
- add-limp: 23 (0.66%)
- base-limp: 155
- unchanged raise: 3,309

By stage:

- pre: 5 add-limp
- approach: 13 add-limp
- ITM: 1 add-limp
- final9 outside those ladder buckets: 4 add-limp

By position near the ladder:

- HJ 2
- CO 4
- BTN 4
- SB 8
- earlier positions 0

Across the full sample, SB contributes 9 / 23 add-limp candidates (39.1%), but the
current action path intentionally blocks SB open-limp.

The signal is sparse and materially entangled with an unresolved action-form semantic
change at SB.  Enabling it now would mix "money pressure should add limps" with
"SB open-limp should exist" in one production change.

**Decision: keep limp-form money pressure shadow-only.**

Do not enable SB open-limp from this sample and do not silently drop SB candidates and
promote the rest after seeing the result.  If limp-form is revisited, lock a separate
SB/non-SB semantic design first and test it on fresh seeds.

## Closure

The current money-jump status is intentionally:

- unopened range factor: **live**
- open-size factor: **shadow-only / not promoted**
- limp-form pull: **shadow-only / not promoted**

This is not an accidental missing wire.  The two shadow channels were measured and
deliberately left inactive.

No production behavior or frozen regression baseline changed in this audit.
