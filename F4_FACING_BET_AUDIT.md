# Sequential audit — F4 flop, unacted hero faces a bet

Status: CLEAR F4 WAGER/EVENT-SEMANTIC DEFECTS FIXED; multiway response strategy remains open.

Reference model: judgment -> response plan -> action.

## Situation

Hero has not checked earlier in the current street and reaches a decision with `tocall > 0`.

Canonical cases:

1. opponent bets -> hero;
2. opponent bets -> caller -> hero;
3. opponent bets -> multiple callers -> hero;
4. opponent raises another player -> hero cold response;
5. short all-in bet/raise -> hero;
6. incomplete all-in changes the price;
7. multiway side-pot/live-player cases.

This is distinct from F3:

```
hero check -> opponent bet -> hero
```

F3 owns check-raise production.  F4 owns direct facing-bet/raise response.

## Rational judgment inputs

- exact current pot;
- exact incremental price hero must call;
- **actual size of the aggressor's latest wager relative to the pot before that wager**;
- aggressor range/read;
- each other live opponent range;
- joint equity;
- hero relative/made/draw strength;
- players still to act;
- legal raise right;
- effective stacks;
- line/barrel history;
- ICM;
- stable skill/perception limits.

## Response-plan candidates

- fold;
- call / bluff-catch;
- value raise;
- semibluff raise;
- bluff raise;
- effective-all-in raise where legal.

The current response plan must be chosen before execution.

---

# Fixed defects

## F4-1 FIXED — hero call price was used as opponent bet size

Old line-read code used:

`size = hero_to_call / current_pot`.

Old calldown sizing perception reconstructed:

`hero_to_call / (current_pot - hero_to_call)`.

Those only approximate the aggressor's true bet fraction in the simplest heads-up first-bet case.

Example:

```
pot 100
A bets 50
B calls 50
hero acts
```

Actual A sizing:
`50 / 100 = 0.50 pot`.

Old line read:
`50 / 200 = 0.25 pot`.

The caller's chips were incorrectly interpreted as evidence about A's sizing.

Fix:
`Round.action_meta` now preserves each action's exact chip increment.
Session reconstructs:

`aggressor increment / pot immediately before aggressor action`.

That value is passed separately from hero's actual call price.

## F4-2 FIXED — sizing-tell observation used target / street-start pot

Old postflop `observe_size` used:
- logged target amount;
- divided by the pot at the start of the street.

This is wrong after calls/raises and wrong for a player acting a second time.

Fix:
sizing observation now uses:

`chips newly invested on this action / pot immediately before this action`.

## F4-3 FIXED — all-in call could become the new postflop aggressor

The human postflop branch previously did:

`if action string in bet/raise/allin: aggressor = seat`.

But `allin` can be an all-in **call**.

Fix:
aggressor changes only when `Round.action_meta['raised']` is true.

Bot execution uses the same rule-event source.

## F4-4 FIXED — postflop reads treated all-in call/raise by UI spelling

`observe_postflop` receives normalized rule semantics now:

- all-in raise -> `raise`;
- all-in call -> `call`.

Thus:
- cbet/barrel counts;
- aggressive/passive action counts;
- fold-to-bet contexts;

no longer depend on whether the action happened to be spelled `allin`.

## F4-5 FIXED — barrel count lagged one street

When hero faced a turn bet, the current turn action was still in `r2.log`, not yet in `full_log`.

Old `n_barrels` therefore counted completed previous streets only.

A flop bet + current turn bet could be interpreted as one barrel instead of two.

Fix:
barrel count uses actual aggressive **street count** from:
- completed `full_action_meta`;
- current `Round.action_meta`.

## F4-6 FIXED — check-through/no-bite detection used action strings

An all-in call string could make a street look as though a bet occurred.

That could:
- prevent trap no-bite handling;
- corrupt delayed-cbet/check-through context.

Fix:
street aggression/check-through now prefers actual `raised` metadata.

---

# What is already structurally sound

## F4-K1 KEEP — current opponent pools reach joint equity

The previously validated per-opponent range preservation is used before the response.

## F4-K2 KEEP — legal raise rights reach plan selection

An incomplete all-in that closes raising rights removes raise candidates before execution.

## F4-K3 KEEP — F3 and F4 raise producers are now separated

If hero checked earlier:
- checkraise gate owns the raise.

If hero had not checked:
- generic direct response may choose a raise.

---

# Remaining strategic gaps

## F4-A MAJOR MULTIWAY GAP — raise quality still uses union-range strength in places

Joint equity is opponent-specific, but generic value-raise logic can still use
`relative_strength(hero, board, opp_range)` where `opp_range` is a union.

For bet + caller + hero, raise decisions should reason about:
- bettor continuing range;
- caller continuing range;
- who can re-raise;
- who is capped/uncapped.

## F4-B MAJOR MULTIWAY GAP — one aggressor read plus behind-count is not enough

`calldown_need` receives:
- one aggressor read;
- count of players behind.

Joint equity sees all ranges, but exploit/risk adjustment does not yet model each live player's:
- raise propensity;
- stack;
- call/overcall range.

## F4-C REVIEW — the same observed opponent information can affect response through multiple channels

Line bluff prior and opponent behavioral read can both derive from the same observation history.

They represent different concepts:
- line-specific bluff likelihood;
- stable opponent tendency.

But the later architecture should explicitly document how these combine so the same evidence is
not accidentally counted twice.

## F4-D ARCH_MISMATCH — response plan is still not a persistent first-class object

The response calculation returns an action/size/reason and writes trace provenance.

The future target is an explicit object such as:

```
{
  goal: bluffcatch / value_raise / semibluff_raise / fold,
  action: call / raise / fold,
  strategic_size: ...,
  evidence: ...
}
```

before ACTION.

## F4-E GLOBAL — emotion and execution-boundary issues remain

As in F1-F3:
- current tilt still alters the judgment profile;
- execution can still reshape strategic size.

Those remain global V2 refactors.

---

# Verification target

`tools/verify_f4_facing_bet.py` checks:

1. per-action chip increment is exact;
2. bet->call->hero preserves the original bettor's true size fraction;
3. calldown sizing perception receives that facing-wager fraction rather than hero call-price proxy;
4. barrel count includes the current street exactly once;
5. all-in call/raise normalize to passive/aggressive observation semantics;
6. session aggressor update is rule-event based.


## Validation

User validation (Termux, 2026-09-26): compile succeeded and `tools/verify_f4_facing_bet.py` reported `6/6 F4 structural checks passed`.
