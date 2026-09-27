#!/usr/bin/env python3
"""W2/W3 weighted aggregates + transforms.

Structural gate:
1) legacy list input remains exactly compatible with the pre-W2/W3 formulas;
2) weighted input keeps the same selected support while preserving incoming mass;
3) aggregate consumers react to posterior mass instead of combo count.
"""

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bot
import plan as PL
import ranges as R
import runner as RU
import preflop as PF


checks = 0


def need(cond, msg):
    global checks
    if not cond:
        raise AssertionError(msg)
    checks += 1


def same_float(a, b, tol=1e-12):
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def old_ranked(r, board):
    return sorted(r, key=lambda c: bot._sd_strength(c, board), reverse=True)


def old_bet_range(r, board, street, bluff_axis, size_frac, damp=1.0, barrel=0.0):
    ranked = old_ranked(r, board)
    n = len(ranked)
    vfrac = {'flop': 0.42, 'turn': 0.30, 'river': 0.22}.get(street, 0.32)
    vfrac = max(0.08, min(0.85, vfrac * (1.0 + 1.15*barrel)))
    if size_frac >= 1.0:
        vfrac *= 0.60
    elif size_frac >= 0.7:
        vfrac *= 0.78
    elif size_frac <= 0.35:
        vfrac *= 1.45
    vfrac = R._damp(vfrac, damp)
    nv = max(1, int(n*min(0.95, vfrac)))
    value = ranked[:nv]
    nb = bot.bluff_count(nv, size_frac, street, bluff_axis)
    return value + bot.pick_bluffs(ranked, board, street, nb)


def old_continue_range(r, board, street, size_frac, damp=1.0):
    ranked = old_ranked(r, board)
    n = len(ranked)
    keep = {'flop': 0.62, 'turn': 0.48, 'river': 0.38}.get(street, 0.50)
    keep = R._damp(keep * (1.25 - 0.45*min(1.5, size_frac)), damp)
    k = max(1, int(n*min(0.95, keep)))
    out = ranked[:k]
    return out if len(out) >= R._MIN_KEEP else ranked[:R._MIN_KEEP] or ranked


def old_call_range(r, board, street, size_frac, damp=1.0):
    ranked = old_ranked(r, board)
    n = len(ranked)
    keep = {'flop': 0.62, 'turn': 0.48, 'river': 0.38}.get(street, 0.50)
    keep = R._damp(keep * (1.25 - 0.45*min(1.5, size_frac)), damp)
    cut = max(1, int(n*0.18))
    trap_keep = max(0, int(cut*0.25))
    lo = ranked[:trap_keep]
    mid = ranked[cut:max(cut+1, int(n*min(0.95, keep)))]
    out = lo + mid
    return out if len(out) >= R._MIN_KEEP else ranked[cut:cut+R._MIN_KEEP] or ranked[:R._MIN_KEEP]


def old_check_range(r, board, street, cbet_axis, damp=1.0):
    ranked = old_ranked(r, board)
    n = len(ranked)
    drop = int(n*0.10*min(1.0, cbet_axis/6.0)*damp)
    return ranked[drop:] if n - drop >= R._MIN_KEEP else ranked


def old_narrow_by_actions(base, board, acts, actor_read=None):
    if not board or not base:
        return base
    bluff = 5.0
    cbet = 5.0
    barrel = 0.0
    if actor_read and actor_read.get('w', 0) > 0:
        w = actor_read['w']
        bluff = max(1.0, min(10.0, 5.0 + 5.0*actor_read.get('bluff_gap', 0.0)*w))
        cbet = max(1.0, min(10.0, 5.0 - 5.0*actor_read.get('passive', 0.0)*w))
        barrel = max(-1.0, min(1.0, actor_read.get('barrel_gap', 0.0)))
    r = list(base)
    floor = max(R._MIN_KEEP, int(len(base)*R._MIN_FRAC))
    step = 0
    for stt, a, sz in acts:
        if len(r) <= floor:
            break
        d = R._DECAY ** step
        if a in ('bet', 'raise', 'allin'):
            r = old_bet_range(r, board, stt, bluff, sz, d, barrel)
        elif a == 'call':
            r = old_call_range(r, board, stt, sz, d)
        elif a == 'check':
            r = old_check_range(r, board, stt, cbet, d)
        else:
            continue
        step += 1
    return r if r else list(base)


def old_relative_strength(hero, board, opp_range=None):
    if len(board) < 3:
        return 0.5
    mine = bot.eval7(hero + board)
    dead = set(hero) | set(board)
    pool = opp_range if opp_range else None
    if pool:
        cand = [c for c in pool if not (set(c) & dead)]
    else:
        deck = [c for c in bot.FULLDECK if c not in dead]
        cand = [(deck[i], deck[j])
                for i in range(len(deck)) for j in range(i+1, len(deck))]
    if not cand:
        return 0.5
    ranked = sorted(cand, key=lambda c: bot.eval7(list(c)+board), reverse=True)
    top = ranked if pool else ranked[:max(1, len(ranked)//2)]
    better = sum(1 for c in top if bot.eval7(list(c)+board) > mine)
    return 1.0 - better/len(top)


def old_strong_share(r, board, cutoff=2):
    n = ok = 0
    for c in r:
        if set(c) & set(board):
            continue
        n += 1
        if bot.eval7(list(c)+board)[0] >= cutoff:
            ok += 1
    return ok/n if n else 0.0


def old_blocker_score(hero, opp_range, board):
    strong = sorted(
        opp_range,
        key=lambda c: bot.eval7(list(c)+board),
        reverse=True)
    strong = strong[:max(4, len(strong)//5)]
    return sum(
        1 for c in strong
        if c[0] in hero or c[1] in hero) / len(strong)


def old_blocker_effect(hero, opp_range, board, street, size_frac, for_value=False):
    calls = set(old_call_range(opp_range, board, street, size_frac))
    folds = [c for c in opp_range if c not in calls]
    if not calls or not folds:
        return 0.0
    hit = lambda c: c[0] in hero or c[1] in hero
    blocked_call = sum(1 for c in calls if hit(c)) / len(calls)
    blocked_fold = sum(1 for c in folds if hit(c)) / len(folds)
    net = blocked_call - blocked_fold
    return max(-1.0, min(1.0, -net if for_value else net))


def weighted_fixture(base):
    # Non-uniform but deterministic positive masses.
    return {c: 0.25 + (i % 11) * 0.37 for i, c in enumerate(base)}


board = ['Jh', '7d', '2c']
dead = set(board)
base = [
    c for c in R.preflop_range(
        'reg', 'BTN', 'open', 40.0, dead, seats=9, ante=True)
    if not (set(c) & dead)
][:120]
need(len(base) >= 40, 'legacy transform fixture too small')
wr = weighted_fixture(base)

# ---------- W3: exact legacy support parity + mass preservation ----------
transform_cases = [
    ('bet', lambda x: R._bet_range(x, board, 'flop', 5.8, 0.72, 0.75, 0.15),
     lambda x: old_bet_range(x, board, 'flop', 5.8, 0.72, 0.75, 0.15)),
    ('continue', lambda x: R._continue_range(x, board, 'flop', 0.66, 0.75),
     lambda x: old_continue_range(x, board, 'flop', 0.66, 0.75)),
    ('call', lambda x: R._call_range(x, board, 'flop', 0.66, 0.75),
     lambda x: old_call_range(x, board, 'flop', 0.66, 0.75)),
    ('check', lambda x: R._check_range(x, board, 'flop', 7.0, 0.75),
     lambda x: old_check_range(x, board, 'flop', 7.0, 0.75)),
]

for name, newf, oldf in transform_cases:
    want = oldf(base)
    got = newf(base)
    need(got == want, '%s legacy support/order changed' % name)

    wg = newf(wr)
    need(isinstance(wg, dict), '%s weighted transform flattened to list' % name)
    # Canonical weighted representation has one key per combo. Legacy _bet_range
    # can accidentally emit the same combo from both value and bluff slices; the
    # weighted support is therefore the first-occurrence de-duplication of that
    # legacy selection, while each surviving combo keeps its incoming mass.
    want_support = list(dict.fromkeys(want))
    need(list(wg) == want_support,
         '%s weighted support differs from canonicalized legacy selection' % name)
    need(all(same_float(wg[c], wr[c]) for c in wg),
         '%s changed surviving probability mass' % name)

# Sequential transform parity is checked on a no-duplicate path. Bet support is
# already checked above as a one-step canonicalization because legacy bet can
# contain duplicate value/bluff combos.
acts = [
    ('flop', 'call', 0.62),
    ('turn', 'check', 0.0),
    ('river', 'call', 0.55),
]
actor_read = {'w': 0.8, 'bluff_gap': 0.25, 'passive': -0.15, 'barrel_gap': 0.2}
want = old_narrow_by_actions(base, board, acts, actor_read)
got = R.narrow_by_actions(base, board, acts, actor_read)
need(got == want, 'narrow_by_actions legacy support/order changed')
wg = R.narrow_by_actions(wr, board, acts, actor_read)
need(list(wg) == want, 'weighted narrow_by_actions support changed')
need(all(same_float(wg[c], wr[c]) for c in wg),
     'narrow_by_actions changed surviving mass')

profile_full = {'concepts': {'range_read': 9.0}}
x = R.perceived_range(base, board, acts, profile_full, actor_read)
y = R.perceived_range(wr, board, acts, profile_full, actor_read)
need(list(y) == x, 'perceived_range full-read support mismatch')
need(all(same_float(y[c], wr[c]) for c in y),
     'perceived_range full-read changed mass')

profile_partial = {'concepts': {'range_read': 4.0}}
x = R.perceived_range(base, board, acts, profile_partial, actor_read)
y = R.perceived_range(wr, board, acts, profile_partial, actor_read)
need(list(y) == x, 'perceived_range partial support mismatch')
need(all(same_float(y[c], wr[c]) for c in y),
     'perceived_range partial changed mass')

x = R.perceived_facing_bet_response(
    base, board, 'flop', 0.7, profile_partial, raise_possible=True)
y = R.perceived_facing_bet_response(
    wr, board, 'flop', 0.7, profile_partial, raise_possible=True)
need(list(y) == x, 'facing-bet perceived support mismatch')
need(all(same_float(y[c], wr[c]) for c in y),
     'facing-bet perceived transform changed mass')

# ---------- W2: legacy aggregates unchanged ----------
hero = ['As', 'Ah']
agg_range = [c for c in base if not (set(c) & set(hero))]
PL._RS_CACHE.clear()
want = old_relative_strength(hero, board, agg_range)
got = PL.relative_strength(hero, board, agg_range)
need(same_float(got, want), 'relative_strength legacy value changed')

for cutoff in (2, 3):
    need(same_float(R._strong_share(agg_range, board, cutoff),
                    old_strong_share(agg_range, board, cutoff)),
         '_strong_share legacy value changed cutoff=%s' % cutoff)

need(same_float(R.blocker_score(hero, agg_range, board),
                old_blocker_score(hero, agg_range, board)),
     'blocker_score legacy value changed')
need(same_float(R.blocker_effect(hero, agg_range, board, 'flop', 0.7),
                old_blocker_effect(hero, agg_range, board, 'flop', 0.7)),
     'blocker_effect legacy value changed')

# Uniform weighted input must equal legacy count semantics exactly.
uniform = {c: 3.0 for c in agg_range}
PL._RS_CACHE.clear()
need(same_float(PL.relative_strength(hero, board, uniform), want),
     'relative_strength uniform-weight parity failed')
need(same_float(R._strong_share(uniform, board, 2),
                old_strong_share(agg_range, board, 2)),
     '_strong_share uniform-weight parity failed')
need(same_float(R.blocker_score(hero, uniform, board),
                old_blocker_score(hero, agg_range, board)),
     'blocker_score uniform-weight parity failed')
need(same_float(R.blocker_effect(hero, uniform, board, 'flop', 0.7),
                old_blocker_effect(hero, agg_range, board, 'flop', 0.7)),
     'blocker_effect uniform-weight parity failed')

# Posterior mass must matter. Weight combos that beat AA much more heavily.
stronger = [c for c in agg_range if bot.eval7(list(c)+board) > bot.eval7(hero+board)]
weaker = [c for c in agg_range if c not in set(stronger)]
need(bool(stronger) and bool(weaker), 'relative-strength direction fixture invalid')
mass_strong = {c: (40.0 if c in set(stronger) else 1.0) for c in agg_range}
mass_weak = {c: (1.0 if c in set(stronger) else 40.0) for c in agg_range}
PL._RS_CACHE.clear()
rs_strong = PL.relative_strength(hero, board, mass_strong)
rs_weak = PL.relative_strength(hero, board, mass_weak)
need(rs_strong < rs_weak,
     'relative_strength ignored posterior mass direction')

# Strong-share direction: heavily weight made >= pair+ versus weak support.
strong_set = {
    c for c in agg_range
    if bot.eval7(list(c)+board)[0] >= 2
}
weak_set = set(agg_range) - strong_set
need(bool(strong_set) and bool(weak_set), 'strong-share fixture invalid')
w_hi = {c: (30.0 if c in strong_set else 1.0) for c in agg_range}
w_lo = {c: (1.0 if c in strong_set else 30.0) for c in agg_range}
need(R._strong_share(w_hi, board, 2) > R._strong_share(w_lo, board, 2),
     '_strong_share ignored posterior mass direction')

# Blocker aggregate must react to mass while preserving support.
bs_support = sorted(
    agg_range,
    key=lambda c: bot.eval7(list(c)+board),
    reverse=True)[:max(4, len(agg_range)//5)]
blocked = {c for c in bs_support if c[0] in hero or c[1] in hero}
unblocked = set(bs_support) - blocked
if blocked and unblocked:
    b_hi = {c: (25.0 if c in blocked else 1.0) for c in agg_range}
    b_lo = {c: (1.0 if c in blocked else 25.0) for c in agg_range}
    need(R.blocker_score(hero, b_hi, board) > R.blocker_score(hero, b_lo, board),
         'blocker_score ignored posterior mass direction')

# joint_blocker_effect: uniform dict must preserve exact legacy RNG path.
opp2 = [
    c for c in R.preflop_range(
        'reg', 'CO', 'call', 40.0, dead,
        opener_pos='BTN', seats=9, ante=True)
    if not (set(c) & dead)
][:80]
if len(opp2) < 20:
    opp2 = list(reversed(agg_range[:80]))
legacy_opps = {2: agg_range[:70], 5: opp2[:70]}
uniform_opps = {s: {c: 1.0 for c in pool} for s, pool in legacy_opps.items()}
jb_legacy = R.joint_blocker_effect(
    hero, legacy_opps, board, 'flop', 0.7,
    n_opp=2, sims=800, seed=20260927)
jb_uniform = R.joint_blocker_effect(
    hero, uniform_opps, board, 'flop', 0.7,
    n_opp=2, sims=800, seed=20260927)
need(same_float(jb_legacy, jb_uniform),
     'joint_blocker_effect uniform weighted parity failed')

# ---------- runner.adjust_range_by_history ----------
class FakeDyn:
    def __init__(self, hands):
        self.hands = hands
    def shown(self, _pid):
        return list(self.hands)

# Strong shown hands -> narrowing. Existing masses must be untouched.
dyn_narrow = FakeDyn([['As','Ah'], ['Ks','Kh'], ['Qs','Qh']])
rn, note = RU.adjust_range_by_history(wr, dyn_narrow, 7, board, dead=hero)
need(isinstance(rn, dict), 'history narrow flattened weighted range')
need(bool(note), 'history narrow fixture produced no note')
need(all(c in wr and same_float(w, wr[c]) for c, w in rn.items()),
     'history narrow changed incoming mass')

# Weak shown hands -> expansion. Existing combos keep mass; any new support gets
# neutral mean mass.
weak_hands = [['7c','2d'], ['8c','3d'], ['9c','4d']]
dyn_wide = FakeDyn(weak_hands)
rw, note = RU.adjust_range_by_history(wr, dyn_wide, 7, board, dead=hero)
need(isinstance(rw, dict), 'history widen flattened weighted range')
need(bool(note), 'history widen fixture produced no note')
for c in set(rw) & set(wr):
    need(same_float(rw[c], wr[c]), 'history widen changed existing mass')
new = set(rw) - set(wr)
if new:
    mean = R.range_mean_mass(wr)
    need(all(same_float(rw[c], mean) for c in new),
         'history widen gave non-neutral mass to new support')

print({
    'checks': checks,
    'legacy_combos': len(base),
    'weighted_mass': round(R.range_mass(wr), 6),
    'relative_strength_mass_direction': [round(rs_strong, 6), round(rs_weak, 6)],
    'joint_blocker_uniform_parity': round(jb_legacy, 9),
    'history_new_support': len(new),
})
print('PASS W2/W3 weighted aggregate + transform wiring')
