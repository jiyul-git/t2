# Leave-behind audit result — first sample

Branch: `chatgpt/leave-behind-audit-20260925`

Sample: seeds 6100-6107, after effective-all-in v1.

## Population

- aggressive postflop actions: 1,445
- actual near-all-in -> shove promotions: 15
- money-jump observation join missing: 0
- decision classes: facing_bet 9 / free_action 6

## Signal shape

The survival-oriented signals do **not** form a broad high-pressure cluster.

Across the 15 promotions:

- ladder-survival component median: 0.010
- q75: 0.020
- maximum: 0.123
- perceived self-preservation median: 0.008
- perceived urgency median: 0.027
- commitment budget median: 0.992
- preservation minus urgency median: -0.003

One row is a clear positive outlier:

- seed 6107 H120, flop raise, facing_bet
- pre-v1 residual: 0.6 BB
- BF 2.272
- payout importance 0.400
- ladder buffer 0.556
- shorter severity 0.601
- waiting feasibility 0.918
- ladder-survival component 0.123
- perceived preservation 0.110
- urgency 0.035
- preservation minus urgency +0.076

Two additional facing-bet rows have moderate ladder components around 0.043-0.044,
but most promotions are near zero and several free-action rows have urgency clearly
above preservation.

## Interpretation before any policy

This sample does not justify a generic "effective all-in -> leave 1BB" rule.

The only plausible leave-behind region visible so far is a narrow survival-option region,
mainly on facing-bet actions where:

- a payout jump is materially relevant;
- realistic shorter stacks exist;
- waiting remains feasible;
- preservation exceeds urgency.

Even there, no threshold is accepted yet.

Free-action promotions currently show no comparable positive cluster.  A single common
leave-behind selector for free-action and facing-bet would therefore hide materially
different upstream semantics.

## Blocking validation: field-cycle ordering

`fieldsim` plays tables sequentially within one outer field-hand cycle.  Later tables
can observe busts from earlier tables through `remaining()` and `field_stacks`.

Because the strongest candidate is explicitly ladder-sensitive, its signal must be checked
against the field-cycle-start state before using it to define strategy.  Audit tooling now
records:

- cycle-start remaining players;
- cycle-start players-to-jump;
- cycle-start shorter-stack count;
- within-cycle drift versus the action observation.

No production behavior is changed.

## Current status

- effective-all-in v1 remains unchanged;
- no leave-behind execution mode is implemented;
- no one-BB constant is implemented;
- no leave-behind threshold is preregistered yet.

Next: rerun the same 6100-6107 audit with cycle-snapshot fields and determine whether the
strong candidate and any secondary candidates survive the ordering-sensitivity check.


## Cycle-order follow-up

The same seeds were rerun with a field-cycle-start snapshot.

Across all 15 promotions:

- cycle remaining drift: 0 for every row;
- cycle shorter-stack drift: 0 or 1;
- the strongest candidate, seed 6107 H120, had:
  - remaining 8 / cycle-start remaining 8;
  - players-to-jump 4 / cycle-start players-to-jump 4;
  - shorter stacks 5 / cycle-start shorter stacks 5;
  - remaining drift 0;
  - shorter-stack drift 0.

Therefore the strongest exploratory survival signal is not an artifact of within-cycle
table execution order.  Minor one-stack shorter-count drift exists on some secondary
rows and remains visible in OOS audit output.

A shadow selector is now locked in `LEAVE_BEHIND_SHADOW_DESIGN.md` before seeds
6200-6215 are observed.  Production behavior remains unchanged.
