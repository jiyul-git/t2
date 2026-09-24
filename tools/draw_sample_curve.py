#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ_SAMPLE_CURVE 결과 그림. 읽기 전용. (한글 폰트가 없어 라벨은 영문)"""
from __future__ import print_function

import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BLUE, RED, GREEN, GREY = '#1e88e5', '#c62828', '#2e7d32', '#616161'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default='docs/READ_SAMPLE_CURVE.png')
    a = ap.parse_args()
    d = json.load(open(a.data, encoding='utf-8'))
    N = d['n_grid']
    F = d['floor']

    fig, axes = plt.subplots(1, 3, figsize=(16.4, 5.0))

    # --- 1. defend curve --------------------------------------------
    # --- 2. attack curve --------------------------------------------
    for ax, ch, nm, col in ((axes[0], 'D', 'DEFEND', BLUE),
                            (axes[1], 'A', 'ATTACK', RED)):
        for s, ls, mk, alpha in (('SET_A', '-', 'o', 1.0),
                                 ('SET_B', '--', 's', .75)):
            m = [d[s]['%s_n%d' % (ch, n)]['dR'] for n in N]
            lo = [m[i] - d[s]['%s_n%d' % (ch, n)]['ci'][0]
                  for i, n in enumerate(N)]
            hi = [d[s]['%s_n%d' % (ch, n)]['ci'][1] - m[i]
                  for i, n in enumerate(N)]
            ax.errorbar(N, m, yerr=[lo, hi], fmt=ls + mk, ms=6, color=col,
                        capsize=3, lw=1.8, alpha=alpha, label=s)
        ax.axhline(0, color='#212121', lw=1.0)
        ax.axhline(F, color=GREEN, lw=1.3, ls='--')
        ax.annotate('FLOOR %.3f' % F, xy=(N[0], F), xytext=(2, 4),
                    textcoords='offset points', fontsize=8, color=GREEN)
        ax.axvline(12, color=GREY, lw=1.0, ls=':')
        ax.annotate('n=12\nmin(1, n/12) kink', xy=(12.4, ax.get_ylim()[0]),
                    fontsize=7.5, color=GREY, va='bottom')
        ax.set_xlabel('n_obs  (hands observed)')
        ax.set_ylabel('dR = regret(LOW read) - regret(HIGH read)')
        ax.set_title('%s: read accuracy payoff vs sample size\n'
                     'Spearman(n, dR) = %+.3f / %+.3f'
                     % (nm, d['SET_A']['spearman_' + ch],
                        d['SET_B']['spearman_' + ch]), fontsize=10)
        ax.legend(fontsize=8, frameon=False, loc='lower right')

    # --- 3. w gate + ratio ------------------------------------------
    ax = axes[2]
    w = [d['SET_A']['man_n%d' % n]['w_hi'] for n in N]
    ax.plot(N, w, '-D', color='#6a1b9a', ms=6, lw=2.0, label='mean w (HIGH read)')
    ax.set_xlabel('n_obs')
    ax.set_ylabel('exploit weight w', color='#6a1b9a')
    ax.tick_params(axis='y', labelcolor='#6a1b9a')
    ax.axvline(12, color=GREY, lw=1.0, ls=':')
    ax2 = ax.twinx()
    rat = []
    for n in N:
        da = d['SET_A']['D_n%d' % n]['dR']
        aa = d['SET_A']['A_n%d' % n]['dR']
        rat.append(da / aa if abs(aa) > 1e-9 else np.nan)
    ax2.plot(N, rat, '-^', color='#ef6c00', ms=6, lw=2.0,
             label='defend / attack ratio')
    ax2.set_ylabel('defend dR / attack dR', color='#ef6c00')
    ax2.tick_params(axis='y', labelcolor='#ef6c00')
    ax2.axhline(1.0, color=GREY, lw=1.0, ls='--')
    ax.set_title('3. the gate, and how the channels compare\n'
                 'w = use x min(1,conf) x min(1, n/12)', fontsize=10)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, frameon=False, loc='lower right')

    for ax in axes:
        ax.spines['top'].set_visible(False)
    fig.suptitle('READ_SAMPLE_CURVE - read-accuracy payoff by sample size, '
                 'both channels, same clean intervention  |  %s'
                 % d['verdict'], fontsize=11.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(a.out, dpi=140)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
