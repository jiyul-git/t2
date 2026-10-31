#!/usr/bin/env python3
"""Precision panels A and B (standard draft docs/GTO_PRECISION_PRIORITY_20261030.md section 3): two independent 72-flop panels.

    python3 tools/gto_precision/make_precision_panels.py <calc_root>/data/gto_hu_continuation/panel_v1.json data/gto_precision/panels

Fixed BEFORE any value is seen (constants below, never revised after looking at results):
- Same 12 strata (suit/pair structure x top card), same stratum probabilities and the same estimator as panel_v1 (make_panel.py):
  stratified mean, stratum weight P(s) = raw flops / 22,100, each board of a stratum weight P(s) / 6.
- Per stratum: the pool = all canonical flops of the stratum MINUS the 2 panel_v1 boards (so A and B are independent of the 24-board
  quick panel). Panel A = 6 sequential draws proportional to raw-flop count, without replacement, rng = Random(SEED_A).
  Panel B = 6 more draws the same way from the pool minus A, rng = Random(SEED_B). A, B and panel_v1 are pairwise disjoint.
- No restricted randomisation (no coverage rule, no re-draw): the first draw is the panel.
- A union B (144 boards, 12 per stratum, weight P(s) / 12) is written as a third file for the D <= U(144) criterion; it is NOT
  panel_v3_144 (which nests panel_v1).
Every session uses these files as committed (sha256 in MANIFEST.json); never regenerate with other seeds.
"""
import hashlib
import itertools
import json
import os
import random
import sys

SEED_A = 20261031
SEED_B = 20261131
PER_STRATUM = 6
RANKS = '23456789TJQKA'
SUITS = 'cdhs'


def canon(cards):
    best = None
    for perm in itertools.permutations(range(4)):
        c = tuple(sorted(((r, perm[s]) for r, s in cards), reverse=True))
        if best is None or c < best:
            best = c
    return best


def stratum(cards):   # identical to tools/gto_hu_continuation/make_panel.py
    ranks = sorted((r for r, _ in cards), reverse=True)
    suits = [s for _, s in cards]
    paired = len(set(ranks)) < 3
    ns = len(set(suits))
    if ns == 1:
        struct = 'monotone'
    elif paired:
        struct = 'paired'
    elif ns == 2:
        struct = 'twotone'
    else:
        struct = 'rainbow'
    top = ranks[0]
    high = 'A' if top == 12 else ('KQ' if top >= 10 else 'J_or_lower')
    return f'{struct}/{high}'


def fmt(c):
    return ''.join(RANKS[r] + SUITS[s] for r, s in sorted(c, reverse=True))


def draw(rng, pool, n):
    out = []
    for _ in range(n):
        tot = sum(m for _, m in pool)
        x = rng.uniform(0, tot)
        acc = 0
        for i, (k, m) in enumerate(pool):
            acc += m
            if x <= acc:
                out.append(pool.pop(i))
                break
    return out


def write(path, schema, seed, per, panel, strata, extra):
    text = json.dumps(panel, sort_keys=True).encode()
    out = {'schema': schema, 'seed': seed, 'per_stratum': per, 'canonical_flop_classes': 1755, 'strata': strata, 'panel': panel,
           'panel_hash_sha256': hashlib.sha256(text).hexdigest(),
           'estimator': 'stratified: sum_strata P(stratum) * mean(panel values in stratum); draw within stratum proportional to raw-flop count',
           'caveat': "flop probabilities ignore card removal by the players' ranges", **extra}
    json.dump(out, open(path, 'w'), indent=1)
    return out['panel_hash_sha256']


def main():
    v1 = json.load(open(sys.argv[1]))
    od = sys.argv[2]
    os.makedirs(od, exist_ok=True)
    deck = [(r, s) for r in range(13) for s in range(4)]
    classes = {}
    for f in itertools.combinations(deck, 3):
        k = canon(f)
        classes.setdefault(k, [0, stratum(f)])
        classes[k][0] += 1
    assert len(classes) == 1755 and sum(v[0] for v in classes.values()) == 22100
    strata = {}
    for k, (n, st) in classes.items():
        strata.setdefault(st, []).append((k, n))
    old = {}
    for f in v1['panel']:
        old.setdefault(f['stratum'], set()).add(f['board'])
    rng_a, rng_b = random.Random(SEED_A), random.Random(SEED_B)
    pa, pb = [], []
    for st in sorted(strata):
        members = sorted(strata[st])
        raw = sum(n for _, n in members)
        assert abs(raw / 22100 - v1['strata'][st]['probability']) < 1e-15
        pool = [(k, n) for k, n in members if fmt(k) not in old[st]]
        assert len(pool) == len(members) - len(old[st]) == len(members) - 2
        for k, n in draw(rng_a, pool, PER_STRATUM):
            pa.append({'board': fmt(k), 'stratum': st, 'raw_flops_of_class': n, 'weight': raw / 22100 / PER_STRATUM, 'origin': f'precision_A_seed_{SEED_A}'})
        for k, n in draw(rng_b, pool, PER_STRATUM):   # pool no longer holds A's boards
            pb.append({'board': fmt(k), 'stratum': st, 'raw_flops_of_class': n, 'weight': raw / 22100 / PER_STRATUM, 'origin': f'precision_B_seed_{SEED_B}'})
    ba, bb, b1 = {p['board'] for p in pa}, {p['board'] for p in pb}, {f['board'] for f in v1['panel']}
    assert len(ba) == len(bb) == 72 and not (ba & bb) and not (ba & b1) and not (bb & b1)
    extra = {'excluded_panel': {'file': 'panel_v1.json', 'panel_hash_sha256': v1['panel_hash_sha256']},
             'standard': 'docs/GTO_PRECISION_PRIORITY_20261030.md section 3 (precision draft); generator tools/gto_precision/make_precision_panels.py'}
    ha = write(os.path.join(od, 'panel_prec_A72.json'), 'flop_panel_precision_A', SEED_A, PER_STRATUM, pa, v1['strata'], extra)
    hb = write(os.path.join(od, 'panel_prec_B72.json'), 'flop_panel_precision_B', SEED_B, PER_STRATUM, pb, v1['strata'], extra)
    pab = [{**p, 'weight': p['weight'] / 2} for p in pa + pb]
    hab = write(os.path.join(od, 'panel_prec_AB144.json'), 'flop_panel_precision_A_union_B', [SEED_A, SEED_B], 2 * PER_STRATUM, pab, v1['strata'],
                {**extra, 'note': 'union of panel_prec_A72 and panel_prec_B72 (estimator only; flops are solved per panel A / B)'})
    man = {'seed_A': SEED_A, 'seed_B': SEED_B, 'per_stratum': PER_STRATUM,
           'files': {'panel_prec_A72.json': ha, 'panel_prec_B72.json': hb, 'panel_prec_AB144.json': hab},
           'excluded_panel_v1_sha256': v1['panel_hash_sha256'],
           'file_sha256': {f: hashlib.sha256(open(os.path.join(od, f), 'rb').read()).hexdigest() for f in ('panel_prec_A72.json', 'panel_prec_B72.json', 'panel_prec_AB144.json')}}
    json.dump(man, open(os.path.join(od, 'MANIFEST.json'), 'w'), indent=1)
    print(json.dumps(man, indent=1))
    for st in sorted(strata):
        print('%-22s A %s | B %s' % (st, [p['board'] for p in pa if p['stratum'] == st], [p['board'] for p in pb if p['stratum'] == st]))


if __name__ == '__main__':
    main()
