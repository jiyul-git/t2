#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_MODEL_V1 SHADOW 계약 검증.

행동 라인은 건드리지 않는다. 순수 분류기 계약만 확인한다.
실제 행동 보존은 별도로 regress.py current fingerprint가 맡는다.
"""
import copy
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import reads as RD


def base(**kw):
    d = {
        'vpip': 0.26, 'pfr': 0.15, 'rfi_rel': 1.0, 'pf_limp': 0.06,
        'pf_3bet': 0.07, 'pf_4bet': 0.04, 'aggr': 4.2,
        'cbet': 0.55, 'barrel': 0.42, 'ftb': 0.52, 'bluff': 4.5,
        'sz_mean': 0.62, 'sz_sd': 0.22, 'sz_big': 0.15,
        'confidence': 1.0, 'n': 40,
    }
    d.update(kw)
    return d


CASES = {
    'NIT': base(vpip=.12, pfr=.09, rfi_rel=.55, pf_limp=.01,
                pf_3bet=.05, aggr=4.5, cbet=.50, barrel=.35),
    'TAG': base(vpip=.20, pfr=.15, rfi_rel=.90, pf_limp=.02,
                pf_3bet=.08, aggr=6.2, cbet=.60, barrel=.48),
    'LAG': base(vpip=.38, pfr=.28, rfi_rel=1.40, pf_limp=.03,
                pf_3bet=.12, pf_4bet=.06, aggr=7.0, cbet=.65, barrel=.60,
                sz_big=.20, sz_sd=.24),
    'LOOSE_PASSIVE': base(vpip=.45, pfr=.10, rfi_rel=1.20, pf_limp=.30,
                          pf_3bet=.03, aggr=2.2, cbet=.35, barrel=.25),
    'TIGHT_PASSIVE': base(vpip=.14, pfr=.06, rfi_rel=.70, pf_limp=.03,
                          pf_3bet=.03, aggr=2.2, cbet=.35, barrel=.25),
    'MANIAC': base(vpip=.55, pfr=.45, rfi_rel=1.80, pf_limp=.08,
                   pf_3bet=.22, pf_4bet=.12, aggr=9.0, cbet=.82, barrel=.80,
                   sz_big=.55, sz_sd=.50),
}


def main():
    # 1) 무표본은 정확히 균등 + certainty 0.
    u = RD.style_shadow(base(confidence=0.0, n=0))
    assert u['certainty'] == 0.0, u
    vals = list(u['probs'].values())
    assert len(vals) == 6 and max(vals) - min(vals) <= 1e-6, u

    # 2) 전형점은 각 스타일 중심으로 분류.
    for want, est in CASES.items():
        before = copy.deepcopy(est)
        got = RD.style_shadow(est)
        assert est == before, '입력 mutation: %s' % want
        assert got['top'] == want, (want, got)
        assert abs(sum(got['probs'].values()) - 1.0) < 1e-5, got
        assert 0.0 <= got['certainty'] <= 1.0, got
        assert 0.0 <= got['L'] <= 10.0
        assert 0.0 <= got['A'] <= 10.0
        assert 0.0 <= got['X'] <= 10.0
        for k, v in got['modifiers'].items():
            assert 0.0 <= v <= 1.0, (k, v)

    # 3) 같은 행동이면 표본이 늘수록 q가 감소하면 안 된다.
    small = RD.style_shadow(base(confidence=.3, n=4))
    large = RD.style_shadow(base(confidence=.9, n=40))
    assert large['q'] > small['q'], (small, large)

    # 4) modifier 방향 sanity.
    sticky = RD.style_shadow(base(vpip=.45, pfr=.10, ftb=.18, aggr=2.0))
    overfold = RD.style_shadow(base(ftb=.85))
    bluffy = RD.style_shadow(base(bluff=8.5, barrel=.78, sz_big=.50))
    assert sticky['modifiers']['sticky'] > 0.5, sticky
    assert overfold['modifiers']['overfold'] > 0.5, overfold
    assert bluffy['modifiers']['bluffy'] > 0.5, bluffy

    # 5) 스타일은 6종 고정.
    assert tuple(RD.STYLE_V1_NAMES) == (
        'NIT', 'TAG', 'LAG', 'LOOSE_PASSIVE', 'TIGHT_PASSIVE', 'MANIAC')

    print('STYLE_MODEL_V1 shadow contract: PASS')
    for want, est in CASES.items():
        got = RD.style_shadow(est)
        print('%-15s -> %-15s L %.2f A %.2f X %.2f cert %.3f'
              % (want, got['top'], got['L'], got['A'], got['X'], got['certainty']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
