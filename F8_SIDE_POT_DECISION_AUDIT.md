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

Status: **USER-VALIDATED STRATEGY CONSUMER.**

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


---

# F8-D5-A preregistration — proactive bet conditional outcomes

Status: **USER-VALIDATED SHADOW. No strategy consumer.**

D4 fixed the response side of a locked-main / live-side-pot state.  Proactive betting has a
different failure mode.

The live opponent is the only player who can fold to a new bet, but a fold does **not** award the
locked main pot automatically.  The hero must still beat every locked all-in opponent eligible for
that layer.

Therefore the ordinary bluff identity

```
opponent folds -> hero wins the whole existing pot
```

is false in this state.

## D5-A first scope

D5-A intentionally models only:

- one locked-all-in-or-more main-pot opponent(s);
- exactly one active opponent;
- hero faces no wager and has a planned bet;
- two conditional target outcomes: **fold** and **call**.

It does **not** yet assign a fold probability and does **not** model the target raise branch.

Thus D5-A cannot alter strategy.

## Conditional geometry

`_project_bet_outcome_layers` applies the hero's incremental planned bet to a copied state.

For target fold:

- target's prior chips remain in layer amounts;
- target is removed from eligibility in every layer;
- hero's unmatched bet excess remains a sole-eligible upper layer, which is equivalent to an
  uncalled-chip return.

For target call:

- target matches the hero's current-street contribution as far as its stack allows;
- main and side layers are rebuilt from the resulting cumulative contributions;
- any unmatched excess remains separately visible.

Both outcomes are then valued with the same D3 seat-specific range pools and generic
`_layer_investment_summary`.

## Locked-main fixture

Before the bet:

```
A locked all-in 100
hero            100
C active         100
```

Hero bets 20.  On an exact river fixture:

- hero loses to A;
- hero beats C.

If C folds:

```
main 300 -> A/hero        hero equity 0
uncalled 20 -> hero       hero equity 1

gross return = 20
bet cost     = 20
conditional chip EV = 0
```

If C calls:

```
main 300 -> A/hero/C      hero equity 0
side 40  -> hero/C        hero equity 1

gross return = 40
bet cost     = 20
conditional chip EV = +20
```

The important invariant is that **C folding does not produce +300 from the locked main pot**.

## Live shadow wiring

After `update_plan` has produced the actual strategic intent, session computes D5-A only when:

- a locked all-in range exists;
- `tocall == 0`;
- exactly one active opponent remains;
- the current intent is a positive-size bet.

The candidate bet cost uses the strategic intent size converted to chips before later execution
presentation shaping.

Intent provenance stores `bet_ev_shadow` with:

- target seat;
- hero bet cost;
- target call cost;
- fold projected layers/equities/summary;
- call projected layers/equities/summary;
- explicit flags that fold probability and raise branch are not modeled;
- `strategy_consumer=False`.

## D5-A acceptance

`tools/audit_f8_sidepot.py` requires:

- fold geometry = main A/H + sole-hero uncalled return;
- call geometry = main A/H/C + side H/C;
- fold conditional chip-EV = 0 in the locked-main fixture;
- call conditional chip-EV = +20;
- no fold probability;
- no raise branch;
- no strategy consumer.

Acceptance also requires the frozen regression to remain exactly unchanged.


---

# F8-D5-B preregistration — perceived fold probability and exhaustive bet EV

Status: **USER-VALIDATED SHADOW. No strategy consumer.**

D5-A provides `EV | fold` and `EV | call`.  D5-B determines when those two branches can be
combined without inventing an unobserved raise model.

## Fold probability source

No new prior or tuning coefficient is introduced.

D5-B reuses the existing opponent-read architecture:

```
baseline = reads.PRIOR['fold_to_bet']        # currently 0.52
read     = read_opponent(profile, opp_est)
seen     = baseline + street_gap(read, street)
p_fold   = blend(baseline, seen, read['w'])
```

`read_opponent` already gates information through observation/data/use and street-specific
frequency perception.  If no usable opponent estimate exists, the result is exactly the existing
population prior.

This is the same event being modeled: **target faces a bet and folds**.

D5-B deliberately does not use:

- fold-to-raise;
- generic aggression;
- bluff frequency;

as substitutes for a target raise probability.

## Raise branch boundary

The codebase currently has no dedicated postflop statistic for:

```
target faces bet -> target raises
```

Therefore D5-B does not invent one.

For the first complete population, target continuation must be call-only because matching the
planned bet exhausts its remaining stack.  Then:

```
P(call) = 1 - P(fold)
EV(bet) = P(fold) * EV|fold + P(call) * EV|call
```

If target would retain any chips after matching the bet, a raise branch remains possible and
expected bet EV is explicitly:

```
complete = False
reason = raise_branch_unmodeled
expected_chip_ev = None
```

## Fixed arithmetic fixture

Using D5-A conditional results:

```
EV|fold = 0
EV|call = +20
population fold prior = 0.52
```

and a call-only/all-in continuation:

```
EV(bet) = 0.52*0 + 0.48*20 = +9.6
```

The same fixture with chips remaining behind must return unknown, not +9.6.

## Live shadow

For every D5-A eligible live state, provenance now also records:

- perceived fold probability + source metadata;
- whether target can still raise after matching;
- combined expected EV when fold/call are exhaustive;
- explicit incomplete reason otherwise.

Still no strategy function consumes this value.

## D5-B acceptance

`tools/audit_f8_sidepot.py` requires:

- no-read fold probability equals the existing 0.52 prior exactly;
- exhaustive all-in continuation yields expected EV +9.6 in the fixed fixture;
- raise-capable continuation stays unknown;
- no invented raise frequency;
- no strategy consumer.

Frozen regression must remain unchanged.


---

# F8-D5-C1 preregistration — response-conditioned continuation range and check benchmark

Status: **REVISED: effective response price fixed; pending validation with C2.**

D5-B still cannot be consumed safely for two reasons discovered during the consumer audit.

## 1. EV|call must condition the opponent range on actually continuing

D5-A/B initially valued the call branch using the opponent's range **before** it faced the new
bet.  That misses selection: weak hands fold and the continuing range is stronger.

D5-C1 therefore applies one hypothetical facing-bet response to the active target range.

The existing size-dependent call/continue model is reused; no new cutoff coefficient is added.

### Raise-capable call

If the target retains chips after matching, ordinary `_call_range` remains appropriate for the
conditional **call** branch: much of the strongest slice is absent because those hands would often
raise.

### Call exhausts stack

If matching the bet exhausts the target's stack, raise is impossible.  The existing continue-width
formula is reused but the top-raise cut is removed:

```
continue range = strongest existing keep-fraction
```

This preserves strong hands that cannot legally choose the raise branch.

Observer `range_read` limitations are applied in the same style as `perceived_range`.

## 2. Bet EV must be compared with check EV, not zero

A locked-main state can give the hero positive showdown value even without investing another chip.

Therefore:

```
bet EV > 0
```

does not imply betting is better than checking.

The strategic comparison is:

```
bet_minus_check_ev = EV(bet) - EV(check)
```

But a simple showdown check value is valid only when check terminates the decision tree.

D5-C1 therefore computes a check benchmark only for the first safe scope:

- river;
- current actor closes action (`behind == 0`).

For flop/turn, or river with an opponent still to act after a check, `check_summary` remains
unknown because future actions have value.

## Live shadow

D5 shadow provenance now also records:

- target range size before hypothetical response;
- response-conditioned call/continue range size/signature;
- whether check is terminal;
- terminal check summary when valid;
- `bet_minus_check_ev` only when both expected bet EV and check EV are complete;
- `response_range_conditioned=True`;
- `strategy_consumer=False`.

## D5-C1 acceptance

The verifier requires:

- ordinary call range excludes a strong top-raise slice;
- all-in continue range restores that slice when raise is impossible;
- all-in continue range is wider than ordinary call range;
- a fixed example with bet EV 9.6 and check EV 15 yields delta -5.4;
- terminal-check scope is river + behind=0 only;
- no strategy consumer.

Frozen regression must remain unchanged.


---

# F8-D5-U check — strategic sizing unit versus execution unit

Status: **CLEARED — NO DEFECT.**

A diagnostic was added because the execution expression contains `/100`:

```
int(round(pot * intent_size / 100)) * 100
```

Reading the division in isolation suggested a percent/fraction mismatch.  The executable fixture
shows that interpretation was wrong.

The expression is a 100-chip rounding transform:

```
round((pot * fraction) / chip_unit) * chip_unit
```

For:

```
pot = 10,000
intent size = 0.60
chip unit = 100
```

both the strategic contract and execution produce:

```
6,000 chips
```

Therefore:

- `decide_size` / `mk_intent` correctly use pot fractions;
- `act_with_plan` preserves that unit;
- D5 shadow uses the same 100-chip rounding convention;
- no production sizing repair is required.

The failed diagnostic at commit `40f9a05` was an **audit expectation error**, not a production
behavior defect.  Frozen regression remained unchanged, consistent with that conclusion.

D5-C2 may proceed.


---

# F8-D5-C2 implementation — terminal proactive bet/check consumer

Status: **USER-VALIDATED. Frozen regression unchanged.**

After C1, proactive bet EV is complete only in a deliberately narrow terminal population.

## Effective response price correction

When the active target is shorter than the nominal bet, the target does not face the hero's full
nominal fraction.

The response-conditioned continue range now uses:

```
response_size_frac = target_call_cost / action_time_pot
```

rather than the hero's nominal intent fraction.

Thus a target with only 0.20 pot left is conditioned on a 0.20-pot all-in decision even if hero's
nominal bet was 1.00 pot.

No new range-width coefficient is introduced; the existing size-dependent continue model is reused.

## Consumer activation

D5-C2 can revise an existing bet intent only when all of these are true:

- locked-all-in range exists (D5 shadow prerequisite);
- exactly one active opponent;
- hero faces no wager;
- existing judgment intent is a bet;
- river;
- `behind == 0`, so check is terminal;
- target cannot raise after matching (`raise_possible=False`);
- conditional fold/call bet EV is complete;
- terminal check EV is complete;
- `bet_minus_check_ev` is known.

## Decision rule

No fitted threshold is introduced.

```
if EV(bet) - EV(check) < 0:
    bet intent -> check intent
else:
    preserve existing bet intent
```

D5-C2 does **not** create bets from checks.  It is a negative-EV veto on an already selected bet.

The line plan label is preserved.  Only the current-street intent is revised because the new
pot-layer judgment invalidates that immediate action, not the longer-lived strategic goal.

## Architecture boundary

The revision is implemented in `plan.apply_layer_bet_ev_judgment`.

Session supplies the new judgment information and stores provenance, but does not overwrite the
executed action.

`act_with_plan` remains unaware of `bet_minus_check_ev` and simply executes the final intent.

This preserves:

```
judgment -> plan/intent -> action
```

instead of:

```
judgment -> action -> session override
```

## Skill/persona treatment

No new side-pot skill coefficient is added.

The EV inputs are already perception-limited by existing architecture:

- active range perception -> `range_read`;
- target fold tendency -> existing fold-frequency read/use gate;
- action sizing -> actual effective response price;
- locked opponent range -> observer-specific reconstructed perceived range.

The pot-layer accounting itself is treated as factual game-state geometry rather than a new
personality trait.

## Validation

Targeted verifier requires:

- negative delta changes bet -> check;
- positive delta preserves bet;
- unknown delta preserves bet;
- activation source contains every preregistered gate;
- execution layer contains no D5 EV override.

This is an intentional behavior-change patch.  Frozen regression mismatch is allowed only if every
changed action is attributable to the D5-C2 activation population.  The frozen baseline must not be
updated before attribution.


---

# F8-D6-A — preflop decision-time pot-layer provenance

Status: **USER-VALIDATED. No preflop strategy consumer.**

P6 already had sound legal scalars:

- exact incremental `to_call`;
- `Round.contestable_contrib(hero)`;
- raise-right semantics;
- all-in-call normalization.

But those scalars do not preserve which seats are eligible for each portion of a multiway
preflop pot.

D6-A reuses the exact same `_decision_pot_layers` schema already established for postflop.

For every preflop decision:

```
prior_contrib = {}
street_contrib = Round.contrib
folded = Round.folded
stacks = Round.stacks
dead = BB ante / dead money
```

The resulting layers are:

- exposed to the human preflop state as `pot_layers`;
- passed through `preflop_plan` as provenance only;
- stored in `pf_seed['pf_pot_layers']`;
- appended to each `pf_line` decision record.

No preflop action function consumes them yet.

## Fixed geometry fixture

Before hero acts:

```
hero: 10 contributed, 40 behind
A:    20 contributed, all-in
B:    50 contributed, 50 behind
dead ante: 5
```

Expected decision-time layers:

```
level 10: amount 35, eligible H/A/B, hero eligible, A locked
level 20: amount 20, eligible A/B,   hero not yet eligible, A locked
level 50: amount 30, eligible B,     hero not yet eligible
```

The legal scalar view remains:

```
to_call(hero) = 40
contestable_contrib(hero) = 80
```

Those values are not wrong; they simply cannot encode the opponent eligibility split by
themselves.

## D6-A acceptance

Verifier requires:

- exact layer geometry above;
- exact P6 legal scalar values remain unchanged;
- same F8 layer schema is used preflop;
- `defend_decision` and `calloff_decision` still have no pot-layer consumer;
- frozen regression remains unchanged.

After D6-A, D6-B will preserve **seat-keyed perceived preflop ranges** for all eligible opponents
already in the pot, rather than using only `n_callers`.


---

# F8-D6-B — seat-keyed perceived preflop ranges

Status: **USER-VALIDATED. No equity/action consumer.**

D6-A supplies preflop pot layers.  D6-B supplies the missing seat-specific opponent ranges needed
to value those layers.

## Information boundary

For every opponent currently eligible in a contributed preflop layer, the observer reconstructs a
range from public information only:

```
observer Book
    -> perceived_profile(observer, target)
    -> range_profile(perceived target)
    -> R.preflop_range(...)
```

The target's true persona, concepts, temper, tilt, or private cards are never used.

## Action source

If the target has a bot `pf_seed`, its latest public judgment/action context is used because it
preserves:

- role;
- actual action;
- facing position;
- facing price;
- caller count;
- raise level;
- decision-time stack depth.

For seats without a seed (human/external paths), D6-B reconstructs the same public role from
`Round.action_meta`:

- no action -> unacted / any-two prior;
- call before a raise -> limp;
- first price increase -> open;
- call after a raise -> call;
- later price increase -> 3bet+ range model;
- check -> check/any-two BB-style path.

No hidden player state is consulted.

## Storage

The full combo lists are transient and seat-keyed at the decision point.

They are **not** serialized into `pf_seed`, because repeatedly storing hundreds of combos per
seat would bloat tournament state.

Compact provenance is stored instead:

- `pf_opp_ranges_n[seat]`;
- `pf_opp_ranges_sig[seat]`;
- `pf_opp_range_meta[seat]`.

The same compact fields are appended to `pf_line`.

## D6-B acceptance

Verifier requires:

- open / call / 3bet public events classify separately;
- observer-specific public range reconstruction returns non-empty seat-keyed pools;
- at least two distinct action paths produce distinct range signatures;
- compact provenance is present in `preflop_plan`;
- `calloff_decision` still has no range consumer;
- frozen regression remains unchanged.

D6-C may then reuse `bot.equity_vs_combos(hero, board=[], pools)` to compute preflop layer equity
without introducing a second equity engine.


---

# F8-D6-T prerequisite — exact multiway showdown share

Status: **USER-VALIDATED. Frozen regression unchanged.**

Before D6-C could use the shared equity engine for multiway preflop layers, an existing global
equity defect was found.

Both `bot.equity` and canonical `bot.equity_vs_pools` used:

```
win + 0.5 * tie
```

for every tie.

That is correct heads-up but wrong when more than one opponent ties hero for first:

- hero + 1 opponent tie -> hero share 1/2;
- hero + 2 opponents tie -> hero share 1/3;
- hero + 3 opponents tie -> hero share 1/4.

## Repair

A single canonical helper now computes showdown share:

```
hero wins outright        -> 1.0
hero loses                -> 0.0
hero ties N opponents     -> 1 / (N + 1)
```

Both equity entrypoints use the same helper.  No range, strategy, or threshold parameter changes.

## Fixed fixture

A royal flush entirely on the board forces every legal hand to tie.

Required exact values:

```
heads-up           0.500000
3-way              0.333333...
4-way              0.250000
```

The generic `equity(..., n_opp=2)` entrypoint must also return exactly 1/3 on the same board.

## Behavior policy

This is a factual pot-share correction, but it is global.  Frozen regression is therefore checked.

If fingerprints move, the baseline is not updated automatically.  Changes must first be attributed
to decisions whose equity sample contains a multiway first-place tie.

D6-C does not proceed until D6-T targeted verification passes.


---

# F8-D6-C — preflop layer equity and pure-calloff EV shadow

Status: **IMPLEMENTED; pending user validation. No strategy consumer.**

D6-C combines the two previously validated inputs:

- D6-A pot-layer geometry;
- D6-B seat-keyed perceived preflop ranges.

The canonical D6-T equity engine is used with `board=[]`, so the remaining five board cards are
Monte Carlo sampled normally.

## First scope: pure short-shove calloff only

D6-C deliberately does **not** value every preflop call.

Its live shadow activates only when the same P6 conditions identify a terminal short-shove
calloff:

```
aggressor exists
aggressor stack == 0
Round.can_raise(hero) == False
to_call > 0
```

In this state there is no live responder capable of creating a later preflop side action.  The
decision tree is fold versus call, so immediate showdown layer EV is meaningful.

Hero-stack-exhausting calls with other live responders remain outside D6-C even though the old
`calloff_cap` may handle them.  Their main-pot equity can change when those responders later fold
or continue, so they need a separate continuation model.

## Calculation

D6-C projects the exact call with the shared `_project_call_layers`.

Then opponent ranges are split only for provenance:

- stack == 0 -> locked range;
- stack > 0 -> active range.

`_diagnostic_layer_equities(hero, board=[], ...)` computes equity separately for every
hero-eligible layer.

The shared `_layer_call_summary` then records:

```
call_cost
contestable_after_call
gross_return = Σ layer_amount * layer_equity
call_chip_ev = gross_return - call_cost
effective_equity
breakeven_equity = call_cost / contestable_after_call
```

Any missing required range/equity leaves the shadow incomplete.  No fallback range or scalar
`n_callers` approximation is invented.

## Fixed fixture

```
hero: 10 in + 10 behind
A:    20 all-in
B:    50 all-in
```

After hero calls 10:

```
main: 60, eligible H/A/B
upper: 30, eligible B only
```

Only the 60-chip main layer enters hero call EV.

Therefore:

```
call_cost = 10
contestable_after_call = 60
breakeven_equity = 10/60 = 1/6
```

The upper 30 cannot improve hero's price.

## Storage and architecture

Full range combo lists remain transient.

`pf_call_ev_shadow` stores only:

- projected layers;
- layer equity rows;
- objective summary numbers;
- `strategy_consumer=False`.

It is copied into the current preflop seed/line for auditability.

`calloff_decision` still receives none of these values and remains percentile-cap based.

## D6-C acceptance

Verifier requires:

- exact main/upper post-call layer geometry;
- empty-board multiway equity calculation completes;
- upper hero-ineligible layer has no equity value;
- break-even equals 1/6 in the fixed fixture;
- gross return equals layer amount × layer equity;
- live source is gated to pure short-shove/no-responder states;
- `calloff_decision` has no layer-EV consumer;
- P6 structural verifier stays 5/5;
- frozen regression remains unchanged.

After D6-C, D6-D can preregister how objective layer EV interacts with existing ICM/personality
calloff judgment before any action is changed.
