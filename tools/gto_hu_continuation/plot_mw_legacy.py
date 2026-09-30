#!/usr/bin/env python3
"""Figure for T0/T2-B: flop-reach coverage (P9 census), P0 -> P9 reach decomposition, and the
3-way realization-transfer proxy (best-response shares, legacy vs proxy; a proxy, not a measurement).

    python3 tools/gto_hu_continuation/plot_mw_legacy.py docs/GTO_TERMINAL_MW_LEGACY_V2.png
"""
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

D = 'data/gto_terminal_expansion/'
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C1, C2, C3, C4 = '#2a78d6', '#eb6834', '#1baf7a', '#8a5cd1'


def main():
    c = json.load(open(D + 'census_p9.json'))
    m = json.load(open(D + 'mw_legacy/analysis.json'))
    tp = json.load(open(D + 'mw_legacy/transfer_proxy.json'))
    fig, ax = plt.subplots(1, 3, figsize=(19, 6), dpi=120)
    fig.patch.set_facecolor(SURF)
    # (1) coverage: top terminals by flop share, coloured by family
    g = ax[0]
    rows = c['terminals'][:8]
    lab = {6: 'SB–BB (HU)', 246: 'CO+SB+BB (3-way)', 46: 'BTN+SB+BB (3-way)', 28: 'BTN–BB (HU, solved)', 228: 'CO–BB (HU)',
           1371: 'CO–BTN 3bet (HU)', 420: 'CO+BTN+BB (3-way)', 508: '4-way'}
    col = [C3 if r['current_injected_terminal'] else (C1 if r['live_count'] == 2 else C2) for r in rows]
    ys = list(range(len(rows)))[::-1]
    g.barh(ys, [r['share_of_flop_reach'] * 100 for r in rows], color=col, height=0.7)
    for y, r in zip(ys, rows):
        g.text(r['share_of_flop_reach'] * 100 + 0.3, y, f"{r['share_of_flop_reach']:.1%}", va='center', fontsize=8, color=INK)
    g.set_yticks(ys)
    g.set_yticklabels([f"node {r['terminal_node']}  {lab.get(r['terminal_node'], '')}" for r in rows], fontsize=8)
    g.set_xlabel('% of flop reach (P9)', fontsize=9, color=MUTED)
    g.set_title('(1) P9 census: HU (blue), solved (green), multiway legacy (orange)', loc='left', fontsize=10, color=INK)
    # (2) decomposition
    g = ax[1]
    nodes = ['28', '46', '246']
    names = ['node 28\nBTN–BB (solved)', 'node 46\nBTN+SB+BB', 'node 246\nCO+SB+BB']
    colors = [MUTED, C1, C2, C4]
    for i, n in enumerate(nodes):
        pos = neg = 0.0
        for j, t in enumerate(m['decomposition'][n]['terms']):
            v = t['dlog']
            if abs(v) < 0.005:  # |term| below 0.005: no bar, listed in the node caption
                continue
            base = pos if v > 0 else neg
            g.bar([i], [v], 0.55, bottom=[base], color=colors[j % 4], label=t['decision'].split(':')[0] if i == 1 or (i == 0 and j == 3) else None)
            g.text(i + 0.3, base + v / 2, f"{t['decision']} {v:+.3f}", fontsize=7, va='center', color=INK,
                   bbox=dict(facecolor=SURF, edgecolor='none', pad=1))
            if v > 0:
                pos += v
            else:
                neg += v
        d = m['decomposition'][n]
        if pos == 0 and neg == 0:
            g.text(i, -0.04, 'every decision term = 0.000\n(no decision on the CO path\ntouches node 28)', ha='center', va='top', fontsize=8, color=MUTED)
        g.text(i, max(pos, 0) + 0.02 + (0.04 if pos == 0 and neg == 0 else 0), f"reach {d['reach_P0']:.4f}→{d['reach_P9']:.4f} ({d['relative_change']:+.1%})", ha='center', fontsize=8, color=INK)
    g.axhline(0, color=INK, lw=1)
    g.set_xticks(range(len(nodes)))
    g.set_xticklabels(names, fontsize=8)
    g.set_xlim(-0.5, 2.9)
    g.set_ylabel('Δ log reach, P0 → P9 (exact split by decision)', fontsize=9, color=MUTED)
    g.set_title('(2) why node 46 grew: BTN open +0.197, SB flat +0.164, BB 0', loc='left', fontsize=10, color=INK)
    # (3) proxy best-response shares
    g = ax[2]
    labels, a, b = [], [], []
    for n in ('46', '246'):
        for d in tp['nodes'][n]['decisions']:
            labels.append(f"node {n}\n{d['actor']} {d['on_path_action']}")
            a.append(d['best_response_share_of_on_path_action_legacy'])
            b.append(d['best_response_share_of_on_path_action_proxy'])
    xs = list(range(len(labels)))
    g.bar([x - 0.18 for x in xs], a, 0.34, color=C2, label='legacy coupled-deck payoff')
    g.bar([x + 0.18 for x in xs], b, 0.34, color=C1, label='HU-realization transfer proxy (assumption)')
    for x, v1, v2 in zip(xs, a, b):
        g.text(x - 0.18, v1 + 0.01, f'{v1:.2f}', ha='center', fontsize=7, color=INK)
        g.text(x + 0.18, v2 + 0.01, f'{v2:.2f}', ha='center', fontsize=7, color=INK)
    g.set_xticks(xs)
    g.set_xticklabels(labels, fontsize=7)
    g.set_ylabel('share of the actor\'s mass whose best action is the on-path action', fontsize=8, color=MUTED)
    g.set_title('(3) 3-way: decisions under legacy vs proxy (not a measurement)', loc='left', fontsize=10, color=INK)
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
