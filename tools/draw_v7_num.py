#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NUMERIC_BUNDLE_V7 결과 그림. 읽기 전용."""
from __future__ import print_function

import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ORDER = ('range_read', 'potodds', 'spr', 'blocker', 'fold_equity',
         'board_texture')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--interv', required=True)
    ap.add_argument('--pop', required=True)
    ap.add_argument('--out', default='docs/NUMERIC_BUNDLE_V7.png')
    a = ap.parse_args()
    iv = json.load(open(a.interv, encoding='utf-8'))
    pop = json.load(open(a.pop, encoding='utf-8'))

    fig, axes = plt.subplots(1, 3, figsize=(16.4, 5.0))

    # --- 1. paired intervention
    ax = axes[0]
    y = np.arange(len(ORDER))
    dE = [iv[c]['dE'] for c in ORDER]
    lo = [iv[c]['dE'] - iv[c]['dE_ci'][0] for c in ORDER]
    hi = [iv[c]['dE_ci'][1] - iv[c]['dE'] for c in ORDER]
    dG = [iv[c]['dG'] for c in ORDER]
    ax.barh(y - 0.19, dE, 0.38, xerr=[lo, hi], color='#1e88e5',
            error_kw=dict(lw=1.1, capsize=2.5), label='ΔE  (opponent-varying)')
    ax.barh(y + 0.19, dG, 0.38, color='#bdbdbd', label='ΔG  (control)')
    ax.axvline(0.05, color='#c62828', lw=1.6, ls='--')
    ax.annotate('preregistered\nthreshold 0.05', xy=(0.05, 5.4),
                xytext=(8, 0), textcoords='offset points', fontsize=8,
                color='#c62828', va='center')
    ax.axvline(0, color='#616161', lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(['%s\n(resp Δ %.0f%%)'
                        % (c, 100 * iv[c]['frac_response_changed'])
                        for c in ORDER], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('Δ battery score  (concept 2.0 → 8.0, 200 paired profiles)')
    ax.set_title('paired intervention\nonly range_read clears the threshold',
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='lower right')
    ax.grid(axis='x', alpha=0.15, lw=0.5)

    # --- 2. natural population: r vs partial
    ax = axes[1]
    fit = pop['fit']
    r = [fit[c]['r'] for c in ORDER]
    pr = [fit[c]['partial'] for c in ORDER]
    ax.barh(y - 0.19, r, 0.38, color='#8d6e63', label='r(QX_E)')
    ax.barh(y + 0.19, pr, 0.38, color='#2e7d32',
            label='partial (E inputs controlled)')
    ax.axvline(0, color='#616161', lw=0.8)
    ax.axvline(0.05, color='#c62828', lw=1.4, ls='--')
    ax.plot([fit['_adaptability']['r']], [-0.75], marker='v', ms=9,
            color='#6a1b9a', clip_on=False)
    ax.annotate('adaptability r=%.3f  partial=%.3f  (already in E)'
                % (fit['_adaptability']['r'], fit['_adaptability']['partial']),
                xy=(fit['_adaptability']['r'], -0.75), xytext=(-6, 10),
                textcoords='offset points', ha='right', fontsize=8,
                color='#6a1b9a')
    ax.set_yticks(y)
    ax.set_yticklabels(ORDER, fontsize=8)
    ax.invert_yaxis()
    ax.set_ylim(5.6, -1.3)
    ax.set_xlabel('correlation with independent battery score')
    ax.set_title('natural population (fit, 500 bots)\n'
                 'range_read / fold_equity vanish once E is controlled',
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc='lower right')
    ax.grid(axis='x', alpha=0.15, lw=0.5)

    # --- 3. holdout ablation
    ax = axes[2]
    sch = pop['schemes']
    sch = sorted(sch, key=lambda s: s[1])
    names = [s[0] for s in sch]
    vals = [s[1] for s in sch]
    cols = ['#c62828' if n == 'current equal-6' else '#90a4ae' for n in names]
    yy = np.arange(len(names))
    ax.barh(yy, vals, color=cols)
    ax.set_yticks(yy)
    ax.set_yticklabels(names, fontsize=7.5)
    ax.set_xlabel('holdout r(num, QX_E)   — no fitting')
    ax.set_title('pre-specified weighting schemes (holdout, 500 bots)\n'
                 'single range_read beats the current 6-mean', fontsize=10)
    ax.grid(axis='x', alpha=0.15, lw=0.5)

    fig.suptitle('NUMERIC_BUNDLE_V7 — does the 6-concept bundle measure '
                 'quantitative opponent exploitation?', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    fig.savefig(a.out, dpi=150)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
