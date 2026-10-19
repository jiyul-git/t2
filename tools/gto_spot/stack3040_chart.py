#!/usr/bin/env python3
"""PNG summary of the 30 / 40 bb records (docs/GTO_STACK_30_40_V1.md) -> docs/img/GTO_STACK_30_40_V1.png"""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'
SEATS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']
R = {S: json.load(open(f'/home/user/t2/data/gto_spot/records/s{S}.json')) for S in (30, 40)}
nf = lambda n: [p for p in n['line'] if 'Fold' not in p]
pct = lambda m, pre: 100 * sum(v for a, v in m.items() if a.startswith(pre))

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'text.color': INK, 'axes.labelcolor': INK2,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID})
fig, axes = plt.subplots(2, 2, figsize=(13, 8.4), facecolor=SURF, gridspec_kw={'hspace': 0.45, 'wspace': 0.1})
for k, S in enumerate((30, 40)):
    ax = axes[0, k]; ax.set_facecolor(SURF)
    rfi = {n['actor']: n['mix'] for n in R[S]['nodes'] if n['situation'] == 'first_in'}
    for i, s in enumerate(SEATS):
        y = len(SEATS) - 1 - i; m = rfi[s]
        o, l = pct(m, 'Raise'), pct(m, 'Limp')
        ax.barh(y, o, height=0.62, color=C1, edgecolor=SURF, linewidth=1)
        if l > 0.05:
            ax.barh(y, l, left=o, height=0.62, color=C3, edgecolor=SURF, linewidth=1)
        ax.text(o + l + 1.5, y, f'{o:.0f}%' + (f' + limp {l:.0f}%' if l > 0.05 else ''), va='center', fontsize=9, color=INK2)
    ax.set_xlim(0, 130); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_yticks(range(len(SEATS))); ax.set_yticklabels(SEATS[::-1] if k == 0 else [])
    ax.set_xlabel('% of hands'); ax.grid(axis='x', color=GRID); ax.set_axisbelow(True); ax.tick_params(axis='y', length=0)
    for sp in ('top', 'right', 'left'): ax.spines[sp].set_visible(False)
    ax.set_title(f'{S} bb first in  (gap {R[S]["gap_total_exact_bb"]:.4f} bb)', loc='left', fontsize=11)
    ax = axes[1, k]; ax.set_facecolor(SURF)
    OP = SEATS[:-1] + ['SB']
    for i, s in enumerate(OP):
        n = next(n for n in R[S]['nodes'] if n['actor'] == 'BB' and nf(n) and len(nf(n)) == 1 and nf(n)[0].startswith(s + ':Raise'))
        t3, j = pct(n['mix'], '3-bet'), pct(n['mix'], 'All-in')
        ax.bar(i, t3, width=0.62, color=C1, edgecolor=SURF, linewidth=1)
        ax.bar(i, j, bottom=t3, width=0.62, color=C2, edgecolor=SURF, linewidth=1)
        ax.text(i, t3 + j + 0.4, f'{t3 + j:.0f}%', ha='center', fontsize=9, color=INK2)
    ax.set_xticks(range(len(OP))); ax.set_xticklabels(OP); ax.set_ylim(0, 20)
    ax.set_ylabel('BB 3-bet frequency (%)' if k == 0 else ''); ax.grid(axis='y', color=GRID); ax.set_axisbelow(True)
    for sp in ('top', 'right'): ax.spines[sp].set_visible(False)
    ax.set_title(f'{S} bb: BB 3-bets vs an open from each seat (rest: call; fold ~0 %)', loc='left', fontsize=11)
fig.text(0.07, 0.985, 'Stack buckets 30 / 40 bb: first in and BB 3-bet vs an open (quick records)', fontsize=13, weight='bold')
fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in (C1, C3, C2)],
           labels=['Open 2.0 (SB 3.0) / non-jam 3-bet', 'SB limp', '3-bet jam'], loc='upper left', bbox_to_anchor=(0.065, 0.965), ncol=3, frameon=False)
fig.text(0.07, 0.015, 'Caveat: flat calls into a flop pot use the static continuation model; the BB\'s ~100 % defence (call) vs a 2.0 open is '
         'model-dependent and a refinement target. Records data/gto_spot/records/s30.json, s40.json.', fontsize=9, color=INK2)
fig.savefig('/home/user/t2/docs/img/GTO_STACK_30_40_V1.png', dpi=130, facecolor=SURF, bbox_inches='tight')
print('ok')
