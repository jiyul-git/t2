#!/usr/bin/env python3
"""Verify semantic split of flop thin value (thin_value_flop) with legacy identity.

Phase 1: the meaning `thin_value_flop` is separated from the legacy proxy
`range_merge`.  Generated profiles have no `thin_value_flop` key, so every
consumer falls back to `range_merge` (behavior identical).  An explicit
`thin_value_flop` is consumed independently on the flop only.
"""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS
import plan as PL


def prof(**concepts):
    c = {k: 5.0 for k in PS.ALL_CONCEPTS}
    c.update(concepts)
    t = {k: 5.0 for k in PS.TEMPER}
    return {
        'id': None,
        'concepts': c,
        'temper': t,
        'latent': {'study': 5.0, 'aggro': 5.0, 'exp': 5.0},
        'type': 'X',
        'aggr': 5.0, 'bluff': 5.0, 'tight': 5.0, 'gamble': 5.0, 'icm': 5.0,
        'tilt': 0.0, 'tricky': 5.0, 'value': 'mixed',
    }


def p2(profile, street):
    return PL.middle_value_two_street_probability(
        profile, street, 0.62, 0.30, 0.20, 0.40, 5.0, 2, 0)


SPOTS = [
    (['Ah', 'Td'], ['Ts', '7c', '2d']),
    (['Kc', 'Qh'], ['Qs', '9d', '4c']),
    (['9h', '9c'], ['Jd', '6s', '3h']),
    (['As', '5s'], ['5d', 'Kc', '8h']),
    (['Jh', 'Tc'], ['Td', '8s', '2c']),
    (['8d', '8c'], ['Ks', '7h', '3d']),
]


def plans(profile, street, seeds=40):
    out = []
    for hero, flop in SPOTS:
        board = list(flop)
        if street == 'turn':
            board = board + ['2h']
        for s in range(seeds):
            st = PL.make_plan(hero, board, None, None, profile, 600, 9000, street,
                              seed=1000 + s)
            out.append(st.get('plan'))
    return out


def main():
    checks = {}

    mapping = {st: PS.street_concept('thin_value', st) for st in ('flop', 'turn', 'river')}
    checks['street_mapping'] = {
        'pass': mapping == {'flop': 'thin_value_flop', 'turn': 'thin_value_turn',
                            'river': 'thin_value_river'},
        'mapping': mapping,
    }

    legacy = prof(range_merge=6.3, thin_value_turn=4.1, thin_value_river=2.2)
    checks['legacy_fallback_identity'] = {
        'pass': (PS.sk(legacy, 'thin_value_flop') == 6.3
                 and PS.sk(legacy, PS.street_concept('thin_value', 'turn')) == 4.1
                 and PS.sk(legacy, PS.street_concept('thin_value', 'river')) == 2.2),
        'flop': PS.sk(legacy, 'thin_value_flop'),
    }

    split = prof(range_merge=6.3, thin_value_flop=1.2)
    checks['independent_override'] = {
        'pass': (PS.sk(split, 'thin_value_flop') == 1.2
                 and PS.sk(split, 'range_merge') == 6.3),
    }

    # Live consumer 1: middle-value two-street probability (flop uses thin_value_flop).
    same = prof(range_merge=6.3)
    twin = prof(range_merge=6.3, thin_value_flop=6.3)
    lo = prof(range_merge=6.3, thin_value_flop=0.5)
    checks['p2_consumer'] = {
        'pass': (p2(same, 'flop') == p2(twin, 'flop')
                 and p2(lo, 'flop') != p2(same, 'flop')
                 and p2(lo, 'turn') == p2(same, 'turn')),
        'flop_legacy': p2(same, 'flop'), 'flop_low': p2(lo, 'flop'),
    }

    # Live consumer 2: plan creation for medium strength (make_plan).
    #  - explicit thin_value_flop equal to range_merge: identical plans
    #  - extreme thin_value_flop changes flop plans, never turn plans
    base_f, twin_f = plans(same, 'flop'), plans(twin, 'flop')
    hi = prof(range_merge=6.3, thin_value_flop=10.0)
    zero = prof(range_merge=6.3, thin_value_flop=0.0)
    hi_f, zero_f = plans(hi, 'flop'), plans(zero, 'flop')
    base_t, hi_t = plans(same, 'turn'), plans(hi, 'turn')
    checks['make_plan_consumer'] = {
        'pass': (base_f == twin_f and hi_f != zero_f and base_t == hi_t),
        'flop_value2_hi': hi_f.count('value_2street'),
        'flop_value2_zero': zero_f.count('value_2street'),
        'n': len(base_f),
    }

    rr = random.Random(20261005)
    generated = [PS.make_player(rr, 0.78, pid=i) for i in range(100)]
    checks['no_new_prior'] = {
        'pass': all('thin_value_flop' not in p['concepts'] and 'range_merge' in p['concepts']
                    for p in generated),
        'sample_n': len(generated),
    }

    passed = all(x['pass'] for x in checks.values())
    print(json.dumps({'pass': passed, 'checks': checks}, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
