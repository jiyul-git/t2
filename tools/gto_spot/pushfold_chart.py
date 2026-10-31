#!/usr/bin/env python3
"""PNG summary of the push/fold records (docs/GTO_PUSHFOLD_10_25_V1.md): RFI open / jam by seat per bucket, and BB call vs a jam.
    python3 tools/gto_spot/pushfold_chart.py -> docs/img/GTO_PUSHFOLD_10_25_V1.png
"""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
OPEN, JAM = '#2a78d6', '#eb6834'
SEQ = {10: '#86b6ef', 15: '#3987e5', 20: '#1c5cab', 25: '#0d366b'}
SEATS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']
R = {S: json.load(open(f'/home/user/t2/data/gto_spot/records/pf{S}.json')) for S in (10, 15, 20, 25)}


def nf(n):
    return [p for p in n['line'] if 'Fold' not in p]


plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'text.color': INK, 'axes.labelcolor': INK2,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID})
fig = plt.figure(figsize=(14, 8.6), facecolor=SURF)
gs = fig.add_gridspec(2, 4, height_ratios=[1.15, 1], hspace=0.42, wspace=0.12)
for k, S in enumerate((10, 15, 20, 25)):
    ax = fig.add_subplot(gs[0, k], facecolor=SURF)
    rfi = {n['actor']: n['mix'] for n in R[S]['nodes'] if n['situation'] == 'first_in'}
    for i, s in enumerate(SEATS):
        m = rfi[s]
        o = 100 * sum(v for a, v in m.items() if a.startswith('Raise'))
        j = 100 * sum(v for a, v in m.items() if a.startswith('All-in'))
        y = len(SEATS) - 1 - i
        if o > 0.05:
            ax.barh(y, o, height=0.62, color=OPEN, edgecolor=SURF, linewidth=1)
        ax.barh(y, j, left=o, height=0.62, color=JAM, edgecolor=SURF, linewidth=1)
        ax.text(o + j + 1.5, y, f'{o + j:.0f}%', va='center', fontsize=9, color=INK2)
    ax.set_xlim(0, 100); ax.set_yticks(range(len(SEATS))); ax.set_yticklabels(SEATS[::-1] if k == 0 else [])
    ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(['0', '25', '50', '75', '100']); ax.set_xlabel('% of hands')
    ax.grid(axis='x', color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    for sp in ('top', 'right', 'left'):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.set_title(f'{S} bb  (gap {R[S]["gap_total_exact_bb"]:.4f} bb)', fontsize=11, color=INK, loc='left')
fig.text(0.07, 0.955, 'First-in (RFI) frequency by seat: open 2.0 bb (SB 3.0) and open jam', fontsize=13, color=INK, weight='bold')
fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=OPEN), plt.Rectangle((0, 0), 1, 1, color=JAM)],
           labels=['Open 2.0 bb (SB 3.0)', 'Open jam'], loc='upper right', bbox_to_anchor=(0.97, 0.975), ncol=2, frameon=False)

ax = fig.add_subplot(gs[1, :2], facecolor=SURF)
JS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']
for S in (10, 15, 20, 25):
    ys, xs = [], []
    for i, s in enumerate(JS):
        for n in R[S]['nodes']:
            f = nf(n)
            if n['actor'] == 'BB' and len(f) == 1 and f[0].startswith(s + ':All-in') and not n['unsupported_low_reach']:
                xs.append(i); ys.append(100 * sum(v for a, v in n['mix'].items() if a.startswith('Call')))
    ax.plot(xs, ys, color=SEQ[S], linewidth=2, marker='o', markersize=6, markeredgecolor=SURF, markeredgewidth=1.5, label=f'{S} bb')
    ax.text(xs[-1] + 0.12, ys[-1], f'{S} bb', va='center', fontsize=9, color=INK2)
ax.set_xticks(range(len(JS))); ax.set_xticklabels(JS); ax.set_ylim(0, 60); ax.set_xlim(-0.3, len(JS) - 0.3)
ax.set_ylabel('BB call frequency (%)'); ax.grid(axis='y', color=GRID, linewidth=0.8); ax.set_axisbelow(True)
for sp in ('top', 'right'):
    ax.spines[sp].set_visible(False)
ax.set_title('BB calls an open jam from each seat (others folded)', fontsize=11, color=INK, loc='left')
ax.legend(frameon=False, loc='upper left', fontsize=9)

ax = fig.add_subplot(gs[1, 2:]); ax.axis('off')
notes = [
    'Game: 9-max, every seat S bb at hand start (symmetric-stack assumption), ante 1 bb shared, chip EV, no rake.',
    '10 bb: jam / fold.  15-25 bb: fold / open 2.0 (SB 3.0) / jam; facing an open: fold / call / 3-bet jam.',
    'Solver: vendored gtopen preflop DCFR, stop at exact gap <= 0.010 bb (all four pass).',
    'Status quick: no refinement pass; records data/gto_spot/records/pf{10,15,20,25}.json.',
    'Caveat (15-25 bb): flat calls into a flop pot use the static continuation model;',
    '  BB defends ~100 % vs a 2.0 open - model-dependent, a refinement target.',
    '  All-in decisions (jam, call a jam, 3-bet jam) do not depend on that model.',
    'Points with < 1 combo of jams behind them (unsupported_low_reach) are not drawn.',
]
for i, t in enumerate(notes):
    ax.text(0.02, 0.92 - i * 0.115, t, fontsize=9.5, color=INK2 if t.startswith('  ') else INK, transform=ax.transAxes)
fig.savefig('/home/user/t2/docs/img/GTO_PUSHFOLD_10_25_V1.png', dpi=130, facecolor=SURF, bbox_inches='tight')
print('ok')
