# Sequential audit — P6 preflop all-in / call-off / overcall / side-pot

Status: CLEAR ALL-IN ROUTING/PROVENANCE DEFECTS FIXED; strategy model remains incomplete.

Reference model: judgment -> plan -> action.

## Situation families

P6 is not one case.  It contains several strategically different branches.

1. hero short, faces a non-all-in raise that effectively puts hero all-in;
2. opponent open-shoves and hero covers them;
3. opponent 3bet/4bet shoves and hero covers them;
4. hero faces shove + caller(s);
5. hero faces shove with another live stack still able to raise;
6. incomplete short all-in changes the price but does not reopen hero's raise rights;
7. all remaining opponents are all-in, so hero can only fold/call;
8. main-pot all-in exists but live side-pot opponent(s) remain;
9. hero's call itself exhausts hero's stack;
10. hero can reshove over a shorter all-in because another live opponent can still respond.

These must not collapse into a single "allin" flag.

## Rational judgment inputs

- exact incremental amount hero must call;
- exact contestable pot before hero acts;
- hero physical remaining stack;
- latest aggressor's cap and whether they are all-in;
- all other live players and their remaining stacks;
- whether hero's raise rights are open;
- main-pot vs side-pot eligibility;
- opponent-specific shove/call ranges;
- hero's equity against all continuing ranges;
- pot odds;
- ICM / bubble factor;
- players still to act;
- previous preflop story.

## Rational plan candidates

When no live responder remains:
- fold;
- call / call-off.

When another live stack can respond and raise rights are open:
- fold;
- call/overcall;
- value reshove;
- pressure reshove where coherent;
- effective-stack commitment that is not the same as physically shoving a covering stack.

When raise rights are closed after an incomplete all-in:
- fold;
- call only.

---

# Fixed defects

## P6-1 FIXED — short opponent shove did not enter call-off path when hero covered

Old routing used only:

`open_bb >= hero_stack * 0.92`.

Example:

```
hero 100bb
villain shoves 20bb
heads-up / no other live responder
```

Because 20 < 92% of hero's 100bb, the decision went through ordinary defend logic even though
postflop is impossible and hero's only legal strategic options are fold/call.

Fix:

Pure short-shove call-off now triggers when:
- latest aggressor is all-in; and
- no legal live responder exists, so hero cannot raise.

The old hero-own-stack call-off trigger remains for cases where calling the current target
effectively consumes hero's own stack.

## P6-2 FIXED — actual pot and incremental call price were discarded

`calloff_decision` accepted `pot` and `tocall`, but callers were feeding approximations such as:

`1.5 + open_bb * (1 + n_callers)`

and total target instead of the actual incremental price.

Fix:
session now passes from `Round`:
- contestable pot before action, including ante;
- actual incremental `to_call`;
- facing-all-in state;
- legal raise right.

These are also stored in preflop provenance:
- `pf_pot_bb`;
- `pf_to_call_bb`;
- `pf_facing_allin`;
- `pf_can_raise`.

## P6-3 FIXED — a normal "call" that exhausted the stack was not tagged as all-in call

Bot call-off plans return `call`, and `Round.apply` can consume the caller's entire remaining stack.

Old `action_meta['allin_call']` was true only when the input action string itself was `allin`.

Fix:
any non-raising call/allin action that leaves the actor in `Round.allin` is classified as
`allin_call`.

This keeps strategic event classification independent of the UI/action spelling.

## P6-4 KEEP — contestable contribution already caps unreachable side-pot chips

`Round.contestable_contrib(seat)` caps every opponent's current-street contribution by the
maximum amount this seat can reach.

That is the correct legal foundation for:
- short-stack call prices;
- main-pot-only eligibility;
- avoiding pot odds based on chips the player cannot win.

The strategy layer still needs richer side-pot semantics, but the legal contribution primitive is sound.

---

# Remaining strategic gaps

## P6-A MAJOR MISS — call-off model does not yet compare equity to pot odds directly

This is now explicit.

`calloff_decision` receives the correct:
- pot;
- incremental call price.

But `calloff_cap` remains a percentile-threshold heuristic based on:
- defend range;
- raise level;
- stack-depth adjustment;
- bubble factor;
- coarse opponent exploit read.

It does **not** yet calculate:

```
required equity = call / (pot + call)
hero equity vs estimated shove/overcall ranges
EV(call) vs EV(fold)
```

Therefore the old comment claiming a pure equity-vs-pot-odds decision was stronger than the
implementation.

Do not repair this with another hand-tuned multiplier.

Target:
opponent-specific preflop range pools + exact joint preflop equity + actual pot odds + ICM adjustment.

## P6-B MAJOR MISS — multiway all-in/overcall uses caller count, not caller ranges

A shove plus one loose caller and a shove plus one very tight caller are strategically different.

Current `n_callers` tightening cannot represent:
- each caller's range;
- each caller's stack;
- joint hero equity;
- caller who is already all-in vs live caller.

This must reuse the per-opponent range-preservation principle already fixed postflop.

## P6-C MAJOR MISS — main-pot and live side-pot strategy is not explicit

Example:

```
A short stack all-in
B deep stack calls
hero deep stack acts
```

Hero's decision includes:
- equity in the main pot against A+B;
- possible side-pot value/bluff strategy against B;
- whether a raise can create a side pot;
- B's response range.

A scalar `n_callers` cannot express this.

## P6-D MISS — effective cap and physical shove remain conflated in preflop strategy

Example:

```
hero 100bb
all-in opponent 20bb
live player behind 100bb
```

"commit effectively to the 20bb player" is not the same as physically shoving 100bb into the
live player behind.

Required eventual state:
- hero physical cap;
- each opponent effective cap;
- legal raise target;
- strategic effective-all-in target;
- physical all-in flag.

## P6-E ARCH_MISMATCH — no explicit call-off/reshove plan motive

Current action output still loses motive:

- value_calloff;
- exploit_calloff;
- overcall;
- value_reshove;
- pressure_reshove;
- sidepot_isolation.

These belong in the future explicit preflop response-plan object.

## P6-F REVIEW — all-in opponent with live responder remains on general response path

This is deliberate for now.

If the aggressor is all-in **but another live player can respond**, hero may still raise.
Forcing the pure fold/call call-off path would incorrectly remove reshove.

The current general response path preserves the legal option, but its strategy remains too coarse
until P6-B/P6-C/P6-D are implemented.

---

# Verification target

`tools/verify_p6_calloff.py` checks:

1. a stack-exhausting `call` is tagged as all-in call;
2. hero 100bb vs short all-in with no raise option routes to call-off;
3. exact pot and incremental call price reach call-off routing;
4. short all-in with a live responder does not incorrectly force fold/call-only routing;
5. contestable contribution excludes unreachable side-pot chips;
6. P6 context survives in preflop provenance.
