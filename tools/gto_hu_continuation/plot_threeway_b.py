#!/usr/bin/env python3
"""B1/B2 figure: 3-way tree/memory breakdown, showdown-only and HU-degeneration validation,
engine convergence (runs 1-3) vs the vendored HU solver.

    python3 tools/gto_hu_continuation/plot_threeway_b.py docs/GTO_TERMINAL_3WAY_B_V2.png
"""
import json
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

O = 'data/gto_terminal_expansion/threeway/'
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C1, C2, C3, C4 = '#2a78d6', '#eb6834', '#1baf7a', '#8a5cd1'


def log_trace(path):
    out = []
    for line in open(path):
        m = re.match(r'it (\d+) expl ([\d.]+)%', line)
        if m:
            out.append((int(m.group(1)), float(m.group(2))))
    return out


def main():
    b1 = json.load(open(O + 'b1_build_node46_Kc7d4h.json'))
    sd = json.load(open(O + 'b2_showdown_node46_Kc7d4h.json'))
    cmp_ = json.load(open(O + 'b2_hu_degen_compare.json'))
    eng = json.load(open(O + 'b2_hu_degen_engine.json'))
    ven = json.load(open(O + 'hu_degen_vendored/Kc7d4h.json'))
    fig, ax = plt.subplots(1, 3, figsize=(19, 6), dpi=120)
    fig.patch.set_facecolor(SURF)
    # (1) memory breakdown
    g = ax[0]
    streets = b1['streets']
    xs = list(range(3))
    a3 = [s['bytes_3_active_nodes'] / 1e9 for s in streets]
    a2 = [s['bytes_2_active_nodes'] / 1e9 for s in streets]
    g.bar(xs, a3, 0.55, color=C2, label='3 players active')
    g.bar(xs, a2, 0.55, bottom=a3, color=C1, label='2 active (one folded, still blocking)')
    for x, s, u, v in zip(xs, streets, a3, a2):
        g.text(x, u + v + 0.2, f"{u + v:.2f} GB\n{s['action_nodes']:,} action nodes", ha='center', fontsize=8, color=INK)
    g.axhline(15, color=MUTED, ls='--', lw=1)
    g.text(-0.4, 15.2, 'machine RAM 15 GB', fontsize=8, color=MUTED)
    tot = b1['bytes_regret_plus_strategy_f32'] / 1e9
    hu = b1['hu_degenerate_tree']['bytes_regret_plus_strategy_f32'] / 1e9
    g.set_xticks(xs)
    g.set_xticklabels(['flop', 'turn (x49)', 'river (x2,352)'], fontsize=9)
    g.set_ylabel('regret + strategy sum, f32 (GB)', fontsize=9, color=MUTED)
    g.set_title(f'(1) node 46 3-way tree, Kc7d4h: {tot:.2f} GB total\n(HU-degenerate tree {hu:.2f} GB; accounting checked on a slice: RSS/accounted = {b1["alloc"]["rss_delta_over_accounted"]:.4f})',
                loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper left')
    # (2) HU degeneration: engine vs vendored class values
    g = ax[1]
    pos = eng['positions']
    for row, col in zip(eng['final']['players'], (C3, C1)):
        p = pos[row['player']]
        ve = next(x for x in ven['players'] if x['position'] == p)
        pts = [(b, a) for a, b in zip(row['class_gross'], ve['gross_eps']) if a is not None and b is not None]
        g.scatter([x for x, _ in pts], [y for _, y in pts], s=10, color=col,
                  label=f"{p}: mean |engine − vendored| {cmp_['players'][p]['mean_abs_class_diff_bb']:.4f} bb")
    lo = min(min(x for x in ve['gross_eps'] if x is not None) for ve in ven['players'])
    hi = max(max(x for x in ve['gross_eps'] if x is not None) for ve in ven['players'])
    g.plot([lo, hi], [lo, hi], color=MUTED, lw=1, ls=':')
    fb = sd['fast_vs_brute_force']['max_relative_difference']
    g.text(0.02, 0.98, f"B2-1 showdown-only (1,176 runouts): fast vs brute force rel. diff {fb:.1e};\n"
                        f"pot conservation error {sd['conservation']['error']:.1e}\n"
                        f"B2-2 HU degeneration: range EV diff {cmp_['players']['BB']['range_value_diff_bb']:+.5f} / {cmp_['players']['BTN']['range_value_diff_bb']:+.5f} bb;\n"
                        f"root mix diff <= {max(s['max_abs_diff'] for s in cmp_['aggregate_strategy']):.4f}; PASS = {cmp_['pass']}",
           transform=g.transAxes, va='top', fontsize=8, color=INK)
    g.set_xlabel('vendored HU solver, class value (bb)', fontsize=9, color=MUTED)
    g.set_ylabel('3-way engine, SB out & non-blocking (bb)', fontsize=9, color=MUTED)
    g.set_title('(2) validation: HU degeneration (per class) and showdown-only', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='lower right')
    # (3) convergence
    g = ax[2]
    for path, lab, col in ((O + 'b2_hu_degen_engine_run1_bug_avg_weight.log', 'engine run 1 (bug: avg-strategy weight)', C2),
                           (O + 'b2_hu_degen_engine_run2_bug_merged_infosets.log', 'engine run 2 (bug: merged info sets)', C4),
                           (O + 'b2_hu_degen_engine.log', 'engine run 3 (fixed)', C1)):
        tr = log_trace(path)
        if tr:
            g.plot([x for x, _ in tr], [y for _, y in tr], marker='o', color=col, lw=2, label=lab)
    g.plot([x for x, _ in ven['trace']], [y for _, y in ven['trace']], marker='s', ls='--', color=INK, lw=1.5, label='vendored HU solver')
    g.axhline(0.3, color=MUTED, ls=':', lw=1)
    g.set_yscale('log')
    g.set_xlabel('iteration', fontsize=9, color=MUTED)
    g.set_ylabel('exploitability (% pot, log)', fontsize=9, color=MUTED)
    g.set_title('(3) convergence: the two engine bugs found by the test', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(sys.argv[1], facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
