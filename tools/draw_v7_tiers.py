#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V7 구간 분포 그림. 읽기 전용.

왼쪽   구간 분포 — 400인 필드(검증 표본) vs 100인 필드
가운데 Q 분포와 적합된 c5
오른쪽 필드당 5단계 인원수 — 관측 vs 같은 평균의 포아송
"""
from __future__ import print_function

import argparse
import json
import math
import os
import sys
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import reads as RD
import v7_tier_population as POP

SHORT = ['1 NO_EXPLOIT', '2 IMPRESSION', '3 STYLE', '4 QUAL_REG', '5 QUANT']
CBAR = ['#b0bec5', '#90a4ae', '#5c9dd6', '#2e7d32', '#c62828']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--params', default='v7_tier_params.json')
    ap.add_argument('--q-seeds', default='870001-870020')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--extra-key', default='870001-870020:100')
    ap.add_argument('--out', default='docs/HIERARCHICAL_READ_V7_TIERS.png')
    a = ap.parse_args()

    par = json.load(open(a.params, encoding='utf-8'))
    c5 = par['c5']
    v400 = np.asarray(par['verify']['counts'], dtype=float)
    ex = par['extra'].get(a.extra_key)
    v100 = np.asarray(ex['counts'], dtype=float) if ex else None
    per = par['verify']['per_field_level5']

    qs = []
    for sd in POP.span(a.q_seeds):
        rows, _ = POP.draw(sd, a.entries)
        qs.extend(r['Q'] for r in rows)
    qs = np.asarray(qs)

    fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.8))

    ax = axes[0]
    x = np.arange(5)
    wdt = 0.38
    p400 = 100.0 * v400 / v400.sum()
    ax.bar(x - wdt / 2, p400, wdt, color=CBAR, edgecolor='white', linewidth=0.7,
           label='400-entry field')
    if v100 is not None:
        p100 = 100.0 * v100 / v100.sum()
        ax.bar(x + wdt / 2, p100, wdt, color=CBAR, alpha=0.45,
               edgecolor='#455a64', linewidth=0.9, hatch='//',
               label='100-entry field')
    for i in range(5):
        ax.annotate('%.2f%%' % p400[i], (i - wdt / 2, p400[i]), ha='center',
                    va='bottom', fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT, fontsize=8, rotation=18, ha='right')
    ax.set_ylabel('share of bots (%)')
    ax.set_title('tier distribution  (holdout seeds, hero excluded)', fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis='y', alpha=0.15, lw=0.5)

    ax = axes[1]
    ax.hist(qs, bins=np.linspace(0, 1, 61), color='#90a4ae', log=True)
    ax.axvline(c5, color='#c62828', lw=1.9)
    ax.annotate('c5 = %.4f' % c5, xy=(c5, 0.86), xycoords=('data', 'axes fraction'),
                xytext=(-8, 0), textcoords='offset points', ha='right',
                fontsize=9, color='#c62828')
    ax.set_xlabel('Q  =  E · num')
    ax.set_ylabel('bots (log)')
    ax.set_title('Q distribution and the single fitted cut\n'
                 'p50 %.3f · p99 %.3f · max %.3f'
                 % (np.percentile(qs, 50), np.percentile(qs, 99), qs.max()),
                 fontsize=10)
    ax.grid(alpha=0.15, lw=0.5)

    ax = axes[2]
    lam = float(np.mean(per))
    obs = Counter(per)
    ks = list(range(0, max(max(per), 8) + 1))
    ov = [obs.get(k, 0) for k in ks]
    pois = [len(per) * math.exp(-lam) * lam ** k / math.factorial(k) for k in ks]
    ax.bar(np.asarray(ks) - 0.19, ov, 0.38, color='#1e88e5', label='observed')
    ax.bar(np.asarray(ks) + 0.19, pois, 0.38, color='#bdbdbd',
           label='Poisson(λ=%.2f)' % lam)
    ax.set_ylim(0, max(max(ov), max(pois)) * 1.42)
    ax.axvspan(2.5, 4.5, color='#2e7d32', alpha=0.10)
    ax.annotate('target 3-4', xy=(3.5, 0.80), xycoords=('data', 'axes fraction'),
                ha='center', fontsize=9, color='#2e7d32')
    ax.set_xticks(ks)
    ax.set_xlabel('level-5 players per 400-entry field')
    ax.set_ylabel('fields')
    ax.set_title('per-field level-5 count  (%d holdout fields, mean %.2f)'
                 % (len(per), lam), fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='upper left')
    ax.grid(axis='y', alpha=0.15, lw=0.5)

    fig.suptitle('HIERARCHICAL_READ_V7 — exploit-capability tiers in the generated population',
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    fig.savefig(a.out, dpi=150)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
