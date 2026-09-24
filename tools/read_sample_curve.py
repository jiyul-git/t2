#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ_SAMPLE_CURVE — 표본 수에 따른 읽기 정확도의 EV 효과 곡선. 읽기 전용.

두 채널을 **같은 깨끗한 개입**으로 잰다 (READ_USE_SEPARATION 의 R 축):
실제 필드 프로필의 **믿음만** 모집단 사전분포로 블렌드하고 나머지는 고정.
합성 arm(make_arms)을 쓰지 않는다 — 그쪽은 APPLY 개념 다발이 교락돼 있다
(ATTACK_FIXTURE_FIX Amendment D1).

수비 셀   read_use_fixture.pick_cells()   (READ_USE 의 균형 잡힌 20셀)
공격 셀   attack_fixture.pick_cells()     (ftb 가 b_true 와 독립인 9셀)
두 모듈 다 **수정하지 않는다.** 셀 정의만 빌려 n_obs 격자를 갈아끼운다.

production 무수정. qx_ev_fixture.py 무수정.
"""
from __future__ import print_function

import argparse
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import persona as PS
import attack_fixture as AF
import qx_ev_fixture as QF
import read_use_fixture as RU
import v7_num_battery as B
import v7_num_intervention as IV

FLOOR = 0.002
BOOT = 4000
A_LO, A_HI = RU.A_LO, RU.A_HI                 # 0.20 / 1.00
N_GRID = (8, 10, 12, 16, 24, 40)


def pear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x, y):
    rx = np.argsort(np.argsort(np.asarray(x, float)))
    ry = np.argsort(np.argsort(np.asarray(y, float)))
    return pear(rx, ry)


def boot_ci(v, seed=B.SEED, iters=BOOT):
    v = np.asarray(v, float)
    rng = np.random.RandomState(seed & 0x7fffffff)
    m = v[rng.randint(0, len(v), size=(iters, len(v)))].mean(axis=1)
    m.sort()
    return float(m[int(0.025 * iters)]), float(m[int(0.975 * iters)])


def build_states():
    """두 채널을 같은 n_obs 격자로 만든다. 셀 정의는 기존 모듈에서 빌린다."""
    D, A, sid = [], [], 0
    for board, hero, sz, _k in RU.pick_cells():
        for b in RU.B_LEVELS:
            for n in N_GRID:
                D.append(QF.State(sid, 'D', 'READ', hero, board, sz, b, n))
                sid += 1
    sid = 500000
    for board, hero, sz, _k, _st in AF.pick_cells():
        for ftb in AF.FTB_LEVELS:
            for b in AF.B_LEVELS:
                for n in N_GRID:
                    A.append(AF.AttackState(sid, hero, board, sz, b, ftb, n))
                    sid += 1
    return D, A


def run_set(profs, D, A, evs, man_n=20):
    """프로필 × 채널 × n_obs 별 평균 regret. arm 은 R 축 두 수준."""
    reg = {(ch, n, a): [] for ch in 'DA' for n in N_GRID
           for a in (A_LO, A_HI)}
    man = {(n, a): [[], []] for n in N_GRID for a in (A_LO, A_HI)}
    wobs = {(n, a): [] for n in N_GRID for a in (A_LO, A_HI)}
    byn = {('D', n): [s for s in D if s.n_obs == n] for n in N_GRID}
    byn.update({('A', n): [s for s in A if s.n_obs == n] for n in N_GRID})
    for pi, prof in enumerate(profs):
        for a in (A_LO, A_HI):
            with RU.read_arm(a):
                for ch in 'DA':
                    for n in N_GRID:
                        rs = []
                        for s in byn[(ch, n)]:
                            rng = random.Random(QF.FIX_SEED + s.sid)
                            mix, _ = QF.bot_action(s, prof, rng)
                            rs.append(QF.regret_of(s, mix, evs[s.sid]))
                        reg[(ch, n, a)].append(float(np.mean(rs)))
                if pi < man_n:
                    for n in N_GRID:
                        for s in byn[('A', n)]:
                            est = s.est_for(prof,
                                            random.Random(QF.FIX_SEED + s.sid))
                            man[(n, a)][0].append(s.ftb_true)
                            man[(n, a)][1].append(float(est.get('ftb') or 0.52))
                            wobs[(n, a)].append(
                                float(PS.read_opponent(prof, est).get('w', 0.0)))
    out = {}
    for ch in 'DA':
        for n in N_GRID:
            d = [x - y for x, y in zip(reg[(ch, n, A_LO)], reg[(ch, n, A_HI)])]
            ci = boot_ci(d)
            out['%s_n%d' % (ch, n)] = {
                'lo': float(np.mean(reg[(ch, n, A_LO)])),
                'hi': float(np.mean(reg[(ch, n, A_HI)])),
                'dR': float(np.mean(d)), 'ci': list(ci),
                'sig': bool(ci[0] > 0 or ci[1] < 0),
                'ge_floor': bool(abs(float(np.mean(d))) >= FLOOR)}

    def slope(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        return 0.0 if x.std() < 1e-12 else float(np.polyfit(x, y, 1)[0])
    for n in N_GRID:
        out['man_n%d' % n] = {
            'slope_lo': slope(*man[(n, A_LO)]), 'slope_hi': slope(*man[(n, A_HI)]),
            'sd_lo': float(np.std(man[(n, A_LO)][1])),
            'sd_hi': float(np.std(man[(n, A_HI)][1])),
            'w_lo': float(np.mean(wobs[(n, A_LO)])),
            'w_hi': float(np.mean(wobs[(n, A_HI)]))}
    for ch in 'DA':
        out['spearman_' + ch] = spearman(
            N_GRID, [out['%s_n%d' % (ch, n)]['dR'] for n in N_GRID])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--set-a', default='940001-940010')
    ap.add_argument('--set-b', default='950001-950010')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--synth-n', type=int, default=150)
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    D, A = build_states()
    evs = {s.sid: s.ev_actions() for s in D}
    evs.update({s.sid: s.ev_actions() for s in A})
    fD = sum(1 for s in D
             if max(evs[s.sid], key=lambda k: evs[s.sid][k]) == 'call') / float(len(D))
    fA = sum(1 for s in A
             if max(evs[s.sid], key=lambda k: evs[s.sid][k]) == 'bet') / float(len(A))
    print('수비 상태 %d (최적=call %.3f)   공격 상태 %d (최적=bet %.3f)'
          % (len(D), fD, len(A), fA))
    if a.check:
        ok = (0.45 <= fD <= 0.55) and (0.45 <= fA <= 0.55)
        print('[G-b] 구성 균형 -> %s' % ('OK' if ok else 'FAIL'))
        print('n_obs 격자 %s   두 채널 동일 -> %s'
              % (str(N_GRID),
                 'OK' if sorted({s.n_obs for s in D}) ==
                 sorted({s.n_obs for s in A}) == list(N_GRID) else 'FAIL'))
        return 0 if ok else 1

    out = {}
    for label, seeds in (('SET_A', a.set_a), ('SET_B', a.set_b)):
        lo, hi = (int(x) for x in seeds.split('-'))
        profs = IV.base_profiles(range(lo, hi + 1), a.entries, a.n)[:a.synth_n]
        r = run_set(profs, D, A, evs)
        out[label] = r
        print('\n=== %s %s (프로필 %d) ===' % (label, seeds, len(profs)))
        print('%-5s %9s %9s %11s %22s %8s %8s'
              % ('n_obs', 'w(HIGH)', 'slope비', 'dR 수비', '95%CI', 'dR 공격', '95%CI'))
        for n in N_GRID:
            m = r['man_n%d' % n]
            rs = m['slope_hi'] / m['slope_lo'] if m['slope_lo'] else 0.0
            d, k = r['D_n%d' % n], r['A_n%d' % n]
            print('%-5d %9.3f %9.2f %+11.5f [%+.5f,%+.5f] %+8.5f [%+.5f,%+.5f]%s'
                  % (n, m['w_hi'], rs, d['dR'], d['ci'][0], d['ci'][1],
                     k['dR'], k['ci'][0], k['ci'][1],
                     '  <FLOOR' if not k['ge_floor'] else ''))
        print('  단조성 Spearman(n, dR)   수비 %+.3f   공격 %+.3f'
              % (r['spearman_D'], r['spearman_A']))

    # 문턱 판정
    def above(s, n):
        k = out[s]['A_n%d' % n]
        return k['dR'] >= FLOOR and k['sig']
    both = [n for n in N_GRID if above('SET_A', n) and above('SET_B', n)]
    neither = [n for n in N_GRID
               if not above('SET_A', n) and not above('SET_B', n)]
    man_ok = all(4.0 <= (out[s]['man_n%d' % n]['slope_hi']
                         / max(1e-12, out[s]['man_n%d' % n]['slope_lo'])) <= 6.0
                 for s in ('SET_A', 'SET_B') for n in N_GRID)
    if not man_ok:
        v = 'C0_INCONCLUSIVE'
    elif both and neither and min(both) > max(neither):
        v = 'C1_THRESHOLD_FOUND'
    elif not both or not neither:
        v = 'C3_NO_THRESHOLD'
    else:
        v = 'C2_THRESHOLD_UNCLEAR'
    print('\n공격 FLOOR 통과 n (두 집합 모두): %s' % (both or '없음'))
    print('공격 FLOOR 미달 n (두 집합 모두): %s' % (neither or '없음'))
    print('\n========== 판정: %s ==========' % v)
    out['verdict'] = v
    out['floor'] = FLOOR
    out['n_grid'] = list(N_GRID)
    out['n_states'] = {'D': len(D), 'A': len(A)}
    if a.out:
        json.dump(out, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
