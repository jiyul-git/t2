# Sequential audit — F6 caller back-action after a later raise

Status: INFORMATION-PRESERVATION / RESPONSE-PLAN STRUCTURE FIXED IN BRANCH; strategy model remains incomplete.

Reference model: judgment -> response plan -> action.

## Situation

Hero has already called on the current street.  A later opponent then raises/re-raises and action
returns to hero.

Canonical cases:

1. bet -> hero call -> player behind raises -> hero;
2. check -> bet -> hero call -> later player raises -> hero;
3. bet -> raise -> hero call -> another player re-raises -> hero;
4. hero calls an incomplete all-in raise and later price/action returns where legal;
5. bet -> hero call -> raise -> original bettor re-raises -> hero;
6. main-pot all-in + live side-pot player raises -> hero.

This is POST-E from `OPPONENT_ACTION_COVERAGE_V1.md`.

## Rational judgment inputs

The new decision must preserve:

- what price/event hero called previously: bet vs raise;
- current raiser/re-raiser and exact size;
- full-raise depth;
- full vs incomplete raise;
- hero's existing street contribution;
- new incremental call price;
- current pot;
- raise rights open/closed;
- every live opponent's perceived range;
- players still to act;
- effective-stack/side-pot eligibility;
- prior line plan and prior response plan;
- current board/hand/joint equity;
- ICM and stable skill limits.

## Rational response-plan candidates

If raise rights remain open:
- fold;
- call additional amount;
- value backraise;
- semibluff backraise on flop/turn;
- coherent bluff backraise;
- shove/effective-all-in.

If raise rights are closed:
- fold;
- call only.

The previous call is sunk history.  A later raise is new information and therefore creates a new
response plan.

---

# Fixed defects

## F6-1 FIXED — caller_backaction lost what hero had originally called

Old response context retained:

- `prior_action='call'`;
- current `facing_kind='raise'`.

But it did not retain whether that call had been:

- call of a first bet;
- call of a raise.

Thus:

```
bet -> hero call -> raise
```

and

```
bet -> raise -> hero call -> re-raise
```

collapsed to the same stored context.

Fix:
`_postflop_response_context` now preserves `prior_facing_kind`.

## F6-2 FIXED — raise depth / incomplete-raise semantics were not in response provenance

The rules engine already knows full vs incomplete raises, but the response context did not carry it.

Fix:
response context now preserves:

- `raise_depth_full`;
- `raise_depth_any`;
- `facing_full_raise`;
- `facing_incomplete_raise`.

This is derived from public rule events, not action-string guesses.

## F6-3 FIXED — facing-wager decisions had no persistent current-action plan object

The engine had:
- line plan in `plan_state['plan']`;
- response trace;
- final action.

But no explicit persistent object representing:

"given this new opponent action, this is the action I now plan to take."

That made repeated same-street re-decisions hard to distinguish from execution logs.

Fix:
`record_response_plan` now stores per-street response plans.

Each record preserves:
- response kind;
- full response context;
- chosen act;
- strategic target or raise multiplier;
- need;
- estimated equity;
- source;
- reason.

Check-raise plans and generic response plans both use this structure.

Execution can still differ due legality/replay, which remains visible separately in execution provenance.

---

# What remains sound

## F6-K1 KEEP — exact chip coordinates from F5 apply to caller back-action too

A re-raise target is represented in total street-contribution coordinates.

Hero's previous call contribution is included.

## F6-K2 KEEP — joint equity uses separate opponent pools

The current equity call can preserve distinct opponent ranges.

## F6-K3 KEEP — current raise rights are checked before generating raise action

Incomplete all-in semantics therefore remain upstream of execution.

---

# Remaining strategic gaps

## F6-A MAJOR MISS — response selector does not yet use caller-backaction as a distinct strategy state

`response_kind` and the richer context are now preserved, but `decide_response` still uses one
generic response policy for:

- first bet;
- cold raise;
- aggressor back-action;
- caller back-action.

This means the information exists but is not yet fully consumed.

Correct caller-backaction strategy should explicitly condition on:
- the range with which hero called previously;
- whether that call was vs bet or raise;
- new raiser range;
- original bettor/raiser still live;
- new price and stack geometry.

Do not patch this with a single caller-backaction multiplier.

## F6-B MAJOR MISS — raise inference is not semantically distinct enough

As already found in F5, `ranges.narrow_by_actions` routes bet and raise through closely related
aggressive narrowing.

A player raising after a bet/call sequence has a different range from a first bettor.

A future model needs explicit raise-range construction rather than an arbitrary extra-tightening
constant.

## F6-C MAJOR MULTIWAY/SIDE-POT MISS — all-in main-pot opponents are excluded from active street Round

At each postflop street, `session` builds `active` from players with stack > 0.

Players already all-in remain showdown-eligible but are absent from the live betting Round.

That is legally correct for who may act, but a single scalar/joint-equity state is then insufficient
for side-pot strategy.

Example:

```
A all-in in main pot
B and hero still deep
B raises side pot
hero acts
```

Hero's decision contains two economically different equities:
- locked main-pot equity vs A+B;
- marginal side-pot equity vs B.

Simply adding A back into one joint-equity pool would also be wrong.

Target architecture must separate:
- main-pot eligibility/equity;
- each side-pot eligibility/equity;
- marginal EV of the current call/raise.

## F6-D MISS — opponent roles remain partly compressed

In:

```
A bet -> hero call -> B raise -> A call -> hero
```

the response should reason separately about:
- B's raise range;
- A's bet-then-call range;
- whether A can re-raise;
- both stacks.

Joint equity preserves pools, but exploit/response policy still emphasizes one aggressor.

## F6-E GLOBAL — emotion and execution sizing boundary remain open

Still global:
- current tilt mutates judgment through `tilted_view`;
- session/runner may reshape strategic sizing after plan choice.

---

# Verification target

`tools/verify_f6_caller_backaction.py` checks:

1. call-vs-bet then raise preserves `prior_facing_kind='bet'`;
2. call-vs-raise then re-raise preserves `prior_facing_kind='raise'`;
3. full raise depth is preserved;
4. incomplete raise is explicitly preserved;
5. caller back-action creates a persistent response-plan object;
6. the response plan carries the complete response context.


## Validation

User validation (Termux, 2026-09-26): compile succeeded and `tools/verify_f6_caller_backaction.py` reported `4/4 F6 structural checks passed`.
