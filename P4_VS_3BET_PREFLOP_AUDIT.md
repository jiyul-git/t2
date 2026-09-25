# Sequential audit — P4 hero opened, then faces a 3bet

Status: CLEAR INFORMATION-FLOW DEFECTS CLOSED (user-validated); strategy refactor remains.

Reference model: judgment -> plan -> action.

## Situation

Hero previously opened, action continued, and a later player made the first re-raise.

Subcases:

1. open -> 3bet -> hero;
2. open -> caller -> squeeze -> hero;
3. open -> multiple callers -> squeeze -> hero;
4. open -> short-stack 3bet -> hero;
5. open -> 3bet -> cold caller -> hero;
6. open -> 3bet all-in -> hero;
7. hero has players still to act after responding;
8. hero covers the 3bettor, is covered by them, or has deeper live players behind.

## Rational judgment inputs

- hero original open range and motive;
- hero actual hand;
- 3bettor position, size and estimated 3bet range;
- whether the 3bet is linear/polarized;
- hero/3bettor effective stack;
- current pot and hero's already-invested chips;
- cold callers before/after the 3bet;
- live players behind hero;
- 3bettor 4bet-response tendencies where relevant;
- ICM/tournament pressure;
- previous preflop story.

## Rational plan candidates

- fold;
- call to realize;
- call to under-represent premium;
- value 4bet;
- bluff 4bet;
- 4bet shove;
- effective-stack commitment without physically shoving deeper players;
- trap-call with top range.

The current action plan then contains exact strategic size/form.

## Fixed defects

### P4-1 FIXED — preflop story was overwritten on every action

Before:
`h.pf_seed[seat] = new_seed`.

If hero:
`open -> face 3bet -> call`

the final seed remembered only:
`role=defend, act=call`.

The original open action/story disappeared.

Fix:
`_merge_pf_seed` now preserves:
- `pf_line`;
- origin role/action;
- each decision's facing level;
- target size;
- caller/limper counts.

This does not yet create the final V2 plan object, but the chronological evidence is no longer destroyed.

### P4-2 FIXED — postflop range reconstruction ignored re-raise level

`ranges.preflop_range` previously always used `raise_level=1`.

So:
- call a first open;
- call a 3bet after opening;
- call a 4bet;

could all be reconstructed from the same first-open defense band.

Fix:
`raise_level` is now preserved in `pf_seed` and passed into range reconstruction.

The exact facing target `pf_open_bb` and caller count are also preserved and passed.

### P4-3 FIXED — opponent true persona leaked into hero's range judgment

This was a major information leak.

Old postflop range construction did:

`oax, _ = h.axes(opponent)`

then used the opponent's **real** persona/temperament to build the range that hero supposedly
believed.

The observer could therefore benefit from hidden information they had never learned.

Fix:
opponent range construction now uses:
`reads.perceived_profile -> reads.range_profile`

only.

Unknown traits fall back to population-neutral values.  Actual hidden opponent persona/tilt is
not passed into the observer's preflop range model.

### P4-4 FIXED — 3bet+ pot provenance gate was dead

`update_plan` checked:

`pf_role == 'defend' and pf_act == 'raise'`.

But `defend_decision` returns aggressive responses as `3bet` or `shove`, so that condition
did not represent the live path.

Fix:
the provenance gate now uses `pf_initiative` for a defend-role aggressive action.

### P4-5 CLEANED — unused explicit variance/tilt calculation

`defend_decision` still computed `variance_seek(... tilt ...)` even though the result was not
used.

Removed.  The global emotion-boundary refactor remains separate.

## Remaining strategic gaps

### P4-A ARCH_MISMATCH — no explicit response-plan object

Current code still directly returns:
`fold / call / 3bet / shove`.

It does not persist:
- value_4bet;
- bluff_4bet;
- premium trap-call;
- realization call;
- effective-stack commitment.

### P4-B REVIEW — higher-raise baseline is still derived from first-open defense machinery

`defend_thresholds` starts from `gto.defend_pct/threebet_pct`, then applies
`LEVEL_TIGHTEN` for raise_level >= 2.

That preserves internal consistency, but conceptually a response to a 3bet should be built from:
- hero's original opening range;
- opponent's 3bet range;
- current size/effective stack;

rather than simply "first-open defense, tightened".

Do not invent replacement coefficients here.  This needs the explicit plan/range architecture.

### P4-C MISS — effective stack is not separated from physical stack

The response layer still receives hero remaining stack as `stack_bb`.

Needed:
- actor physical cap;
- effective cap vs the current 3bettor;
- deeper players behind;
- strategic effective-all-in target.

Otherwise:
hero 100bb vs 3bettor 24bb with another 100bb player behind
cannot be represented cleanly by one scalar stack.

### P4-D MISS — squeeze/cold-call actors are reduced too aggressively

The current scalar `n_callers` describes calls after the latest raise, not the complete identity
and strength of all players who entered before the squeeze.

The full public log exists, but P4 judgment does not yet consume separate caller ranges/stacks.

### P4-E MISS — players behind hero are not first-class P4 inputs

After hero faces a 3bet, players behind can:
- cold call;
- cold 4bet;
- jam;
- have short reshove stacks.

Those specific threats are not yet represented in the response-plan input.

### P4-F REVIEW — public information should ultimately replace pf_seed for opponent reconstruction

The fixed code no longer consumes hidden opponent persona.

However, some action provenance for range reconstruction is still retrieved through the
internally stored `pf_seed`.

The fields currently consumed are public-action-derived, but the robust endpoint is:
parse the public preflop action story itself, so an observer never depends on another player's
private planning record.

## Verification target

`tools/verify_p4_vs_3bet.py` checks:

1. open -> face 3bet story is preserved rather than overwritten;
2. range reconstruction responds to raise level;
3. observed range profile is built from perceived data;
4. session no longer calls opponent true axes in the opponent range loop;
5. P3/P4 response context fields survive in the seed.


## Validation

User validation (Termux, 2026-09-26): compile succeeded and `tools/verify_p4_vs_3bet.py` reported `5/5 P4 structural checks passed`.
