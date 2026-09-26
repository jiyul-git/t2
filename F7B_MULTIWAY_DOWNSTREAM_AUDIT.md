# F7-B — Multiway downstream semantics audit

Status: **B1/B2 DIAGNOSTIC IMPLEMENTED; strategy repair not started.**

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
