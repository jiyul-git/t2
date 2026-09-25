# Sequential audit — P7 cold-facing a preflop re-raise

Status: DECISION CLASS NOW PRESERVED; dedicated strategy model remains missing.

Reference model: judgment -> plan -> action.

## Situation

Hero has not voluntarily entered the pot yet, but action before hero already contains
two or more full raises.

Canonical examples:

1. UTG open -> HJ 3bet -> hero BTN;
2. open -> caller -> squeeze -> hero, where hero had not acted;
3. open -> 3bet -> cold caller -> hero;
4. open -> 3bet -> 4bet -> hero;
5. short all-in raise plus prior full raise -> hero;
6. multiway cold decision with players still behind.

This is not:
- P4 opener facing a 3bet;
- P5 caller facing a squeeze;
- P6 pure call-off.

## Rational judgment inputs

- original opener's range and stack;
- re-raiser/squeezer range, size and stack;
- cold callers and their ranges;
- current pot / exact incremental price;
- hero position;
- players still behind;
- hero effective cap against each live opponent;
- whether raise rights are open;
- ICM;
- full public preflop sequence.

## Rational plan candidates

Facing a 3bet cold:
- fold;
- cold call where structurally justified;
- value cold 4bet;
- polarized cold 4bet bluff;
- cold 4bet shove.

Facing a 4bet cold:
- usually much narrower fold/call/raise/jam family;
- exact options depend on stack and live-player structure.

## Fixed information-flow defect

### P7-1 FIXED — cold vs re-raise was not distinguishable in the stored decision story

All such states entered generic `defend`.

The seed did not say whether the player:
- was the opener;
- was a prior caller;
- had never acted and was cold-facing the re-raise.

Fix:
preflop plan provenance now stores `pf_decision_kind`:

- `unopened`;
- `limped_unopened`;
- `face_first_open`;
- `cold_vs_reraise`;
- `caller_backaction`;
- `opener_backaction`;
- `reraiser_backaction`.

The previous preflop seed is explicitly passed into the next decision and the kind is preserved
inside `pf_line`.

This is an information-preservation fix, not yet a strategy split.

## Remaining strategic gaps

### P7-A MAJOR MISS — cold defense still reuses generic defend thresholds

A cold 4bet decision should not be modeled as simply:
"first-open defense, tightened by raise level."

Correct construction needs at least:
- opener range;
- 3bettor range;
- whether opener remains live;
- current price;
- hero position;
- effective stacks.

### P7-B MAJOR MISS — original opener disappears from the scalar response interface

The latest aggressor is passed as the main opponent.

In:
`UTG open -> CO 3bet -> hero BTN`

the hero must reason about both UTG and CO, not only CO.

### P7-C MISS — cold-call / cold-4bet tendencies are not separately learned

Current observation correctly avoids contaminating opener 4bet stats with caller backraises,
but there is no dedicated learned channel for an unentered player's:
- cold call vs 3bet;
- cold 4bet.

Keep this as an observation candidate; do not infer it from opener 4bet frequency.

### P7-D MISS — players behind remain scalar/implicit

A cold 4bet can still face:
- opener 5bet;
- 3bettor 5bet;
- another cold player.

Those live response ranges are not first-class planning inputs.

## Decision

Do not add arbitrary cold-4bet coefficients now.

The important prerequisite is complete:
the engine can now tell **which strategic situation occurred**.
The later preflop judgment/plan refactor can branch on that situation without reconstructing it
from lossy final actions.
