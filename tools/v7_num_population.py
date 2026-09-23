#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NUMERIC_BUNDLE_V7 자연 population 검증. 읽기 전용.

사전등록 3-B · 5절. Q 와 tier 를 쓰지 않는다. 각 봇의 자연 concept 값으로
독립 배터리 점수 QX_E 를 직접 재고, concept 들이 그것을 얼마나 설명하는지 본다.
**parameter fitting 을 하지 않는다** — 상관·부분상관과 사전 지정 조합 비교만.

  dump   시드별 봇 표본의 QX_E / QX_G / concept / E 입력을 떨군다
  report fit 집합에서 상관, holdout 에서 사전 지정 조합 비교
"""
from __future__ import print_function

import argparse
import glob
import json
import math
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
import reads as RD
import v7_num_battery as B

NUM = list(RD.TIER_V7_NUMERIC)
E_INPUTS = ('see_freq', 'see_line', 'see_size', 'use')
DIRECT = ('range_read', 'fold_equity')            # 사전등록 1-1
SUPPORT = ('potodds', 'spr', 'blocker', 'board_texture')


def dump(seed, entries, per_field, out):
    f = FS.Field(entries=entries, seed=seed, fmt='standard')
    ids = [pid for pid in sorted(f.players) if pid != 0
           and f.players[pid].get('prof', {}).get('concepts')]
    rng = random.Random(B.SEED + seed)
    ids = sorted(rng.sample(ids, min(per_field, len(ids))))
    rows = []
    for pid in ids:
        prof = f.players[pid]['prof']
        ev = B.evaluate(prof)
        res = PS.read_resolution(prof)
        row = {'seed': seed, 'pid': pid,
               'QX_E': ev['QX_E'], 'QX_G': ev['QX_G'],
               'families': ev['families']}
        for c in NUM + ['sizing_tell']:
            row[c] = PS.sk(prof, c)
        for k in E_INPUTS:
            row[k] = res[k]
        row['overall'] = float(np.mean([PS.sk(prof, c) for c in PS.CALC]))
        rows.append(row)
    json.dump({'seed': seed, 'entries': entries, 'rows': rows},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('seed %d: %d bots -> %s' % (seed, len(rows), out))


def load(pat):
    rows = []
    for p in sorted(glob.glob(pat)):
        rows.extend(json.load(open(p, encoding='utf-8'))['rows'])
    return rows


def col(rows, k):
    return np.asarray([float(r[k]) for r in rows])


def pear(x, y):
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def partial(rows, c, y_key='QX_E'):
    """E 의 입력 넷을 통제한 부분상관."""
    X = np.column_stack([col(rows, k) for k in E_INPUTS] +
                        [np.ones(len(rows))])
    def resid(v):
        beta, *_ = np.linalg.lstsq(X, v, rcond=None)
        return v - X @ beta
    return pear(resid(col(rows, c)), resid(col(rows, y_key)))


def num_of(rows, keys):
    if not keys:
        return np.zeros(len(rows))
    return np.mean(np.column_stack([col(rows, k) / 10.0 for k in keys]), axis=1)


def report(fit_rows, hold_rows):
    print('fit %d bots   holdout %d bots' % (len(fit_rows), len(hold_rows)))
    y = col(fit_rows, 'QX_E')
    yg = col(fit_rows, 'QX_G')
    print('\n=== fit: concept 과 독립 점수의 관계 ===')
    print('%-14s %8s %8s %10s' % ('concept', 'r(QX_E)', 'r(QX_G)', 'partial_E'))
    for c in NUM + ['sizing_tell']:
        x = col(fit_rows, c)
        print('%-14s %+8.4f %+8.4f %+10.4f'
              % (c, pear(x, y), pear(x, yg), partial(fit_rows, c)))
    print('%-14s %+8.4f %+8.4f %10s'
          % ('overall(CALC)', pear(col(fit_rows, 'overall'), y),
             pear(col(fit_rows, 'overall'), yg), '-'))
    for k in E_INPUTS:
        print('%-14s %+8.4f %+8.4f %10s'
              % ('E:' + k, pear(col(fit_rows, k), y), pear(col(fit_rows, k), yg), '-'))

    schemes = [('current equal-6', NUM)]
    for c in NUM:
        schemes.append(('LOO -%s' % c, [k for k in NUM if k != c]))
    for c in NUM:
        schemes.append(('single %s' % c, [c]))
    schemes.append(('DIRECT bundle', list(DIRECT)))
    schemes.append(('SUPPORT bundle', list(SUPPORT)))
    schemes.append(('current + sizing_tell', NUM + ['sizing_tell']))

    print('\n=== holdout: 사전 지정 조합의 num 과 QX_E 의 상관 (적합 없음) ===')
    yh = col(hold_rows, 'QX_E')
    ygh = col(hold_rows, 'QX_G')
    out = []
    for name, keys in schemes:
        v = num_of(hold_rows, keys)
        out.append((name, pear(v, yh), pear(v, ygh)))
    base = [o for o in out if o[0] == 'current equal-6'][0][1]
    for name, r, rg in out:
        mark = ''
        if name != 'current equal-6':
            mark = '  (현재 대비 %+.4f)' % (r - base)
        print('  %-24s r(QX_E) %+.4f   r(QX_G) %+.4f%s' % (name, r, rg, mark))

    print('\n=== 구조 점검 (holdout) ===')
    cur = num_of(hold_rows, NUM)
    mx = np.max(np.column_stack([col(hold_rows, c) for c in NUM]), axis=1)
    mn = np.min(np.column_stack([col(hold_rows, c) for c in NUM]), axis=1)
    print('  r(num, max concept) %+.4f   r(num, min concept) %+.4f' %
          (pear(cur, mx), pear(cur, mn)))
    ov = col(hold_rows, 'overall')
    print('  r(num, overall CALC) %+.4f   vs   r(num, QX_E) %+.4f' %
          (pear(cur, ov), pear(cur, yh)))
    print('  r(QX_E, QX_G) %+.4f' % pear(yh, ygh))
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_argument_group()
    ap.add_argument('--dump-seed', type=int)
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--per-field', type=int, default=50)
    ap.add_argument('--out', default='')
    ap.add_argument('--fit-glob', default='')
    ap.add_argument('--holdout-glob', default='')
    a = ap.parse_args()
    if a.dump_seed:
        dump(a.dump_seed, a.entries, a.per_field, a.out)
        return 0
    fit = load(a.fit_glob)
    hold = load(a.holdout_glob)
    res = report(fit, hold)
    if a.out:
        json.dump({'schemes': res, 'n_fit': len(fit), 'n_hold': len(hold)},
                  open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
