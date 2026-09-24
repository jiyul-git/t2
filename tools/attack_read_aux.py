#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATTACK_FIXTURE_FIX Amendment D1 — 깨끗한 읽기 대조. 읽기 전용.

합성 arm 을 쓰지 않는다. 실제 필드 프로필의 **믿음만** 모집단 사전분포로
블렌드한다 (READ_USE_SEPARATION 의 R 축). 개념 다발 교락이 원리적으로 없다.
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
A_LO, A_HI = RU.A_LO, RU.A_HI          # 0.20 / 1.00 — READ_USE 와 같은 수준


def pear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def boot_ci(v, seed=B.SEED, iters=BOOT):
    v = np.asarray(v, float)
    rng = np.random.RandomState(seed & 0x7fffffff)
    m = v[rng.randint(0, len(v), size=(iters, len(v)))].mean(axis=1)
    m.sort()
    return float(m[int(0.025 * iters)]), float(m[int(0.975 * iters)])


def run_set(profs, states, evs):
    """프로필당 arm 별 평균 regret + 조작 점검용 상관."""
    reg = {A_LO: [], A_HI: []}
    regn = {(a, n): [] for a in (A_LO, A_HI) for n in (6, 40)}
    man = {A_LO: [[], []], A_HI: [[], []]}
    for pi, prof in enumerate(profs):
        for a in (A_LO, A_HI):
            rs, byn = [], {6: [], 40: []}
            with RU.read_arm(a):
                for s in states:
                    rng = random.Random(QF.FIX_SEED + s.sid)
                    mix, _ = QF.bot_action(s, prof, rng)
                    r = QF.regret_of(s, mix, evs[s.sid])
                    rs.append(r)
                    byn[s.n_obs].append(r)
                    if pi < 20:                 # 조작 점검은 일부만
                        est = s.est_for(prof, random.Random(QF.FIX_SEED + s.sid))
                        man[a][0].append(s.ftb_true)
                        man[a][1].append(float(est.get('ftb') or 0.52))
            reg[a].append(float(np.mean(rs)))
            for n in (6, 40):
                regn[(a, n)].append(float(np.mean(byn[n])))
    out = {'mean_lo': float(np.mean(reg[A_LO])),
           'mean_hi': float(np.mean(reg[A_HI]))}
    d = [x - y for x, y in zip(reg[A_LO], reg[A_HI])]
    ci = boot_ci(d)
    out.update({'dR': float(np.mean(d)), 'ci': list(ci),
                'sig': bool(ci[0] > 0 or ci[1] < 0)})
    for n in (6, 40):
        dn = [x - y for x, y in zip(regn[(A_LO, n)], regn[(A_HI, n)])]
        cn = boot_ci(dn)
        out['dR_n%d' % n] = {'mean': float(np.mean(dn)), 'ci': list(cn),
                             'sig': bool(cn[0] > 0 or cn[1] < 0)}
    # Amendment D2 — 상관은 양의 아핀 변환에 **불변**이라 이 개입을 못 잰다.
    # 기울기와 sd 는 a 에 비례한다. 이론 비율은 A_HI/A_LO = 5.0.
    def slope(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        return 0.0 if x.std() < 1e-12 else float(np.polyfit(x, y, 1)[0])
    for a_, tag in ((A_LO, 'lo'), (A_HI, 'hi')):
        out['slope_' + tag] = slope(man[a_][0], man[a_][1])
        out['sd_' + tag] = float(np.std(man[a_][1]))
        out['corr_' + tag] = pear(man[a_][0], man[a_][1])   # 불변임을 보이려고 남긴다
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set-a', default='940001-940010')
    ap.add_argument('--set-b', default='950001-950010')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--synth-n', type=int, default=150)
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    states = AF.build_attack_states()
    evs = {s.sid: s.ev_actions() for s in states}
    print('공격 상태 %d   a: %.2f vs %.2f' % (len(states), A_LO, A_HI))

    out = {}
    for label, seeds in (('SET_A', a.set_a), ('SET_B', a.set_b)):
        lo, hi = (int(x) for x in seeds.split('-'))
        profs = IV.base_profiles(range(lo, hi + 1), a.entries, a.n)[:a.synth_n]
        r = run_set(profs, states, evs)
        out[label] = r
        print('\n=== %s %s (프로필 %d) ===' % (label, seeds, len(profs)))
        rs = r['slope_hi'] / r['slope_lo'] if r['slope_lo'] else 0.0
        rd_ = r['sd_hi'] / r['sd_lo'] if r['sd_lo'] else 0.0
        print('  조작 점검 W0\' (D2)')
        print('    slope(ftb_true->믿는 ftb)  LOW %+.4f  HIGH %+.4f  비율 %.2f'
              % (r['slope_lo'], r['slope_hi'], rs))
        print('    sd(믿는 ftb)               LOW %.4f  HIGH %.4f  비율 %.2f'
              % (r['sd_lo'], r['sd_hi'], rd_))
        print('    corr (불변이라 못 쓴다)     LOW %+.4f  HIGH %+.4f'
              % (r['corr_lo'], r['corr_hi']))
        print('    -> %s  (이론 비율 5.0, 허용 +-20%%)'
              % ('OK' if (4.0 <= rs <= 6.0 and 4.0 <= rd_ <= 6.0) else 'FAIL'))
        print('  regret  LOW_READ %.5f   HIGH_READ %.5f' %
              (r['mean_lo'], r['mean_hi']))
        print('  dR_A %+.5f  95%%CI [%+.5f, %+.5f]  %s%s'
              % (r['dR'], r['ci'][0], r['ci'][1],
                 '유의' if r['sig'] else '유의하지 않음',
                 '' if abs(r['dR']) >= FLOOR else '  (FLOOR %.3f 미만)' % FLOOR))
        for n in (6, 40):
            k = r['dR_n%d' % n]
            print('    n_obs=%-3d  %+.5f  [%+.5f, %+.5f]  %s'
                  % (n, k['mean'], k['ci'][0], k['ci'][1],
                     '유의' if k['sig'] else '유의하지 않음'))

    def _r(s, k):
        return (out[s][k + '_hi'] / out[s][k + '_lo']) if out[s][k + '_lo'] else 0.0
    man_ok = all(4.0 <= _r(s, 'slope') <= 6.0 and 4.0 <= _r(s, 'sd') <= 6.0
                 for s in out)
    def ok(sign):
        return all((out[s]['dR'] * sign) >= FLOOR and out[s]['sig'] for s in out)
    v = ('AUX_INCONCLUSIVE' if not man_ok
         else ('AUX_READ_HELPS' if ok(1)
               else ('AUX_READ_HURTS' if ok(-1) else 'AUX_READ_NULL')))
    print('\n========== 보조 판정: %s ==========' % v)
    out['verdict'] = v
    out['floor'] = FLOOR
    if a.out:
        json.dump(out, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
