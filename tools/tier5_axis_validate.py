#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TIER5_AXIS_DESIGN 소규모 검증. 읽기 전용.

사전등록 TIER5_AXIS_DESIGN_PREREG.md 3-1.

  control   음성 대조 프로필 분리 검정 (배터리 타당성 전제 검정)
  interv    consistency paired intervention
  partial   기존 population dump 에서 consistency 부분상관

새 concept 을 코드에 추가하지 않는다. production 무수정.
"""
from __future__ import print_function

import argparse
import copy
import glob
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
import v7_num_battery as B
import v7_num_intervention as IV

# 사전등록 1절 매핑 결과
PIPE_CONCEPTS = ('range_read', 'sizing_tell')                 # prof['concepts']
PIPE_TEMPER = ('attention', 'adaptability', 'consistency')    # prof['temper']
APPLY_ONLY_CALC = tuple(c for c in PS.CALC if c not in PIPE_CONCEPTS)
HI, LO = 9.0, 2.0


def base_profiles(seeds, entries, k):
    return IV.base_profiles(seeds, entries, k)


def mutate(prof, concepts=None, tempers=None):
    q = copy.deepcopy(prof)
    for k, v in (concepts or {}).items():
        q['concepts'][k] = float(v)
    for k, v in (tempers or {}).items():
        q['temper'][k] = float(v)
    return q


def make_arms(prof):
    calc_only = mutate(
        prof,
        concepts=dict([(c, HI) for c in APPLY_ONLY_CALC] +
                      [(c, LO) for c in PIPE_CONCEPTS]),
        tempers=dict((t, LO) for t in PIPE_TEMPER))
    pipe_only = mutate(
        prof,
        concepts=dict([(c, LO) for c in APPLY_ONLY_CALC] +
                      [(c, HI) for c in PIPE_CONCEPTS]),
        tempers=dict((t, HI) for t in PIPE_TEMPER))
    return calc_only, pipe_only


def run_control(profs):
    a, b, la, lb = [], [], [], []
    for prof in profs:
        c_only, p_only = make_arms(prof)
        ea, eb = B.evaluate(c_only), B.evaluate(p_only)
        a.append(ea['QX_E'])
        b.append(eb['QX_E'])
        la.append(ea['QX_G'])
        lb.append(eb['QX_G'])
    d = [y - x for x, y in zip(a, b)]
    ci = IV.boot_ci(d)
    print('음성 대조 프로필 분리 검정  (n=%d)' % len(profs))
    print('  CALC_ONLY  QX_E %.4f   QX_G %.4f   '
          '(APPLY 전용 CALC %d개=9.0, 파이프라인 5축=2.0)'
          % (float(np.mean(a)), float(np.mean(la)), len(APPLY_ONLY_CALC)))
    print('  PIPE_ONLY  QX_E %.4f   QX_G %.4f   (반대)'
          % (float(np.mean(b)), float(np.mean(lb))))
    print('  차이(PIPE − CALC) QX_E %+.4f  95%%CI [%+.4f, %+.4f]'
          % (float(np.mean(d)), ci[0], ci[1]))
    ok = abs(float(np.mean(d))) >= 0.05 and (ci[0] > 0 or ci[1] < 0)
    print('  전제 검정: %s' % ('통과 — 배터리가 두 능력을 구분한다' if ok
                             else '실패 — 구분 못 한다'))
    return {'calc_only': float(np.mean(a)), 'pipe_only': float(np.mean(b)),
            'calc_only_G': float(np.mean(la)), 'pipe_only_G': float(np.mean(lb)),
            'diff': float(np.mean(d)), 'ci': ci, 'pass': bool(ok),
            'n': len(profs)}


def run_interv(profs, axis='consistency'):
    dE, dG, chg, dl = [], [], [], []
    for prof in profs:
        lo = mutate(prof, tempers={axis: 2.0})
        hi = mutate(prof, tempers={axis: 8.0})
        a, b = B.evaluate(lo), B.evaluate(hi)
        dE.append(b['QX_E'] - a['QX_E'])
        dG.append(b['QX_G'] - a['QX_G'])
        dl.append(b['level'] - a['level'])
        v1, v2 = a['vector'], b['vector']
        chg.append(sum(1 for x, y in zip(v1, v2) if x != y) / float(len(v1)))
    ciE, ciG = IV.boot_ci(dE), IV.boot_ci(dG)
    print('\n%s paired intervention (2.0 -> 8.0, n=%d)' % (axis, len(profs)))
    print('  dE %+.4f  95%%CI [%+.4f, %+.4f]' % (float(np.mean(dE)), ciE[0], ciE[1]))
    print('  dG %+.4f  95%%CI [%+.4f, %+.4f]' % (float(np.mean(dG)), ciG[0], ciG[1]))
    print('  dlevel %+.4f   응답변화 %.1f%%'
          % (float(np.mean(dl)), 100.0 * float(np.mean(chg))))
    return {'axis': axis, 'dE': float(np.mean(dE)), 'dE_ci': ciE,
            'dG': float(np.mean(dG)), 'dG_ci': ciG,
            'd_level': float(np.mean(dl)),
            'frac_response_changed': float(np.mean(chg)), 'n': len(profs)}


def run_partial(pop_glob, axis='consistency'):
    rows = []
    for p in sorted(glob.glob(pop_glob)):
        d = json.load(open(p, encoding='utf-8'))
        f = FS.Field(entries=d['entries'], seed=d['seed'], fmt='standard')
        for r in d['rows']:
            prof = f.players[r['pid']]['prof']
            r[axis] = PS.temper(prof, axis, 5.0)
            rows.append(r)
    E = ('see_freq', 'see_line', 'see_size', 'use')
    X = np.column_stack([[r[k] for r in rows] for k in E] + [np.ones(len(rows))])

    def resid(v):
        v = np.asarray(v, float)
        b, *_ = np.linalg.lstsq(X, v, rcond=None)
        return v - X @ b

    def pear(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        return 0.0 if x.std() < 1e-12 or y.std() < 1e-12 else float(np.corrcoef(x, y)[0, 1])

    y = [r['QX_E'] for r in rows]
    r_raw = pear([r[axis] for r in rows], y)
    r_par = pear(resid([r[axis] for r in rows]), resid(y))
    print('\n%s 자연 population (n=%d):  r(QX_E) %+.4f   partial(E 통제) %+.4f'
          % (axis, len(rows), r_raw, r_par))
    return {'axis': axis, 'n': len(rows), 'r': r_raw, 'partial': r_par}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='910001-910004')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--pop-glob', default='')
    ap.add_argument('--mode', default='all',
                    choices=['all', 'control', 'interv', 'partial'])
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))
    out = {}
    if a.mode in ('all', 'control', 'interv'):
        profs = base_profiles(range(lo, hi + 1), a.entries, a.n)
        print('기저 프로필 %d개 (시드 %s, entries %d)' % (len(profs), a.seeds, a.entries))
        if a.mode in ('all', 'control'):
            out['control'] = run_control(profs)
        if a.mode in ('all', 'interv'):
            out['intervention'] = run_interv(profs)
    if a.mode in ('all', 'partial') and a.pop_glob:
        out['partial'] = run_partial(a.pop_glob)
    if a.out:
        json.dump(out, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('\nwrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
