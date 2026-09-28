#!/usr/bin/env python3
"""Summarize the tight-RFI root-cause runs (X1..X4) produced by t2_profile with T2_REPORT=1.

    python3 tools/gtopen_audit/summarize_rfi.py <dir with x_*.json> --ref <crosscheck.json> \
        --out-json data/gtopen_audit/rfi_experiments.json --out-png docs/GTOPEN_RFI_EXPERIMENTS_V1.png

The public aggregate (PreflopRanges) is drawn only as a sanity marker. Conditions differ
(SB open size, limp, BBA vs uniform ante, full 4bet tree) and it is never a fitting target.
"""
import argparse
import glob
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
if os.path.exists(FONT):
    fm.fontManager.addfont(FONT)
    matplotlib.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name()
matplotlib.rcParams['axes.unicode_minus'] = False
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eeb122', '#7c5fd0']
POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']
LABEL = {
    'X1_base': 'X1 pilot (mr2, eq1200, static)',
    'X2_eq20k': 'X2 eq 20000 samples',
    'X3_legacy': 'X3 multiway legacy_product',
    'X4_balanced': 'X4 realization balanced (=raw)',
}


def load(d):
    runs = {}
    for f in sorted(glob.glob(os.path.join(d, 'x_*.json'))):
        name = os.path.basename(f)[2:-5]
        try:
            j = json.load(open(f))
        except (json.JSONDecodeError, ValueError):
            continue
        runs[name] = j
    return runs


def checkpoints(run):
    out = []
    for g in run.get('gaps', []):
        rep = g.get('report') or {}
        rfi = {p: v['enter'] for p, v in rep.get('rfi', {}).items()}
        mixes = {p: v['mix'] for p, v in rep.get('rfi', {}).items()}
        out.append({'iteration': g['iteration'], 'gap_total': g['gap_total'], 'gaps': g['gaps'],
                    'rfi': rfi, 'rfi_mix': mixes, 'responses': rep.get('responses', {})})
    return out


SUBLABEL = {
    'check_base': 'base (mr4, eq1200, static k=0.16)', 'raw': 'realization raw (k=0)',
    'eq20k': 'eq 20000 samples', 'legacy': 'multiway legacy_product', 'sb35': 'SB open 3.5bb',
    'sb35_limp': 'SB 3.5 + limp allowed (global)', 'k0': 'static k=0', 'k032': 'static k=0.32 (2x)',
    'k064': 'static k=0.64 (4x)', 'seed303': 'eq/multiway seed 303',
}
SUBPOS = ['CO', 'BTN', 'SB']


def final_report(j):
    g = j['gaps'][-1]
    rep = g['report']
    rfi = {p: v['enter'] for p, v in rep['rfi'].items()}
    resp = rep['responses']
    bb = resp.get('BB_vs_BTN_open', {})
    return {'iteration': g['iteration'], 'gap_total': g['gap_total'], 'rfi': rfi,
            'bb_fold_vs_btn': bb.get('fold'), 'sb_fold_vs_btn': resp.get('SB_vs_BTN_open', {}).get('fold'),
            'btn_vs_bb_3bet': resp.get('BTN_vs_BB_3bet'), 'responses': resp}


def load_sub(d):
    out = {'max_raises_sweep': {}, 'sensitivity_4handed_mr4': {}}
    for f in sorted(glob.glob(os.path.join(d, 'sub*_mr*.json'))):
        try:
            j = json.load(open(f))
        except (json.JSONDecodeError, ValueError):
            continue
        out['max_raises_sweep'][os.path.basename(f)[:-5]] = dict(final_report(j), nodes=j['built']['nodes'])
    for f in sorted(glob.glob(os.path.join(d, 's_*.json'))):
        try:
            j = json.load(open(f))
        except (json.JSONDecodeError, ValueError):
            continue
        n = os.path.basename(f)[2:-5]
        out['sensitivity_4handed_mr4'][n] = dict(final_report(j), label=SUBLABEL.get(n, n))
    return out


def style(ax):
    ax.set_facecolor(SURF)
    ax.grid(color=GRID, lw=0.8, axis='x')
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)


def draw_sub(axes, sub):
    # (4) max_raises sweep, 4-handed and 5-handed
    ax = axes[0]
    sw = sub.get('max_raises_sweep', {})
    rows = [k for k in sorted(sw)]
    y = 0
    ticks, labels = [], []
    for k in rows:
        r = sw[k]
        for i, p in enumerate(SUBPOS):
            v = r['rfi'].get(p)
            if v is None:
                continue
            ax.barh(y + i * 0.25, v, 0.24, color=SERIES[i], label=p if k == rows[0] else None)
            ax.text(v + 0.005, y + i * 0.25, '%.3f' % v, va='center', fontsize=7.5, color=INK)
        ticks.append(y + 0.25)
        labels.append('%s  (%d nodes)' % (k.replace('sub', '').replace('_mr', '-handed, max_raises '), r['nodes']))
        y += 1
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.8)
    ax.set_xlabel('RFI at iteration 200', fontsize=9, color=MUTED)
    ax.legend(fontsize=8, frameon=False, loc='lower right')
    ax.set_title('(4) late-position subgame: 4bet menu barely moves RFI', loc='left', fontsize=11, color=INK)
    style(ax)
    # (5) one-factor sensitivity, 4-handed mr4
    ax = axes[1]
    se = sub.get('sensitivity_4handed_mr4', {})
    order = [k for k in SUBLABEL if k in se]
    for yi, k in enumerate(order):
        r = se[k]
        for i, p in enumerate(SUBPOS):
            v = r['rfi'].get(p, 0.0)
            ax.barh(yi + i * 0.25, v, 0.24, color=SERIES[i], label=p if yi == 0 else None)
            ax.text(v + 0.005, yi + i * 0.25, '%.3f' % v, va='center', fontsize=7.5, color=INK)
    ax.set_yticks([i + 0.25 for i in range(len(order))])
    ax.set_yticklabels([SUBLABEL[k] for k in order], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel('RFI at iteration 200 (4-handed CO/BTN/SB/BB, max_raises 4)', fontsize=9, color=MUTED)
    ax.legend(fontsize=8, frameon=False, loc='lower right')
    ax.set_title('(5) one factor at a time (sensitivity, NOT calibration)', loc='left', fontsize=11, color=INK)
    style(ax)
    # (6) BB fold vs BTN open
    ax = axes[2]
    vals = [(se[k]['bb_fold_vs_btn'] or 0.0) for k in order]
    ax.barh(range(len(order)), vals, 0.6, color=SERIES[4])
    for i, v in enumerate(vals):
        ax.text(v + 0.005, i, '%.3f' % v, va='center', fontsize=8, color=INK)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([SUBLABEL[k] for k in order], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.6)
    ax.set_xlabel('BB fold frequency vs BTN 2bb open', fontsize=9, color=MUTED)
    ax.set_title('(6) BB over-defense', loc='left', fontsize=11, color=INK)
    style(ax)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--ref', required=True)
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-png', required=True)
    ap.add_argument('--sub', help='dir with 4/5-handed subgame runs (sub*_mr*.json, s_*.json)')
    a = ap.parse_args()
    runs = load(a.dir)
    ref = json.load(open(a.ref))['stacks']['30']['rfi']
    summary = {'reference_sanity_only': {'source': 'PreflopRanges 30bb aggregate', 'rfi': ref,
                                         'condition_mismatch': ['SB opens 3.5bb (pilot 2.5bb)', 'SB limp present (pilot: no limp)',
                                                                'BBA (pilot: uniform 1/9bb ante)', '4bet tree (pilot max_raises=2: none)',
                                                                'unknown solver/continuation model']},
               'runs': {}}
    for name, run in runs.items():
        summary['runs'][name] = {
            'label': LABEL.get(name, name), 'eq_samples': run['eq_samples'],
            'multiway_model': run['multiway_model'], 'realization': run['realization'],
            'realization_note': run.get('realization_note'), 'iterations': run['iterations'],
            'solve_ms': run['solve_ms'], 'checkpoints': checkpoints(run)}
    sub = load_sub(a.sub) if a.sub else {}
    summary['subgame'] = sub
    json.dump(summary, open(a.out_json, 'w'), indent=1)

    fig, grid = plt.subplots(2, 3, figsize=(19, 11.5), dpi=120, gridspec_kw={'width_ratios': [1.25, 1.25, 0.8]})
    fig.patch.set_facecolor(SURF)
    axes = grid[0]
    draw_sub(grid[1], sub)
    x = list(range(len(POS)))
    # (1) X1 drift over iterations
    ax = axes[0]
    base = summary['runs'].get('X1_base', {}).get('checkpoints', [])
    for i, cp in enumerate(base):
        ax.plot(x, [cp['rfi'].get(p, float('nan')) for p in POS], 'o-', color=SERIES[i], lw=2, ms=5,
                label='X1 iteration %d (gap %.3f)' % (cp['iteration'], cp['gap_total']))
    ax.plot(x, [ref[p] for p in POS], 's--', color=MUTED, lw=1.2, ms=5, label='public aggregate (sanity only; conditions differ)')
    ax.set_title('(1) pilot game: RFI vs iteration', loc='left', fontsize=11, color=INK)
    # (2) variants at the same iteration (last common checkpoint)
    ax = axes[1]
    names = [n for n in LABEL if n in summary['runs'] and summary['runs'][n]['checkpoints']]
    common = min((max(c['iteration'] for c in summary['runs'][n]['checkpoints']) for n in names), default=None)
    for i, n in enumerate(names):
        cp = [c for c in summary['runs'][n]['checkpoints'] if c['iteration'] == common]
        if not cp:
            continue
        ax.plot(x, [cp[0]['rfi'].get(p, float('nan')) for p in POS], 'o-', color=SERIES[i], lw=2, ms=5,
                label='%s (gap %.3f)' % (LABEL[n], cp[0]['gap_total']))
    ax.plot(x, [ref[p] for p in POS], 's--', color=MUTED, lw=1.2, ms=5, label='public aggregate (sanity only)')
    ax.set_title('(2) one factor at a time, iteration %s, seed 202' % common, loc='left', fontsize=11, color=INK)
    for ax in axes[:2]:
        ax.set_xticks(x)
        ax.set_xticklabels(POS, fontsize=9)
        ax.set_ylabel('RFI (raise+jam+limp mass)', fontsize=9, color=MUTED)
        ax.set_ylim(0, 1.0)
        ax.grid(color=GRID, lw=0.8)
        ax.legend(fontsize=7.5, frameon=False, loc='upper left')
        ax.set_facecolor(SURF)
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
    # (3) gap trajectories
    ax = axes[2]
    for i, n in enumerate(names):
        cps = summary['runs'][n]['checkpoints']
        ax.plot([c['iteration'] for c in cps], [c['gap_total'] for c in cps], 'o-', color=SERIES[i], lw=2, ms=5, label=LABEL[n])
    ax.axhline(0.15, color=MUTED, lw=1, ls=':')
    ax.text(ax.get_xlim()[1] if names else 1, 0.15, ' pilot stop 0.15', fontsize=8, color=MUTED, va='bottom', ha='right')
    ax.set_yscale('log')
    ax.set_xlabel('iteration', fontsize=9, color=MUTED)
    ax.set_ylabel('gap_total (bb, model game)', fontsize=9, color=MUTED)
    ax.set_title('(3) gap (model game only)', loc='left', fontsize=11, color=INK)
    ax.grid(color=GRID, lw=0.8)
    ax.legend(fontsize=7.5, frameon=False)
    ax.set_facecolor(SURF)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(a.out_png, facecolor=SURF, bbox_inches='tight')
    print('wrote', a.out_json, a.out_png)


if __name__ == '__main__':
    main()
