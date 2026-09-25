# Sequential audit — P5 caller faces squeeze / back-action

Status: CLEAR EVENT-CLASSIFICATION DEFECTS CLOSED (user-validated); strategy refactor remains.

Reference model: judgment -> plan -> action.

## Situation

Hero previously called a first raise, then a later player raises and action returns to hero.

Canonical forms:

1. open -> hero call -> squeeze -> hero;
2. open -> caller -> hero call -> squeeze -> hero;
3. limp -> open -> hero call -> squeeze -> hero;
4. open -> hero call -> short incomplete all-in raise -> hero;
5. open -> hero call -> full all-in squeeze -> hero;
6. open -> hero call -> squeeze -> opener calls -> hero;
7. open -> hero call -> squeeze -> opener 4bets before hero returns;
8. hero is already partially committed and may or may not retain raise rights.

This is not the same state as:
- opener facing a 3bet;
- unacted player facing the first raise;
- limper facing the first isolation raise.

## Rational judgment inputs

- hero's prior call range and motive;
- current squeeze size;
- squeezer estimated range;
- original opener range and response;
- any cold callers;
- hero's already-invested contribution;
- actual additional price to continue;
- hero/squeezer/opener effective stacks;
- whether action has been reopened legally;
- players still live behind;
- ICM / tournament state;
- previous preflop line.

## Rational plan candidates

If raise rights are open:
- fold;
- call additional amount;
- value backraise;
- bluff backraise where coherent;
- backraise shove / effective-stack commitment.

If raise rights are closed by an incomplete all-in:
- fold;
- call only.

The plan must not ask execution to discover that a raise was illegal and silently replace it.

---

# Fixed defects

## P5-1 FIXED — string "allin" was treated as a raise

Old session logic counted every `allin` log action as a raise.

But poker distinguishes:
- all-in call;
- incomplete all-in raise;
- full all-in raise.

Consequences included possible corruption of:
- raise level;
- current aggressor;
- 3bet/4bet observation counters;
- caller counts.

Fix:
`runner.Round` now records rule-derived `action_meta` with:
- `raised`;
- `full_raise`;
- `incomplete_raise`;
- `allin_call`;
- `full_raise_count`.

The old public log is retained for compatibility.

## P5-2 FIXED — raise level now counts actual full raises

Old:
count strings `raise/allin` in the log.

New:
use `Round.full_raise_count`.

An all-in call no longer turns a 3bet spot into a 4bet-level spot.
An incomplete raise changes the price but does not falsely become another full-raise level.

## P5-3 FIXED — aggressor/caller state follows actual rule event

Human, replay, and bot branches previously updated `aggressor` from the requested action string.

Now they update from `action_meta` after the action is legally applied.

An all-in call therefore remains a call instead of becoming the new aggressor.

## P5-4 FIXED — opener fold-to-3bet was contaminated by callers facing squeezes

Old preflop observation logic used only "number of raises before actor".

A player who:
`call open -> face squeeze -> fold`

was counted in `pf_fold_to_3bet`.

But that statistic is consumed as:
"when **this opener** gets 3bet, how often do they fold?"

This mixed two strategically different populations.

Fix:
public action roles are now classified explicitly.

`pf_fold_to_3bet` only records the **first raiser** responding to the second full raise.

## P5-5 FIXED — 4bet frequency mixed opener 4bets and caller backraises

Old `pf_4bet` could include any actor acting after two raises.

That mixed:
- opener -> face 3bet -> 4bet;
- caller -> face squeeze -> backraise;
- other cold-action cases.

Fix:
- opener 4bet stays in `pf_4bet`;
- caller backraise is separately observed as `pf_backraise`;
- caller fold after call+squeeze is separately observed.

The new backraise channels are SHADOW only for now; no new strategy coefficient was invented.

## P5-6 FIXED — old persisted read books could miss new keys

`Book.rec` previously used `setdefault(key, defaults)`, which only initializes a new record.

An existing saved record created before a schema addition would not receive new fields and could
raise KeyError when the new observer wrote into it.

Fix:
`Book.rec` now hydrates missing default fields on every access.

## P5-7 FIXED — plan could choose an illegal re-raise after incomplete all-in

Old architecture:

```
strategy chooses raise
-> Round.can_raise says no
-> ValueError
-> session silently calls
```

That violates judgment -> plan -> action.

Fix:
actual `rnd.can_raise(seat)` is passed into preflop planning.
If raise rights are closed:
- hot-zone reshove branch is disabled;
- raise weight is zeroed before plan selection.

Execution no longer has to change a strategic raise into a call for this case.

---

# Remaining strategic gaps

## P5-A ARCH_MISMATCH — caller-vs-squeeze still reuses generic defend machinery

The actor's prior role is now preserved in `pf_line`, but `defend_decision` still does not use it
as a first-class judgment input.

Thus a caller facing a squeeze is still too close structurally to an opener facing a 3bet.

Correct future judgment should condition on:
- caller's capped/uncapped prior range;
- whether the call was trap / realization / implied odds;
- opener still live behind;
- squeeze range.

## P5-B MISS — exact caller-specific ranges/stacks are not consumed

The full public story exists, but the current scalar interface still mainly provides:
- latest aggressor read;
- caller count.

It does not yet pass separate original-opener/caller/squeezer range pools into preflop response planning.

## P5-C MISS — actual additional price and sunk contribution are not first-class plan inputs

The code knows `Round.to_call` and `Round.contrib`, but generic defense thresholds still center on
the total current target `open_bb`.

For back-action, the player has already invested chips.  The correct response should see:
- sunk contribution;
- incremental call price;
- actual pot;
- side-pot/effective-cap geometry.

Do not patch with another constant.

## P5-D MISS — live players after hero response are not modeled explicitly

A backraise can still face:
- squeezer response;
- opener response;
- cold caller response.

The strategic plan needs those players and stacks, not only position-based population pressure.

## P5-E ARCH_MISMATCH — explicit response motive still absent

Needed plan motives include:
- call_realize_after_squeeze;
- trap_call_continue;
- value_backraise;
- bluff_backraise;
- backraise_shove;
- fold.

The current function still directly returns an action.

## Verification target

`tools/verify_p5_backaction.py` checks:

1. all-in call is not a raise;
2. incomplete raise does not increment full-raise level;
3. caller fold to squeeze is not counted as opener fold-to-3bet;
4. caller backraise is a separate observation class;
5. old read records hydrate new keys;
6. closed raise rights remove raise plans.


## Validation

User validation (Termux, 2026-09-26): compile succeeded and `tools/verify_p5_backaction.py` reported `6/6 P5 structural checks passed`.
