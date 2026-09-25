# Sequential audit — F8 main-pot / side-pot decision semantics

Status: **MAJOR DECISION-LAYER GAP CONFIRMED; settlement/legal primitives are sound; no strategy fix applied yet.**

Reference model: `judgment -> plan -> action -> observed result -> next judgment`.

## Why F8 exists

F7 closed the public action story across streets, but explicitly left one unsolved case:

> a player is already all-in while two or more deeper players continue.

That state is not described by one scalar pot and one opponent set.

Example after a previous street:

```
A: all-in, total contribution 20
B: live,   total contribution 50
C: live,   total contribution 50
```

The pot is two layers:

- main pot: 60, eligible A/B/C;
- side pot: 60, eligible B/C.

On the next street B and C can still act.  Their decision cannot be valued as
"equity versus C times 120", because:

- main-pot equity is against A **and** C;
- side-pot equity is against C only;
- folding to a side-pot wager also forfeits B's main-pot eligibility, so the main pot cannot simply
  be deleted from call/fold EV either.

The decision must therefore retain pot layers and their eligible opponent sets.

---

# Current live path

## Settlement

`session.award_pots` already decomposes cumulative contributions by contribution level.

For each level it computes:

- layer amount;
- all contributors reaching that level;
- non-folded eligible seats;
- winners for that layer.

Dead money is added to the first/main layer only.

This is a sound showdown-settlement primitive.

## Current-street legal reach

`runner.Round.contestable_contrib(seat)` caps each current-street contribution by the maximum
target that the acting seat can physically reach.

This correctly prevents a short stack from treating unreachable current-street side-pot chips as
contestable.

`Round.settle_uncalled()` also returns the unique unmatched top excess after a betting round.

These are legal/accounting primitives, not a full strategic side-pot model.

---

# Confirmed decision-layer gap

## F8-1 MAJOR — prior all-in money remains in `pot_now`, but the all-in opponent is removed from equity

At the start of each postflop street, session does:

```python
active = [x for x in live if h.stacks[x] > 0]
order = [... active ...]
r2 = Round(..., order, ...)
pot_now = sum(contrib.values()) + dead
```

A previous-street all-in seat remains in cumulative `contrib`, so their main-pot chips remain in
`pot_now`.

But the seat is absent from `order`, therefore absent from:

- `r2.live()`;
- `n_opp = len(r2.live()) - 1`;
- the `for o in r2.live()` opponent-range loop;
- `opp_ranges`;
- postflop joint equity.

Thus the plan can consume a pot containing A's chips while its equity model contains only B/C.

This is not merely missing provenance.  It is a mismatch between the money being valued and the
opponent set used to value it.

## F8-2 MAJOR — one scalar `pot_live` cannot represent mixed main/side eligibility

Current postflop planning receives:

```
pot_live = pot_now + r2.contestable_contrib(hero)
```

The current-street component is capped legally for hero, but `pot_now` is a cumulative scalar.

There is no representation of:

- main-pot amount;
- side-pot amount(s);
- hero eligibility per layer;
- locked all-in opponents per layer;
- active opponents per layer.

Therefore a correct layer-specific equity/EV calculation cannot be reconstructed downstream.

## F8-3 MAJOR — response EV needs layer-specific equity

Facing a wager, current code has one:

- `tocall`;
- `pot_live`;
- joint equity over the active opponent pools.

In a locked-main + live-side-pot state, the call/fold comparison needs at least:

```
for each pot layer L:
    amount(L)
    hero eligible?
    eligible locked opponents(L)
    eligible active opponents(L)
    hero equity in L if continuing
```

A fold to a side-pot bet forfeits hero's claim to **all** pots, including the locked main pot.
Therefore the correct fix is not "use side-pot size only" and not "use main+side pot with HU
equity".  It must compare EV by layer.

## F8-4 MAJOR — proactive bet/raise EV is also layered

A deep player betting into another deep player while a short player is locked all-in can:

- win side-pot chips immediately if the live opponent folds;
- remove that live opponent from the main-pot contest;
- still have to beat the locked all-in player in the main pot.

Fold equity and value equity therefore operate over different opponent sets and different pot
layers.  The current scalar pot / active-only range model cannot express that.

## F8-5 PREFLOP — P6 legal pot information is correct but strategy remains scalar

P6 already established:

- exact incremental call price;
- `Round.contestable_contrib`;
- legal raise rights;
- facing-all-in provenance.

But the remaining P6 findings are still open:

- multiway all-in/overcall uses caller count rather than opponent-specific continuing ranges;
- main-pot and live side-pot strategy is not explicit;
- call-off strategy is not yet exact equity-vs-pot-odds EV.

F8 owns the shared pot-layer semantics needed to solve those without inventing another preflop-only
heuristic.

## F8-6 AUDITABILITY — decision traces do not preserve pot layers

Current intent records preserve scalar `pot`, `eq`, opponent-range signatures, and response
context.

They do not preserve:

- layer amounts;
- eligible seats by layer;
- locked all-in seats;
- active seats by layer;
- layer-specific equity.

Without those fields, a later review cannot tell whether a side-pot decision used the correct money
and opponent set.

---

# What must not be changed yet

Do **not** repair F8 by:

- subtracting the main pot from every side-pot decision;
- adding one side-pot multiplier;
- treating every previous all-in as another ordinary active opponent;
- replacing `n_opp` with one larger scalar;
- adding a hand-tuned call threshold;
- changing `award_pots` simply because strategy is incomplete.

The settlement/accounting layer and the strategy layer are separate problems.

---

# Target architecture

At every decision point, preserve a read-only pot-layer context such as:

```
layers = [
    {
        amount,
        eligible_seats,
        hero_eligible,
        locked_allin_opponents,
        active_opponents,
    },
    ...
]
```

Opponent-specific ranges must remain keyed by seat, including locked all-in seats.

Then the judgment layer can derive layer-specific equities:

```
main equity  = equity vs opponents eligible for main
side equity  = equity vs opponents eligible for side layer
...
```

The response-plan layer can compare fold/call/raise EV without collapsing those values prematurely.

Execution still receives only the selected action/strategic size and applies legality/chip
conversion.

---

# Implementation / verification order

1. **F8-D0 diagnostic fixture** — reproduce main-3way + side-HU and prove the current opponent-set
   mismatch.  No production behavior change.
2. **F8-D1 pot-layer provenance** — derive cumulative decision-time layers and log them.  Verify
   against `award_pots` geometry.  Still no strategy use.
3. **F8-D2 locked-opponent range preservation** — reconstruct/preserve public ranges for previous
   all-in seats as well as active seats.
4. **F8-D3 layer-equity diagnostics** — compute main/side equity separately but do not consume it
   for actions yet.
5. **F8-D4 response EV** — specify fold/call EV by layer, preregister fixtures, then wire it.
6. **F8-D5 proactive bet/raise EV** — specify how folds change main and side eligibility before
   wiring.
7. **F8-D6 preflop reuse** — replace P6 scalar side-pot semantics with the same layer context.
8. Run targeted fixtures + F1-F7/P1-P7 structural checks + frozen `842bd58` generation
   regression before accepting any behavior change.

No production strategic coefficient is changed in F8-D0 through F8-D3.
