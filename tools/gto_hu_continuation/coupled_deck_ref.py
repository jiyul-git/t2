#!/usr/bin/env python3
"""Independent re-implementation of the preflop multiway payoff `coupled_deck_v1`
(vendor/gtopen/crates/solver/src/preflop/multiway.rs), for diagnostics only.

Reproduces, from the published algorithm and without calling the Rust code:
- the particle table: SAMPLES shuffled decks (SplitMix-style RNG seeded by
  PREFLOP_MULTIWAY_SEED), one sampled combo per class that removes only its own cards,
  board = the first five remaining deck cards, 7-card strength per class;
- per particle the ascending strength order with strict / inclusive CDF indices;
- equity(h) = mean over particles of sum_k w_k prod_opp (less + t_k * equal), the
  Gauss-Legendre rule chosen by the number of opponents.
The 7-card evaluator here is written from the rules of poker; only the ordering and ties
of hands matter, so any correct evaluator reproduces the table.

    python3 tools/gto_hu_continuation/coupled_deck_ref.py <terminal_export.json> [seed]
"""
import itertools
import json
import sys

SAMPLES = 1024
MASK = (1 << 64) - 1
QUAD = {1: ([0.5], [1.0]),
        2: ([0.211324865405187, 0.788675134594813], [0.5, 0.5]),
        3: ([0.112701665379258, 0.5, 0.887298334620742], [0.277777777777778, 0.444444444444444, 0.277777777777778])}


class Rng:
    def __init__(self, seed):
        self.s = seed & MASK

    def next(self):
        self.s = (self.s + 0x9e3779b97f4a7c15) & MASK
        z = self.s
        z = ((z ^ (z >> 30)) * 0xbf58476d1ce4e5b9) & MASK
        z = ((z ^ (z >> 27)) * 0x94d049bb133111eb) & MASK
        return z ^ (z >> 31)


def class_index(a, b, suited):
    hi, lo = (a, b) if a >= b else (b, a)
    if hi == lo:
        return hi * 13 + hi
    return hi * 13 + lo if suited else lo * 13 + hi


def strength(cards):
    """Comparable strength of the best 5-card hand in 7 cards (card = rank*4 + suit)."""
    ranks = sorted((c // 4 for c in cards), reverse=True)
    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    suits = {}
    for c in cards:
        suits.setdefault(c % 4, []).append(c // 4)

    def straight_top(rs):
        u = sorted(set(rs), reverse=True)
        if 12 in u:
            u.append(-1)  # wheel: ace plays low
        run = 1
        for i in range(1, len(u)):
            run = run + 1 if u[i] == u[i - 1] - 1 else 1
            if run >= 5:
                return u[i] + 4
        return None

    flush = next((sorted(v, reverse=True) for v in suits.values() if len(v) >= 5), None)
    if flush:
        sf = straight_top(flush)
        if sf is not None:
            return (8, sf)
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    if groups[0][1] == 4:
        quad = groups[0][0]
        return (7, quad, max(r for r in ranks if r != quad))
    trips = [r for r, n in groups if n == 3]
    pairs = [r for r, n in groups if n == 2]
    if trips and (len(trips) > 1 or pairs):
        t = trips[0]
        p = max([x for x in trips[1:]] + pairs)
        return (6, t, p)
    if flush:
        return (5,) + tuple(flush[:5])
    st = straight_top(ranks)
    if st is not None:
        return (4, st)
    if trips:
        t = trips[0]
        return (3, t) + tuple([r for r in ranks if r != t][:2])
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return (2, p1, p2, max(r for r in ranks if r not in (p1, p2)))
    if pairs:
        p = pairs[0]
        return (1, p) + tuple([r for r in ranks if r != p][:3])
    return (0,) + tuple(ranks[:5])


def build(seed):
    combos = [[] for _ in range(169)]
    for a in range(52):
        for b in range(a + 1, 52):
            combos[class_index(a // 4, b // 4, a % 4 == b % 4)].append((a, b))
    rng = Rng(seed)
    order, lower, upper = [], [], []
    for _ in range(SAMPLES):
        deck = list(range(52))
        for i in range(51, 0, -1):
            j = rng.next() % (i + 1)
            deck[i], deck[j] = deck[j], deck[i]
        st = []
        for h in range(169):
            c = combos[h][rng.next() % len(combos[h])]
            board = [x for x in deck if x != c[0] and x != c[1]][:5]
            st.append(strength(list(c) + board))
        o = sorted(range(169), key=lambda h: (st[h], h))
        lo_, hi_ = [0] * 169, [0] * 169
        lo = 0
        while lo < 169:
            hi = lo + 1
            while hi < 169 and st[o[hi]] == st[o[lo]]:
                hi += 1
            for h in o[lo:hi]:
                lo_[h], hi_[h] = lo, hi
            lo = hi
        order.append(o)
        lower.append(lo_)
        upper.append(hi_)
    return order, lower, upper


def equities(table, opponents):
    order, lower, upper = table
    t, w = QUAD[len(opponents)]
    sums = [0.0] * 169
    for s in range(SAMPLES):
        cdfs = []
        for dist in opponents:
            c = [0.0]
            for i in range(169):
                c.append(c[-1] + dist[order[s][i]])
            cdfs.append(c)
        for h in range(169):
            lo, hi = lower[s][h], upper[s][h]
            vals = [1.0] * len(t)
            for c in cdfs:
                less = c[lo]
                equal = c[hi] - less
                for k in range(len(t)):
                    vals[k] *= less + t[k] * equal
            acc = -0.0
            for v, ww in zip(vals, w):
                acc += v * ww
            sums[h] += acc
    return [x / SAMPLES for x in sums]


def main():
    term = json.load(open(sys.argv[1]))
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 202
    table = build(seed)
    out = {}
    for pl in term['players']:
        opp = [q['class_reach_normalized'] for q in term['players'] if q['seat'] != pl['seat']]
        eq = equities(table, opp)
        g = [term['pot_bb'] * e for e in eq]
        d64 = max(abs(a - b) for a, b in zip(g, pl['coupled_deck_gross_f64']))
        d32 = max(abs(a - b) for a, b in zip(g, pl['legacy_gross']))
        out[pl['position']] = {'max_abs_diff_vs_rust_f64': d64, 'max_abs_diff_vs_terminal_value_f32': d32,
                               'bit_identical_f64': g == pl['coupled_deck_gross_f64']}
        print(pl['position'], out[pl['position']])
    return out


if __name__ == '__main__':
    main()
