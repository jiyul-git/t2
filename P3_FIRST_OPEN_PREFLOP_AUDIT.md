# Sequential audit — P3 facing first open raise

Status: CLEAR DOMAIN LEAK FIXED; strategic architecture gaps remain.

Reference model: judgment -> plan -> action.

## Situation

Hero has not voluntarily raised yet and faces the first full preflop raise.

Subcases are explicitly distinct:

1. open -> hero;
2. open -> caller -> hero;
3. open -> multiple callers -> hero;
4. open -> short all-in caller -> hero;
5. hero is in a blind and already has forced chips invested;
6. players remain behind hero;
7. opener is short / medium / deep relative to hero;
8. one or more callers cover hero or are short.

The current P3 audit excludes the special case where the **opener itself is all-in**.
That is audited under P6 call-off / reshove because legal response options change.

## Rational judgment inputs

- hero hand / position;
- opener position and estimated opening range;
- exact open size;
- opener stack and **effective stack vs hero**;
- caller identities, ranges, stacks and actions;
- dead money;
- players still to act behind hero;
- behind players' squeeze/cold-4bet tendencies and reshove stacks;
- hero's forced blind contribution / exact price to call;
- tournament/ICM context;
- previous observations and confidence;
- stable skill/perception limits.

## Rational plan candidates

### Fold
Hand does not justify continuing at the current price/risk.

### Flat
Possible motives:
- realize equity;
- preserve dominated worse ranges;
- pot control / avoid 4bet;
- positional realization;
- deliberate premium under-representation;
- exploit weak postflop opponent;
- multiway implied-odds realization.

### 3bet
Possible motives:
- clear value;
- linear/merged value-pressure raise;
- polarized bluff 3bet;
- isolation of opener;
- exploit wide opener;
- exploit opener who overfolds to 3bet.

### Squeeze
Open + caller(s) create extra dead money.
The plan must distinguish:
- value squeeze;
- bluff squeeze;
- reshove squeeze.

### Reshove
At appropriate effective depth:
- value reshove;
- fold-equity reshove;
- squeeze reshove.

Final action form:
`fold / call / raise / effective-all-in / physical-all-in`.

The last two must not be conflated when hero covers a short opponent and deeper live players remain.

---

# Current code path

```
session
 -> aggressor = latest raiser
 -> callers = count after latest raise
 -> perceived_profile(opener)
 -> preflop_plan
      -> read_opponent
      -> defend_decision
           -> defend_thresholds
           -> opener exploit adjustments
           -> optional hot-zone reshove branch
           -> fold/call/3bet mixed weights
           -> raise_form
 -> session converts 3bet/shove to Round action
```

## What is already structurally sound

### P3-K1 KEEP — open size and position enter baseline defense

`defend_thresholds` uses:
- hero position;
- opener position;
- actual open target size;
- seats;
- stack-depth input;
- ante;
- number of callers.

This is substantially better than a fixed "top X%" defense chart.

### P3-K2 KEEP — opener-specific exploit channels are preflop-specific

The current first-open response can use:
- opener width vs positional baseline (`open_gap`);
- fold-to-3bet (`f2tb_gap`);
- 4bet frequency (`fb_gap`).

This is the correct category of evidence.  It does not intentionally use postflop fold-to-bet
for the normal 3bet exploit path.

### P3-K3 KEEP — squeeze is not treated identically to single-open defense

`n_callers`:
- tightens total continuation;
- changes 3bet share;
- enlarges raise target;
- changes reshove fold-equity assumptions.

The semantic coverage exists, although caller-specific information is still lost.

---

# Fixed defect

## P3-1 FIXED — postflop thin-value skill changed preflop 3bet/flat mix

Old code used:

`PS.sk(prof, 'thin_value')`

inside `defend_decision`.

Because generic `thin_value` aliases to `thin_value_turn`, changing a player's **turn thin-value
skill** changed whether they 3bet or flat premiums preflop.

That is a direct domain leak.

Fix:
- removed the thin-value dependency;
- premium under-representation now uses stable `slowplay_taste` and aggression;
- no new preflop concept was invented just to patch the leak.

The old unused `variance_seek(...tilt...)` local in `defend_decision` was also removed.
It was calculated and never consumed.

---

# Remaining strategic gaps

## P3-A ARCH_MISMATCH — no explicit response-plan object

`defend_decision` still directly chooses:
- fold;
- call;
- 3bet;
- shove.

It does not return an explicit motive such as:
- value_3bet;
- bluff_3bet;
- flat_realize;
- premium_underrep;
- value_squeeze;
- bluff_squeeze;
- reshove.

So flop receives action provenance but not the strategic reason.

Target:
`judge_first_open -> choose_response_plan -> execute`.

## P3-B MISS — effective stack vs opener is not a first-class input

The current `stack_bb` passed to `defend_decision/raise_form` is hero's remaining physical stack.

That is not equivalent to effective stack.

Example:
- hero 100bb;
- opener 24bb;
- hero faces 2.5bb.

The strategic geometry is approximately 24bb against the opener, but the current raise-form
geometry can reason from hero's 100bb physical stack.

This cannot be fixed by simply replacing `stack_bb` with `min(hero, opener)`, because a
strategic "effective all-in to 24bb" is **not** the same as physically shoving 100bb when deeper
players remain behind.

Required refactor:
separate:
- actor physical stack/cap;
- effective cap vs each opponent;
- strategic effective-all-in target;
- physical all-in action.

## P3-C MISS — caller identities are reduced to a count

For open + caller(s), current planning receives `n_callers`, but not the callers' separate:
- ranges;
- stack depths;
- call tendencies;
- backraise tendencies;
- postflop weaknesses.

Thus:

```
tight opener + strong cold caller
```

and

```
loose opener + weak recreational caller
```

can share the same `n_callers=1` structural input despite requiring different squeeze/flat plans.

This is the preflop counterpart of the multiway information-preservation work already completed
postflop.

## P3-D MISS — players behind are not strategically modeled in first-open defense

The baseline position already indirectly reflects how many players exist behind, but the current
P3 planner does not consume their actual:
- squeeze/cold-4bet frequencies;
- reshove stack sizes;
- coverage of hero;
- individual ranges.

Specific table information is therefore lost.

Do not reuse unopened `table_pressure` blindly: facing-open behind threats have different
semantics (squeeze/cold-4bet rather than ordinary 3bet vs open).

## P3-E REVIEW — squeeze is an action family but motive is not represented

The code changes thresholds and sizing when callers exist, so squeeze behavior exists.

But it cannot distinguish in persistent plan state:
- value squeeze;
- bluff squeeze;
- isolation squeeze;
- reshove squeeze.

This should be solved by the response-plan representation, not by creating four disconnected
action functions.

## P3-F ARCH_MISMATCH — emotion boundary still wrong globally

Current `profile` can already be a `tilted_view`, so tilt may affect judgment inputs.

At the same time the explicit tilt argument in this P3 function was dead.

Under V2:
- judgment uses stable skill/personality;
- one explicit emotion state biases response-plan selection;
- execution receives no emotion.

## P3-G REVIEW — exact pot / blind investment is not a clean planning input

Normal defense uses `open_bb` as open target size, which is correct for range context.

But raise-form/call-off geometry still contains approximations such as:
`1.5 + open_bb*(1+n_callers)`.

Actual pot can differ because of:
- ante;
- hero blind already invested;
- caller stack caps;
- unusual all-in contributions.

Do not patch this with another constant.  The later response-plan interface should receive
actual current pot, hero contribution and each opponent contribution from `Round`.

## P3-H DEFER TO P6 — opener all-in

If the opener itself is all-in, hero may:
- fold;
- call;
- overcall;
- reshove only if live opponents remain and a raise is legal/useful.

This is not ordinary P3 and is handled under P6.

---

# P3 decision before moving on

Immediate code defect fixed:
- cross-domain thin_value leak.

Do not yet invent coefficients for:
- caller-specific squeeze strategy;
- behind-player cold-action pressure;
- effective-stack action forms.

Those need the explicit judgment/plan state so information can be preserved without another set
of hidden multipliers.

Targeted verifier:
`tools/verify_p3_first_open.py`.
