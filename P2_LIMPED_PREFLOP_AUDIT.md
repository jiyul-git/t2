# Sequential audit — P2 limpers, no raise

Status: LOCAL DEFECTS FIXED IN BRANCH; architecture refactor still open.

Reference model: judgment -> plan -> action.

## Situation

One or more players have limped and no full voluntary raise exists when action reaches hero.

This includes:

- one limper;
- multiple limpers;
- SB completing;
- BB option after limp-around;
- players still to act behind hero;
- short stacks behind that can reshove;
- limpers with different limp/fold/postflop tendencies.

## Rational judgment inputs

- hero hand / position;
- actual stack depth;
- seat count / ante;
- number and positions of limpers;
- each limper's estimated limp range;
- each limper's response to a raise after limping;
- postflop playability against those limpers;
- players behind: 3bet/squeeze propensity and reshove stacks;
- ICM / tournament state;
- effective stacks;
- current emotion only when choosing the plan.

## Rational plan candidates

- fold;
- overlimp for realization / implied odds;
- value isolation raise;
- isolation bluff / dead-money attack;
- larger multi-limper isolation;
- premium trap-overlimp where justified;
- short-stack isolation shove;
- BB free check;
- tournament-pressure isolation where the target is vulnerable.

Action form is then:
`fold / call(limp) / check / raise / shove`.

## Current-code findings

### P2-1 FIXED — wrong base context

Old `iso_decision` called:

`_open(prof, pos)`

which silently used the defaults:
- 8 seats;
- 100bb;
- ante on.

So a 20bb six-handed no-ante iso spot started from the wrong base range.

Fix:
actual `seats / bb / ante` are now passed.

### P2-2 FIXED — iso skill was applied twice and could fold premiums

Old path:

```
threshold *= (1 + 0.35*iso_trait)
then
if hand <= threshold and rng < iso_trait: raise
else possibly fold
```

The same iso tendency first widened the range and then gated execution again.
A normal TAG could therefore have AA inside the isolation range and still fold when the second
roll failed.

Fix:
the iso trait now defines the range width; hands inside that range isolate without a second
independent iso roll.

Mixing, if later desired, belongs in explicit plan selection rather than a duplicate execution gate.

### P2-3 FIXED — behind-player threats disappeared in limped pots

Session previously built `behind_stacks` and `behind_est` only when there were **no limpers**.

Thus an iso decision ignored:
- squeeze/3bet threats behind;
- reshove stack geometry behind.

Fix:
limped pots now preserve behind stacks and reads, and reuse the existing
`table_pressure` / `hotzone_pressure` channels.

### P2-4 FIXED — wrong fold statistic for isolation targets

Old `iso_decision` used `fold_gap`, which is derived from **postflop fold-to-bet**.

That is not the same behavior as:

`limp -> face first preflop raise -> fold`.

Fix:
reads now tracks a dedicated `pf_fold_after_limp_raise` channel and
`persona.read_opponent` exposes `f2iso_gap`.

The iso path consumes that instead of postflop fold-to-bet.

### P2-5 FIXED — RFI sample confidence was doubled

`reads.observe_preflop` contained the same RFI accumulation block twice.

Ratios were often unchanged, but:
- rfi opportunity count doubled;
- expected count doubled;
- shrinkage treated the sample as larger than it really was.

Fix:
the duplicate accumulation was removed.

### P2-6 FIXED — BB option could be recorded as a fold

When BB had no additional amount to call after limpers, `iso_decision` could return `fold`.
Session legally converted that to `check`, but `pf_seed['pf_act']` still said `fold`.

So action and plan story diverged.

Fix:
the P2 planner can explicitly return `check`, and session executes/checks it as such.

### P2-7 FIXED — role-only postflop range reconstruction

Old postflop code interpreted any `pf_role='iso'` as an open-style range even when the actual
action was:
- overlimp;
- BB check.

Fix:
postflop preflop-range reconstruction now prioritizes `pf_act`:
- check -> any-two BB check range;
- limp -> limp range;
- call -> call range;
- defend raise -> 3bet range;
- open/iso raise -> open-style approximation.

Remaining limitation:
BB iso-raise still uses the previous call-range approximation because RFI for BB is undefined.
A dedicated isolation-range provenance should replace that approximation in the later preflop
plan-object refactor.

### P2-8 FIXED — behavior depended on display label spelling

Old overlimp fallback required:

`prof['type'] in ('FISH','STATION')`

but `type` is documented as a display label.  A suffix/prefix such as `*_TILTY` or
`STUDIED_*` could therefore change strategy.

Fix:
overlimp fallback now uses the existing limp model/traits rather than exact display labels.

## Remaining architecture work

### P2-A ARCH_MISMATCH — still no explicit P2 plan object

The code still returns the action directly.

Target should preserve motive such as:
- value_iso;
- bluff_iso;
- overlimp_realize;
- trap_overlimp;
- structural_iso_shove;
- pressure_iso;
- BB_check.

### P2-B REVIEW — isolation sizing is still fixed

Current iso raise size remains `3 + n_limpers` bb before session sizing shaping.

The V2 architecture requires strategic sizing to be selected in the plan and execution to perform
only chip conversion/legality.  This will be handled with the global sizing-boundary refactor,
not silently retuned here.

### P2-C MISS — limp-reraise tendency is not separately learned

We now know whether a limper folds to the first raise.
We do not yet have a dedicated observation for:
- limp -> face raise -> backraise.

That matters for premium trap-limp / limp-reraise populations and remains an observation candidate.

### P2-D ARCH_MISMATCH — emotion boundary remains global

As in P1, the profile reaching iso judgment can already be tilt-transformed.
That global problem is deferred to the judgment/plan separation refactor.

## Verification target

`tools/verify_p2_limped_pot.py` must confirm:

1. RFI increments once;
2. dedicated limp-raise fold channel exists;
3. premium inside iso range cannot be folded by a second iso roll;
4. actual seats/stack/ante reach the base range lookup;
5. BB free option is an explicit check;
6. actual pf action drives postflop range role.
