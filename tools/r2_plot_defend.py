#!/usr/bin/env python3
"""R2-B figure: reference vs code (8-max / 9-max) realized defend and 3bet share by stack."""
import json, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = json.load(open(os.path.join(ROOT, 'docs/semantic_audit/r2/defend_reference_comparison.json')))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'docs/semantic_audit/r2/defend_vs_reference.png')
SPOTS = [('BTN-vs-BB', 'BB vs BTN open'), ('EP-vs-BB', 'BB vs EP open'),
         ('BTN-vs-SB', 'SB vs BTN open'), ('EP-vs-BTN', 'BTN vs EP open')]
SER = [('ref', 'reference 8-max chart', '#2a78d6', 'o', '-'),
       ('c8', 'code 8-max (realized)', '#eb6834', 's', '--'),
       ('c9', 'code 9-max (realized)', '#1baf7a', '^', '-')]
INK, MUTED, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'

fig, axes = plt.subplots(2, 4, figsize=(15, 7.2), facecolor=SURF)
for j, (node, title) in enumerate(SPOTS):
    rows = sorted([r for r in C['rows'] if r['ref_node'] == node], key=lambda r: r['stack_bb'])
    r8 = [r for r in rows if r['seats'] == 8]
    r9 = [r for r in rows if r['seats'] == 9]
    xs = [r['stack_bb'] for r in r8]
    data = {
        0: {'ref': [r['ref_defend'] for r in r8], 'c8': [r['L2_defend'] for r in r8],
            'c9': [r['L2_defend'] for r in r9]},
        1: {'ref': [r['ref_3bet_share'] for r in r8], 'c8': [r['L2_3bet_share'] for r in r8],
            'c9': [r['L2_3bet_share'] for r in r9]},
    }
    for i in (0, 1):
        ax = axes[i][j]
        ax.set_facecolor(SURF)
        for key, lab, col, mk, ls in SER:
            ys = data[i][key]
            ax.plot(xs, ys, color=col, lw=2, ls=ls, marker=mk, ms=8, label=lab,
                    markeredgecolor=SURF, markeredgewidth=2)
        ax.set_xscale('log')
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_xticks([15, 20, 30, 50, 100])
        ax.set_xticklabels(['15', '20', '30', '50', '100'], color=MUTED, fontsize=9)
        ax.set_ylim(0, 1.05)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.grid(True, color=GRID, lw=0.8)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        for s in ('left', 'bottom'):
            ax.spines[s].set_color(GRID)
        if i == 0:
            ax.set_title(title, color=INK, fontsize=11, loc='left')
        if j == 0:
            ax.set_ylabel('defend frequency (call + 3bet)' if i == 0 else '3bet share of defend',
                          color=INK, fontsize=10)
        if i == 1:
            ax.set_xlabel('effective stack (bb)', color=MUTED, fontsize=9)
h, l = axes[0][0].get_legend_handles_labels()
fig.legend(h, l, loc='upper center', bbox_to_anchor=(0.5, 0.955), ncol=3, frameon=False, fontsize=10, labelcolor=INK)
fig.suptitle('R2-B  vs-open defense: code at 46a2070 (max-skill, neutral) vs public 8-max MTT chart '
             '(conditions partly unknown; 9-max row is reference-only)', color=INK, fontsize=11, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.91))
fig.savefig(OUT, dpi=130, facecolor=SURF)
print(OUT)
