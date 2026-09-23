#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_HIERARCHY_V3 SHADOW 계약 검증."""
import copy
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import reads as RD


def est(**kw):
    d = {
        'vpip': .26, 'pfr': .15, 'rfi_rel': 1.0, 'pf_limp': .06,
        'pf_3bet': .07, 'pf_4bet': .04, 'aggr': 5.0,
        'cbet': .55, 'barrel': .42, 'ftb': .52, 'bluff': 4.5,
        'sz_mean': .62, 'sz_sd': .22, 'sz_big': .15,
        'confidence': .75, 'n': 20,
    }
    d.update(kw)
    return d


def close(a, b, eps=1e-6):
    return abs(float(a) - float(b)) <= eps


def main():
    x = est(vpip=.22, pfr=.17, rfi_rel=.90, pf_3bet=.08,
            aggr=6.3, cbet=.61, barrel=.50)
    before = copy.deepcopy(x)
    v1 = RD.style_shadow(x)
    v3 = RD.hierarchical_belief_v3(x)

    assert x == before, 'input mutated'
    assert v3['version'] == 'STYLE_HIERARCHY_V3'

    # Layer 1은 기존 SHADOW를 바꾸지 않는다.
    assert v3['coarse']['probs'] == v1['probs']
    assert v3['coarse']['top'] == v1['top']
    assert close(v3['coarse']['certainty'], v1['certainty'])

    ranked = sorted(v1['probs'].items(), key=lambda kv: (-kv[1], kv[0]))
    assert v3['coarse']['second'] == ranked[1][0]
    assert close(v3['coarse']['margin'], ranked[0][1] - ranked[1][1])

    # Layer 2도 기존 연속값/수정자를 그대로 보존한다.
    for k in ('L', 'A', 'X'):
        assert close(v3['traits'][k], v1[k]), (k, v3['traits'][k], v1[k])
    assert v3['traits']['modifiers'] == v1['modifiers']

    top = v1['top']
    c = RD.STYLE_V1_CENTERS[top]
    assert close(v3['traits']['residual_from_top']['L'], v1['L'] - c[0])
    assert close(v3['traits']['residual_from_top']['A'], v1['A'] - c[1])
    assert close(v3['traits']['residual_from_top']['X'], v1['X'] - c[2])

    # Layer 3은 관찰값, prior, delta만 가진다.
    assert close(v3['detail']['vpip']['value'], x['vpip'])
    assert close(v3['detail']['vpip']['prior'], RD.PRIOR['vpip'])
    assert close(v3['detail']['vpip']['delta'], x['vpip'] - RD.PRIOR['vpip'])
    assert close(v3['detail']['pf_3bet']['value'], x['pf_3bet'])
    assert close(v3['detail']['sz_big']['prior'], .15)

    # 결측은 prior로 돌아가되 가짜 극단값을 만들지 않는다.
    miss = est()
    del miss['pf_4bet']
    m = RD.hierarchical_belief_v3(miss)
    assert close(m['detail']['pf_4bet']['value'], RD.PRIOR['pf_4bet'])
    assert close(m['detail']['pf_4bet']['delta'], 0.0)

    # 무표본에서는 coarse가 균등이고 certainty=0.
    z = RD.hierarchical_belief_v3(est(confidence=0.0, n=0))
    ps = list(z['coarse']['probs'].values())
    assert max(ps) - min(ps) <= 1e-6, z['coarse']
    assert z['coarse']['certainty'] == 0.0

    # MANIAC 정보를 억지로 만들지 않는다. 극단 합성점에서만 자연스럽게 커진다.
    extreme = RD.hierarchical_belief_v3(est(
        vpip=.58, pfr=.47, rfi_rel=1.8, pf_3bet=.24, pf_4bet=.14,
        aggr=9.2, cbet=.85, barrel=.82, sz_big=.58, sz_sd=.52,
        confidence=1.0, n=50))
    assert extreme['coarse']['top'] == 'MANIAC', extreme['coarse']
    assert extreme['traits']['X'] > 8.0, extreme['traits']

    print('STYLE_HIERARCHY_V3 contract: PASS')
    print('top=%s second=%s margin=%.3f certainty=%.3f'
          % (v3['coarse']['top'], v3['coarse']['second'],
             v3['coarse']['margin'], v3['coarse']['certainty']))
    print('traits L=%.2f A=%.2f X=%.2f residual=%s'
          % (v3['traits']['L'], v3['traits']['A'], v3['traits']['X'],
             v3['traits']['residual_from_top']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
