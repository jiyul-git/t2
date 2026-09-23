#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ_USE_SEPARATION 타당성 검사 (사전등록 4절). 읽기 전용.

**regret 을 집계하지 않는다.** 결과를 보기 전에 통과해야 하는 것만 본다.
"""
from __future__ import print_function

import argparse
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import persona as PS
import plan as PL
import read_use_fixture as FX
import v7_num_intervention as IV


def capture_sz(fn):
    """calldown_need 안의 지역변수 _sz_seen 을 size_read 반환값으로 잡는다."""
    box = []
    orig = PS.size_read

    def patched(prof, size_frac):
        v = orig(prof, size_frac)
        box.append(v)
        return v

    PS.size_read = patched
    try:
        fn()
    finally:
        PS.size_read = orig
    return box


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='940001-940003')
    ap.add_argument('--n', type=int, default=60)
    ap.add_argument('--entries', type=int, default=400)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))
    profs = IV.base_profiles(range(lo, hi + 1), a.entries, a.n)
    states = FX.build_states()
    evs = {s.sid: s.ev_actions() for s in states}
    print('프로필 %d · 상태 %d' % (len(profs), len(states)))

    ok = {}

    # 4-6 판별력
    flips = {}
    for s in states:
        e = evs[s.sid]
        flips.setdefault((tuple(s.board), tuple(s.hero), s.sz), set()).add(
            max(e, key=lambda k: e[k]))
    nf = sum(1 for v in flips.values() if len(v) > 1)
    ncall = sum(1 for s in states
                if max(evs[s.sid], key=lambda k: evs[s.sid][k]) == 'call')
    ok['4-6'] = (nf == len(flips))
    print('\n[4-6] 뒤집힘 셀 %d/%d   최적=call 비율 %.3f   -> %s'
          % (nf, len(flips), ncall / float(len(states)),
             'OK' if ok['4-6'] else 'FAIL'))

    # 4-1 / 4-3
    bad_w, n_w = 0, 0
    err = {FX.A_LO: [], FX.A_HI: []}
    rvs = {FX.A_LO: [], FX.A_HI: []}
    bls = {FX.A_LO: [], FX.A_HI: []}
    bts = []
    ests = {}
    for pi, prof in enumerate(profs):
        for aa in (FX.A_LO, FX.A_HI):
            for s in states:
                se, sn = FX.seeds_for(pi, s.sid)
                e = FX.est_for_arm(s, prof, se, aa)
                ests[(pi, aa, s.sid)] = e
                rv = PL.line_bluff_prior(e, 'turn', 1, s.sz, s.board, False)
                err[aa].append(abs(rv - s.b_true))
                rvs[aa].append(rv)
                bls[aa].append(e['bluff'])
                if aa == FX.A_LO:
                    bts.append(s.b_true)
        for s in states:
            w1 = PS.read_opponent(prof, ests[(pi, FX.A_LO, s.sid)]).get('w', 0.0)
            w2 = PS.read_opponent(prof, ests[(pi, FX.A_HI, s.sid)]).get('w', 0.0)
            n_w += 1
            if w1 != w2:
                bad_w += 1
    ok['4-1'] = (bad_w == 0)
    print('[4-1] R 이 w 를 바꾼 건수 %d / %d   -> %s'
          % (bad_w, n_w, 'OK' if ok['4-1'] else 'FAIL'))
    e_lo = sum(err[FX.A_LO]) / len(err[FX.A_LO])
    e_hi = sum(err[FX.A_HI]) / len(err[FX.A_HI])
    ok['4-3'] = (e_hi < e_lo)
    print('[4-3] |line_bluff_prior - b_true| 평균   LOW_READ %.4f   HIGH_READ %.4f'
          '   -> %s' % (e_lo, e_hi, 'OK' if ok['4-3'] else 'FAIL'))
    # 아래는 게이트가 아니라 개입 강도 진단이다 (사전등록에 없음, 서술용).
    # |rv - b_true| 는 line_bluff_prior 의 상태별 배수 때문에 계통 오차가
    # 커서 개입 강도를 과소평가한다. 신호 추적력을 같이 본다.
    import numpy as _np

    def _r(x, y):
        x, y = _np.asarray(x, float), _np.asarray(y, float)
        if x.std() < 1e-12 or y.std() < 1e-12:
            return 0.0
        return float(_np.corrcoef(x, y)[0, 1])

    def _slope(x, y):
        x, y = _np.asarray(x, float), _np.asarray(y, float)
        if x.std() < 1e-12:
            return 0.0
        return float(_np.polyfit(x, y, 1)[0])
    print('      [진단] r(rv, b_true)      LOW %+.4f   HIGH %+.4f'
          % (_r(bts, rvs[FX.A_LO]), _r(bts, rvs[FX.A_HI])))
    print('      [진단] slope(b_true->rv)  LOW %+.4f   HIGH %+.4f'
          % (_slope(bts, rvs[FX.A_LO]), _slope(bts, rvs[FX.A_HI])))
    print('      [진단] rv 평균/sd         LOW %.4f/%.4f   HIGH %.4f/%.4f'
          % (float(_np.mean(rvs[FX.A_LO])), float(_np.std(rvs[FX.A_LO])),
             float(_np.mean(rvs[FX.A_HI])), float(_np.std(rvs[FX.A_HI]))))
    print('      [진단] est[bluff] 평균/sd LOW %.3f/%.3f   HIGH %.3f/%.3f'
          % (float(_np.mean(bls[FX.A_LO])), float(_np.std(bls[FX.A_LO])),
             float(_np.mean(bls[FX.A_HI])), float(_np.std(bls[FX.A_HI]))))

    # 4-2 U 는 인식 사이즈를 안 바꾼다
    sub = profs[:12]
    szs = {}
    for uu in (FX.U_LO, FX.U_HI):
        acc = []

        def run(uu=uu, acc=acc):
            with FX.use_arm(uu):
                for pi, prof in enumerate(sub):
                    for s in states:
                        se, sn = FX.seeds_for(pi, s.sid)
                        FX.decide(s, prof, ests[(pi, FX.A_HI, s.sid)], sn, uu)
        szs[uu] = capture_sz(run)
    d = sum(1 for x, y in zip(szs[FX.U_LO], szs[FX.U_HI]) if x != y)
    ok['4-2'] = (d == 0 and len(szs[FX.U_LO]) == len(szs[FX.U_HI])
                 and len(szs[FX.U_LO]) > 0)
    print('[4-2] U 가 인식 사이즈를 바꾼 건수 %d / %d   -> %s'
          % (d, len(szs[FX.U_LO]), 'OK' if ok['4-2'] else 'FAIL'))

    # 4-4 널 개입 대조 — need 가 비트까지 같아야 한다
    def needs(aa1, aa2, u1, u2):
        n1, n2 = [], []
        for arm, acc in (((aa1, u1), n1), ((aa2, u2), n2)):
            av, uv = arm
            with FX.use_arm(uv):
                for pi, prof in enumerate(sub):
                    for s in states:
                        se, sn = FX.seeds_for(pi, s.sid)
                        e = FX.est_for_arm(s, prof, se, av)
                        acc.append(FX.decide(s, prof, e, sn, uv)[1])
        return sum(1 for x, y in zip(n1, n2) if x != y), len(n1)
    dr, nr = needs(1.0, 1.0, FX.U_HI, FX.U_HI)
    du, nu = needs(FX.A_HI, FX.A_HI, 1.0, 1.0)
    ok['4-4'] = (dr == 0 and du == 0)
    print('[4-4] 널 개입에서 need 불일치   R축 %d/%d   U축 %d/%d   -> %s'
          % (dr, nr, du, nu, 'OK' if ok['4-4'] else 'FAIL'))

    # 4-5 arm 이 행동을 바꾼다
    acts = {}
    for aa in (FX.A_LO, FX.A_HI):
        for uu in (FX.U_LO, FX.U_HI):
            with FX.use_arm(uu):
                for pi, prof in enumerate(profs):
                    for s in states:
                        se, sn = FX.seeds_for(pi, s.sid)
                        acts[(aa, uu, pi, s.sid)] = FX.decide(
                            s, prof, ests[(pi, aa, s.sid)], sn, uu)[0]
    tot = diff = 0
    for pi in range(len(profs)):
        for s in states:
            v = {acts[(aa, uu, pi, s.sid)]
                 for aa in (FX.A_LO, FX.A_HI) for uu in (FX.U_LO, FX.U_HI)}
            tot += 1
            if len(v) > 1:
                diff += 1
    rate = diff / float(tot)
    ok['4-5'] = (rate >= 0.10)
    print('[4-5] arm 사이 행동이 갈리는 (프로필,상태) 비율 %.4f (%d/%d)   -> %s'
          % (rate, diff, tot, 'OK' if ok['4-5'] else 'FAIL'))

    print('\n전체: %s' % ('통과' if all(ok.values())
                        else '실패 — ' + ', '.join(k for k, v in ok.items() if not v)))
    return 0 if all(ok.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
