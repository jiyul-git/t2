#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QX_EV_VALIDATION 결과 그림. 읽기 전용."""
from __future__ import print_function

import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default='docs/QX_EV_VALIDATION.png')
    a = ap.parse_args()
    d = json.load(open(a.data, encoding='utf-8'))

    fig, axes = plt.subplots(1, 3, figsize=(16.0, 5.0))

    # 1. 채널·집합별 상관
    ax = axes[0]
    keys = ['READ_D', 'READ_A', 'READ_all', 'GEN_all']
    x = np.arange(len(keys))
    for i, (qx, col, mk) in enumerate((('QX_E', '#1e88e5', 'o'),
                                       ('QX_S', '#2e7d32', 's'))):
        f = [d['fit'][qx][k] for k in keys]
        h = [d['holdout'][qx][k] for k in keys]
        ax.bar(x + (i - 0.5) * 0.36, f, 0.36, color=col, alpha=0.85,
               label='%s fit' % qx)
        ax.plot(x + (i - 0.5) * 0.36, h, ls='', marker=mk, ms=8,
                color='#212121', mfc='white', mew=1.6,
                label='%s holdout' % qx)
    ax.axhline(0, color='#616161', lw=0.9)
    ax.axhline(0.20, color='#c62828', lw=1.4, ls='--')
    ax.annotate('VALID threshold 0.20', xy=(3.45, 0.205), ha='right',
                fontsize=8, color='#c62828')
    ax.set_ylim(-0.33, 0.37)
    ax.set_xticks(x)
    ax.set_xticklabels(['READ\ndefend', 'READ\nattack', 'READ\nall', 'GEN\nall'],
                       fontsize=8.5)
    ax.set_ylabel('r( QX , −regret )')
    ax.set_title('QX vs chip regret by channel\n'
                 'defend links; attack is reversed', fontsize=10)
    ax.legend(fontsize=7.5, frameon=False, ncol=2, loc='upper left')
    ax.grid(axis='y', alpha=0.15, lw=0.5)

    # 2. 통제 후에도 남는가
    ax = axes[1]
    labs = ['raw', '+overall\nCALC', '+overall\n+act rate']
    x = np.arange(3)
    for i, (qx, col) in enumerate((('QX_E', '#1e88e5'), ('QX_S', '#2e7d32'))):
        for j, (s, alpha, hatch) in enumerate((('fit', 0.85, None),
                                               ('holdout', 0.40, '//'))):
            v = [d[s][qx]['READ_all'], d[s][qx]['partial_READ'],
                 d[s][qx]['partial_READ_act']]
            ax.bar(x + (i - 0.5) * 0.4 + (j - 0.5) * 0.18, v, 0.17,
                   color=col, alpha=alpha, hatch=hatch, edgecolor='white',
                   linewidth=0.6,
                   label='%s %s' % (qx, s) if True else None)
    ax.axhline(0.10, color='#c62828', lw=1.3, ls='--')
    ax.annotate('partial threshold 0.10', xy=(2.45, 0.105), ha='right',
                fontsize=8, color='#c62828')
    ax.axhline(0, color='#616161', lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=8.5)
    ax.set_ylabel('r( QX , −regret )  on READ')
    ax.set_title('does the link survive controls?\n'
                 'QX_E does, QX_S does not on holdout', fontsize=10)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h[:4], l[:4], fontsize=7.5, frameon=False, loc='upper right')
    ax.grid(axis='y', alpha=0.15, lw=0.5)

    # 3. 사분위 regret + 합성 대조
    ax = axes[2]
    groups = ['QX_E\nlow 25%', 'QX_E\nhigh 25%', 'QX_S\nlow 25%',
              'QX_S\nhigh 25%', 'CALC\nONLY', 'PIPE\nONLY']
    fitv = [d['fit']['QX_E']['q_low_regret'], d['fit']['QX_E']['q_high_regret'],
            d['fit']['QX_S']['q_low_regret'], d['fit']['QX_S']['q_high_regret'],
            d['synth']['calc_only'], d['synth']['pipe_only']]
    cols = ['#90a4ae', '#1e88e5', '#a5d6a7', '#2e7d32', '#ffb74d', '#8d6e63']
    y = np.arange(len(groups))
    ax.barh(y, fitv, color=cols)
    for i, v in enumerate(fitv):
        ax.annotate('%.4f' % v, (v, i), xytext=(4, 0),
                    textcoords='offset points', va='center', fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(groups, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, max(fitv) * 1.25)
    ax.set_xlabel('mean regret on READ states  (fraction of pot)')
    ax.set_title('quartile split separates; synthetic extremes do not\n'
                 'CALC−PIPE = +0.0004  95%%CI [%.5f, %.5f]'
                 % (d['synth']['ci'][0], d['synth']['ci'][1]), fontsize=10)
    ax.grid(axis='x', alpha=0.15, lw=0.5)

    fig.suptitle('QX_EV_VALIDATION — is QX a valid proxy for chip EV?  '
                 'verdict: QX_PARTIAL', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    dd = os.path.dirname(os.path.abspath(a.out))
    if dd and not os.path.isdir(dd):
        os.makedirs(dd)
    fig.savefig(a.out, dpi=150)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
