#!/usr/bin/env python3
"""A4R robust-policy audit (data/gto_terminal_expansion/a4r_robust/prereg.json).

    python3 tools/gto_hu_continuation/a4r_robust.py run
    python3 tools/gto_hu_continuation/a4r_robust.py analyze [--png docs/GTO_TERMINAL_A4R_ROBUST_V2.png]

Holds the F72 (= P15) and F144 preflop profiles fixed and evaluates each under the A4b tables
(points and blended bootstrap replicates) with t2_cross_eval: loss = gap_total(sigma; T) - gap_total(sigma_T; T).
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a4_audit import BIN, ENV  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
B = E + 'a4b_panel144/'
OUT = E + 'a4r_robust/'
POL = {'sigma72': B + 'F72/point/profile.gtop', 'sigma144': B + 'F144/point/profile.gtop'}


def xeval(save, game_dir, out):
    if not os.path.exists(out):
        subprocess.run([BIN + '/t2_cross_eval', save, out], check=True, env={**os.environ, **ENV, 'T2_CONT_FILE': os.path.join(game_dir, 'manifest.json')},
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return json.load(open(out))


def games(R):
    g = {'M14_72': (B + 'F72/point', R['F72']), 'M14_144': (B + 'F144/point', R['F144'])}
    for size in (72, 144):
        for i, r in R[f'boot{size}'].items():
            if 'gaps' in r:
                g[f'boot{size}_r{int(i):02d}'] = (B + f'F{size}/r{int(i):02d}', r)
    return g


def run(a):
    R = json.load(open(B + 'results.json'))
    os.makedirs(OUT + 'evals', exist_ok=True)
    v = xeval(POL['sigma72'], B + 'F72/point', OUT + 'evals/validation_sigma72_M14_72.json')
    ok = v['gaps'] == R['F72']['gaps'] and v['evs'] == R['F72']['evs']
    print('validation: cross-eval of the F72 save under M14_72 reproduces F72 gaps/EVs exactly:', ok, flush=True)
    if not ok:
        raise SystemExit(f"validation failed: {v['gaps']} vs {R['F72']['gaps']}")
    rows = {}
    for pol, save in POL.items():
        for name, (d, ref) in games(R).items():
            x = xeval(save, d, OUT + f'evals/{pol}__{name}.json')
            rows[f'{pol}|{name}'] = {'policy': pol, 'game': name, 'gap_total': x['gap_total'], 'gaps': x['gaps'], 'evs': x['evs'],
                                     'own_gap_total': ref['gap_total'], 'own_gaps': ref['gaps'], 'positions': x['positions'],
                                     'loss': x['gap_total'] - ref['gap_total'],
                                     'loss_by_seat': {p: g - o for p, g, o in zip(x['positions'], x['gaps'], ref['gaps'])}}
        print(pol, 'done', flush=True)
    json.dump({'validation_exact': ok, 'rows': rows}, open(OUT + 'evals.json', 'w'), indent=1)


def analyze(a):
    D = json.load(open(OUT + 'evals.json'))
    rows = D['rows']
    q95 = lambda xs: sorted(xs)[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]
    pick = lambda pol, pre: [r for r in rows.values() if r['policy'] == pol and r['game'].startswith(pre)]
    res = {'validation_exact': D['validation_exact']}
    res['L_switch'] = rows['sigma72|M14_144']['loss']
    res['L_switch_reverse'] = rows['sigma144|M14_72']['loss']
    res['L_noise_144'] = q95([r['loss'] for r in pick('sigma144', 'boot144')])
    res['L_noise_72'] = q95([r['loss'] for r in pick('sigma72', 'boot72')])
    res['cross'] = {f'{pol} on boot{s}': {'q95': q95([r['loss'] for r in pick(pol, f'boot{s}')]), 'mean': sum(r['loss'] for r in pick(pol, f'boot{s}')) / len(pick(pol, f'boot{s}')),
                                            'max': max(r['loss'] for r in pick(pol, f'boot{s}')), 'n': len(pick(pol, f'boot{s}'))}
                    for pol in ('sigma72', 'sigma144') for s in (72, 144)}
    pos = rows['sigma72|M14_144']['positions']
    res['by_seat_q95'] = {f'{pol} on boot{s}': {p: q95([r['loss_by_seat'][p] for r in pick(pol, f'boot{s}')]) for p in pos}
                          for pol, s in (('sigma72', 72), ('sigma144', 144))}
    res['by_seat_switch'] = rows['sigma72|M14_144']['loss_by_seat']
    if res['L_noise_144'] <= 0.005 and res['L_switch'] <= 0.005:
        cls = 'ROBUST'
    elif res['L_noise_144'] > 0.02 or res['L_switch'] > 0.02:
        cls = 'NOT_ROBUST'
    else:
        cls = 'BORDERLINE'
    res['classification'] = cls
    res['thresholds_bb_per_hand'] = {'robust': 0.005, 'not_robust': 0.02}
    json.dump(res, open(OUT + 'a4r_verdict.json', 'w'), indent=1)
    print(json.dumps(res, indent=1))
    figure(res, rows, a.png)


def figure(res, rows, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
    C = {'sigma72': '#c9a227', 'sigma144': '#2a78d6'}
    fig, ax = plt.subplots(1, 2, figsize=(18, 6.5), dpi=115)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    groups = [('sigma72', 72), ('sigma144', 72), ('sigma72', 144), ('sigma144', 144)]
    data = [[r['loss'] * 100 for r in rows.values() if r['policy'] == p and r['game'].startswith(f'boot{s}')] for p, s in groups]
    bp = g.boxplot(data, positions=range(4), widths=0.5, patch_artist=True, showfliers=True)
    for patch, (p, _) in zip(bp['boxes'], groups):
        patch.set_facecolor(C[p])
        patch.set_alpha(0.6)
    for k in ('medians', 'whiskers', 'caps'):
        for l in bp[k]:
            l.set_color(INK)
    for x, (p, s) in enumerate(groups):
        ys = sorted(r['loss'] * 100 for r in rows.values() if r['policy'] == p and r['game'].startswith(f'boot{s}'))
        g.scatter([x] * len(ys), ys, color=INK, s=8, zorder=3)
    g.axhline(0.5, color='#1baf7a', ls='--', lw=1)
    g.axhline(2.0, color='#c0392b', ls='--', lw=1)
    g.text(3.35, 0.5, 'ROBUST ≤ 0.5', color='#1baf7a', fontsize=8, va='bottom', ha='right')
    g.text(3.35, 2.0, 'NOT ROBUST > 2', color='#c0392b', fontsize=8, va='bottom', ha='right')
    g.set_xticks(range(4))
    g.set_xticklabels([f'{p.replace("sigma", "policy ")}\non 72-panel tables' if s == 72 else f'{p.replace("sigma", "policy ")}\non 144-panel tables' for p, s in groups], fontsize=8)
    g.set_ylabel('policy loss (bb / 100 hands)', fontsize=9, color=MUTED)
    g.set_title('(1) loss of a fixed preflop policy under bootstrap tables (30 each)', loc='left', fontsize=10, color=INK)
    g = ax[1]
    names = ['policy 72 on M14_144\n(L_switch)', 'policy 144 on M14_72', 'q95 policy 144\non 144-panel tables (L_noise_144)', 'q95 policy 72\non 72-panel tables']
    vals = [res['L_switch'], res['L_switch_reverse'], res['L_noise_144'], res['L_noise_72']]
    cols = [C['sigma72'], C['sigma144'], C['sigma144'], C['sigma72']]
    g.barh(range(4), [v * 100 for v in vals], color=cols)
    for i, v in enumerate(vals):
        g.text(v * 100, i, f' {v * 100:.3f}', va='center', fontsize=8, color=INK)
    g.axvline(0.5, color='#1baf7a', ls='--', lw=1)
    g.axvline(2.0, color='#c0392b', ls='--', lw=1)
    g.set_yticks(range(4))
    g.set_yticklabels(names, fontsize=8)
    g.invert_yaxis()
    g.set_xlabel('policy loss (bb / 100 hands)', fontsize=9, color=MUTED)
    g.set_title('(2) pre-registered quantities', loc='left', fontsize=10, color=INK)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.suptitle(f"A4R robust-policy audit: {res['classification']} (loss = exploitability of the fixed policy under table T minus that of T's own solve)",
                 fontsize=11, color=INK, x=0.01, ha='left')
    fig.text(0.01, 0.005, 'Policies: F72 (= A3 P15) and F144 preflop profiles. Tables: A3 k14 rule (0.5 V14 + 0.5 M13, guard) on the 72- and 144-flop panels and on '
             '30 stratified board resamples of each; P14 ranges. Thresholds are provisional research thresholds, not the production-DB criterion.',
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'analyze'])
    ap.add_argument('--png', default=os.path.join(ROOT, 'docs/GTO_TERMINAL_A4R_ROBUST_V2.png'))
    a = ap.parse_args()
    run(a) if a.cmd == 'run' else analyze(a)
