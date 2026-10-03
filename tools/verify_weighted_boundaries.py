#!/usr/bin/env python3
"""W4 weighted range boundaries/signatures/provenance gate."""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plan as PL
import ranges as R

checks = 0


def need(cond, msg):
    global checks
    if not cond:
        raise AssertionError(msg)
    checks += 1


def old_range_sig(combos):
    if not combos:
        return None
    payload = '\n'.join(sorted(str(tuple(c)) for c in combos))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


a = [('As','Ks'), ('Qh','Qd'), ('7c','6c'), ('2s','2h')]
b = [('As','Ks'), ('Jh','Th'), ('9c','9d')]

# sorted(set(...)) compatibility on legacy input.
need(R.range_unique_sorted(a + [a[0], a[2]]) == sorted(set(a)),
     'legacy unique/sort semantics changed')

wa = {c: float(i + 1) for i, c in enumerate(a)}
ua = R.range_unique_sorted(wa)
need(isinstance(ua, dict), 'weighted unique/sort flattened')
need(list(ua) == sorted(a), 'weighted unique/sort support unstable')
need(all(ua[c] == wa[c] for c in ua), 'weighted unique/sort changed mass')

# Union: legacy exact; weighted overlap sums source masses.
need(R.range_union(a, b) == sorted(set(a + b)),
     'legacy union changed')
wb = {
    ('As','Ks'): 10.0,
    ('Jh','Th'): 2.0,
    ('9c','9d'): 3.0,
}
wu = R.range_union(a, wb)
need(isinstance(wu, dict), 'weighted union flattened')
need(wu[('As','Ks')] == 11.0, 'weighted overlap mass not summed')
need(wu[('Jh','Th')] == 2.0 and wu[('9c','9d')] == 3.0,
     'weighted unique source mass changed')
need(wu[('Qh','Qd')] == 1.0 and wu[('7c','6c')] == 1.0,
     'legacy source did not contribute unit mass')

# Archive signature: historical legacy bytes must not move.
legacy_sig = old_range_sig(a)
need(PL._range_sig(a) == legacy_sig, 'legacy archive signature changed')
uniform = {c: 7.0 for c in a}
need(PL._range_sig(uniform) == legacy_sig,
     'uniform weighted signature lost legacy compatibility')

w1 = {c: float(i + 1) for i, c in enumerate(a)}
w2 = {c: float((i + 1) * 2) for i, c in enumerate(a)}
w3 = dict(w1)
w3[a[0]] *= 4.0
need(PL._range_sig(w1) == PL._range_sig(w2),
     'weighted signature is not scale invariant')
need(PL._range_sig(w1) != PL._range_sig(w3),
     'weighted signature ignored mass redistribution')

# In-process decision signature: legacy exact old hash, but mass movement visible.
old_decision = hash(frozenset(map(str, a)))
need(PL._decision_range_sig(a) == old_decision,
     'legacy decision signature changed')
need(PL._decision_range_sig(uniform) == old_decision,
     'uniform weighted decision signature changed')
need(PL._decision_range_sig(w1) != PL._decision_range_sig(w3),
     'decision refresh signature ignored weight movement')

# Per-seat pool normalization must preserve weighted representation and isolate copies.
pools = PL._normalize_opp_pools(
    w1, 3, {2: w1, 5: b})
need(len(pools) == 3, 'pool normalization lost opponent slots')
need(isinstance(pools[0], dict), 'weighted seat pool flattened')
need(pools[0] == w1, 'weighted seat pool mass changed')
need(pools[0] is not w1, 'pool normalization leaked input identity')
# Unknown seats are NOT cloned from a known villain or the union range
# (eca264f5 "stop cloning known villains into unknown multiway seats"); they
# stay None and downstream equity uses the neutral fallback.  The old checks
# expected the retired clone (stage10: stale expectation).
need(pools[1] is not None and pools[1] == b and pools[1] is not b,
     'known second seat pool lost or aliased')
need(pools[2] is None, 'unknown seat was filled by cloning another range')

legacy_pools = PL._normalize_opp_pools(a, 2, {2: a})
need(legacy_pools[0] == a and legacy_pools[0] is not a and legacy_pools[1] is None,
     'legacy pool normalization changed')

# Source-level guard for the exact flattening boundaries closed by W4.
session_src = (ROOT / 'session.py').read_text(encoding='utf-8')
for bad in (
    'return sorted(set(rr)), {',
    'return sorted(set(orange)), {',
    'my_r = sorted(set(my_r))',
    'orange = sorted(set(orange))',
    'opp_r.extend(orange)',
    'opp_r = sorted(set(opp_r))',
    '_base_target_range = list(opp_ranges.get(_target) or [])',
):
    need(bad not in session_src, 'session flatten boundary remains: %s' % bad)

for required in (
    'R.range_unique_sorted(rr)',
    'R.range_unique_sorted(orange)',
    'R.range_union(*[',
    'R.range_copy(',
    "'my_range_mass'",
    "'opp_range_mass'",
    "'opp_ranges_mass'",
    "'locked_opp_ranges_mass'",
):
    need(required in session_src, 'session weighted wiring missing: %s' % required)

plan_src = (ROOT / 'plan.py').read_text(encoding='utf-8')
for required in (
    'def _decision_range_sig',
    'R.range_signature(combos)',
    "'my_range_mass'",
    "'opp_range_mass'",
    "'opp_ranges_mass'",
    "'pf_opp_ranges_mass'",
):
    need(required in plan_src, 'plan weighted wiring missing: %s' % required)

print({
    'checks': checks,
    'legacy_sig': legacy_sig,
    'weighted_sig': PL._range_sig(w1),
    'union_mass': R.range_mass(wu),
    'pool_types': [type(x).__name__ for x in pools],
})
print('PASS W4 weighted boundary/signature/provenance wiring')
