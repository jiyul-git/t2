#!/usr/bin/env python3
"""W0 weighted-range representation / legacy-adapter contract."""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ranges as R


checks = 0


def need(cond, msg):
    global checks
    if not cond:
        raise AssertionError(msg)
    checks += 1


# Production-style unique legacy range must round-trip exactly.
legacy = R.preflop_range(
    'reg', 'BTN', 'open', 40.0, set(),
    seats=9, ante=True)
need(bool(legacy), 'fixture legacy range is empty')
wr = R.weighted_range(legacy)
need(len(wr) == len(legacy), 'unique legacy support changed')
need(all(abs(w - 1.0) <= 1e-12 for w in wr.values()),
     'legacy combos did not receive unit mass')
need(R.legacy_range(wr) == legacy,
     'legacy -> weighted -> legacy ordering/support changed')
need(abs(R.range_mass(wr) - len(legacy)) <= 1e-12,
     'legacy mass is not combo count')
checks_before = checks

# Duplicate occurrences are probability mass, not something set() may erase.
dup = [('As', 'Kd'), ('Qh', 'Qs'), ('As', 'Kd')]
wd = R.weighted_range(dup)
need(wd[('As', 'Kd')] == 2.0 and wd[('Qh', 'Qs')] == 1.0,
     'duplicate legacy combo mass not aggregated')
need(abs(R.range_mass(wd) - 3.0) <= 1e-12,
     'duplicate mass total wrong')

# Weighted input: zero is omitted, positive finite weights preserved.
raw = {
    ('As', 'Kd'): 0.25,
    ('Qh', 'Qs'): 2.5,
    ('2c', '3c'): 0.0,
}
ww = R.weighted_range(raw)
need(ww == {('As', 'Kd'): 0.25, ('Qh', 'Qs'): 2.5},
     'weighted normalization changed mass')
need(abs(R.range_weight(ww, ('Qh', 'Qs')) - 2.5) <= 1e-12,
     'range_weight lookup wrong')
need(not R.range_is_uniform(ww), 'non-uniform range marked uniform')

# Fail closed: old list-only code may not silently discard true weights.
try:
    R.legacy_range(ww)
except ValueError:
    checks += 1
else:
    raise AssertionError('non-uniform weighted range flattened silently')

# Equal common scale is safe to flatten because the distribution is uniform.
eq = {('As', 'Kd'): 3.0, ('Qh', 'Qs'): 3.0}
need(R.range_is_uniform(eq), 'equal weighted range not uniform')
need(R.legacy_range(eq) == [('As', 'Kd'), ('Qh', 'Qs')],
     'uniform weighted range legacy adapter wrong')

# Filter must preserve surviving masses exactly.
flt = R.range_filter(ww, lambda c: c[0] == 'As')
need(flt == {('As', 'Kd'): 0.25}, 'range_filter changed weight')

# Invalid mass/card shapes must be rejected instead of poisoning later math.
for bad in (
    {('As', 'Kd'): -1.0},
    {('As', 'Kd'): float('nan')},
    {('As', 'Kd'): float('inf')},
):
    try:
        R.weighted_range(bad)
    except ValueError:
        checks += 1
    else:
        raise AssertionError('invalid weight accepted: %r' % (bad,))

for bad_combo in ([('As',)], [('As', 'As')], [(1, 'Kd')]):
    try:
        R.weighted_range(bad_combo)
    except ValueError:
        checks += 1
    else:
        raise AssertionError('invalid combo accepted: %r' % (bad_combo,))

# Stable item ordering must not depend on dict insertion order.
a = {('Qh', 'Qs'): 2.0, ('As', 'Kd'): 1.0}
b = {('As', 'Kd'): 1.0, ('Qh', 'Qs'): 2.0}
need(R.range_items(a) == R.range_items(b),
     'weighted stable ordering depends on dict insertion')

print({
    'checks': checks,
    'legacy_fixture_combos': len(legacy),
    'legacy_roundtrip_checks': checks_before,
    'duplicate_mass': R.range_mass(wd),
    'nonuniform_flatten_rejected': True,
    'stable_items': True,
})
print('PASS W0 weighted-range representation / legacy adapter')
