#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_CALIB_V2 결과 그림. 읽기 전용 — 엔진을 건드리지 않는다.

calibration 덤프의 raw L/A/X 구름 위에 V1 중심과 V2 중심을 같이 찍고,
X 분포에서 MANIAC 영역이 얼마나 비어 있는지 보인다.
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

import style_params_v2 as SP

NAMES = SP.NAMES
SHORT = {'NIT': 'NIT', 'TAG': 'TAG', 'LAG': 'LAG', 'LOOSE_PASSIVE': 'LP',
         'TIGHT_PASSIVE': 'TP', 'MANIAC': 'MAN'}


def load(paths):
    pts = []
    for p in sorted(paths):
        d = json.load(open(p, encoding='utf-8'))
        if d.get('engine_errors'):
            continue
        for pr in d['pairs']:
            for w in ('w1', 'w2'):
                r = pr['raw'].get(w)
                if r and int(r.get('hands', 0)) >= 6:
                    pts.append((r['L'], r['A'], r['X']))
    return np.asarray(pts, dtype=float)


def panel(ax, P, i, j, v2, labels):
    ax.hexbin(P[:, i], P[:, j], gridsize=44, cmap='Blues', bins='log',
              mincnt=1, linewidths=0)
    for n in NAMES:
        c1 = SP.V1_CENTERS[n]
        c2 = v2['centers'][n]
        ax.plot(c1[i], c1[j], marker='x', ms=9, mew=2.2, color='#c62828', zorder=5)
        ax.plot(c2[i], c2[j], marker='o', ms=7, mfc='none', mew=2.2,
                color='#1b5e20', zorder=5)
        ax.annotate(SHORT[n], (c1[i], c1[j]), textcoords='offset points',
                    xytext=(6, 4), fontsize=7.5, color='#c62828')
        ax.annotate(SHORT[n], (c2[i], c2[j]), textcoords='offset points',
                    xytext=(6, -10), fontsize=7.5, color='#1b5e20')
    ax.set_xlabel(labels[i])
    ax.set_ylabel(labels[j])
    ax.set_xlim(0, 10.4)
    ax.set_ylim(0, 10.4)
    ax.grid(alpha=0.15, lw=0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dumps', nargs='+', required=True)
    ap.add_argument('--params', default='style_params_v2.json')
    ap.add_argument('--out', default='docs/STYLE_CALIB_V2.png')
    a = ap.parse_args()

    paths = []
    for g in a.dumps:
        paths.extend(glob.glob(g) if any(ch in g for ch in '*?[') else [g])
    P = load(paths)
    v2 = SP.load_params(a.params)
    labels = ('L  looseness', 'A  aggression', 'X  pressure extremeness')

    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.7))
    panel(axes[0], P, 0, 1, v2, labels)
    axes[0].set_title('L vs A  (n=%d raw windows)' % P.shape[0], fontsize=10)
    panel(axes[1], P, 1, 2, v2, labels)
    axes[1].set_title('A vs X', fontsize=10)

    ax = axes[2]
    ax.hist(P[:, 2], bins=np.linspace(1, 10, 55), color='#90a4ae', log=True)
    ax.axvline(8.0, color='#c62828', lw=1.8)
    ax.axvline(v2['centers']['MANIAC'][2], color='#1b5e20', lw=1.8, ls='--')
    ax.set_xlabel(labels[2])
    ax.set_ylabel('count (log)')
    ax.set_title('X  p99=%.2f  max=%.2f  P(X>=8)=%.3f%%'
                 % (np.percentile(P[:, 2], 99), P[:, 2].max(),
                    100.0 * (P[:, 2] >= 8).mean()), fontsize=10)
    ax.grid(alpha=0.15, lw=0.5)

    h = [plt.Line2D([], [], marker='x', ls='', color='#c62828', mew=2.2,
                    label='V1 center  (shipped SHADOW)'),
         plt.Line2D([], [], marker='o', ls='', mfc='none', color='#1b5e20',
                    mew=2.2, label='V2 center  (calibrated, frozen)')]
    fig.legend(handles=h, loc='lower center', ncol=2, frameon=False, fontsize=9)
    fig.suptitle('STYLE_CALIB_V2 — behavior-space clouds and style centers',
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    fig.savefig(a.out, dpi=150)
    print('wrote %s  (n=%d)' % (a.out, P.shape[0]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
