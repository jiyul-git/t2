#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ_USE_SEPARATION 결과 그림. 읽기 전용. (한글 폰트가 없어 라벨은 영문)"""
from __future__ import print_function

import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

U_LADDER = (0.0, 0.4, 0.7, 1.0, 1.3, 1.6, 2.0)
BLUE, RED, GREY = '#1e88e5', '#c62828', '#616161'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default='docs/READ_USE_SEPARATION.png')
    a = ap.parse_args()
    d = json.load(open(a.data, encoding='utf-8'))
    sets = [k for k in d if k.startswith('SET_')]
    sets.sort()
    A, B = d[sets[0]], d[sets[1]]
    floor = d['floor']

    fig, axes = plt.subplots(1, 4, figsize=(19.5, 4.9))

    # --- 1. 2x2 cells -------------------------------------------------
    ax = axes[0]
    labs = ['LOW read\nLOW use', 'LOW read\nHIGH use',
            'HIGH read\nLOW use', 'HIGH read\nHIGH use']
    la, lb = A['ladder_LOW_READ'], A['ladder_HIGH_READ']
    hb_a, hb_b = B['ladder_LOW_READ'], B['ladder_HIGH_READ']
    i_lo, i_hi = U_LADDER.index(0.4), U_LADDER.index(1.6)
    va = [la[i_lo], la[i_hi], lb[i_lo], lb[i_hi]]
    vb = [hb_a[i_lo], hb_a[i_hi], hb_b[i_lo], hb_b[i_hi]]
    x = np.arange(4)
    ax.bar(x - 0.19, va, 0.38, color=BLUE, alpha=.88, label='SET_A')
    ax.bar(x + 0.19, vb, 0.38, color=RED, alpha=.88, label='SET_B')
    for xi, (p, q) in enumerate(zip(va, vb)):
        ax.annotate('%.4f' % p, (xi - 0.19, p), ha='right', va='bottom',
                    fontsize=7.2, rotation=90)
        ax.annotate('%.4f' % q, (xi + 0.19, q), ha='left', va='bottom',
                    fontsize=7.2, rotation=90)
    ax.set_ylim(0, max(va + vb) * 1.30)
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=8)
    ax.set_ylabel('mean regret (pot fraction)')
    ax.set_title('1. the 2x2 cells\nread pays at low use, not at high use',
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False)

    # --- 2. U ladder --------------------------------------------------
    ax = axes[1]
    for s, nm, ls in ((A, sets[0], '-'), (B, sets[1], '--')):
        ax.plot(U_LADDER, s['ladder_LOW_READ'], ls, color=RED, marker='o',
                ms=5, label='LOW read  %s' % nm.split()[0], lw=1.6)
        ax.plot(U_LADDER, s['ladder_HIGH_READ'], ls, color=BLUE, marker='s',
                ms=5, label='HIGH read %s' % nm.split()[0], lw=1.6)
    ax.axvline(1.0, color=GREY, lw=1.0, ls=':')
    ax.annotate('production u=1', xy=(1.02, ax.get_ylim()[1]), fontsize=7.5,
                color=GREY, va='top')
    ax.set_xlabel('u  (exploit application strength)')
    ax.set_ylabel('mean regret (pot fraction)')
    ax.set_title('2. U ladder (descriptive)\nthe two curves converge as u grows',
                 fontsize=10)
    ax.legend(fontsize=7, frameon=False, ncol=2)

    # --- 3. dR with CI ------------------------------------------------
    ax = axes[2]
    keys = ['dR(u=0.40)', 'dR(u=1.60)',
            'dR[n=6](u=0.40)', 'dR[n=40](u=0.40)',
            'dR[n=6](u=1.60)', 'dR[n=40](u=1.60)']
    y = np.arange(len(keys))[::-1]
    for s, col, off, nm in ((A, BLUE, .16, sets[0].split()[0]),
                            (B, RED, -.16, sets[1].split()[0])):
        m = [s[k]['mean'] for k in keys]
        lo = [s[k]['mean'] - s[k]['ci'][0] for k in keys]
        hi = [s[k]['ci'][1] - s[k]['mean'] for k in keys]
        ax.errorbar(m, y + off, xerr=[lo, hi], fmt='o', ms=6, color=col,
                    capsize=3, lw=1.4, label=nm)
    ax.axvline(0, color='#212121', lw=1.0)
    ax.axvline(floor, color='#2e7d32', lw=1.2, ls='--')
    ax.annotate('FLOOR %.3f' % floor, xy=(floor, y[0] + .42), fontsize=7.5,
                color='#2e7d32')
    ax.set_yticks(y)
    ax.set_yticklabels(keys, fontsize=8)
    ax.set_xlabel('regret(LOW read) - regret(HIGH read)   >0 = reading helps')
    ax.set_title('3. read effect with use held fixed\n'
                 '95% cluster bootstrap CI', fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='lower right')

    # --- 4. call rate confound ----------------------------------------
    ax = axes[3]
    for s, nm, ls in ((A, sets[0].split()[0], '-'), (B, sets[1].split()[0], '--')):
        ax.plot(U_LADDER, s.get('rate_HIGH_READ', []), ls, color='#6a1b9a',
                marker='D', ms=5, label='call rate %s' % nm)
    ax.axhline(0.5, color='#2e7d32', lw=1.4, ls='--')
    ax.annotate('optimal call rate 0.500 (by construction)', xy=(0.02, 0.51),
                fontsize=8, color='#2e7d32')
    ax.set_xlabel('u  (exploit application strength)')
    ax.set_ylabel('fraction of states called')
    ax.set_title('4. u is not a pure strength knob\nit also shifts the call rate',
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='lower right')

    for ax in axes:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    fig.suptitle('READ_USE_SEPARATION - separating read accuracy (R) from '
                 'application strength (U) on the defend channel  |  '
                 'verdict: %s' % d['verdict'], fontsize=11.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(a.out, dpi=140)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
