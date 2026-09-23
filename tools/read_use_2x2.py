#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ_USE_SEPARATION — 2x2 인과 분리 측정. 읽기 전용.

사전등록 READ_USE_SEPARATION_PREREG.md 3·5·6절.
production 무수정. 새 concept 없음. 공격 채널 없음.
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

import read_use_fixture as FX
import v7_num_battery as B
import v7_num_intervention as IV

BOOT = 4000
FLOOR = 0.002


def boot_ci(per_prof, seed=B.SEED, iters=BOOT):
    """프로필 단위 클러스터 부트스트랩. 상태는 모든 프로필이 공유한다."""
    v = np.asarray(per_prof, float)
    n = len(v)
    rng = np.random.RandomState(seed & 0x7fffffff)
    idx = rng.randint(0, n, size=(iters, n))
    m = v[idx].mean(axis=1)
    m.sort()
    return float(m[int(0.025 * iters)]), float(m[int(0.975 * iters)])


def run_profiles(profs, states, evs):
    """프로필마다 (a,u) 셀별 평균 regret 과 부수 지표."""
    rows = []
    small = [s for s in states if s.n_obs <= 6]
    large = [s for s in states if s.n_obs > 6]
    for pi, prof in enumerate(profs):
        cell, cell_s, cell_l, rate = {}, {}, {}, {}
        for aa in (FX.A_LO, FX.A_HI):
            with FX.read_arm(aa):
                ests = {s.sid: s.est_for(prof, random.Random(FX.seeds_for(pi, s.sid)[0]))
                        for s in states}
            for uu in FX.U_LADDER:
                acts = {}
                with FX.use_arm(uu):
                    for s in states:
                        acts[s.sid] = FX.decide(
                            s, prof, ests[s.sid], FX.seeds_for(pi, s.sid)[1], uu)[0]
                g = lambda ss: float(np.mean([FX.regret(s, acts[s.sid], evs)
                                              for s in ss]))
                cell[(aa, uu)] = g(states)
                cell_s[(aa, uu)] = g(small)
                cell_l[(aa, uu)] = g(large)
                rate[(aa, uu)] = float(np.mean(
                    [1.0 if acts[s.sid] == 'call' else 0.0 for s in states]))
        rows.append({'cell': cell, 'small': cell_s, 'large': cell_l,
                     'rate': rate})
    return rows


def contrast(rows, key, arm_a, arm_b):
    """arm_a − arm_b 를 프로필마다 낸다. >0 이면 arm_b 쪽이 regret 이 낮다."""
    return [r[key][arm_a] - r[key][arm_b] for r in rows]


def report(rows, label, out):
    n = len(rows)
    print('\n=== %s (프로필 %d) ===' % (label, n))
    print('네 arm 평균 regret (팟 대비)')
    print('%-14s %12s %12s' % ('', 'U=%.2f' % FX.U_LO, 'U=%.2f' % FX.U_HI))
    for aa, nm in ((FX.A_LO, 'LOW_READ'), (FX.A_HI, 'HIGH_READ')):
        print('%-14s %12.5f %12.5f'
              % (nm, float(np.mean([r['cell'][(aa, FX.U_LO)] for r in rows])),
                 float(np.mean([r['cell'][(aa, FX.U_HI)] for r in rows]))))

    res = {}

    def emit(name, diffs, tag=''):
        m = float(np.mean(diffs))
        ci = boot_ci(diffs)
        sig = (ci[0] > 0) or (ci[1] < 0)
        big = abs(m) >= FLOOR
        res[name] = {'mean': m, 'ci': list(ci), 'sig': sig, 'ge_floor': big}
        print('  %-22s %+.5f  95%%CI [%+.5f, %+.5f]  %s%s'
              % (name, m, ci[0], ci[1],
                 ('유의' if sig else '유의하지 않음'),
                 ('' if big else '  (FLOOR %.3f 미만)' % FLOOR), ))
        return res[name]

    print('\n주효과 — 양수면 그 축을 올리는 쪽이 regret 이 낮다')
    for uu in (FX.U_LO, FX.U_HI):
        emit('dR(u=%.2f)' % uu,
             contrast(rows, 'cell', (FX.A_LO, uu), (FX.A_HI, uu)))
    for aa in (FX.A_LO, FX.A_HI):
        emit('dU(a=%.2f)' % aa,
             contrast(rows, 'cell', (aa, FX.U_LO), (aa, FX.U_HI)))
    emit('INT',
         [x - y for x, y in zip(
             contrast(rows, 'cell', (FX.A_LO, FX.U_HI), (FX.A_HI, FX.U_HI)),
             contrast(rows, 'cell', (FX.A_LO, FX.U_LO), (FX.A_HI, FX.U_LO)))])

    print('\n표본 크기별 dR (사전 방향 예측: n=40 에서 더 크다. 게이트 아님)')
    for key, nm in (('small', 'n=6'), ('large', 'n=40')):
        for uu in (FX.U_LO, FX.U_HI):
            emit('dR[%s](u=%.2f)' % (nm, uu),
                 contrast(rows, key, (FX.A_LO, uu), (FX.A_HI, uu)))

    print('\nU 사다리 (서술용 — 판정에 쓰지 않는다)')
    print('%-12s %s' % ('', '  '.join('u=%.1f' % u for u in FX.U_LADDER)))
    for aa, nm in ((FX.A_LO, 'LOW_READ'), (FX.A_HI, 'HIGH_READ')):
        print('%-12s %s' % (nm, '  '.join(
            '%.4f' % float(np.mean([r['cell'][(aa, u)] for r in rows]))
            for u in FX.U_LADDER)))
        res['ladder_%s' % nm] = [
            float(np.mean([r['cell'][(aa, u)] for r in rows]))
            for u in FX.U_LADDER]
    for aa, nm in ((FX.A_LO, 'LOW_READ'), (FX.A_HI, 'HIGH_READ')):
        res['rate_%s' % nm] = [
            float(np.mean([r['rate'][(aa, u)] for r in rows]))
            for u in FX.U_LADDER]
    print('%-12s %s' % ('콜 비율', '  '.join(
        '%.3f' % v for v in res['rate_HIGH_READ'])))

    print('\n상쇄 가설 (사전등록 6절)')
    d_cancel = contrast(rows, 'cell', (FX.A_HI, FX.U_HI), (FX.A_LO, FX.U_LO))
    c = emit('g[HI][HI] - g[LO][LO]', d_cancel)
    dr_hi = res['dR(u=%.2f)' % FX.U_HI]
    du_hi = res['dU(a=%.2f)' % FX.A_HI]
    cancel = (dr_hi['sig'] and dr_hi['mean'] >= FLOOR
              and du_hi['mean'] <= -FLOOR and du_hi['sig']
              and abs(c['mean']) < FLOOR and not c['sig'])
    res['cancel'] = 'CANCEL_SUPPORTED' if cancel else 'CANCEL_NOT_SUPPORTED'
    print('  -> %s' % res['cancel'])
    out[label] = res
    return res


def verdict(a, b):
    """사전등록 5절. OK 는 두 집합 모두에서 성립해야 한다."""
    def ok(name):
        return all(s[name]['sig'] and s[name]['mean'] >= FLOOR for s in (a, b))

    def ok_abs(name):
        return all(s[name]['sig'] and abs(s[name]['mean']) >= FLOOR
                   for s in (a, b))
    r_lo = ok('dR(u=%.2f)' % FX.U_LO)
    r_hi = ok('dR(u=%.2f)' % FX.U_HI)
    if r_lo and r_hi:
        return 'READ_ABILITY_JUSTIFIED', (r_lo, r_hi)
    if r_hi:
        return 'READ_ONLY_IN_INTERACTION', (r_lo, r_hi)
    # R3 은 사전등록 문구가 "dR 이 **어느 u 에서도** 불충족" 이다.
    # 처음 구현은 이 조건을 빠뜨려서 r_lo=True, r_hi=False 일 때
    # USE_DOMINATES 를 냈다. 사전등록 쪽이 기준이므로 코드를 고친다.
    if (not r_lo) and (not r_hi) and any(
            ok_abs('dU(a=%.2f)' % x) for x in (FX.A_LO, FX.A_HI)):
        return 'USE_DOMINATES', (r_lo, r_hi)
    return 'NO_CAUSAL_READ_EFFECT', (r_lo, r_hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set-a', default='940001-940010')
    ap.add_argument('--set-b', default='950001-950010')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--out', default='')
    ap.add_argument('--from-json', default='',
                    help='이미 저장된 결과에서 판정만 다시 낸다')
    a = ap.parse_args()

    if a.from_json:
        d = json.load(open(a.from_json, encoding='utf-8'))
        ks = sorted(k for k in d if k.startswith('SET_'))
        v, flags = verdict(d[ks[0]], d[ks[1]])
        print('%s / %s' % (ks[0], ks[1]))
        for nm in ('dR(u=%.2f)' % FX.U_LO, 'dR(u=%.2f)' % FX.U_HI,
                   'dU(a=%.2f)' % FX.A_LO, 'dU(a=%.2f)' % FX.A_HI, 'INT'):
            print('  %-14s A %+.5f [%+.5f,%+.5f]  B %+.5f [%+.5f,%+.5f]'
                  % (nm, d[ks[0]][nm]['mean'], d[ks[0]][nm]['ci'][0],
                     d[ks[0]][nm]['ci'][1], d[ks[1]][nm]['mean'],
                     d[ks[1]][nm]['ci'][0], d[ks[1]][nm]['ci'][1]))
        print('OK(dR u_lo) %s   OK(dR u_hi) %s' % flags)
        print('판정: %s' % v)
        if d.get('verdict') and d['verdict'] != v:
            print('(저장된 판정 %s 는 수정 전 규칙 구현에서 나온 값이다)'
                  % d['verdict'])
        d['verdict'] = v
        json.dump(d, open(a.from_json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True, default=str)
        return 0

    states = FX.build_states()
    evs = {s.sid: s.ev_actions() for s in states}
    spread = [max(v.values()) - min(v.values()) for v in evs.values()]
    print('상태 %d   EV 격차(팟 대비) mean %.4f sd %.4f'
          % (len(states), float(np.mean(spread)), float(np.std(spread))))

    def span(t):
        lo, hi = (int(x) for x in t.split('-'))
        return range(lo, hi + 1)

    out = {}
    ra = report(run_profiles(IV.base_profiles(span(a.set_a), a.entries, a.n),
                             states, evs), 'SET_A %s' % a.set_a, out)
    rb = report(run_profiles(IV.base_profiles(span(a.set_b), a.entries, a.n),
                             states, evs), 'SET_B %s' % a.set_b, out)
    v, flags = verdict(ra, rb)
    print('\n========== 판정: %s ==========' % v)
    print('OK(dR(u=%.2f)) %s   OK(dR(u=%.2f)) %s'
          % (FX.U_LO, flags[0], FX.U_HI, flags[1]))
    out['verdict'] = v
    out['floor'] = FLOOR
    out['ev_spread_mean'] = float(np.mean(spread))
    out['n_states'] = len(states)
    if a.out:
        json.dump(out, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True, default=str)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
