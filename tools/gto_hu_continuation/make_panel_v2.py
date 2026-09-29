#!/usr/bin/env python3
"""Nested 72-flop panel: panel_v1's 24 flops kept verbatim + 4 more draws per stratum.

    python3 tools/gto_hu_continuation/make_panel_v2.py data/gto_hu_continuation/panel_v1.json \
        data/gto_hu_continuation/panel_v2_72.json

Fixed BEFORE any value of the new flops is seen:
- Same 12 strata, same stratum probabilities, same estimator as panel_v1 (make_panel.py).
- Each stratum continues panel_v1's sequential draw: proportional to raw-flop count, without
  replacement, from the stratum's pool minus the flops already drawn. The 6 flops of a stratum
  are therefore distributed as a 6-draw sequence of panel_v1's own scheme; weight = P(s) / 6.
- Texture coverage (restricted randomisation, rule set before drawing): every category below
  must hold >= MIN_COVER flops of the 72. A draw that fails is rejected and the seed advances
  by one (SEED_EXT, SEED_EXT+1, ...); every rejected attempt is recorded in the manifest.
    texture:  monotone, paired, rainbow_dry, rainbow_connected, twotone_dry, twotone_connected
    rank:     unpaired top card A / K-Q / middle (J-8) / low (7-2);
              paired by pair rank high (A-T) / mid (9-6) / low (5-2)
  connected = the three flop ranks fit in a 5-rank window (a straight is possible with two
  hole cards; A also counts low), dry = otherwise. These labels are descriptive only: they do
  not enter the estimator. (J2 called Tc9d5h "rainbow connected" informally; under this rule it
  is rainbow_dry, span 6.)
"""
import hashlib
import json
import random
import sys
import itertools

sys.path.insert(0, __import__('os').path.dirname(__file__))
import make_panel as mp  # noqa: E402

SEED_EXT = 20260929
PER_STRATUM = 6
MIN_COVER = 3
MAX_ATTEMPTS = 50


def parse(board):
    return tuple((mp.RANKS.index(board[i]), 'cdhs'.index(board[i + 1])) for i in range(0, 6, 2))


def connected(ranks):
    hi = {r + 2 for r in ranks}
    lo = {1 if r == 12 else r + 2 for r in ranks}
    return max(hi) - min(hi) <= 4 or max(lo) - min(lo) <= 4


def tags(board):
    cards = parse(board)
    ranks = sorted((r for r, _ in cards), reverse=True)
    ns = len({s for _, s in cards})
    paired = len(set(ranks)) < 3
    if ns == 1:
        tex = 'monotone'
    elif paired:
        tex = 'paired'
    else:
        tex = ('twotone' if ns == 2 else 'rainbow') + ('_connected' if connected(ranks) else '_dry')
    if paired:
        pr = [r for r in ranks if ranks.count(r) >= 2][0]
        rank = 'paired_high' if pr >= 8 else ('paired_mid' if pr >= 4 else 'paired_low')
    else:
        top = ranks[0]
        rank = 'A_high' if top == 12 else ('KQ_high' if top >= 10 else ('middle' if top >= 6 else 'low'))
    return {'texture': tex, 'rank_bucket': rank, 'straight_possible': None if paired else connected(ranks)}


CATS = {'texture': ['monotone', 'paired', 'rainbow_dry', 'rainbow_connected', 'twotone_dry', 'twotone_connected'],
        'rank_bucket': ['A_high', 'KQ_high', 'middle', 'low', 'paired_high', 'paired_mid', 'paired_low']}


def coverage(boards):
    out = {}
    for dim, cats in CATS.items():
        out[dim] = {c: sum(1 for b in boards if tags(b)[dim] == c) for c in cats}
    return out


def main():
    v1 = json.load(open(sys.argv[1]))
    deck = [(r, s) for r in range(13) for s in range(4)]
    classes = {}
    for f in itertools.combinations(deck, 3):
        k = mp.canon(f)
        classes.setdefault(k, [0, mp.stratum(f)])
        classes[k][0] += 1
    strata = {}
    for k, (n, st) in classes.items():
        strata.setdefault(st, []).append((k, n))
    old = {}
    for f in v1['panel']:
        old.setdefault(f['stratum'], []).append(f['board'])
    rejected = []
    for attempt in range(MAX_ATTEMPTS):
        seed = SEED_EXT + attempt
        rng = random.Random(seed)
        panel = []
        for st in sorted(strata):
            members = sorted(strata[st])
            raw = sum(n for _, n in members)
            assert abs(raw / 22100 - v1['strata'][st]['probability']) < 1e-15
            pool = [(k, n) for k, n in members if mp.fmt(k) not in old[st]]
            assert len(pool) == len(members) - len(old[st])
            for b in old[st]:
                n = next(n for k, n in members if mp.fmt(k) == b)
                panel.append({'board': b, 'stratum': st, 'raw_flops_of_class': n, 'weight': raw / 22100 / PER_STRATUM,
                              'origin': 'panel_v1', **tags(b)})
            for _ in range(PER_STRATUM - len(old[st])):
                tot = sum(n for _, n in pool)
                x = rng.uniform(0, tot)
                acc = 0
                for i, (k, n) in enumerate(pool):
                    acc += n
                    if x <= acc:
                        k, n = pool.pop(i)
                        b = mp.fmt(k)
                        panel.append({'board': b, 'stratum': st, 'raw_flops_of_class': n,
                                      'weight': raw / 22100 / PER_STRATUM, 'origin': f'extension_seed_{seed}', **tags(b)})
                        break
        cov = coverage([p['board'] for p in panel])
        short = {f'{d}:{c}': n for d, cs in cov.items() for c, n in cs.items() if n < MIN_COVER}
        if not short:
            break
        rejected.append({'seed': seed, 'shortfall': short})
    else:
        raise SystemExit('no accepted draw')
    assert len(panel) == 72 and len({p['board'] for p in panel}) == 72
    assert sum(1 for p in panel if p['origin'] == 'panel_v1') == 24
    text = json.dumps(panel, sort_keys=True).encode()
    out = {'schema': 'flop_panel_v2_nested', 'parent_panel': {'file': 'panel_v1.json', 'panel_hash_sha256': v1['panel_hash_sha256'],
                                                           'seed': v1['seed']},
           'seed_extension_accepted': seed, 'seed_extension_rejected': rejected, 'per_stratum': PER_STRATUM,
           'coverage_rule': f'>= {MIN_COVER} flops per texture and rank category (restricted randomisation)',
           'coverage': cov, 'canonical_flop_classes': len(classes), 'strata': v1['strata'], 'panel': panel,
           'panel_hash_sha256': hashlib.sha256(text).hexdigest(),
           'estimator': v1['estimator'], 'caveat': v1['caveat'],
           'tag_definitions': __doc__.split('Texture coverage')[1].strip()}
    json.dump(out, open(sys.argv[2], 'w'), indent=1)
    print('accepted seed', seed, 'rejected', rejected, 'hash', out['panel_hash_sha256'][:16])
    for d, cs in cov.items():
        print(d, cs)
    for st in sorted(strata):
        print('%-20s %s' % (st, ' '.join(p['board'] + ('*' if p['origin'] == 'panel_v1' else '') for p in panel if p['stratum'] == st)))


if __name__ == '__main__':
    main()
