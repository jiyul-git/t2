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


---

# F8-D1 implementation — decision-time pot-layer provenance

Status: **USER-VALIDATED. No strategy consumer added.**

A new `session._decision_pot_layers(...)` helper derives read-only pot geometry from:

- completed-street cumulative contributions;
- current-street contributions before the actor acts;
- cumulative/current folds;
- current stacks;
- dead money.

Each layer records:

- `level`;
- `amount`;
- `contributors`;
- `eligible_seats`;
- `hero_eligible`;
- `locked_allin_seats`;
- `active_seats`;
- `locked_allin_opponents`;
- `active_opponents`.

Dead money is added only to the first/main layer, matching `award_pots` settlement geometry.
Folded players' chips still contribute to the amount but the folded seats are removed from
eligibility.

The helper intentionally preserves an unmatched current-street upper contribution layer before
the facing player acts.  In that layer `hero_eligible=False` until the hero actually matches the
price.  This is necessary for later D4 EV work; silently deleting the unmatched wager would make
the decision-time state impossible to reconstruct.

## Wiring

At every postflop action opportunity, session computes `_pot_layers` before the actor acts.

The value is exposed only as provenance:

- human-yield state: `pot_layers`;
- bot intent/audit row: `pot_layers`.

It is **not** passed to:

- `update_plan`;
- `act_with_plan`;
- any sizing function;
- any equity function.

Therefore D1 must preserve the frozen F7 behavioral fingerprint exactly.

## D1 verification

`tools/audit_f8_sidepot.py` now checks:

1. settlement geometry still separates main/side layers;
2. current-street contestable cap remains sound;
3. the original locked-all-in opponent-set gap is still reproduced;
4. production D1 provenance records:
   - main layer with locked all-in opponent;
   - side layer with active opponent only;
   - pending unmatched upper layer with `hero_eligible=False`;
   - live `HandRun._run` wiring.

Acceptance requires:

- F8 diagnostic: 4/4;
- frozen regression: exact fingerprint match to baseline rev `2a53584`.

D1 does **not** claim the F8 strategy gap is fixed.  D2 is still required to preserve/reconstruct
the locked all-in opponent's range before layer equity can be computed.


---

# F8-D2 implementation — locked all-in opponent range preservation

Status: **USER-VALIDATED. No strategy consumer added.**

D1 can now identify a previous-street all-in opponent in a pot layer, but the current
postflop strategy pools still contain only current `Round.live()` seats.

D2 reconstructs a separate `locked_opp_ranges` map for seats that:

- remain eligible in at least one current decision-time pot layer;
- have zero remaining stack;
- are not the current actor.

## Preflop stack-depth provenance

A direct reconstruction using `h.bbs(target)` is invalid after the target is all-in because that
value is now 0bb.

D2 therefore records `pf_stack_bb` in each normal preflop plan seed: the actor's stack depth at
that exact preflop decision before the action is applied.

Locked-opponent reconstruction uses:

1. final/current `pf_seed['pf_stack_bb']` when available;
2. hand-start stack / BB only as a compatibility fallback for old/replay seeds.

This new field is provenance only.

## Public-story reconstruction

`HandRun._locked_postflop_range` uses the same public information family as the active-opponent
range path:

- stored preflop role/action/raise level;
- observer-specific perceived profile;
- public postflop action story from `_acts_of`;
- showdown-history adjustment;
- observer range-read limits.

It never reads the target's true persona/tilt.

## Isolation rule

The reconstructed locked ranges are intentionally **not** merged into:

- legacy union `opp_r`;
- active `opp_ranges`;
- `n_opp`;
- `update_plan`;
- `act_with_plan`;
- any equity calculation.

Intent provenance records only:

- `locked_opp_ranges_n`;
- `locked_opp_ranges_sig`;
- `locked_opp_range_stack_bb`.

D3 will be the first stage that computes layer-specific equity from active + locked range maps,
and D3 still will not alter actions.

## D2 acceptance

`tools/audit_f8_sidepot.py` checks that:

- locked reconstruction uses stored 23.5bb rather than current 0bb;
- the prior public postflop action story reaches range narrowing;
- the range is stored separately;
- production source does not merge the locked pool into current strategy pools.

Acceptance requires:

- F8 diagnostic: 5/5;
- frozen regression remains exactly equal to baseline rev `2a53584`.


---

# F8-D3 implementation — layer-specific equity diagnostics

Status: **IMPLEMENTED; pending user validation. No strategy consumer added.**

D3 combines the two information structures established earlier:

- D1 pot layers and eligibility;
- D2 seat-keyed active and locked-all-in opponent range pools.

`session._diagnostic_layer_equities` computes a separate showdown equity for each layer in which
the hero is **currently eligible**.

For each diagnostic layer it records:

- layer index/level/amount;
- exact opponent seat set;
- whether each range came from the active or locked-all-in map;
- missing range seats;
- completeness;
- equity and simulation count.

## No invented fallback

If any eligible opponent range is missing, D3 records:

```
complete = False
equity = None
reason = missing_opponent_range
```

It does not substitute a population 35% range or duplicate another opponent's pool.

## Pending unmatched wagers

A decision-time upper layer created by an unmatched wager can have
`hero_eligible=False`.

D3 deliberately records no equity for that layer.  Treating the current upper layer as though the
hero had already called would confuse current-state provenance with a hypothetical action.

D4 will build explicit fold/call hypothetical states before EV is calculated.

## Diagnostic example

With:

- main layer opponents = locked A + active C;
- side layer opponent = active C;
- hero currently eligible for both;

D3 calls the existing canonical `bot.equity_vs_combos` implementation with separate pools:

```
main equity = hero vs [range(A), range(C)]
side equity = hero vs [range(C)]
```

No union range is used for this diagnostic.

## Isolation

D3 runs only when a locked all-in opponent is present, so ordinary pots incur no additional
simulation work.

The result is written only to intent provenance as `layer_equities`.

It is not passed to:

- `update_plan`;
- `act_with_plan`;
- response thresholds;
- sizing;
- execution.

## D3 acceptance

`tools/audit_f8_sidepot.py` adds an exact full-board fixture where:

- hero loses the main pot to the locked all-in range;
- hero beats the active opponent in the side pot.

Expected diagnostics:

- main equity = 0.0 vs seats [locked, active];
- side equity = 1.0 vs [active];
- missing opponent range -> equity None;
- current unmatched/ineligible layer -> equity None.

Acceptance requires:

- F8 diagnostic: 6/6;
- frozen regression: exact fingerprint match to baseline rev `2a53584`.


---

# F8-D4 preregistration — layer-aware call/fold EV

Status: **SHADOW USER-VALIDATED; STRATEGY CONSUMER IMPLEMENTED, pending behavior validation.**

D3 proves that main and side equity can differ.  D4 must therefore avoid replacing the current
response `eq` with one layer equity or with an unweighted average.

## Why the existing response `eq` cannot simply be replaced

`act_with_plan` / `decide_response` use the current scalar `eq` for more than call/fold:

- nut/value re-raise eligibility;
- semibluff raise logic;
- bluff raise logic;
- final call/fold.

If a new layer-weighted number is substituted globally, a side-pot call fix would silently alter
raise strategy.  That belongs to D5, not D4.

D4 therefore defines the call value separately.

## Hypothetical call state

For a facing wager, `_project_call_layers`:

1. adds only the actual incremental `tocall` to hero's current-street contribution;
2. subtracts the same amount from hero's remaining stack;
3. rebuilds D1 contribution layers;
4. leaves unreachable/unmatched upper layers explicitly hero-ineligible.

No action is executed and no production state is mutated.

## Objective chip-EV definition

For projected post-call layers where hero is eligible:

```
gross_return
    = sum(layer_amount * layer_equity)

call_chip_ev
    = gross_return - incremental_call_cost

contestable_after_call
    = sum(layer_amount for hero-eligible layers)

effective_equity
    = gross_return / contestable_after_call

breakeven_equity
    = incremental_call_cost / contestable_after_call
```

Prior hero contributions are sunk costs.  Fold is therefore the zero future-cashflow reference
point for this incremental chip-EV calculation.

This is equivalent to ordinary pot odds in a one-layer pot, but remains correct when different
layers have different opponent sets/equities.

## Locked-main failure fixture

Preregistered geometry:

```
before new wager:
    A locked all-in 100
    hero          100
    C             100

C bets 10, hero faces call 10

after hypothetical call:
    main = 300, A/hero/C
    side = 20, hero/C
```

Synthetic equities:

```
main equity = 0.00
side equity = 0.20
```

Expected:

```
gross_return = 300*0.00 + 20*0.20 = 4
call_chip_ev = 4 - 10 = -6
effective_equity = 4/320 = 0.0125
breakeven_equity = 10/320 = 0.03125
=> objective call is losing
```

This captures the exact bug class: active-only side equity can look adequate against a tiny price
created by a large locked main pot, even though the hero has almost no claim on that main pot.

## Unknowns stay unknown

If any hero-eligible projected layer lacks an opponent range/equity, D4 returns:

```
complete = False
call_chip_ev = None
```

No population-range fallback or copied opponent pool is invented.

## Strategy integration boundary — locked before implementation

D4 strategy wiring, when implemented, must obey all of these:

1. **Do not overwrite the existing response `eq`.**
   Raise logic continues to see the current active-opponent response equity until D5.
2. Add separate `call_eq` / `call_need` (or equivalent explicit call-value object).
3. Layer-aware values may affect only the eventual **call vs fold** choice.
4. If a raise is selected, D4 does not veto/approve it; D5 owns raise EV.
5. Do not consume incomplete layer summaries.
6. First activation population is locked-all-in side-pot states only.
7. For multi-active-player states with `to_act_behind > 0`, keep the layer call value shadow-only
   until continuation/behind-player semantics are separately specified.
8. Existing ICM/personality/read adjustments are not deleted.  Before strategy wiring, map the
   objective layer breakeven/effective equity into the existing `calldown_need` perception chain
   rather than adding a new hand-tuned side-pot multiplier.

## Current shadow wiring

When a locked all-in opponent exists and `tocall > 0`, session records:

- projected post-call layers;
- projected layer equities;
- raw layer call summary;
- `to_act_behind`.

This is stored under intent provenance `call_ev_shadow` only.

No argument named `call_ev_shadow` reaches `update_plan`, `act_with_plan`,
`decide_response`, sizing, or execution.

## D4 shadow acceptance

`tools/audit_f8_sidepot.py` requires:

- the locked-main fixture above gives call chip-EV = -6;
- effective equity = 0.0125;
- breakeven = 0.03125;
- missing main equity leaves the result unknown;
- source scan confirms no strategy consumer.

Acceptance requires:

- F8 diagnostic: 7/7;
- frozen regression still exactly matches baseline rev `2a53584`.

Only after those pass may the D4 strategy-consumer patch be designed against the frozen
preregistration above.


## D4 strategy consumer implementation

The preregistered shadow is now consumed only when all first-activation gates hold:

- at least one locked all-in opponent is present;
- the projected layer summary is complete;
- `to_act_behind == 0`.

Session passes a separate `call_value` object into `act_with_plan` containing only:

- layer-weighted `effective_equity`;
- objective `breakeven_equity`;
- raw `call_chip_ev` for provenance.

### Perception-chain mapping

`calldown_need` keeps its legacy scalar `need` unchanged.

When an objective layer break-even is supplied, it derives a separate `call_need`.
The same existing perception chain is applied in parallel:

- ICM bubble factor;
- sizing-read distortion, mapped by the ratio of perceived scalar pot odds to true scalar pot odds;
- pot-odds calculation noise;
- players-behind penalty (although first activation excludes behind players);
- line/bluff read adjustment;
- existing upper/lower clamps;
- personal call bias;
- perceived opponent bluff tendency.

No new side-pot tuning coefficient is introduced.

### Raise isolation

`decide_response` receives both pairs:

```
legacy eq / need       -> raise eligibility and raise probabilities
call_eq / call_need    -> only when response reaches call versus fold
```

This means:

- nut/value raise gates remain on legacy response equity;
- semibluff/bluff raise gates remain on legacy response equity;
- checkraise production remains unchanged;
- if a raise is not selected, the fallback call can become a fold from layer EV;
- giveup / semibluff / generic bluffcatch call-vs-fold use layer values.

### Behavior validation rule

Unlike D1-D3 and D4-shadow, this patch is allowed to change behavior, but only inside the
preregistered locked-allin/no-behind population.

Therefore frozen-baseline mismatch after this commit is **not automatically a failure**.
If a fingerprint moves, the next step is attribution against parent `720cc40`, and every changed
decision must have `layer_call_active=True`.

Any changed decision outside that population rejects the implementation.
