#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SYNTH_CHANNEL_SPLIT 결과 그림. 읽기 전용. (한글 폰트가 없어 라벨은 영문)"""
from __future__ import print_function

import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BLUE, RED, GREEN, GREY = '#1e88e5', '#c62828', '#2e7d32', '#616161'
B_LEVELS = (0.15, 0.35, 0.55, 0.75)
F_BLUFF, F_VALUE = 0.78, 0.18


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', required=True)
    ap.add_argument('--path', required=True)
    ap.add_argument('--out', default='docs/AGGR_INFO_PATH.png')
    a = ap.parse_args()
    S = json.load(open(a.split, encoding='utf-8'))['result']
    P = json.load(open(a.path, encoding='utf-8'))

    fig, axes = plt.subplots(1, 3, figsize=(16.2, 5.0))

    # --- 1. channel split -------------------------------------------
    ax = axes[0]
    keys = ['D', 'A', 'pooled']
    labs = ['defend\n(24 states)', 'attack\n(48 states)', 'pooled\n(72 states)']
    x = np.arange(3)
    ca = [S[k]['calc_only'] for k in keys]
    pi = [S[k]['pipe_only'] for k in keys]
    ax.bar(x - 0.19, ca, 0.38, color=GREY, alpha=.9, label='CALC_ONLY')
    ax.bar(x + 0.19, pi, 0.38, color=BLUE, alpha=.9, label='PIPE_ONLY')
    for i, k in enumerate(keys):
        d = S[k]['diff']
        ax.annotate('d=%+.5f\n%s' % (d, 'sig' if S[k]['sig'] else 'n.s.'),
                    (i, max(ca[i], pi[i])), ha='center', va='bottom',
                    fontsize=8, color=(GREEN if S[k]['sig'] else RED))
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=9)
    ax.set_ylim(0, max(ca + pi) * 1.30)
    ax.set_ylabel('mean regret (pot fraction)')
    ax.set_title('1. the pooled null is a cancellation\n'
                 '24(+0.00527) + 48(-0.00200) over 72 = +0.00042', fontsize=10)
    ax.legend(fontsize=8, frameon=False)

    # --- 2. attack channel contradiction ----------------------------
    ax = axes[1]
    book = [1.0 - b for b in B_LEVELS]
    oracle = [b * F_BLUFF + (1 - b) * F_VALUE for b in B_LEVELS]
    ax.plot(B_LEVELS, book, '-o', color=RED, ms=7, lw=2.2,
            label="public record: fold_to_bet = 1 - b_true")
    ax.plot(B_LEVELS, oracle, '-s', color=GREEN, ms=7, lw=2.2,
            label="EV oracle: P(fold to my bet) = .18 + .60*b_true")
    ax.annotate('r = -1.000', xy=(0.62, 0.32), color=RED, fontsize=9)
    ax.annotate('r = +1.000', xy=(0.62, 0.66), color=GREEN, fontsize=9)
    ax.annotate('r(what the reader believes,\nwhat the oracle uses) = %+.4f'
                % P['corr']['ftb_seen_p_fold_ev'],
                xy=(0.16, 0.83), fontsize=9.5, color='#212121')
    ax.set_xlabel('b_true  (opponent bluff fraction)')
    ax.set_ylabel('probability the opponent folds')
    ax.set_ylim(0, 1.0)
    ax.set_title('2. ATTACK: record and oracle run opposite\n'
                 'reading accurately is penalised by construction', fontsize=10)
    ax.legend(fontsize=7.6, frameon=False, loc='lower left')

    # --- 3. defend control ------------------------------------------
    ax = axes[2]
    d = P['defend_corr']
    ks = ['b_bluff_seen', 'b_rv', 'b_edge_call', 'rv_edge_call']
    nm = ['b_true ->\nbelieved bluff', 'b_true ->\nline_bluff_prior',
          'b_true ->\noracle call edge', 'line_bluff_prior ->\noracle call edge']
    v = [d[k] for k in ks]
    y = np.arange(len(ks))[::-1]
    ax.barh(y, v, 0.52, color=[BLUE, BLUE, GREY, GREEN])
    ax.axvline(0, color='#212121', lw=1.0)
    for i, val in zip(y, v):
        ax.annotate('%+.4f' % val, (val, i), xytext=(-6, 0),
                    textcoords='offset points', ha='right', va='center',
                    fontsize=8.5, color='white')
    ax.set_yticks(y)
    ax.set_yticklabels(nm, fontsize=8)
    ax.set_xlim(-1.0, 1.0)
    ax.set_xlabel('correlation')
    ax.set_title('3. DEFEND control: all positive\n'
                 'the defect is attack-specific, not global', fontsize=10)

    for ax in axes:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    fig.suptitle('SYNTH_CHANNEL_SPLIT - the QX_EV PIPE_ONLY null is channel '
                 'cancellation, and the attack side of it is a fixture defect',
                 fontsize=11.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(a.out, dpi=140)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
