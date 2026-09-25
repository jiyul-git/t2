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
