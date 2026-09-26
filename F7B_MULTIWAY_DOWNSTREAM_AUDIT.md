# F7-B — Multiway downstream semantics audit

Status: **B1-A CLOSED; B1-B1 RANGE-ADV CLOSED; B1-B2 NUT SHADOW HELD.**

F8 established seat-keyed opponent ranges and pot-layer equity.  The next global question is
whether downstream planning preserves that identity or collapses it again.

The answer is mixed:

- showdown equity already consumes one range pool per opponent;
- F8 layer equity also preserves opponent identity;
- several plan metrics still consume one union `opp_range`;
- multiway exploit/stack context still chooses one representative opponent.

This means the same decision can simultaneously use exact seat-keyed equity and a collapsed
single-opponent heuristic for strength, blockers, range advantage, or reads.

## B1 — union range collapse

`session.HandRun._run` intentionally builds both:

```
opp_ranges[seat] = perceived range for that seat
opp_r             = union of all active opponent combos
```

Both are passed into `plan.update_plan`.

The equity path is already seat-aware:

```
_eq_vs(..., opp_ranges=opp_ranges)
    -> bot.equity_vs_combos(hero, board, [seatA_pool, seatB_pool, ...])
```

But the following live strategy metrics still use the union:

- `relative_strength(hero, board, opp_range)`;
- `R.blocker_score(hero, opp_range, board)`;
- `R.blocker_effect(..., opp_range, ...)`;
- `R.nut_advantage(my_range, opp_range, board)`;
- `R.range_advantage(my_range, opp_range, board)`;
- river bluff blocker logic;
- overbet nut-advantage logic.

### Why union is not a neutral average

A union weights opponents by **number of combos**, not by seat.

Fixed fixture:

- hero has AA on `2c 7d Jh 4s 3c`;
- seat A has exactly `JsJd` and always beats hero;
- seat B has forty weak combos that all lose to hero.

Per-seat relative strength is:

```
vs A = 0
vs B = 1
equal-seat mean = 0.5
```

The union contains 41 combos, so the wide weak seat gets forty times the weight of the tight
seat.  Union relative strength becomes above 0.90 even though hero's exact current-board
multiway share is **0** because seat A always wins.

The same combo-count weighting affects `range_advantage`.

Therefore union is not valid as a factual multiway opponent-strength representation.

It may remain useful only when a caller explicitly wants a combo-weighted *field mixture* and
documents that meaning.  Current plan consumers do not make that distinction.

## B1-P — partial pool fallback

`plan._normalize_opp_pools` skips empty seat ranges and then pads missing opponents by copying
`opp_range` / the last known pool.

So:

```
seat A -> known tight range
seat B -> unknown/empty range
```

can silently become:

```
seat A -> tight range
seat B -> union range
```

This violates the F8 rule that missing required opponent information remains unknown rather than
being invented.

Production may usually supply every active range, so repair should follow a reachability/frequency
measurement rather than immediately changing behavior.

## B2 — one representative opponent in a multiway pot

After building all seat-keyed ranges, session chooses:

```
_main = current aggressor, else deepest active opponent
_est  = perceived profile of _main
_ostk = stack of _main
```

and passes only:

```
opp_est=_est
opp_stack_bb=_ostk
```

into the general plan.

Those values affect live strategy including:

- fold-tendency adjustment of value/bluff thresholds;
- c-bet frequency;
- overbet response adjustment;
- effective-stack/commit planning.

In heads-up this is correct.

In multiway it can leak one opponent's behavior onto the whole field.  For example, one
fold-heavy aggressor does not imply a bluff succeeds when a second station remains in the pot.

B2 therefore needs a separate design.  The likely replacement is **not** a union profile:
probabilities such as "all opponents fold" and stack constraints have different aggregation rules.

## F7-B-T — record-only multiway tie cleanup

During B1 inspection, `plan._eq_current` still used:

```
win + 0.5 * tie
```

for all ties.

Unlike D6-T's canonical equity engine, this made a three-way board tie record as 1/2 instead of
1/3.

`eq_current` and `eq_delta` are explicitly provenance-only and have no strategy consumer.
The implementation now reuses `bot._showdown_share` so current-board records use exact pot share.

This cleanup must preserve all action fingerprints.

## Classification

### Already sound / seat-aware

- `bot.equity_vs_combos` / `_eq_vs`;
- F8 layer equity and EV;
- seat-keyed range provenance;
- heads-up union use (one opponent only).

### Unsafe or semantically ambiguous in multiway

- union `relative_strength`;
- union blocker metrics;
- union nut/range advantage;
- union-dependent overbet / river-bluff logic;
- silent missing-pool fallback;
- single-main-opponent exploit and stack context.

### Safe uses of the union

- recording `opp_range_n` / signature;
- backward-compatible heads-up interfaces;
- an explicitly documented combo-weighted field-mixture statistic.

No live multiway strategy consumer is changed in B1/B2 diagnostic.

## Next steps

1. **B1 measurement**
   - count live multiway decisions;
   - count how often per-seat ranges materially differ;
   - measure union-vs-seat-aware deltas for rel/range_adv/nut/blocker;
   - count partial/empty seat pools.

2. **B1 preregistration**
   - define aggregation separately by metric instead of one generic "multiway range":
     - showdown equity: joint seat pools;
     - relative hand strength: joint probability hero beats all opponents or another explicit
       quantity;
     - range/nut advantage: equal-seat or action-weighted statistic only if its strategic meaning
       is defined;
     - blocker/fold EV: opponent-specific response probabilities, not union combo counts.

3. **B2 measurement/design**
   - identify multiway spots where main-opponent read differs strongly from remaining opponents;
   - replace single `opp_est` only where the downstream quantity has a mathematically defined
     multi-opponent aggregation.

4. Targeted fixtures and frozen post-F8 regression before any consumer activation.

Broad balance tuning remains blocked until B1/B2 and the remaining emotion/execution boundaries
are closed.


---

## B1 measurement preregistration

`tools/measure_f7b_multiway.py` measures the live exposure without patching strategy.

Default fixture:

```
seeds 3000-3005
30 hands per seed
```

It wraps `plan.update_plan` only for observation and records every multiway call where at least
two non-empty seat-keyed opponent pools exist.

For each such decision it measures:

- opponent pool size imbalance;
- union relative strength versus the equal-seat mean of per-seat relative strengths;
- union range advantage versus equal-seat mean;
- union nut advantage versus equal-seat mean;
- union blocker score versus equal-seat mean;
- union blocker-effect value versus equal-seat mean;
- partial/empty pool frequency.

The equal-seat mean is **not preregistered as the final replacement formula**.  It is only a
diagnostic comparator that removes union's combo-count weighting and therefore quantifies whether
the collapse matters in live states.

No pass/fail magnitude threshold is invented before seeing the data.  The tool reports raw counts,
mean, p50, p90, p99, maximum, and largest examples.

Repair formulas will be designed only after this measurement.


---

## B1-A candidate semantics — joint current-board relative strength

The live B1 measurement confirms union collapse is material:

- 493 total plan-update calls;
- 96 multiway calls (**19.5%**);
- all 96 had at least two non-empty seat pools;
- all 96 had unequal pool sizes;
- pool-size ratio mean 1.94, p90 2.99, max 8.29.

Observed union-versus-equal-seat diagnostic deltas:

- relative strength: mean 0.042, p90 0.085, max 0.349;
- range advantage: mean 0.105, p90 0.202, max 0.673;
- nut advantage: mean 0.110, p90 0.218, max 0.595;
- blocker effect: mean 0.041, p90 0.097, max 0.273.

So B1 is a live strategy issue, not only a synthetic fixture.

### Relative strength has a natural multiway extension

The existing heads-up `relative_strength` means:

> among the opponent's perceived current-board combos, what fraction does **not strictly beat**
> hero?

Ties therefore count as "not behind".

For multiway the direct extension is:

> sample one compatible combo from every seat-specific perceived range; what is the probability
> that **no opponent strictly beats hero** on the current board?

This preserves opponent identity and preserves the heads-up definition exactly.

It is intentionally distinct from showdown pot share:

- `joint_not_behind`: ties count as 1 because the question is "am I currently behind?";
- `joint_current_share`: ties split by exact pot share and is reported alongside it.

`tools/measure_f7b_joint_rel.py` preregisters this as a **shadow metric only**.

Acceptance before any consumer change:

- fixed distortion fixture: union relative strength > 0.90 but joint not-behind = 0;
- one-opponent case exactly matches current `relative_strength`;
- missing seat pool => unknown, never copied from another opponent;
- default 3000-3005/30-hand fixture reports joint-vs-union delta and threshold-band crossings;
- production continues to consume the union until the shadow results are reviewed.

This does **not** choose replacements yet for range advantage, nut advantage, or blocker logic.
Those metrics have different strategic meanings and need separate aggregation rules.


---

## B1-A consumer — joint relative strength

Status: **IMPLEMENTED; targeted/regression validation pending.**

The shadow result was decisive:

- 96 / 96 live multiway decisions had complete seat-keyed pools;
- union versus joint absolute delta mean **0.189**;
- p90 **0.353**;
- max **0.818**;
- **59 / 96 (61.5%)** crossed at least one existing relative-strength strategy band;
- the three largest examples had union rel 0.738-0.818 while joint rel was exactly 0.

Therefore B1-A now replaces only the live `relative_strength` factual input.

### Activation

Heads-up:

```
relative_strength(hero, board, single_range)
```

is unchanged.

Multiway:

```
joint_relative_strength(hero, board, seat_ranges)
```

is used only when every active opponent has a non-empty seat-keyed range.

If any required seat range is missing, the joint value is **unknown** and the decision temporarily
falls back to the legacy union metric.  No missing opponent is synthesized from another range.

### Consumers changed

Exactly three relative-strength consumers are wired:

1. `make_plan` initial factual relative strength;
2. `refresh` factual relative strength after board/range changes;
3. the nut-hand re-raise probability inside `decide_response`, which previously recomputed a
   fresh union relative strength after the plan had already become seat-aware.

The response path receives the existing `opp_ranges` and `n_opp`; no new range model is built.

### Determinism

Each decision uses a separate child seed:

- `f7b_rel_make`;
- `f7b_rel_refresh`;
- `f7b_rel_response`.

If no seed is supplied in a direct/helper call, the helper derives one from hero, board, pool
contents, and simulation count.

The shared hand RNG is not consumed.

### Provenance

Plan state records:

- `rel_true`;
- `rel_union`;
- `rel_joint`;
- `rel_source` = `heads_up`, `joint_seat_pools`, or `union_fallback_incomplete`.

The response-only recomputation records corresponding `_last_response_rel_*` fields.

### Deliberately unchanged

This patch does **not** alter:

- range advantage;
- nut advantage;
- blocker score/effect;
- river blocker logic;
- overbet nut metric;
- single-main-opponent reads/stacks.

Those remain separate F7-B work items.

### Validation rule

This is an intentional strategy change.

The frozen post-F8 baseline must not be overwritten if fingerprints move.  Any movement must first
be attributed to states where:

```
n_opp > 1
AND rel_source == joint_seat_pools
AND rel_joint != rel_union
```

Only after attribution may B1-A be closed.


---

## B1-A behavior attribution tool

`tools/attribute_f7b_rel.py` isolates only the newly activated relative-strength consumer.

It requires the frozen local `baseline_9max_post_f8.json` and runs the canonical
3000-3005 / 30-hand regression twice:

1. current joint-relative behavior;
2. identical code with only `_decision_relative_strength` forced back to the legacy union value.

Acceptance:

- any current fingerprint movement is allowed at this intentional behavior-change step;
- **every** forced-union fingerprint must match the frozen post-F8 baseline exactly.

If forced-union does not restore every fingerprint, B1-A cannot be closed and the unexplained
movement must be isolated before proceeding.

Intent provenance now also records `rel_true`, `rel_union`, `rel_joint`, and `rel_source`.


---

## B1-A closure

User validation at local commit `43d2a6f`:

- targeted F7-B: **6/6**;
- post-F8 regression changed seeds: **3000, 3001, 3002, 3004, 3005**;
- `tools/attribute_f7b_rel.py` forced only the B1-A consumer back to union;
- forced-union mismatches: **[]**.

Therefore every frozen-fixture behavior change is fully attributed to the preregistered
joint-relative consumer.  B1-A is closed.

---

## B1-B shadow — range advantage and nut advantage

Status: **SHADOW ONLY. No production consumer changed.**

These two metrics answer different strategic questions and therefore do not share one generic
"multiway average".

### Range advantage candidate

Existing heads-up meaning:

> If a random combo from my range and a random combo from the opponent range reach this board,
> which range has more current-board showdown equity?

For multiway the direct extension samples:

- one compatible combo from my range;
- one compatible combo from every seat-specific opponent range.

Let `E` be hero's exact current-board showdown pot share and:

```
fair = 1 / (number_of_opponents + 1)
```

The candidate is normalized around fair share:

```
if E >= fair:
    adv = (E - fair) / (1 - fair)
else:
    adv = (E - fair) / fair
```

This has three required invariants:

- always lose -> -1;
- equal/fair field share -> 0;
- always win -> +1.

With one opponent `fair=0.5`, so it reduces exactly to the existing
`2*equity - 1` scale.

This is a factual field-level equity-distribution metric suitable for the current c-bet-frequency
meaning of `range_advantage`.

### Nut advantage candidate

Existing code does not measure literal nuts; it compares two "strong occupancy" bands:

- made category >= 2;
- made category >= 3.

The hero side remains the existing exact share of `my_range` in those bands.

For a multiway field, averaging opponent seats is not the right question for large sizing.
The relevant field event is:

> does **at least one** remaining opponent occupy that strong region?

The shadow therefore samples one compatible combo from each opponent seat and measures:

```
P(any opponent category >= 2)
P(any opponent category >= 3)
```

then plugs those field probabilities into the existing weighted/scaled nut-advantage formula.

With one opponent this falls back exactly to existing `R.nut_advantage`.

### Preregistered measurement

`tools/measure_f7b_range_nut.py` runs the same 3000-3005 / 30-hand fixture and reports:

- complete/unknown multiway states;
- range-advantage absolute delta;
- range-advantage sign flips;
- nut-advantage absolute delta;
- nut-advantage sign flips;
- crossings of the live `nut_adv >= 0.55` polarized-bluff threshold;
- largest examples.

No magnitude threshold is invented in advance.  Results decide whether each metric proceeds to a
consumer separately.

Blocker aggregation and B2 single-main-opponent reads remain outside this step.


---

## B1-B shadow result

User validation on the 3000-3005 / 30-hand fixture:

```
multiway_seen = 112
complete      = 112
unknown       = 0
```

### Range advantage

```
sign flips      20 / 112  (17.9%)
abs delta mean  0.123
p90             0.255
max             1.075
```

The largest live example moved from:

```
union  +0.6325
joint  -0.4425
```

so the field-level conclusion reverses.

The candidate has exact heads-up parity and an explicit fair-share zero point
`1/(N+1)`.  Therefore **range advantage is approved to proceed to a separate consumer step**
after a B1-A behavior checkpoint is frozen.

### Nut advantage

```
sign flips          38 / 112
abs delta mean      0.559
p90                 1.002
max                 1.433
live 0.55 crossings 5
```

The candidate frequently saturates near `-1` because "any opponent in a strong band" becomes
increasingly likely as the field grows.

This may be strategically appropriate for some large-sizing decisions, but the movement is much
larger than range advantage and the existing `nut_advantage` scale was calibrated for heads-up
strong-share differences.

Therefore **nut advantage is NOT approved as a consumer yet**.

Before activation it needs one more semantics check:

- separate the field-size effect from true distributional nut ownership;
- inspect the five live `0.55` threshold crossings;
- decide whether current overbet/polarized-bluff consumers want
  "any opponent strong", "strongest opponent range", or another explicitly derived field quantity.

No coefficient will be tuned to make the values look similar to the union metric.

### Regression interpretation

The shadow patch itself changes no production strategy.

The persistent mismatch against `baseline_9max_post_f8.json` at seeds
3000, 3001, 3002, 3004, and 3005 is the already-attributed B1-A joint-relative consumer,
not B1-B.

A new B1-A checkpoint must be frozen before the range-advantage consumer is activated so the next
behavior delta remains singly attributable.


---

## B1-B1 consumer — joint range advantage

Status: **IMPLEMENTED; validation pending.**

The shadow result approved range advantage separately from nut advantage.

### Consumer semantics

Heads-up is unchanged and calls existing `R.range_advantage`.

For complete multiway seat pools, `R.joint_range_advantage` samples one compatible combo from
hero's range and one from every opponent seat range, computes exact current-board showdown pot
share, and normalizes around fair field share `1/(N+1)`.

The scale therefore remains:

- always lose = -1;
- fair field share = 0;
- always win = +1;
- heads-up = existing `2*equity-1` behavior.

If any required opponent range is missing, the metric is unknown and the decision falls back to
the legacy union range advantage.  No range is synthesized.

### Live consumers changed

Only:

1. `make_plan` initial `range_adv`;
2. `refresh` updated `range_adv`.

The downstream `cbet_freq` formula is unchanged and simply receives the corrected field metric.

### Provenance

Plan/intent state records:

- `range_adv`;
- `range_adv_union`;
- `range_adv_joint`;
- `range_adv_source`.

### Deliberately unchanged

- nut advantage;
- blocker score/effect;
- overbet nut logic;
- river blocker logic;
- single-main-opponent reads/stacks.

### Behavior baseline

Attribution uses the frozen `tools/baseline_9max_post_b1a.json`, not post-F8.

`tools/attribute_f7b_range_adv.py` disables only `_decision_range_advantage` while leaving B1-A
active.  Every forced-union fingerprint must restore the post-B1A checkpoint before this consumer
can close.


---

## B1-B1 closure

User validation at `c0e6b22`:

- production modules compiled;
- post-B1A frozen regression: **all six fingerprints identical**;
- B1-B1 attribution: changed seeds **[]**;
- forcing only the range-advantage consumer back to legacy union also produced
  **forced-union mismatches []**.

Therefore the joint field range-advantage consumer is behavior-preserving on the frozen six-seed
fixture while repairing the live multiway factual input for future/reachable states.

The first targeted run failed only because `check_downstream_source_map()` still asserted that
the old union `R.range_advantage(... opp_range ...)` call existed in `make_plan` / `refresh`.
That assertion described the defect that B1-B1 intentionally removed.  Production behavior and
the attribution check both passed.

The verifier now requires `_decision_range_advantage` in both `make_plan` and `refresh` and
continues to require the still-unrepaired union consumers for nut advantage and blockers.

B1-B1 is **CLOSED**.  Nut advantage remains shadow-only.
