#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V6 결과 그림. 읽기 전용.

왼쪽   CF 가 실제로 쓴 bin 축(detail_access)에서의 층 비중 — freq 의 MID trait 역전
가운데 같은 모집단을 각 채널 자신의 a 로 bin 했을 때 — 세 축 전부 정상
오른쪽 seed 850006 최초 divergence 를 낸 결정의 층별 기여 vs production
"""
from __future__ import print_function

import argparse
import glob
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import fieldsim as FS
import persona as PS
import reads as RD

BINS = ('LOW', 'MID', 'HIGH')
AX = ('freq', 'line', 'size')
LY = ('coarse', 'trait', 'detail')
COL = {'coarse': '#8d6e63', 'trait': '#1e88e5', 'detail': '#43a047'}


def cf_pooled(paths):
    recs = []
    for p in sorted(paths):
        for line in open(p, encoding='utf-8'):
            if line.startswith('V6_CF_JSON='):
                recs.append(json.loads(line.split('=', 1)[1]))
    out = {}
    for b in BINS:
        for ax in AX:
            num = {ly: 0.0 for ly in LY}
            den = 0
            for r in recs:
                bb = r['read_stats']['by_bin'][b]
                c = bb['calls']
                if not c:
                    continue
                den += c
                for ly in LY:
                    num[ly] += bb['axis'][ax][ly] * c
            out[(b, ax)] = {ly: (num[ly] / den if den else 0.0) for ly in LY}
    return out, len(recs)


def own_axis_pooled(lo, hi, entries):
    rows = []
    for sd in range(lo, hi + 1):
        f = FS.Field(entries=entries, seed=sd, fmt='standard')
        for p in f.players.values():
            prof = p.get('prof')
            if prof:
                r = PS.read_resolution(prof)
                rows.append((r['see_freq'], r['see_line'], r['see_size']))
    out = {}
    for i, ax in enumerate(AX):
        for b in BINS:
            sel = [r[i] for r in rows
                   if ('LOW' if r[i] < .34 else ('MID' if r[i] < .67 else 'HIGH')) == b]
            if not sel:
                out[(b, ax)] = {ly: 0.0 for ly in LY}
                continue
            out[(b, ax)] = {
                'coarse': float(np.mean([(1 - a) ** 2 for a in sel])),
                'trait': float(np.mean([2 * a * (1 - a) for a in sel])),
                'detail': float(np.mean([a ** 2 for a in sel])),
            }
    return out, len(rows)


def grouped(ax, data, title, note=None):
    x = np.arange(len(AX) * len(BINS))
    labels = []
    bottom = np.zeros(len(x))
    vals = {ly: [] for ly in LY}
    for a in AX:
        for b in BINS:
            labels.append('%s\n%s' % (a, b))
            for ly in LY:
                vals[ly].append(data[(b, a)][ly])
    for ly in LY:
        v = np.asarray(vals[ly])
        ax.bar(x, v, bottom=bottom, color=COL[ly], label=ly, width=0.72,
               edgecolor='white', linewidth=0.6)
        bottom += v
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel('source weight (sums to 1)')
    ax.set_title(title + (('\n' + note) if note else '\n'), fontsize=10,
                 color='#212121')
    for i in (2.5, 5.5):
        ax.axvline(i, color='#9e9e9e', lw=0.8, ls=':')
    ax.grid(axis='y', alpha=0.15, lw=0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cf-glob', required=True,
                    help="CF stdout 파일 glob (V6_CF_JSON= 줄 포함)")
    ap.add_argument('--probe', required=True, help='probe13.json')
    ap.add_argument('--seeds', default='850001-850012')
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--out', default='docs/HIERARCHICAL_READ_V6.png')
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))

    cf, n_seed = cf_pooled(glob.glob(a.cf_glob))
    own, n_obs = own_axis_pooled(lo, hi, a.entries)

    pr = json.load(open(a.probe, encoding='utf-8'))
    s3 = [x for x in pr['probes']['v6']
          if x['log_len'] == 13 and x['observer_seat'] == '3'][0]
    sw, ls = s3['source_weights'], s3['layer_sources']
    keys = [('passive', 'freq'), ('open_gap', 'freq'), ('fold_gap', 'freq'),
            ('size_info', 'size'), ('size_gap', 'size'), ('size_big', 'size')]

    fig, axes = plt.subplots(1, 3, figsize=(16.2, 5.0))
    grouped(axes[0], cf,
            'CF as measured — binned by detail_access  (%d seeds)' % n_seed,
            note='freq: MID trait < LOW trait')
    grouped(axes[1], own,
            "same population — binned by each channel's own a  (%d observers)" % n_obs)

    ax = axes[2]
    y = np.arange(len(keys))
    left = np.zeros(len(keys))
    for ly in LY:
        v = np.asarray([ls[ly].get(k, 0.0) * sw[axn][ly] for k, axn in keys])
        ax.barh(y, v, left=left, color=COL[ly], label=ly, height=0.55,
                edgecolor='white', linewidth=0.6)
        left += v
    ctl = [s3['control'][k] for k, _ in keys]
    ax.plot(ctl, y, marker='D', ls='', ms=7, color='#c62828', zorder=5,
            label='production value')
    ax.set_yticks(y)
    ax.set_yticklabels(['%s\n(%s)' % (k, axn) for k, axn in keys], fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color='#616161', lw=0.8)
    ax.set_xlabel('read value  (stacked = V6 layer contribution)')
    ax.set_title('seed 850006 h13 e14 — the read that flipped turn call to fold\n'
                 'seat 3, see_freq≈0.05, coarse_top=%s' % s3['coarse_top'],
                 fontsize=10)
    ax.grid(axis='x', alpha=0.15, lw=0.5)
    ax.legend(fontsize=8, loc='upper right', frameon=True, framealpha=0.92,
              edgecolor='#e0e0e0')
    ax.set_xlim(min(-0.09, min(ctl) - 0.04), max(0.46, max(ctl) + 0.05))

    h, lb = axes[0].get_legend_handles_labels()
    fig.legend(h, lb, fontsize=9, ncol=3, loc='lower left',
               bbox_to_anchor=(0.03, 0.005), frameon=False)
    fig.suptitle('HIERARCHICAL_READ_V6 — source-weight separation and the first divergence',
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.055, 1, 0.91))
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    fig.savefig(a.out, dpi=150)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
