#!/usr/bin/env python3
"""Verify semantic split of turn/river checkraise skill with legacy identity."""

import json
import pathlib
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
    }


def main():
    checks = {}

    mapping = {
        'flop': PS.street_concept('checkraise', 'flop'),
        'turn': PS.street_concept('checkraise', 'turn'),
        'river': PS.street_concept('checkraise', 'river'),
    }
    checks['street_mapping'] = {
        'pass': mapping == {
            'flop': 'checkraise_flop',
            'turn': 'checkraise_turn',
            'river': 'checkraise_river',
        },
        'mapping': mapping,
    }

    # Existing generated profiles only contain checkraise_late. New semantic
    # names must therefore reproduce the exact legacy value through fallback.
    legacy = prof(checkraise_late=4.7)
    legacy_turn = PS.sk(legacy, 'checkraise_turn')
    legacy_river = PS.sk(legacy, 'checkraise_river')
    checks['legacy_fallback_identity'] = {
        'pass': legacy_turn == 4.7 and legacy_river == 4.7,
        'turn': legacy_turn,
        'river': legacy_river,
    }

    # An explicit street value overrides the compatibility fallback and must
    # not leak into the other street.
    split = prof(checkraise_late=4.7, checkraise_turn=1.2, checkraise_river=8.6)
    turn = PS.sk(split, PS.street_concept('checkraise', 'turn'))
    river = PS.sk(split, PS.street_concept('checkraise', 'river'))
    flop = PS.sk(split, PS.street_concept('checkraise', 'flop'))
    checks['independent_override'] = {
        'pass': turn == 1.2 and river == 8.6 and flop == 5.0,
        'flop': flop, 'turn': turn, 'river': river,
    }

    # Runtime supplier used by checkraise_decision must consume the separated
    # street concept, not the old shared name directly.
    turn_supply = PL.checkraise_street_skill(split, 'turn')
    river_supply = PL.checkraise_street_skill(split, 'river')
    legacy_turn_supply = PL.checkraise_street_skill(legacy, 'turn')
    legacy_river_supply = PL.checkraise_street_skill(legacy, 'river')
    checks['runtime_supplier_split'] = {
        'pass': (
            turn_supply == 1.2/3.33
            and river_supply == 8.6/3.33
            and legacy_turn_supply == 4.7/3.33
            and legacy_river_supply == 4.7/3.33
        ),
        'split_turn': turn_supply,
        'split_river': river_supply,
        'legacy_turn': legacy_turn_supply,
        'legacy_river': legacy_river_supply,
    }

    # Existing population generation must not invent new priors yet.
    import random
    rr = random.Random(20261005)
    generated = [PS.make_player(rr, 0.78, pid=i) for i in range(100)]
    no_new_prior = all(
        'checkraise_turn' not in p['concepts']
        and 'checkraise_river' not in p['concepts']
        and 'checkraise_late' in p['concepts']
        for p in generated
    )
    checks['no_new_prior'] = {
        'pass': no_new_prior,
        'sample_n': len(generated),
    }

    passed = all(x['pass'] for x in checks.values())
    print(json.dumps({'pass': passed, 'checks': checks}, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
