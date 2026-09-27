# WEIGHTED RANGE DESIGN — 2026-09-27

Scope: opponent/hero combo-range representation only. This phase is structural wiring, not balance tuning.

## 1. Problem

Production ranges are currently plain combo lists. A combo is either present or absent.

That is enough for a hard threshold range, but it cannot represent a posterior such as:

- AA still possible but only 20% as likely after this action;
- missed draws remain but with lower mass;
- a shown tendency increases some bluff combos without making every bluff combo equally likely.

Several current operations also collapse information:

- `sorted(set(range))` removes multiplicity/mass;
- set/list reconstruction in transforms loses weights;
- uniform `rng.choice(pool)` ignores posterior mass;
- aggregate metrics divide by combo count rather than probability mass;
- signatures that hash combo membership only cannot distinguish two distributions with the same support.

The migration must fix representation first, then consumers, without mixing the change with strategy tuning.

## 2. Canonical representation

Weighted range:

```python
{
    ('As', 'Kd'): 1.0,
    ('Qh', 'Qs'): 0.35,
}
```

The value is **relative probability mass**, not necessarily normalized probability.

Properties:

- only positive finite mass is stored;
- zero mass is omitted;
- a common scale factor does not change the distribution;
- legacy iterable ranges are interpreted as mass 1.0 per occurrence;
- duplicate legacy combos aggregate their mass instead of being silently discarded.

## 3. Legacy boundary

`ranges.weighted_range(r)` converts legacy or weighted input to canonical form.

`ranges.legacy_range(r)` is deliberately fail-closed:

- legacy input -> list unchanged;
- uniformly weighted dict -> safe list view;
- non-uniform weighted dict -> raises `ValueError`.

This is intentional. Once a true posterior exists, an old consumer must not silently flatten it.

`range_items`, `range_mass`, `range_weight`, `range_filter` are the migration primitives.

## 4. Migration order

### W0 — representation + adapter
Current step.

- add canonical helper API;
- no production consumer receives non-uniform weights;
- strategy behavior must remain unchanged.

### W1 — weighted sampling consumers

Convert only sampling, preserving existing seeds and deterministic ordering:

- `bot.equity_vs_pools`;
- `bot.equity_vs_combos`;
- `ranges.range_advantage`;
- `ranges.joint_range_advantage`;
- `plan.joint_relative_strength`;
- `plan._eq_current`.

Legacy uniform input must have exact or statistically locked parity before activation.

### W2 — weighted aggregate consumers

Use probability mass instead of combo count:

- `plan.relative_strength`;
- `ranges._strong_share` / nut advantage;
- `ranges.blocker_score`;
- `ranges.blocker_effect`;
- `ranges.joint_blocker_effect`.

### W3 — transforms preserve weights

Rewrite:

- `ranges._ranked`;
- `_bet_range`;
- `_continue_range`;
- `_call_range`;
- `_check_range`;
- `perceived_range`;
- `narrow_by_actions`;
- `runner.adjust_range_by_history`.

Selection may change support, but surviving combos keep their incoming mass unless the model explicitly applies a likelihood multiplier.

### W4 — signatures / adapters / collapse removal

Remove or replace weight-destroying boundaries:

- `session.py: sorted(set(orange))`;
- locked-range set collapse;
- `plan._normalize_opp_pools: list(r)`;
- range signatures;
- archive range length/count semantics.

Weighted signatures must include combo and stable numeric mass.

### W5 — posterior production

Only after all downstream paths are weight-safe:

- observed preflop/action evidence may produce non-uniform mass;
- postflop observations update mass rather than only hard-cut support;
- read/persona attribution is measured before any strategic promotion.

## 5. Invariants

1. No non-uniform weighted range may cross a legacy flattening boundary silently.
2. Uniform weighted input must retain the existing legacy strategy distribution.
3. Range order is not semantic; every sampling boundary establishes deterministic order.
4. No shared gameplay RNG stream is consumed differently merely because representation changed.
5. Unknown/missing seat ranges remain unknown; no pool is invented to fill them.
6. Weighting changes are attributed separately from multiway semantics, ICM, exploit, and sizing changes.
7. No VPIP/PFR/bluff coefficient tuning in this phase.

## 6. Current gate

`tools/verify_weighted_range_adapter.py`

W0 closes only when:

- helper validation passes;
- legacy -> weighted -> legacy round-trip is exact for production-style unique ranges;
- duplicate legacy occurrences aggregate mass;
- non-uniform weighted flattening is rejected;
- current regression baseline remains unchanged.

After W0, proceed to W1 one consumer family at a time.
