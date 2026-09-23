#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_OBSERVER_DEPTH_V4 SHADOW 계약 검증."""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import reads as RD


def est():
    return {
        'vpip': .31, 'pfr': .21, 'rfi_rel': 1.15, 'pf_limp': .05,
        'pf_3bet': .10, 'pf_4bet': .05, 'aggr': 6.1,
        'cbet': .62, 'barrel': .50, 'ftb': .47, 'bluff': 5.2,
        'sz_mean': .68, 'sz_sd': .25, 'sz_big': .20,
        'confidence': .72, 'n': 20,
    }


def prof(att, adp, rr, st):
    return {
        'type': 'TEST',
        'concepts': {'range_read': rr, 'sizing_tell': st},
        'temper': {
            'attention': att, 'adaptability': adp,
            'consistency': 5.0, 'aggression': 5.0,
            'looseness': 5.0, 'gamble': 5.0,
            'discipline': 5.0,
        },
    }


def main():
    e = est()
    before = copy.deepcopy(e)

    weak = prof(2.0, 4.0, 2.0, 2.0)
    mid = prof(5.0, 5.0, 5.0, 4.0)
    reg = prof(8.0, 8.0, 8.0, 8.0)

    w = RD.hierarchical_belief_v4(e, weak)
    m = RD.hierarchical_belief_v4(e, mid)
    r = RD.hierarchical_belief_v4(e, reg)

    # session이 쓰는 재사용 경로도 독립 계산과 정확히 같아야 한다.
    sh = RD.style_shadow(e)
    h3 = RD.hierarchical_belief_v3(e, style_base=sh)
    rr = RD.hierarchical_belief_v4(e, reg, hierarchy_base=h3)
    assert h3 == RD.hierarchical_belief_v3(e)
    assert rr == r

    assert e == before, 'input mutated'

    # 같은 상대 관찰이면 coarse/traits/detail 원자료는 관찰자 depth 때문에
    # 다시 쓰이지 않는다. 달라지는 것은 접근 해상도뿐이다.
    assert w['coarse'] == m['coarse'] == r['coarse']
    assert w['traits'] == m['traits'] == r['traits']
    assert w['detail'] == m['detail'] == r['detail']

    dw, dm, dr = w['observer_depth'], m['observer_depth'], r['observer_depth']
    assert dw['coarse_access'] == dm['coarse_access'] == dr['coarse_access'] == 1.0
    assert dw['trait_access'] < dm['trait_access'] < dr['trait_access']
    assert dw['detail_access'] < dm['detail_access'] < dr['detail_access']
    assert dw['apply_willingness'] < dm['apply_willingness'] < dr['apply_willingness']

    assert w['mode'] == 'COARSE', w
    assert m['mode'] == 'TRAIT', m
    assert r['mode'] == 'DETAIL', r

    # 강한 관찰자는 세 축을 모두 읽고, 약한 관찰자는 구체 라인/사이즈를 못 읽는다.
    assert dr['see_freq'] == 1.0 and dr['see_line'] == 1.0 and dr['see_size'] == 1.0
    assert dw['see_freq'] == 0.0 and dw['see_line'] == 0.0 and dw['see_size'] == 0.0

    # 프로필이 없는 옛 호출자는 안전하게 coarse only.
    z = RD.observer_resolution_v4(None)
    assert z['coarse_access'] == 1.0
    assert z['trait_access'] == 0.0 and z['detail_access'] == 0.0

    print('STYLE_OBSERVER_DEPTH_V4 contract: PASS')
    print('weak:', w['mode'], dw)
    print('mid :', m['mode'], dm)
    print('reg :', r['mode'], dr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
