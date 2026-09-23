#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QX_EV_VALIDATION — QX 와 실제 chip regret 의 연결. 읽기 전용.

사전등록 QX_EV_VALIDATION_PREREG.md 5·6·7절.
production 무수정. 새 concept 추가 없음.
"""
from __future__ import print_function

import argparse
import copy
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

import fieldsim as FS
import persona as PS
import qx_ev_fixture as FX
import tier5_axis_validate as T5
import tier5_estimate_battery as ES
import v7_num_battery as B
import v7_num_intervention as IV

CELLS = (('READ', 'D'), ('READ', 'A'), ('GEN', 'D'), ('GEN', 'A'))


def pear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def partial(x, y, ctrl):
    X = np.column_stack([np.asarray(ctrl, float), np.ones(len(x))])
    def res(v):
        v = np.asarray(v, float)
        b, *_ = np.linalg.lstsq(X, v, rcond=None)
        return v - X @ b
    return pear(res(x), res(y))


def profile_row(prof, states, evs):
    reg = {c: [] for c in CELLS}
    reg_n = {'small': [], 'large': []}
    for s in states:
        mix, _ = FX.bot_action(s, prof, random.Random(FX.FIX_SEED + s.sid))
        r = FX.regret_of(s, mix, evs[s.sid])
        reg[(s.group, s.channel)].append(r)
        if s.group == 'READ':
            reg_n['small' if s.n_obs <= 6 else 'large'].append(r)
    row = {c[0] + '_' + c[1]: float(np.mean(v)) for c, v in reg.items()}
    row['READ_all'] = float(np.mean(reg[('READ', 'D')] + reg[('READ', 'A')]))
    row['GEN_all'] = float(np.mean(reg[('GEN', 'D')] + reg[('GEN', 'A')]))
    row['READ_smalln'] = float(np.mean(reg_n['small']))
    row['READ_largen'] = float(np.mean(reg_n['large']))
    row['QX_E'] = B.evaluate(prof)['QX_E']
    row['QX_S'] = ES.evaluate(prof)['QX_S']
    row['overall'] = float(np.mean([PS.sk(prof, c) for c in PS.CALC]))
    return row


def collect(seeds, entries, n, states, evs):
    profs = IV.base_profiles(seeds, entries, n)
    return [profile_row(p, states, evs) for p in profs], profs


def report_set(rows, label):
    print('\n=== %s (n=%d) ===' % (label, len(rows)))
    print('regret (팟 대비) 평균  ' + '  '.join(
        '%s %.4f' % (k, float(np.mean([r[k] for r in rows])))
        for k in ('READ_all', 'GEN_all', 'READ_smalln', 'READ_largen')))
    print('%-10s %10s %10s %10s %10s %10s'
          % ('QX', 'READ_all', 'READ_D', 'READ_A', 'GEN_all', 'partial(READ)'))
    out = {}
    for qx in ('QX_E', 'QX_S'):
        x = [r[qx] for r in rows]
        ctrl = [r['overall'] for r in rows]
        vals = {}
        for k in ('READ_all', 'READ_D', 'READ_A', 'GEN_all'):
            vals[k] = pear(x, [-r[k] for r in rows])
        pr = partial(x, [-r['READ_all'] for r in rows], ctrl)
        vals['partial_READ'] = pr
        vals['READ_smalln'] = pear(x, [-r['READ_smalln'] for r in rows])
        vals['READ_largen'] = pear(x, [-r['READ_largen'] for r in rows])
        out[qx] = vals
        print('%-10s %+10.4f %+10.4f %+10.4f %+10.4f %+10.4f'
              % (qx, vals['READ_all'], vals['READ_D'], vals['READ_A'],
                 vals['GEN_all'], pr))
    print('%-10s %10s %10s' % ('', 'READ n=6', 'READ n=40'))
    for qx in ('QX_E', 'QX_S'):
        print('%-10s %+10.4f %+10.4f'
              % (qx, out[qx]['READ_smalln'], out[qx]['READ_largen']))
    # 사분위 분할
    for qx in ('QX_E', 'QX_S'):
        x = np.asarray([r[qx] for r in rows])
        y = np.asarray([r['READ_all'] for r in rows])
        lo, hi = np.percentile(x, 25), np.percentile(x, 75)
        a, b = y[x <= lo].mean(), y[x >= hi].mean()
        out[qx]['q_low_regret'] = float(a)
        out[qx]['q_high_regret'] = float(b)
        print('  %s 하위25%% regret %.4f  vs  상위25%% %.4f   (차이 %+.4f)'
              % (qx, a, b, b - a))
    return out


def synth_control(profs, states, evs):
    ca, pi = [], []
    for prof in profs:
        c_only, p_only = T5.make_arms(prof)
        for prof2, acc in ((c_only, ca), (p_only, pi)):
            reg = [FX.regret_of(s, FX.bot_action(
                s, prof2, random.Random(FX.FIX_SEED + s.sid))[0], evs[s.sid])
                for s in states if s.group == 'READ']
            acc.append(float(np.mean(reg)))
    d = [x - y for x, y in zip(ca, pi)]       # CALC − PIPE
    ci = IV.boot_ci(d)
    print('\n=== 합성 프로필 (READ, n=%d) ===' % len(profs))
    print('  CALC_ONLY regret %.4f   PIPE_ONLY regret %.4f'
          % (float(np.mean(ca)), float(np.mean(pi))))
    print('  차이 (CALC − PIPE) %+.4f  95%%CI [%+.4f, %+.4f]   %s'
          % (float(np.mean(d)), ci[0], ci[1],
             'PIPE 가 낫다' if ci[0] > 0 else
             ('CALC 가 낫다' if ci[1] < 0 else '유의하지 않다')))
    return {'calc_only': float(np.mean(ca)), 'pipe_only': float(np.mean(pi)),
            'diff': float(np.mean(d)), 'ci': ci}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fit', default='940001-940010')
    ap.add_argument('--holdout', default='950001-950010')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--synth-n', type=int, default=120)
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    states = FX.build_states()
    evs = {s.sid: s.ev_actions() for s in states}
    spread = [max(v.values()) - min(v.values()) for v in evs.values()]
    print('fixture: %d states, EV 격차 mean %.4f sd %.4f (팟 대비)'
          % (len(states), float(np.mean(spread)), float(np.std(spread))))

    def span(t):
        lo, hi = (int(x) for x in t.split('-'))
        return range(lo, hi + 1)

    fit_rows, fit_profs = collect(span(a.fit), a.entries, a.n, states, evs)
    hold_rows, _ = collect(span(a.holdout), a.entries, a.n, states, evs)
    r_fit = report_set(fit_rows, 'fit %s' % a.fit)
    r_hold = report_set(hold_rows, 'holdout %s' % a.holdout)
    syn = synth_control(fit_profs[:a.synth_n], states, evs)

    if a.out:
        json.dump({'fit': r_fit, 'holdout': r_hold, 'synth': syn,
                   'n_fit': len(fit_rows), 'n_hold': len(hold_rows),
                   'ev_spread_mean': float(np.mean(spread)),
                   'fit_regret': {k: float(np.mean([r[k] for r in fit_rows]))
                                  for k in ('READ_all', 'GEN_all',
                                            'READ_smalln', 'READ_largen')}},
                  open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('\nwrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
