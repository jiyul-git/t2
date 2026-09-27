#!/usr/bin/env python3
"""W1 weighted sampling consumers: exact legacy parity + weighted direction."""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bot
import ranges as R
import plan as PL


checks = 0


def need(cond, msg):
    global checks
    if not cond:
        raise AssertionError(msg)
    checks += 1


def uni(xs):
    return {c: 1.0 for c in xs}


hero = ['As', 'Ah']
board = ['2c', '7d', 'Jh']
p1 = sorted([
    ('Kc', 'Kd'), ('Qc', 'Qd'), ('Tc', 'Td'), ('9c', '9d'),
])
p2 = sorted([
    ('Ks', 'Kh'), ('Qs', 'Qh'), ('Ts', 'Th'), ('9s', '9h'),
])

# The uniform weighted path must consume exactly the same RNG sequence as
# rng.choice(sorted_legacy_pool).
a = random.Random(20260927)
b = random.Random(20260927)
seq_a = [a.choice(p1) for _ in range(100)]
seq_b = [bot._sample_pool_combo(b, uni(p1)) for _ in range(100)]
need(seq_a == seq_b, 'uniform weighted sampler changed combo sequence')
need(a.getstate() == b.getstate(), 'uniform weighted sampler changed RNG state')

# Core equity implementation.
x = bot.equity_vs_pools(hero, board, [p1, p2], sims=250, seed=101)
y = bot.equity_vs_pools(hero, board, [uni(p1), uni(p2)], sims=250, seed=101)
need(x == y, 'equity_vs_pools uniform weighted parity failed')

x = bot.equity_vs_combos(hero, board, [p1, p2], sims=250, seed=102)
y = bot.equity_vs_combos(hero, board, [uni(p1), uni(p2)], sims=250, seed=102)
need(x == y, 'equity_vs_combos uniform weighted parity failed')

# Heads-up range advantage.
myr = sorted([
    ('As', 'Ad'), ('Kc', 'Kd'), ('Qc', 'Qd'), ('Tc', 'Td'),
])
oppr = sorted([
    ('Js', 'Jc'), ('7c', '7h'), ('6c', '6d'), ('5c', '5d'),
])
x = R.range_advantage(myr, oppr, board, sims=250, seed=103)
y = R.range_advantage(uni(myr), uni(oppr), board, sims=250, seed=103)
need(x == y, 'range_advantage uniform weighted parity failed')

# Multiway field range advantage.
opps_legacy = {2: p1, 5: p2}
opps_weighted = {2: uni(p1), 5: uni(p2)}
x = R.joint_range_advantage(
    myr, opps_legacy, board, n_opp=2, sims=300, seed=104)
y = R.joint_range_advantage(
    uni(myr), opps_weighted, board, n_opp=2, sims=300, seed=104)
need(x == y, 'joint_range_advantage uniform weighted parity failed')

# Multiway relative strength.
x = PL.joint_relative_strength(
    hero, board, opps_legacy, n_opp=2, sims=300, seed=105)
y = PL.joint_relative_strength(
    hero, board, opps_weighted, n_opp=2, sims=300, seed=105)
need(x == y, 'joint_relative_strength uniform weighted parity failed')

# Current-board record-only equity.
union_legacy = sorted(set(p1 + p2))
union_weighted = uni(union_legacy)
x = PL._eq_current(
    hero, board, union_legacy, 2, sims=300, seed=106,
    opp_ranges=opps_legacy)
y = PL._eq_current(
    hero, board, union_weighted, 2, sims=300, seed=106,
    opp_ranges=opps_weighted)
need(x == y, '_eq_current uniform weighted parity failed')

# Non-uniform weights must actually change the sampling distribution.
strong = ('Jc', 'Jd')
weak = ('3c', '4c')
wr = {strong: 40.0, weak: 1.0}
rng = random.Random(107)
draws = [bot._sample_pool_combo(rng, wr) for _ in range(2000)]
strong_n = sum(1 for c in draws if c == strong)
need(strong_n > 1850, 'non-uniform sampler ignored mass')

# And a consumer must move in the expected direction: heavily weighting the
# opponent's set makes AA's current-board range advantage worse than weighting air.
hero_r = [('As', 'Ah')]
opp_strong = {strong: 40.0, weak: 1.0}
opp_weak = {strong: 1.0, weak: 40.0}
adv_strong = R.range_advantage(hero_r, opp_strong, board, sims=1200, seed=108)
adv_weak = R.range_advantage(hero_r, opp_weak, board, sims=1200, seed=108)
need(adv_strong < adv_weak,
     'weighted range advantage did not respond to probability mass')

print({
    'checks': checks,
    'equity_vs_pools': x,
    'strong_draws': strong_n,
    'adv_strong': round(adv_strong, 6),
    'adv_weak': round(adv_weak, 6),
    'legacy_rng_exact': True,
})
print('PASS W1 weighted sampling consumers')
