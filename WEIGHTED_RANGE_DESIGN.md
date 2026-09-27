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

### W0 — representation + adapter — CLOSED

- canonical helper API implemented;
- legacy occurrences map to mass;
- non-uniform flattening fails closed;
- production behavior unchanged.

### W1 — weighted sampling consumers — CLOSED

Legacy list input retains the exact old `rng.choice(list)` path. Uniform
weighted dicts use stable support, and only genuinely non-uniform weights use
cumulative weighted draws.

Converted sampling consumers:

- `bot.equity_vs_pools`;
- `bot.equity_vs_combos`;
- `ranges.range_advantage`;
- `ranges.joint_range_advantage`;
- `plan.joint_relative_strength`;
- `plan._eq_current`.

### W2 — weighted aggregate consumers — CLOSED

Probability-mass aggregation is wired through:

- `plan.relative_strength`;
- `ranges._strong_share` / nut advantage;
- `ranges.blocker_score`;
- `ranges.blocker_effect`;
- `ranges.joint_blocker_effect`.

Legacy list input retains the historical count semantics.

### W3 — transforms preserve weights — CLOSED

Weight-preserving transforms are wired through:

- `ranges._ranked`;
- `_bet_range`;
- `_continue_range`;
- `_call_range`;
- `_check_range`;
- `perceived_range`;
- `perceived_facing_bet_response`;
- `narrow_by_actions`;
- `runner.adjust_range_by_history`.

Selection may change support, but surviving weighted combos retain their incoming
mass. Legacy list execution remains unchanged. The historical bet-range list can
contain duplicate value/bluff combos; canonical weighted support de-duplicates
the key while preserving incoming mass. Production still uses the legacy list
path, so this cleanup does not change live actions.

### W4 — signatures / adapters / collapse removal — CLOSED

Weight-destroying boundaries are removed from the downstream path:

- session range unique/sort boundaries preserve weighted mass;
- active-opponent union uses `range_union` and sums mass only when weighted input exists;
- locked ranges remain weighted through postflop reconstruction;
- `plan._normalize_opp_pools` preserves representation;
- archive signatures preserve the historical hash for legacy/uniform ranges and
  include normalized mass only for genuinely non-uniform posteriors;
- in-process refresh signatures detect mass movement at fixed support;
- provenance now records both support count and range mass.

### W5 — posterior production — LOGIC BARRIER / NOT STARTED

W5 is the first stage that intentionally changes the information distribution
consumed by strategy. It is **not plumbing**.

Only after the user explicitly moves to logic/strategy work:

- observed preflop/action evidence may produce non-uniform mass;
- postflop observations may update mass rather than only hard-cut support;
- read/persona attribution must be measured before strategic promotion.

## 5. Invariants

1. No non-uniform weighted range may cross a legacy flattening boundary silently.
2. Uniform weighted input must retain the existing legacy strategy distribution.
3. Range order is not semantic; every sampling boundary establishes deterministic order.
4. No shared gameplay RNG stream is consumed differently merely because representation changed.
5. Unknown/missing seat ranges remain unknown; no pool is invented to fill them.
6. Weighting changes are attributed separately from multiway semantics, ICM, exploit, and sizing changes.
7. No VPIP/PFR/bluff coefficient tuning in this phase.

## 6. Current gates

Canonical CI: `.github/workflows/weighted-range-wiring.yml`

It runs:

- `tools/verify_weighted_range_adapter.py` — W0;
- `tools/verify_weighted_sampling.py` — W1;
- `tools/verify_weighted_aggregate_transform.py` — W2/W3;
- `tools/verify_weighted_boundaries.py` — W4;
- exact production fingerprint comparison against pre-W2 checkpoint
  `dc649f7fa66e11802c63c70deeddd39f63dd3e07`.

2026-09-27 canonical result: **PASS**.

The six production fingerprints are unchanged:

- 3000 `12c2daefd7c87cbb`
- 3001 `8b83f668c038d002`
- 3002 `0badaa6a21474fd3`
- 3003 `3aebdd1942b57229`
- 3004 `d4295da0aace11ca`
- 3005 `2c50d0b71bd16614`

Aggregate fixture is also identical: 180 hands, 1,368 preflop decisions,
283 VPIP events, 165 PFR events, 85 flop-seen hands.

**Exit:** W0-W4 structural migration is closed. W5 is intentionally held until
logic adjustment begins.
