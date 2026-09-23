#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V7 반사실 그림. 읽기 전용.

왼쪽   구간별 read 호출 비중과 평균 채널 크기 (주 100인 / 보조 400인)
가운데 n 이 쌓일 때 evidence 비중(data)과 채널 크기 — 증거가 prior 를 덮는다
오른쪽 주 반사실의 시드별 독립 원인 vs 연쇄 엔트리
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

NB = ('n<6', '6-11', '12-29', 'n>=30')
NAMES = ['1 NO_EXPLOIT', '2 IMPRESSION', '3 STYLE', '4 QUAL_REG', '5 QUANT']
CBAR = ['#b0bec5', '#90a4ae', '#5c9dd6', '#2e7d32', '#c62828']


def load(pat):
    recs = []
    for p in sorted(glob.glob(pat)):
        for line in open(p, encoding='utf-8'):
            if line.startswith('V7_CF_JSON='):
                recs.append(json.loads(line.split('=', 1)[1]))
    return sorted(recs, key=lambda r: r['seed'])


def agg(recs):
    calls = np.zeros(5)
    mag = np.zeros(5)
    bn = {t: [[0, 0.0, 0.0] for _ in NB] for t in (4, 5)}
    for r in recs:
        for t, st in r['tier_stats'].items():
            i = int(t) - 1
            calls[i] += st['calls']
            mag[i] += st['sum_mag']
            if int(t) in bn:
                for j, b in enumerate(st['by_n']):
                    bn[int(t)][j][0] += b['calls']
                    bn[int(t)][j][1] += b['sum_data']
                    bn[int(t)][j][2] += b['sum_mag']
    mean_mag = np.where(calls > 0, mag / np.maximum(calls, 1), np.nan)
    share = 100.0 * calls / max(1.0, calls.sum())
    return calls, share, mean_mag, bn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main', required=True)
    ap.add_argument('--supp', required=True)
    ap.add_argument('--out', default='docs/HIERARCHICAL_READ_V7.png')
    a = ap.parse_args()

    m, s_ = load(a.main), load(a.supp)
    mc, ms, mm, mbn = agg(m)
    sc, ss, sm, sbn = agg(s_)

    fig, axes = plt.subplots(1, 3, figsize=(16.0, 5.0))

    ax = axes[0]
    x = np.arange(5)
    ax.bar(x - 0.19, ms, 0.38, color=CBAR, edgecolor='white', linewidth=0.7,
           label='calls, 100-entry (main)')
    ax.bar(x + 0.19, ss, 0.38, color=CBAR, alpha=0.45, hatch='//',
           edgecolor='#455a64', linewidth=0.9, label='calls, 400-entry (supp)')
    ax.set_xticks(x)
    ax.set_xticklabels(NAMES, fontsize=8, rotation=18, ha='right')
    ax.set_ylabel('share of read calls (%)')
    ax.set_ylim(0, 58)
    ax2 = ax.twinx()
    ax2.plot(x, mm, marker='o', color='#37474f', lw=1.8, ms=6,
             label='mean Σ|channel| (main)')
    ax2.plot(x, sm, marker='s', ls='--', color='#7e57c2', lw=1.6, ms=5,
             label='mean Σ|channel| (supp)')
    ax2.set_ylabel('mean Σ|channel| per call')
    ax2.set_ylim(0, 1.35)
    ax.annotate('w>0 in 0 of %d calls' % int(mc[0]), xy=(0.30, ms[0]),
                xytext=(0, 7), textcoords='offset points', ha='left',
                fontsize=7.5, color='#c62828')
    ax.annotate('0 calls\nin main run', xy=(4, 1.5), ha='center',
                fontsize=7.5, color='#c62828')
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7.5, loc='upper right', frameon=False)
    ax.set_title('tier share of read calls, and read magnitude', fontsize=10)
    ax.grid(axis='y', alpha=0.15, lw=0.5)

    ax = axes[1]
    xs = np.arange(len(NB))
    for tier, style, col in ((4, '-', '#2e7d32'), (5, '--', '#c62828')):
        for src, bn, mk in (('main', mbn, 'o'), ('supp', sbn, 's')):
            d = [(b[1] / b[0]) if b[0] else np.nan for b in bn[tier]]
            if all(np.isnan(v) for v in d):
                continue
            ax.plot(xs, d, style, marker=mk, color=col, lw=1.7, ms=6,
                    alpha=1.0 if src == 'main' else 0.55,
                    label='tier %d (%s)' % (tier, src))
    ax.set_xticks(xs)
    ax.set_xticklabels(NB)
    ax.set_xlabel('observations on that opponent (n)')
    ax.set_ylabel('mean data  =  evidence weight')
    ax.set_ylim(0, 1.05)
    ax.set_title('evidence overrides the style prior as n grows\n'
                 'out = (1−data)·s·PRIOR + data·EVIDENCE', fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='upper left')
    ax.grid(alpha=0.15, lw=0.5)

    ax = axes[2]
    seeds = [r['seed'] for r in m]
    ind = np.asarray([r['independent_entries'] for r in m], dtype=float)
    ch = np.asarray([r['chain_entries'] for r in m], dtype=float)
    y = np.arange(len(seeds))
    ax.barh(y, ind, color='#1e88e5', label='independent cause')
    ax.barh(y, ch, left=ind, color='#bdbdbd', label='chain')
    ax.set_yticks(y)
    ax.set_yticklabels([str(s) for s in seeds], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('diverging log entries')
    ax.set_title('main run: %d entries = %d independent + %d chain'
                 % (int(ind.sum() + ch.sum()), int(ind.sum()), int(ch.sum())),
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='lower right')
    ax.grid(axis='x', alpha=0.15, lw=0.5)

    fig.suptitle('HIERARCHICAL_READ_V7 — tiered opponent reading, counterfactual',
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
