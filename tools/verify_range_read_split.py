#!/usr/bin/env python3
"""Verify phase-1 semantic split of range_read into three roles.

  range_reconstruction — narrowing the opponent range from actions
                         (ranges.perceived_range / perceived_facing_bet_response /
                          perceived_continue_range)
  line_interpretation  — interpreting lines / tendencies / bluff threat
                         (persona bias 'bluff_fear', read_opponent see_line,
                          reads.obs_from_profile observation skill)
  read_application     — applying evidence to one's own decision
                         (preflop multiway evidence capacity,
                          money_pressure actor capacity)

Generated profiles have none of the three keys and fall back to range_read
(behavior identical).  Each explicit override must move only its own role.
"""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS
import ranges as RG
import reads as RD
import money_pressure as MP

ROLES = ('range_reconstruction', 'line_interpretation', 'read_application')


def prof(**concepts):
    c = {k: 5.0 for k in PS.ALL_CONCEPTS}
    c.update(concepts)
    t = {k: 5.0 for k in PS.TEMPER}
    return {
        'id': None, 'concepts': c, 'temper': t,
        'latent': {'study': 5.0, 'aggro': 5.0, 'exp': 5.0}, 'type': 'X',
        'aggr': 5.0, 'bluff': 5.0, 'tight': 5.0, 'gamble': 5.0, 'icm': 5.0,
        'tilt': 0.0, 'tricky': 5.0, 'value': 'mixed',
    }


BASE = RG.preflop_range('TAG', 'CO', 'open', 40.0, set())
BOARD = ['Ks', '9d', '4c']


def recon(p):
    r = RG.perceived_continue_range(BASE, BOARD, 'flop', 0.66, p)
    return RG.range_signature(r)


def interp(p):
    return (round(PS.bias(p, 'bluff_fear', 'river'), 9),
            round(RD.obs_from_profile(p)['skill'], 9))


def appl(p):
    return MP.actor_from_profile(p, PS.sk, PS.temper)['range_read']


def main():
    checks = {}
    legacy = prof(range_read=6.0)
    twin = prof(range_read=6.0, range_reconstruction=6.0, line_interpretation=6.0,
                read_application=6.0)
    checks['legacy_fallback_identity'] = {
        'pass': (all(PS.sk(legacy, r) == 6.0 for r in ROLES)
                 and recon(legacy) == recon(twin) and interp(legacy) == interp(twin)
                 and appl(legacy) == appl(twin)),
    }
    moved = {}
    for role in ROLES:
        p = prof(range_read=6.0, **{role: 1.0 if role != 'read_application' else 9.5})
        moved[role] = {
            'reconstruction': recon(p) != recon(legacy),
            'interpretation': interp(p) != interp(legacy),
            'application': appl(p) != appl(legacy),
        }
    expect = {
        'range_reconstruction': {'reconstruction': True, 'interpretation': False, 'application': False},
        'line_interpretation': {'reconstruction': False, 'interpretation': True, 'application': False},
        'read_application': {'reconstruction': False, 'interpretation': False, 'application': True},
    }
    checks['override_moves_only_own_role'] = {'pass': moved == expect, 'moved': moved}
    rr = random.Random(20261005)
    generated = [PS.make_player(rr, 0.78, pid=i) for i in range(100)]
    checks['no_new_prior'] = {
        'pass': all(not any(r in p['concepts'] for r in ROLES) and 'range_read' in p['concepts']
                    for p in generated),
        'sample_n': len(generated),
    }
    passed = all(x['pass'] for x in checks.values())
    print(json.dumps({'pass': passed, 'checks': checks}, indent=2, sort_keys=True, default=str))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
