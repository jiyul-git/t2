#!/usr/bin/env python3
"""Verify semantic split of limp theory knowledge and isolation-raise skill.

Phase 1:
  limp_theory  - limp_theory_knowledge reads it; falls back to pf_range (RFI chart memory).
  iso_raise    - iso_entry_threshold's chart-memory input; falls back to pf_range.
Generated profiles have neither key (behavior identical, no new prior).
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
    # 기질 방향이 0 이면 차트 기억(크기)이 폭에 영향을 주지 않는다 — 루즈한 사람으로 본다.
    t['looseness'] = 8.0
    return {
        'id': None, 'concepts': c, 'temper': t,
        'latent': {'study': 5.0, 'aggro': 5.0, 'exp': 5.0}, 'type': 'X',
        'aggr': 5.0, 'bluff': 5.0, 'tight': 5.0, 'gamble': 5.0, 'icm': 5.0,
        'tilt': 0.0, 'tricky': 5.0, 'value': 'mixed',
    }


def iso(p):
    t = PS.traits_of(p)
    return PF.iso_entry_threshold(p, 'CO', 40.0, 9, True, t, None, [])


def opn(p):
    return PF._open(p, 'CO', 9, 40.0, True)


def main():
    checks = {}
    legacy = prof(pf_range=6.0)
    twin = prof(pf_range=6.0, limp_theory=6.0, iso_raise=6.0)
    hi = prof(pf_range=6.0, limp_theory=9.0, iso_raise=1.0)

    checks['legacy_fallback_identity'] = {
        'pass': (PF.limp_theory_knowledge(legacy) == PS.gto_knowledge(legacy, 'rfi')
                 and PF.limp_theory_knowledge(twin) == PF.limp_theory_knowledge(legacy)
                 and iso(twin) == iso(legacy)),
        'limp_knowledge': PF.limp_theory_knowledge(legacy), 'iso': iso(legacy),
    }
    checks['independent_override'] = {
        'pass': (PF.limp_theory_knowledge(hi) != PF.limp_theory_knowledge(legacy)
                 and iso(hi) != iso(legacy)),
        'limp_knowledge_hi': PF.limp_theory_knowledge(hi), 'iso_hi': iso(hi),
    }
    checks['rfi_unchanged'] = {
        'pass': opn(hi) == opn(legacy) and PS.gto_knowledge(hi, 'rfi') == PS.gto_knowledge(legacy, 'rfi'),
        'open': opn(legacy),
    }
    rr = random.Random(20261005)
    generated = [PS.make_player(rr, 0.78, pid=i) for i in range(100)]
    checks['no_new_prior'] = {
        'pass': all('limp_theory' not in p['concepts'] and 'iso_raise' not in p['concepts']
                    for p in generated),
        'sample_n': len(generated),
    }
    passed = all(x['pass'] for x in checks.values())
    print(json.dumps({'pass': passed, 'checks': checks}, indent=2, sort_keys=True, default=str))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
