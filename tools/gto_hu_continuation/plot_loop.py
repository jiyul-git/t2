#!/usr/bin/env python3
"""Outer fixed-point trajectories of the HU continuation prototype (undamped vs damped A/B).

    python3 tools/gto_hu_continuation/plot_loop.py data/gto_hu_continuation/outer_v1 \
        data/gto_hu_continuation/outer_v1_damped_a05 docs/GTO_HU_CONTINUATION_LOOP_V1.png
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker

INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C_U, C_D = '#2a78d6', '#eb6834'


def load(d):
    T, V = {}, {}
    k = 0
    while os.path.exists(os.path.join(d, f'k{k}', 'terminal.json')):
        T[k] = json.load(open(os.path.join(d, f'k{k}', 'terminal.json')))
        for name in ('table_measured.json', 'table.json'):
            p = os.path.join(d, f'k{k}', name)
            if os.path.exists(p):
                V[k] = json.load(open(p))
                break
        k += 1
    return T, V


def l1(a, b, pos):
    x = next(p for p in a['players'] if p['position'] == pos)['class_reach_normalized']
    y = next(p for p in b['players'] if p['position'] == pos)['class_reach_normalized']
    return sum(abs(i - j) for i, j in zip(x, y))


def dv(a, b, pos):
    x = next(s for s in a['seats'] if s['position'] == pos)['gross']
    y = next(s for s in b['seats'] if s['position'] == pos)['gross']
    return sum(abs(i - j) for i, j in zip(x, y)) / len(x)


def style(ax, title):
    ax.set_facecolor(SURF)
    ax.grid(color=GRID, lw=0.8)
    ax.set_title(title, loc='left', fontsize=11, color=INK)
    ax.set_xlabel('outer step k', fontsize=9, color=MUTED)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)


def main():
    und, dmp, out = sys.argv[1:4]
    TU, VU = load(und)
    TD, VD = load(dmp)
    damp_from = min(k for k in VD if os.path.exists(os.path.join(dmp, f'k{k}', 'table_measured.json')))
    fig, ax = plt.subplots(2, 2, figsize=(14, 9), dpi=120)
    fig.patch.set_facecolor(SURF)
    # (1) frequencies
    a = ax[0][0]
    for T, col, lab, ks in ((TU, C_U, 'undamped', sorted(TU)), (TD, C_D, 'damped α=0.5 (from k3)', [k for k in sorted(TD) if k >= damp_from])):
        a.plot(ks, [T[k]['frequencies']['rfi_BTN']['mix'].get('raise_2', 0) for k in ks], 'o-', color=col, lw=2, label=f'BTN open 2bb — {lab}')
        a.plot(ks, [T[k]['frequencies']['terminal_parent']['mix']['fold'] for k in ks], 's--', color=col, lw=2, label=f'BB fold vs BTN — {lab}')
    style(a, '(1) P_k: BTN open and BB fold (4-handed, injected terminal only)')
    a.set_ylabel('frequency', fontsize=9, color=MUTED)
    a.legend(fontsize=8, frameon=False)
    # (2) range step sizes
    a = ax[0][1]
    for T, col, lab, start in ((TU, C_U, 'undamped', 1), (TD, C_D, 'damped', damp_from + 1)):
        ks = [k for k in sorted(T) if k >= start]
        for pos, mk in (('BTN', 'o-'), ('BB', 's--')):
            a.plot(ks, [l1(T[k - 1], T[k], pos) for k in ks], mk, color=col, lw=2, label=f'{pos} — {lab}')
    style(a, '(2) arriving-range change |P_k − P_{k−1}|₁')
    a.set_ylabel('L1 distance of class reach', fontsize=9, color=MUTED)
    a.legend(fontsize=8, frameon=False)
    # (3) value change (measured tables)
    a = ax[1][0]
    for V, col, lab, start in ((VU, C_U, 'undamped', 1), (VD, C_D, 'damped (measured)', damp_from + 1)):
        ks = [k for k in sorted(V) if k >= start and k - 1 in V]
        for pos, mk in (('BTN', 'o-'), ('BB', 's--')):
            a.plot(ks, [dv(V[k - 1], V[k], pos) for k in ks], mk, color=col, lw=2, label=f'{pos} — {lab}')
    style(a, '(3) measured continuation table change, mean |ΔV| per class')
    a.set_ylabel('bb', fontsize=9, color=MUTED)
    a.set_yscale('log')
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: '%g' % v))
    a.legend(fontsize=8, frameon=False)
    # (4) staleness: previous injected table evaluated at the new ranges
    a = ax[1][1]
    for T, V, col, lab in ((TU, VU, C_U, 'undamped'), (TD, VD, C_D, 'damped')):
        ks, ys = [], []
        for k in sorted(T):
            if k - 1 in V and k >= 1:
                tab = V[k - 1]
                if lab == 'damped' and os.path.exists(os.path.join(dmp, f'k{k-1}', 'table.json')):
                    tab = json.load(open(os.path.join(dmp, f'k{k-1}', 'table.json')))
                tot = sum(sum(pl['class_reach_normalized'][h] * next(s for s in tab['seats'] if s['position'] == pl['position'])['gross'][h]
                              for h in range(169)) for pl in T[k]['players'])
                ks.append(k)
                ys.append(T[k]['pot_bb'] - tot)
        a.plot(ks, ys, 'o-', color=col, lw=2, label=lab)
    a.axhline(0, color=MUTED, lw=1)
    a.axhspan(-0.05, 0.05, color=GRID, alpha=0.6, lw=0)
    style(a, '(4) injected table evaluated at the ranges it produced (unallocated bb)')
    a.set_ylabel('pot − Σ range·V  (bb; ±0.05 guard band shaded)', fontsize=9, color=MUTED)
    a.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURF, bbox_inches='tight')
    print('wrote', out)


if __name__ == '__main__':
    main()
