#!/usr/bin/env python3
"""Verify semantic split of preflop 3-bet skill (pf_threebet) with legacy identity.

Phase 1: traits_of()['threebet'] reads `pf_threebet`; generated profiles have no
such key and fall back to `pf_defend` (behavior identical).  The defend-chart
memory used by defend_thresholds (3-bet + call widths of one chart) stays on
`pf_defend` in phase 1.
"""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS
import preflop as PF


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


def tb(p):
    return PS.traits_of(p)['threebet']


def reshove(p):
    return PF.reshove_range(p, 'BB', 'CO', 18.0, 2.2)


def defend(p):
    return PF.defend_thresholds(p, 'BB', 'CO', 40.0)


def main():
    checks = {}
    legacy = prof(pf_defend=6.4)
    twin = prof(pf_defend=6.4, pf_threebet=6.4)
    hi = prof(pf_defend=6.4, pf_threebet=9.5)
    checks['legacy_fallback_identity'] = {
        'pass': (PS.sk(legacy, 'pf_threebet') == 6.4 and tb(legacy) == tb(twin)
                 and reshove(legacy) == reshove(twin)),
        'threebet': tb(legacy),
    }
    checks['independent_override'] = {
        'pass': tb(hi) > tb(legacy) and reshove(hi) > reshove(legacy),
        'threebet_hi': tb(hi), 'reshove_legacy': reshove(legacy), 'reshove_hi': reshove(hi),
    }
    checks['defend_chart_memory_unchanged'] = {
        'pass': defend(hi) == defend(legacy),
        'note': 'defend_thresholds keeps pf_defend in phase 1',
    }
    rr = random.Random(20261005)
    generated = [PS.make_player(rr, 0.78, pid=i) for i in range(100)]
    checks['no_new_prior'] = {
        'pass': all('pf_threebet' not in p['concepts'] and 'pf_defend' in p['concepts']
                    for p in generated),
        'sample_n': len(generated),
    }
    passed = all(x['pass'] for x in checks.values())
    print(json.dumps({'pass': passed, 'checks': checks}, indent=2, sort_keys=True, default=str))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
