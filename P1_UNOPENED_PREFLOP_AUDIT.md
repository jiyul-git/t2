# Sequential audit — P1 unopened preflop

Status: MAPPED, NOT YET REFACTORED.

Reference model: judgment -> plan -> action.

## Situation

Action reaches hero with no voluntary raise and no limper before hero.

Available information:

- hole cards / position / table size;
- stack depth and effective stacks behind;
- ante/blind structure;
- tournament/ICM/field state;
- reads on players behind;
- reshove threats behind;
- money-jump pressure;
- stable player skill/temperament;
- current emotion, but only for plan selection under V2.

## Rational plan candidates

These are motives/line plans, not final chip actions:

1. fold / preserve;
2. standard open for range realization/value;
3. steal / exploit folds behind;
4. pressure open using tournament topology;
5. mixed limp strategy;
6. premium trap-limp where strategically supported;
7. short-stack open-shove;
8. deliberate variance-seeking shove.

The final current-action plan then chooses:
- fold;
- limp;
- raise to strategic size;
- shove.

## Current code path

```
preflop_plan
 -> open_decision
      -> feel_of
      -> variance_seek
      -> _open * table_pressure * hotzone_pressure
      -> money_open range factor
      -> open_form (raise vs shove)
      -> limp_p
      -> open_size_bb
 -> returns action + size directly
 -> session shape_size
 -> Round.apply
```

## Findings

### P1-1 ARCH_MISMATCH — no explicit plan object

`open_decision` directly chooses fold/limp/raise/shove.

`preflop_plan` stores only:
- pf_role='open';
- pf_act;
- position/level/initiative;
- hand percentile;
- money_open provenance.

It does not preserve **why** the player opened:
standard value/realization, steal, pressure exploit, deliberate variance, strategic limp, etc.

Consequence:
postflop receives the action but loses important motive/story information.

Target:
explicit preflop plan object containing at least:
- motive;
- horizon/goal where relevant;
- current action;
- strategic size;
- rationale/provenance.

### P1-2 ARCH_MISMATCH — emotion currently contaminates judgment

`session` passes `h.axes(s)`, whose profile is already `tilted_view(base,t)`.
That altered profile is used by:
- depth perception;
- pf_range/open percentage;
- table-pressure interpretation;
- SPR awareness;
- sizing knowledge;
- stable traits used inside judgment.

Separately, `variance_seek(... tilt=...)` receives tilt explicitly.

Under V2:
- stable skill/temperament may limit judgment;
- current tilt may bias plan choice only.

So P1 currently mixes the two.

### P1-3 DOUBLE EMOTION PATH — variance path can receive tilt twice conceptually

The profile has already been tilt-transformed before `open_decision`,
then `variance_seek` also consumes explicit tilt.

This is not necessarily numerically the same term twice, but current emotion can affect both
inputs feeding plan selection.

Target:
judgment uses calm/base profile;
plan selector receives a single explicit emotion state.

### P1-4 STORY LOSS — variance shove and structural shove collapse to the same action

`open_form` correctly distinguishes internally:
- structural shallow-stack shove;
- variance-seeking shove.

But it returns only `('shove', bb)`.

The reason is lost from `pf_seed`.

Target:
preserve motive, because later interpretation of the preflop range/line should know whether
the shove came from stack geometry or deliberate variance.

### P1-5 STORY LOSS — standard open, steal and pressure-open collapse

`table_pressure`, hot-zone pressure and money pressure alter the open threshold, but the final
seed still records only `pf_role='open'`.

Target:
do not invent separate actions, but retain motive components/provenance in the plan.

### P1-6 REVIEW — SB limp is globally blocked

`limp_p` models both theoretical and habitual limping, but `open_decision` executes a limp only
when `pos != 'SB'`.

A folded-to SB limp is a legitimate strategic family in tournament poker and should not be
globally impossible without a separate reason.

Status: REVIEW before behavior change; verify table/headsup semantics and current SB action order.

### P1-7 ARCH_MISMATCH — execution still changes strategic size

After `open_size_bb` chooses the strategic size, `session` applies
`runner.shape_size`, which adds type-family jitter/rounding before legality.

Under the new invariant, strategic randomness/style belongs in the current action plan.
Execution should only:
- convert BB to chips;
- round to chip unit if necessary;
- apply legal minimum/cap.

The same issue also exists postflop and will be handled as a global execution-boundary refactor,
not patched only in P1.

## P1 target architecture

```
base profile + public state
 -> judge_unopened_preflop()
      returns judged state
 -> choose_unopened_plan(judged, previous context, emotion)
      motive = fold / standard_open / steal / pressure / limp / trap_limp / structural_shove / variance_shove
      action = fold / limp / raise / shove
      size_bb = strategic size
 -> execute_preflop_action(plan)
      legality + chip conversion only
```

## Decision

Do not tweak thresholds yet.

Required before closing P1:
1. split judgment from plan/action;
2. preserve motive in pf_seed/plan state;
3. isolate current emotion to plan selector;
4. move strategic size jitter out of executor;
5. resolve SB limp semantics with a targeted legality/strategy check;
6. preserve existing frozen behavior where the refactor is meant to be structural only, then
   separately measure intended semantic changes.


## Follow-up fixes found during preflop closure pass

### P1-8 FIXED — live variance-seek input was accidentally removed during the audit

During the P3/P4 cleanup, the unused `variance_seek` value in `defend_decision` was correctly
removed, but the similarly named value in `open_decision` was also removed even though
`open_form(..., vs=...)` consumes it.

That would cause an unopened in-range hand to hit an undefined `vs`.

Fix:
restore the explicit variance-seek value in `open_decision`.

Architecturally this is a PLAN-selection input, so its location is compatible with V2.
The broader problem that `profile` itself is still a tilted view remains open.

### P1-9 FIXED — SB complete was globally impossible

Old code required `pos != 'SB'` for any open limp.

That excluded a normal tournament action family:
`folded to SB -> complete`.

Fix:
SB can now use the same limp-plan mechanism.

### P1-10 FIXED — habitual weak-hand limp branch was unreachable

`limp_p` is explicitly designed so habitual limpers can limp wider/weaker hands.

But `open_decision` returned fold immediately when the hand was outside the raise threshold,
before `limp_p` was evaluated.

So the documented "weak habitual limp" logic could not occur.

Fix:
- raise/shove eligibility still uses the open threshold;
- limp is evaluated separately;
- outside the raise range, a player may limp if the limp plan wins, otherwise fold.

No new coefficient was invented; this makes the existing limp model reachable.
