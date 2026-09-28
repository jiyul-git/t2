#!/usr/bin/env python3
"""Pre-registered, texture-stratified flop panel for the HU continuation prototype.

    python3 tools/gto_hu_continuation/make_panel.py data/gto_hu_continuation/panel_v1.json

Fixed BEFORE any panel result is seen (strata, allocation and seed are constants here):
- 22,100 flops enumerated, canonicalised under the 24 suit permutations (1,755 classes).
- 12 strata = suit/pair structure {monotone, paired (incl. trips), two-tone unpaired,
  rainbow unpaired} x top card {A, K-Q, J or lower}.
- Stratum probability = raw flops in stratum / 22,100 (no card removal from the ranges).
- PER_STRATUM canonical flops drawn per stratum with SEED, each weighted by its raw-flop
  count within the stratum draw; the stratified estimator weights strata by probability.
The draw is never revised after looking at values.
"""
import hashlib
import itertools
import json
import random
import sys

SEED = 20260928
PER_STRATUM = 2
RANKS = '23456789TJQKA'
SUITS = 'cdhs'


def canon(cards):
    best = None
    for perm in itertools.permutations(range(4)):
        c = tuple(sorted(((r, perm[s]) for r, s in cards), reverse=True))
        if best is None or c < best:
            best = c
    return best


def stratum(cards):
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


def main():
    deck = [(r, s) for r in range(13) for s in range(4)]
    classes = {}
    for f in itertools.combinations(deck, 3):
        k = canon(f)
        classes.setdefault(k, [0, stratum(f)])
        classes[k][0] += 1
    assert sum(v[0] for v in classes.values()) == 22100
    strata = {}
    for k, (n, st) in classes.items():
        strata.setdefault(st, []).append((k, n))
    rng = random.Random(SEED)
    panel = []
    summary = {}
    for st in sorted(strata):
        members = sorted(strata[st])
        raw = sum(n for _, n in members)
        # draw proportional to raw-flop count (each raw flop equally likely)
        picks = []
        pool = list(members)
        for _ in range(PER_STRATUM):
            tot = sum(n for _, n in pool)
            x = rng.uniform(0, tot)
            acc = 0
            for i, (k, n) in enumerate(pool):
                acc += n
                if x <= acc:
                    picks.append(pool.pop(i))
                    break
        summary[st] = {'canonical_flops': len(members), 'raw_flops': raw, 'probability': raw / 22100}
        for k, n in picks:
            panel.append({'board': fmt(k), 'stratum': st, 'raw_flops_of_class': n,
                          'weight': raw / 22100 / PER_STRATUM})
    text = json.dumps(panel, sort_keys=True).encode()
    out = {'schema': 'flop_panel_v1', 'seed': SEED, 'per_stratum': PER_STRATUM,
           'canonical_flop_classes': len(classes), 'strata': summary, 'panel': panel,
           'panel_hash_sha256': hashlib.sha256(text).hexdigest(),
           'estimator': 'stratified: sum_strata P(stratum) * mean(panel values in stratum); '
                        'draw within stratum proportional to raw-flop count',
           'caveat': 'flop probabilities ignore card removal by the players\' ranges'}
    json.dump(out, open(sys.argv[1], 'w'), indent=1)
    print(len(classes), 'canonical;', len(panel), 'panel flops; hash', out['panel_hash_sha256'][:16])
    for st, v in sorted(summary.items()):
        print('%-22s p=%.4f canon=%d  %s' % (st, v['probability'], v['canonical_flops'],
                                            [p['board'] for p in panel if p['stratum'] == st]))


if __name__ == '__main__':
    main()
