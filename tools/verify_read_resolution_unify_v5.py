#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""production read_opponent와 V4가 하나의 read-resolution 원천을 쓰는지 검증."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persona as PS
import reads as RD


def prof(att, adp, rr, st):
    return {
        'type': 'TEST',
        'concepts': {'range_read': rr, 'sizing_tell': st},
        'temper': {
            'attention': att, 'adaptability': adp,
            'consistency': 5.0, 'aggression': 5.0,
            'looseness': 5.0, 'gamble': 5.0, 'discipline': 5.0,
        },
    }


def old_see(v):
    return max(0.0, min(1.0, (float(v) - 2.0) / 6.0))


def main():
    vals = [0.0, 1.9, 2.0, 2.1, 3.9, 4.1, 5.0, 7.9, 8.0, 9.5, 10.0]
    n = 0
    for att in vals:
        for adp in (1.0, 2.0, 5.0, 8.0, 10.0):
            for rr in (1.0, 2.0, 4.5, 8.0, 10.0):
                for st in (1.0, 2.0, 5.5, 8.0, 10.0):
                    p = prof(att, adp, rr, st)
                    x = PS.read_resolution(p)
                    assert x['see_freq'] == old_see(att)
                    assert x['see_line'] == old_see(rr)
                    assert x['see_size'] == old_see(st)
                    assert x['use'] == old_see(adp)

                    v4 = RD.observer_resolution_v4(p)
                    assert v4['see_freq'] == round(x['see_freq'], 3)
                    assert v4['see_line'] == round(x['see_line'], 3)
                    assert v4['see_size'] == round(x['see_size'], 3)
                    assert v4['apply_willingness'] == round(x['use'], 3)
                    n += 1

    z = PS.read_resolution(None)
    assert z == {'see_freq': 0.0, 'see_line': 0.0, 'see_size': 0.0, 'use': 0.0}
    zv4 = RD.observer_resolution_v4(None)
    assert zv4['trait_access'] == 0.0
    assert zv4['detail_access'] == 0.0
    assert zv4['coarse_access'] == 1.0

    # production read_opponent가 helper 수치를 그대로 외부 진단에도 노출한다.
    p = prof(6.2, 7.1, 5.3, 4.4)
    e = {
        'confidence': .8, 'n': 20, 'ftb': .60, 'bluff': 5.0, 'aggr': 6.0,
        'ftb_flop': .58, 'ftb_turn': .62, 'ftb_river': .66,
        'rfi_rel': 1.1, 'pf_limp': .04, 'barrel': .50,
        'pf_3bet': .09, 'pf_fold_to_3bet': .55, 'pf_4bet': .05,
        'pf_fold_to_4bet': .60, 'sz_mean': .70, 'sz_sd': .25,
        'sz_n': 10, 'sz_big': .2, 'sz_river': .72,
    }
    res = PS.read_resolution(p)
    rd = PS.read_opponent(p, e)
    assert rd['see_freq'] == round(res['see_freq'], 3)
    assert rd['see_line'] == round(res['see_line'], 3)
    assert rd['see_size'] == round(res['see_size'], 3)

    print('READ_RESOLUTION_UNIFY_V5 contract: PASS')
    print('grid_cases=%d' % n)
    print('sample=%s' % res)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
