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


---

## B1-B2 — separate nut ownership from field collision

Status: **DIAGNOSTIC ONLY.**

The first multiway nut shadow used:

> probability that at least one opponent occupies the strong band.

That quantity is real, but it combines two effects:

1. **range ownership** — whether hero's range has more top-end than an opponent range;
2. **field collision** — with more opponents, the probability that somebody has a strong hand rises
   even if every seat has the same distribution.

The existing heads-up `nut_advantage` was designed as an ownership comparison, while current
consumers use it for two different tasks:

- `bluff_mode`: `nut_adv >= 0.55` allows a polarized bluff mode;
- `overbet_frac`: recomputes union nut advantage and uses it in both overbet probability and
  overbet size.

Those two consumers need not want the same multiway quantity.

### Candidate A — worst-seat ownership

Compute the existing heads-up `R.nut_advantage(my_range, seat_range, board)` independently for
every active opponent and take the **minimum**.

Meaning:

> does hero own the top-end even against the opponent range with the strongest top-end claim?

Properties:

- exact heads-up parity;
- no combo-count weighting;
- no artificial player-count penalty;
- no synthetic "average opponent";
- preserves the existing nut-advantage scale and its 0.55 threshold meaning better than
  any-opponent occupancy.

This is the leading candidate for `bluff_mode`.

### Candidate B — any-field collision

Keep the first shadow definition:

> probability that at least one compatible opponent combo lies in the strong bands.

This intentionally becomes more adverse as the number of opponents grows.

It is not pure nut ownership.  It may still be relevant to **overbet risk**, where the chance that
somebody can continue strongly genuinely rises with field size.

### Measurement

`tools/measure_f7b_nut_semantics.py` compares, on the same live states:

- current union nut advantage;
- worst-seat ownership;
- any-field collision.

It reports:

- sign flips;
- `0.55` threshold crossings;
- disagreements between worst-seat and any-field at 0.55;
- absolute deltas;
- breakdown by number of opponents;
- the existing overbet nut multiplier under all three definitions.

No production consumer changes in this step.

Decision rule after measurement:

- if worst-seat ownership is stable enough and materially differs from union in live states, it may
  replace the `bluff_mode` ownership input;
- any-field collision will not replace ownership merely because it is more conservative;
- `overbet_frac` remains blocked until the ownership/collision split and B2 multi-opponent response
  semantics are jointly understood.


---

## B1-B2C — actual bluff-mode reachability

The ownership/collision measurement shows:

- worst-seat ownership stays materially closer to the original ownership scale than any-field
  collision;
- any-field increasingly saturates negative as opponent count grows, confirming that it is a
  field-collision quantity rather than a drop-in ownership replacement;
- union versus worst-seat crosses the existing `0.55` threshold only 5 times in 112 multiway
  planning states.

A threshold crossing alone is insufficient evidence for a consumer change because `bluff_mode`
is not called in every planning state.

`tools/measure_f7b_nut_bluffmode.py` therefore shadows the **actual consumer**.

For every production `bluff_mode` call it:

1. runs the current union-nut call from the real RNG state;
2. saves the exact post-call RNG state;
3. restores the pre-call state;
4. replays the same call with worst-seat ownership;
5. restores the production post-call RNG state;
6. returns the original union result.

It reports:

- how many multiway states actually call `bluff_mode`;
- how many of those have complete seat pools;
- threshold crossings **at the consumer**;
- actual mode changes under identical random rolls;
- transitions to/from `polarized`.

Production behavior and production RNG consumption remain unchanged.

Worst-seat ownership will only be approved for `bluff_mode` if the consumer-level shadow supports
the semantic replacement.  `overbet_frac` remains blocked.


---

## B1-B3 — all live nut consumers and wiring defect

The actual `bluff_mode` shadow found only **2 multiway bluff-mode calls** in the frozen fixture.
One call crossed the 0.55 threshold (union 0.809 vs worst-seat -0.571), but both inputs produced
the same `barrel` result under the identical RNG state.  Therefore worst-seat ownership causes
**0 bluff-mode behavior changes** in this fixture.

That does not close nut semantics because source inspection shows three distinct consumers:

1. `make_plan` continuous `bluff_ok` multiplier;
2. `bluff_mode` polarized/merged/barrel/probe selection;
3. `overbet_frac` probability and size.

There is also a wiring defect:

- `refresh` updates `st['nut_adv']`;
- `attach_intent` passes that value as `decide_size(..., nut=...)`;
- `decide_size` does not actually use the `nut` argument;
- `overbet_frac` instead recomputes `R.nut_advantage(my_range, opp_range, board)` from the
  collapsed union.

So the current implementation violates the intended judgment/plan boundary: a factual range metric
is recomputed inside sizing instead of consuming the already-established judgment state.

`tools/measure_f7b_nut_consumers.py` now shadows all live nut consumers separately:

### make_plan shadow

Re-runs `make_plan` with identical inputs and seed while replacing only nut ownership with
worst-seat ownership.  It reports:

- plan-label changes, including to/from `bluff_2street`;
- bluff-mode/multiplier changes.

Because `make_plan` owns a local deterministic RNG, the production run is returned unchanged.

### overbet shadow

For each actual multiway `overbet_frac` call:

- runs production union input;
- restores the exact pre-call RNG state;
- replays with worst-seat ownership;
- restores pre-call state again;
- replays with any-field collision;
- finally restores the production post-call RNG state and returns production output.

It distinguishes:

- overbet selection changes (None vs size);
- size-only changes when both select an overbet.

No production behavior changes in this diagnostic.

The next structural repair, if supported by reachability results, should remove the hidden union
recomputation from sizing and pass explicit judgment quantities forward rather than merely replacing
one scalar inside `overbet_frac`.


---

## B1-B3A — repair nut judgment-to-sizing wiring

Status: **IMPLEMENTED; behavior-preservation validation pending.**

The all-consumer shadow established:

- 60 / 60 multiway `make_plan` states had complete worst-seat ownership;
- replacing union ownership with worst-seat ownership changed **0 plan labels**;
- changed **0 bluff modes**;
- 11 multiway overbet calls were complete;
- neither worst-seat nor any-field changed overbet selection;
- one turn value overbet changed size only:
  - current union: **1.60 pot**
  - worst-seat: **1.55 pot**
  - any-field: **1.52 pot**.

The structural defect is independent of which multiway nut definition is ultimately chosen:
`overbet_frac` was recomputing a factual union-range judgment inside sizing even though
`refresh` already maintained `nut_adv`.

This repair deliberately does **not** change nut semantics yet.

### Wiring after repair

Judgment state stores both:

- `nut_adv` — rounded display/legacy value;
- `nut_adv_raw` — exact production union value.

`attach_intent` forwards `nut_adv_raw` to `decide_size`.

`decide_size` forwards that value explicitly to `overbet_frac`.

`overbet_frac` no longer calls `R.nut_advantage` and therefore cannot silently rebuild a
collapsed union judgment inside the sizing layer.

### Expected behavior

Because `nut_adv_raw` preserves the exact pre-repair union value, this is intended to be a
strict behavior-preserving architecture correction.

Acceptance requires:

1. F7-B targeted verifier **8/8**;
2. exact equality with frozen `baseline_9max_post_b1a.json`;
3. no new baseline save.

Worst-seat ownership and any-field collision remain shadow semantics.  They are not activated by
this patch.


---

## F7-B1C — blocker representation prerequisite

Status: **DIAGNOSTIC ONLY.**

Before choosing a multiway blocker aggregation, source tracing found a lower-level representation
inconsistency.

Normal postflop perceived ranges are initially built with only board cards dead, so combos containing
the observer's own hole cards can remain in the counterfactual range.  That is exactly what
`blocker_score` / `blocker_effect` need: they ask which opponent combos hero's cards remove.

However, the showdown-history **range expansion** branch in
`runner.adjust_range_by_history()` explicitly removes:

```
hero hole cards + board
```

from the widened range.

Therefore the same strategic range can expose blocker information or erase it solely because its
provenance passed through history widening.

This is not required for equity safety.  `bot.equity_vs_combos()` independently filters every
opponent pool against `hero + board` before simulation.

So there are two distinct concepts that should not be conflated:

1. **counterfactual perceived range** — may contain hero-blocked combos so blocker effects are
   measurable;
2. **feasible showdown pool** — must remove hero/board conflicts before equity sampling.

`tools/measure_f7b_blocker_representation.py` first proves in a fixed fixture that preserving
hero-blocked combos leaves equity identical because the equity consumer filters them itself, while
the current history-widening path collapses blocker signal to zero.

It then measures whether that history-widening path is reached in the frozen live fixture and how
often blocker signal differs from a board-only-dead counterfactual expansion.

No multiway blocker aggregation will be activated until this representation prerequisite is closed.


---

## F7-B1C2 — field-level multiway blocker shadow

The blocker concept already exists in production and already affects bluffing:

- `blocker_score` changes initial `bluff_ok`;
- `blocker_effect` changes initial `bluff_ok` again using call-vs-fold composition;
- `river_fix` uses `blocker_effect` to promote missed hands into `river_bluff`;
- value sizing flips the same net effect because blocking calls hurts value extraction.

The remaining problem is multiway aggregation: all seat ranges are collapsed into one union before
those metrics are computed.

A simple seat average is not adopted because blocker value is a **field event**.

### Direct field counterfactual

`tools/measure_f7b_blocker_field.py` samples compatible combos from every seat-specific perceived
range in two worlds:

1. board cards dead, but hero hole cards not dead — counterfactual "hero does not hold these
   blockers";
2. board + hero cards dead — actual world.

It measures two events:

#### Strong-presence blocker

```
P(any opponent is in that seat's top current-board strength band)
before hero blockers
-
same probability after hero blockers
```

Positive means hero removes strong field configurations.

#### Fold-field blocker

```
P(all opponents fold to the nominal bet | hero cards dead)
-
P(all opponents fold | hero cards not dead)
```

Positive means hero's cards directly improve whole-field fold probability.

Sampling enforces card compatibility between different opponents in both worlds, so this is not an
independent-seat product approximation.

The diagnostic compares these field quantities with the current union
`blocker_score` / `blocker_effect`, including sign reversals and largest live discrepancies.

No production strategy changes in this step.


---

## F7-B1C3 — blocker duplicate-consumer decomposition

The field shadow shows the union blocker is not merely mis-scaled in multiway pots:

- union `blocker_effect` vs direct whole-field fold effect reverses sign in **32 / 112**
  multiway states;
- union `blocker_score > 0` while the direct field strong-presence effect is negative in
  **54 / 112** states.

Before activating any field replacement, another source-level issue must be separated.

`ranges.blocker_score` explicitly describes itself as an approximate **fallback** for when the
bet size is unknown.  `ranges.blocker_effect` is the more specific call-vs-fold net effect.

But `make_plan` has a nominal street size and consumes both simultaneously:

```
bluff_ok *= (0.5 + 1.8 * blocker_score)
bluff_ok *= (1 + 4 * blocker_effect * awareness)
```

So the same blocker concept contributes twice: once through the approximate strong-combo proxy and
again through the response-specific net effect.

`tools/measure_f7b_blocker_consumers.py` replays only multiway `make_plan` calls from the
identical seed in four modes:

- production: score + effect;
- effect-only: `blocker_score=0`, which leaves the formula's existing base factor `0.5`;
- score-only: `blocker_effect=0`;
- neither.

No new constants are introduced.  The production result is always returned.

The purpose is attribution, not tuning: if removing the approximate score changes strategy, that
change must be understood before replacing union aggregation with a field-level blocker metric.


---

## F7-B1C4 — correction: exact neutralization of blocker_score

B1C3 exposed that removing `blocker_effect` changes one multiway plan in the frozen fixture, while
forcing `blocker_score=0` changes none.

That result does **not** yet mean the approximate score can simply be removed.

The reason is algebraic:

```
score factor = 0.5 + 1.8 * blocker_score
```

so `blocker_score=0` leaves a factor of **0.5**, not the neutral multiplicative factor 1.0.
The previous B1C3 label `effect_only` was therefore imprecise: it meant "effect active with
score value zero", not "score contribution removed".

The exact score value that cancels the existing factor is:

```
blocker_score = (1.0 - 0.5) / 1.8 = 5/18
```

This is **not a proposed poker constant** and is not tuning.  It is only the algebraic value that
makes the existing score factor equal exactly 1.0.

`tools/measure_f7b_blocker_neutral.py` replays each multiway `make_plan` under identical seeds:

- production;
- score factor neutralized exactly to 1.0, effect retained;
- effect zeroed, score retained;
- both blocker influences removed (score factor 1.0, effect zero).

Production output is always returned.

This diagnostic must be interpreted before any blocker consumer is removed or any field-level
replacement is activated.


---

## F7-B1C5 — exact consumer-factor isolation

B1C4 revealed a second diagnostic error.  The attempted algebraic neutralization used the raw
`blocker_score`, but production first applies blocker awareness:

```
blk = blocker_score * blocker_awareness
factor = 0.5 + 1.8 * blk
```

Therefore setting raw `blocker_score=5/18` only produces factor 1.0 when awareness is exactly
1.0.  The live output itself exposed this: the observed score factor averaged about 0.596.

To stop reverse-engineering internal inputs, production is refactored **without changing either
formula** into two explicit helpers:

```
_blocker_score_bluff_factor(blk)     -> 0.5 + 1.8*blk
_blocker_net_bluff_factor(blk_net)   -> clamp(1 + 4*blk_net, 0.45, 1.65)
```

`make_plan` calls those helpers at the exact old locations.

This is a behavior-preserving wiring change only.  It creates a clean audit seam.

`tools/measure_f7b_blocker_factor_attribution.py` then replays multiway `make_plan` calls with
identical inputs/seeds and neutralizes the **consumer factor itself** to 1.0:

- score factor neutral, net factor production;
- net factor neutral, score factor production;
- both neutral.

Raw blocker values, blocker skill/awareness, all coefficients, and production output remain
untouched.

This replaces B1C3/B1C4 for strategy attribution.  Their measurements remain useful historical
diagnostics but are not sufficient for consumer-removal decisions.


---

## F7-B1C6 — same-scale joint blocker-effect candidate

B1C5 gives exact consumer attribution:

- neutralizing the approximate score factor alone changes 1 / 60 multiway
  `make_plan` decisions;
- neutralizing the response-specific net factor alone changes 1 / 60;
- neutralizing both changes 3 / 60.

So both current factors are behaviorally live.

The next question is semantic, not tuning.

The earlier direct field metric measured a **change in whole-field fold probability**.  That exposed
direction errors in the union collapse, but its magnitude is not on the same scale as legacy
`blocker_effect`.  Feeding it into the existing `1 + 4*effect` consumer would silently change
the meaning of that coefficient.

### Same-scale generalization

Legacy heads-up `blocker_effect` is:

```
fraction of CALL combos blocked by hero
-
fraction of FOLD combos blocked by hero
```

The multiway generalization replaces a single opponent combo with a compatible **joint field
configuration**:

```
continue configuration = at least one opponent is in that seat's call range
fold configuration     = every opponent is in that seat's fold range

joint blocker effect =
    fraction of CONTINUE configurations blocked by hero
  - fraction of ALL-FOLD configurations blocked by hero
```

This preserves:

- exact heads-up parity;
- the legacy `[-1, +1]` scale;
- positive = hero removes continuing configurations more than folding configurations;
- negative = hero removes folding configurations more than continuing configurations.

It also enforces cross-opponent card compatibility and returns `None` for incomplete seat pools
instead of inventing the missing opponent from the union.

`ranges.joint_blocker_effect` is added as an unused semantic helper in this step.

`tools/measure_f7b_blocker_joint.py` compares current union effect with the same-scale joint
effect and shadows the structurally clean candidate:

1. approximate `blocker_score` strategy factor neutralized to exactly 1.0;
2. response-specific `blocker_effect` replaced with `joint_blocker_effect`;
3. all existing coefficients, blocker awareness and RNG streams unchanged.

Production output is always returned.  Activation requires the measured behavior attribution first.


---

## F7-B1C7 — stale blocker judgment and split consumers

After the same-scale joint candidate passed exact heads-up parity, source tracing exposed a separate
architecture defect that must be closed before activation.

### Current split

`make_plan` computes and stores:

```
blocker
blocker_net
stackoff['_blk_net']
```

But `refresh()` updates rel / equity / outs / nut advantage / range advantage and **does not
refresh either blocker metric**.

That stale copy is behaviorally live: `decide_size()` reads
`stackoff['_blk_net']` for value sizing on later streets.

Meanwhile `river_fix()` does not consume the stored judgment.  It independently recomputes
`R.blocker_effect(...)` from the current **union** range on the river.

So blocker judgment currently has three different paths:

1. make-plan bluff probability;
2. stale make-plan copy inside later-street value sizing;
3. fresh but union-collapsed recomputation inside river busted-draw bluffing.

This violates the target architecture:

```
judgment -> plan -> action
```

because the same factual concept is stale in one consumer and silently recomputed inside another.

`tools/measure_f7b_blocker_stale.py` measures, on every multiway refresh:

- stored blocker net vs current-board union blocker net;
- stored stackoff copy vs current union;
- current union vs same-scale joint blocker;
- sign reversals;
- the implied change in the existing value-sizing multiplier;
- river states where the union and joint judgments disagree.

No production behavior changes in this diagnostic.


---

## F7-B1C8 — full paired replay of unified blocker judgment

B1C7 confirms the stale path is material in the frozen fixture:

- 55 / 63 multiway refreshes have a stored blocker net different from the current-board union value;
- 17 / 63 reverse sign;
- the value-sizing multiplier would differ by at least 0.02 in 33 / 63 states;
- maximum multiplier difference is 0.418;
- current union vs same-scale joint blocker also continues to disagree, including river sign reversals.

This is no longer just a multiway aggregation issue.  It is a broken factual-judgment lifecycle.

### Unified candidate

Before production activation, `tools/measure_f7b_blocker_unified_candidate.py` performs a full
paired replay of the frozen 9-max fixture.

Production and candidate both start from identical tournament seeds.

The candidate changes no tuning coefficients.  It only changes blocker wiring/semantics:

1. the approximate `blocker_score` bluff multiplier is neutralized to 1.0;
2. the response-specific blocker judgment uses `joint_blocker_effect`
   (HU exact legacy parity; multiway seat-keyed);
3. `refresh` recomputes that judgment on current board/current ranges;
4. `stackoff['_blk_net']` is refreshed from the same judgment before value sizing;
5. `river_fix` receives the same joint factual judgment rather than independently using union
   `blocker_effect`;
6. incomplete multiway seat pools yield a neutral blocker contribution rather than inventing a
   missing opponent from the union.

The script compares full action fingerprints, every hand log, VPIP/PFR/flop summaries, first
divergence points and candidate joint-judgment coverage.

This is the activation gate.  A production blocker rewrite should not be committed until the paired
behavior change is measured and attributable.


---

## F7-B1C9 — direct attribution without tournament cascade

B1C8 proves that the unified blocker candidate can alter tournament trajectories, but the raw
33 changed hands are **not** 33 direct blocker decisions.

Once an early postflop action changes, stacks, busts, button order and later dealt seats diverge.
Later preflop differences are therefore downstream state divergence, not direct evidence that the
blocker touched preflop logic.

`tools/measure_f7b_blocker_unified_direct.py` removes that confound.

For every production `update_plan` call it:

1. deep-copies the exact pre-decision arguments/state;
2. runs production normally and returns that result to the tournament;
3. replays the copied state through the B1C8 unified blocker candidate;
4. compares only the two outputs for that exact decision.

The real tournament always follows production, so candidate differences can never cascade into later
states.

It attributes separately for heads-up and multiway:

- plan-label changes;
- current-street intent action changes;
- current-street intent size changes;
- bluff-mode changes;
- blocker state / stackoff blocker changes.

This is the direct activation gate. Full paired replay remains useful for downstream impact, but
production activation should be justified by this non-cascading attribution.
