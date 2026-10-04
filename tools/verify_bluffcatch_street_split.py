#!/usr/bin/env python3
"""Verify semantic split of flop/turn bluffcatch skill with legacy identity."""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS


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
    }


def main():
    checks = {}

    mapping = {
        'flop': PS.street_concept('bluffcatch', 'flop'),
        'turn': PS.street_concept('bluffcatch', 'turn'),
        'river': PS.street_concept('bluffcatch', 'river'),
    }
    checks['street_mapping'] = {
        'pass': mapping == {
            'flop': 'bluffcatch_flop',
            'turn': 'bluffcatch_turn',
            'river': 'bluffcatch_river',
        },
        'mapping': mapping,
    }

    legacy = prof(bluffcatch_early=4.4, bluffcatch_river=3.1)
    checks['legacy_fallback_identity'] = {
        'pass': (
            PS.sk(legacy, 'bluffcatch_flop') == 4.4
            and PS.sk(legacy, 'bluffcatch_turn') == 4.4
            and PS.sk(legacy, 'bluffcatch_river') == 3.1
        ),
        'flop': PS.sk(legacy, 'bluffcatch_flop'),
        'turn': PS.sk(legacy, 'bluffcatch_turn'),
        'river': PS.sk(legacy, 'bluffcatch_river'),
    }

    split = prof(
        bluffcatch_early=4.4,
        bluffcatch_flop=1.5,
        bluffcatch_turn=7.2,
        bluffcatch_river=8.8,
    )
    vals = {
        st: PS.sk(split, PS.street_concept('bluffcatch', st))
        for st in ('flop', 'turn', 'river')
    }
    checks['independent_override'] = {
        'pass': vals == {'flop': 1.5, 'turn': 7.2, 'river': 8.8},
        'values': vals,
    }

    # bias() is the live bluffcatch consumer. Same state except street-specific
    # skill must change only the matching street's bluff-fear / hero-call input.
    split['temper']['aggression'] = 5.0
    b_flop = PS.bias(split, 'bluff_fear', 'flop')
    b_turn = PS.bias(split, 'bluff_fear', 'turn')
    b_river = PS.bias(split, 'bluff_fear', 'river')
    checks['live_bias_consumer'] = {
        'pass': len({round(b_flop, 6), round(b_turn, 6), round(b_river, 6)}) == 3,
        'flop': b_flop, 'turn': b_turn, 'river': b_river,
    }

    rr = random.Random(20261005)
    generated = [PS.make_player(rr, 0.78, pid=i) for i in range(100)]
    checks['no_new_prior'] = {
        'pass': all(
            'bluffcatch_flop' not in p['concepts']
            and 'bluffcatch_turn' not in p['concepts']
            and 'bluffcatch_early' in p['concepts']
            for p in generated
        ),
        'sample_n': len(generated),
    }

    passed = all(x['pass'] for x in checks.values())
    print(json.dumps({'pass': passed, 'checks': checks}, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
