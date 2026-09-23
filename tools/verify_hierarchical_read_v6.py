#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V6 계약 테스트."""
import os, sys, math
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
            'attention': att, 'adaptability': adp, 'consistency': 5.0,
            'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0,
            'discipline': 5.0,
        },
    }


def est():
    return {
        'vpip': .34, 'pfr': .23, 'rfi_rel': 1.28, 'pf_limp': .04,
        'pf_3bet': .11, 'pf_fold_to_3bet': .61,
        'pf_4bet': .055, 'pf_fold_to_4bet': .64,
        'cbet': .66, 'barrel': .56,
        'ftb': .58, 'ftb_flop': .54, 'ftb_turn': .61, 'ftb_river': .66,
        'aggr': 6.4, 'bluff': 5.7,
        'sz_mean': .74, 'sz_sd': .31, 'sz_big': .24, 'sz_river': .82, 'sz_n': 12,
        'confidence': .80, 'n': 24,
    }


def close(a, b, eps=1e-9):
    return abs(float(a)-float(b)) <= eps


def main():
    e = est()
    weak = prof(2.0, 5.0, 2.0, 2.0)
    mid = prof(5.0, 5.0, 5.0, 5.0)
    high = prof(8.0, 8.0, 8.0, 8.0)

    rw = RD.hierarchical_read_v6(weak, e)
    rm = RD.hierarchical_read_v6(mid, e)
    rh = RD.hierarchical_read_v6(high, e)

    # LOW = coarse only. 기존 direct read는 아무 축도 못 보면 중립이지만,
    # V6는 사용 의지가 있는 약한 관찰자에게 큰 가설을 남긴다.
    for axis in ('freq','line','size'):
        assert rw['source_weights'][axis] == {'coarse':1.0,'trait':0.0,'detail':0.0}
    old_w = PS.read_opponent(weak, e)
    assert old_w.get('w', 0.0) == 0.0
    assert rw['w'] > 0.0
    assert abs(rw['open_gap']) > 1e-9 or abs(rw['barrel_gap']) > 1e-9

    # MID = 25/50/25 exactly.
    want = {'coarse':.25,'trait':.5,'detail':.25}
    for axis in ('freq','line','size'):
        assert rm['source_weights'][axis] == want, rm['source_weights']

    # HIGH = detail only이며 기존 production direct read와 action-facing 값이 같다.
    for axis in ('freq','line','size'):
        assert rh['source_weights'][axis] == {'coarse':0.0,'trait':0.0,'detail':1.0}
    old_h = PS.read_opponent(high, e)
    keys = (
        'w','see_freq','see_line','see_size',
        'fold_gap','fold_gap_flop','fold_gap_turn','fold_gap_river',
        'open_gap','limp_gap','barrel_gap','tb_gap','tb_polar',
        'f2tb_gap','fb_gap','f2fb_gap',
        'size_gap','size_info','size_big','size_river','bluff_gap','passive'
    )
    for k in keys:
        assert close(rh[k], old_h[k], 1e-9), (k, rh[k], old_h[k])

    # weight 합은 모든 a에서 1이고 trait는 중간에서 최대.
    for a in [0,.1,.25,.5,.75,.9,1.0]:
        q = RD._style_v6_weights(a)
        assert close(sum(q.values()), 1.0, 1e-9), (a,q)
    assert RD._style_v6_weights(.5)['trait'] == .5

    # 사용 의지가 0이면 정보가 있어도 action-facing neutral.
    no_use = RD.hierarchical_read_v6(prof(8,2,8,8), e)
    assert no_use['w'] == 0.0

    # 무표본도 neutral.
    ez = dict(e); ez['n']=0; ez['confidence']=0
    z = RD.hierarchical_read_v6(high, ez)
    assert z['w'] == 0.0

    # hidden target profile은 함수 인자에 존재하지 않는다.
    assert math.isclose(sum(rh['coarse_probs'].values()), 1.0, abs_tol=1e-5)

    print('HIERARCHICAL_READ_V6 contract: PASS')
    print('weak top=%s open=%+.3f barrel=%+.3f w=%.3f' %
          (rw['coarse_top'], rw['open_gap'], rw['barrel_gap'], rw['w']))
    print('mid weights=%s' % rm['source_weights'])
    print('high exact-match channels=%d' % len(keys))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
