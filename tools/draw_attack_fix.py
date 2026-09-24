#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATTACK_FIXTURE_FIX 결과 그림. 읽기 전용. (한글 폰트가 없어 라벨은 영문)"""
from __future__ import print_function

import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BLUE, RED, GREEN, GREY = '#1e88e5', '#c62828', '#2e7d32', '#616161'
FLOOR = 0.002


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main', required=True)
    ap.add_argument('--aux', required=True)
    ap.add_argument('--out', default='docs/ATTACK_FIXTURE_FIX.png')
    a = ap.parse_args()
    M = json.load(open(a.main, encoding='utf-8'))
    X = json.load(open(a.aux, encoding='utf-8'))

    fig, axes = plt.subplots(1, 3, figsize=(16.6, 5.0))

    # --- 1. the fixture fix ------------------------------------------
    ax = axes[0]
    g = np.array([0.15, 0.35, 0.55, 0.75])
    ax.plot(g, 1 - g, '--o', color=RED, ms=6, lw=2.0,
            label='OLD book: ftb = 1 - b_true')
    ax.plot(g, 0.18 + 0.60 * g, '--s', color=RED, ms=6, lw=2.0, alpha=.55,
            label='OLD oracle: P(fold) rises with b_true')
    f = np.array([0.32, 0.44, 0.56, 0.68])
    ax.plot(f, f, '-^', color=GREEN, ms=7, lw=2.6,
            label='NEW: book and oracle both = ftb_true')
    ax.set_xlabel('opponent parameter')
    ax.set_ylabel('probability the opponent folds')
    ax.set_ylim(0, 1)
    ax.annotate('old: r = -1.000 vs +1.000  (anti-informative)',
                xy=(0.16, 0.02), fontsize=8.2, color=RED)
    ax.annotate('new: identity, r = +1.000', xy=(0.42, 0.60), fontsize=8.5,
                color=GREEN, rotation=34)
    ax.set_title('1. what was fixed\nftb split off from b_true', fontsize=10)
    ax.legend(fontsize=7.0, frameon=False, loc='lower left',
              bbox_to_anchor=(0.0, 0.14))

    # --- 2. primary (confounded) -------------------------------------
    ax = axes[1]
    keys = ['attack', 'defend', 'pooled']
    labs = ['attack\n288 st.', 'defend\n24 st.', 'pooled\n(weighted)']
    y = np.arange(3)[::-1]
    for s, col, off in (('SET_A', BLUE, .16), ('SET_B', RED, -.16)):
        m = [M[s][k]['diff'] for k in keys]
        lo = [M[s][k]['diff'] - M[s][k]['ci'][0] for k in keys]
        hi = [M[s][k]['ci'][1] - M[s][k]['diff'] for k in keys]
        ax.errorbar(m, y + off, xerr=[lo, hi], fmt='o', ms=6, color=col,
                    capsize=3, lw=1.4, label=s)
    ax.axvline(0, color='#212121', lw=1.0)
    for v in (FLOOR, -FLOOR):
        ax.axvline(v, color=GREEN, lw=1.1, ls='--')
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=8.5)
    ax.set_xlabel('CALC_ONLY - PIPE_ONLY   >0 = the reading arm is better')
    ax.set_title('2. PRIMARY statistic - but it is confounded\n'
                 'the two arms differ in ~20 apply-side concepts too',
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='lower right')

    # --- 3. clean R-axis contrast ------------------------------------
    ax = axes[2]
    rows = [('pooled', 'dR'), ('n_obs = 6', 'dR_n6'), ('n_obs = 40', 'dR_n40')]
    y = np.arange(len(rows))[::-1]
    for s, col, off in (('SET_A', BLUE, .15), ('SET_B', RED, -.15)):
        m, lo, hi = [], [], []
        for _, k in rows:
            d = X[s][k] if isinstance(X[s][k], dict) else {
                'mean': X[s]['dR'], 'ci': X[s]['ci']}
            mv = d.get('mean', d.get('dR'))
            m.append(mv)
            lo.append(mv - d['ci'][0])
            hi.append(d['ci'][1] - mv)
        ax.errorbar(m, y + off, xerr=[lo, hi], fmt='o', ms=6, color=col,
                    capsize=3, lw=1.4, label=s)
    ax.axvline(0, color='#212121', lw=1.0)
    ax.axvline(FLOOR, color=GREEN, lw=1.3, ls='--')
    ax.annotate('FLOOR 0.002', xy=(FLOOR, y[0] + .40), fontsize=8, color=GREEN)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=9)
    ax.set_xlabel('regret(LOW read) - regret(HIGH read)   >0 = reading helps')
    ax.set_title('3. CLEAN contrast (real profiles, belief only)\n'
                 'attack reading pays, but only with enough sample',
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='lower right')

    for ax in axes:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    fig.suptitle('ATTACK_FIXTURE_FIX - with the attack channel wired correctly, '
                 'read accuracy helps at n=40 (+0.0029/+0.0026) and not at n=6',
                 fontsize=11.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(a.out, dpi=140)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
