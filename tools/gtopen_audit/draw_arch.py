#!/usr/bin/env python3
"""GTOpen preflop solver — architecture + measured cost figure for the T2 audit.

    python3 tools/gtopen_audit/draw_arch.py --prof-mr2 prof_mr2.json --prof-mr3 prof_mr3.json \
        --out docs/GTOPEN_ARCH_AUDIT_V1.png

Left: the pipeline as implemented in vendor/gtopen/crates/solver/src/preflop (each box
labelled EXACT / MODEL / MC so identity never depends on colour alone).
Right: measured terminal CPU share per payoff kind and seconds per DCFR iteration.
"""
import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch

FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
fm.fontManager.addfont(FONT)
matplotlib.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name()
matplotlib.rcParams['axes.unicode_minus'] = False
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C_EXACT, C_MODEL, C_MC = '#2a78d6', '#eb6834', '#1baf7a'   # validated slots 1-3
TAG = {'EXACT': C_EXACT, 'MODEL': C_MODEL, 'MC': C_MC, 'ALGO': '#6b6a64'}

BOXES = [
    ('config', 'PreflopConfig  (mod.rs:61)\n9 seats · posts SB .5/BB 1 · uniform ante 1/9 (≈BBA)\nopen 2bb (SB 2.5) · 3bet ×3/×3.5 · 4bet ×2.2\nmax_raises 2 ⇒ open+3bet only · jam ≥85% stack', 'MODEL'),
    ('tree', 'build() / legal_actions_of()  (mod.rs:842, 3163)\nfull enumeration, per-node Vec/String metadata ≈354 B/node\n30bb: max_raises 2→75.7k nodes · 3→1.75M · 4→16.1M', 'EXACT'),
    ('chance', 'chance = 169 hand classes per seat, independent\nroot reach = combos/1326; NO joint card removal', 'MODEL'),
    ('cfr', 'try_iterate()  (mod.rs:2016)\nfull-tree vector CFR, 9 alternating traversals / iter\nDCFR α1.5 β0 γ2 · regret pruning after 32 it · rayon depth<7', 'ALGO'),
    ('term', 'terminal_value()  (mod.rs:1673)\nfold-win: exact chips  ·  HU pot-share: pairwise 169×169 table × realization r\n3+ way pot-share: coupled_deck_v1 showdown share, NO realization', 'MODEL'),
    ('eq', 'EquityTable (equity.rs)  MC 1200 samples/pair (server default 20000)\nmean |err| vs exact 0.011 (1200) / 0.002 (20000)\nCoupledDeck (multiway.rs) 1024 fixed particles, seed 90210/env', 'MC'),
    ('upd', 'regret & strategy-sum arenas: f32, 2×(actions×169) per action node\nDCFR discount over whole arena each iteration', 'ALGO'),
    ('gap', 'gaps_and_evs()  (mod.rs:3753)\nBR vs average strategy, per seat, IN THE MODEL GAME\nsmall gap ≠ poker Nash', 'ALGO'),
    ('io', 'save_game / load_game (save.rs)  — same table: resume bit-exact (verified)\nJSON header (config, iteration, locks) + raw f32 arenas\nNOT stored: eq samples/seed, multiway seed, fit → other-seed load accepted', 'EXACT'),
    ('out', 'node / export → per-class action frequencies (169)\n(average strategy)', 'EXACT'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prof-mr2', required=True)
    ap.add_argument('--prof-mr3', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    p2 = json.load(open(a.prof_mr2))
    p3 = json.load(open(a.prof_mr3))

    fig = plt.figure(figsize=(17, 11), dpi=120)
    fig.patch.set_facecolor(SURF)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], height_ratios=[1, 1], wspace=0.12, hspace=0.35)
    ax = fig.add_subplot(gs[:, 0])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(BOXES) + 0.6)
    ax.axis('off')
    for i, (key, text, tag) in enumerate(BOXES):
        y = len(BOXES) - i - 0.5
        col = TAG[tag]
        ax.add_patch(FancyBboxPatch((0.25, y - 0.42), 9.5, 0.84, boxstyle='round,pad=0.02',
                                    fc='white', ec=col, lw=2.2))
        ax.add_patch(FancyBboxPatch((0.25, y - 0.42), 0.95, 0.84, boxstyle='round,pad=0.02',
                                    fc=col, ec=col, lw=0))
        ax.text(0.72, y, '%d\n%s' % (i + 1, tag), ha='center', va='center', fontsize=9, color='white',
                fontweight='bold', linespacing=1.3)
        ax.text(1.35, y, text, ha='left', va='center', fontsize=8.6, color=INK, linespacing=1.35)
    ax.text(0.25, len(BOXES) + 0.25,
            '현재 GTOpen preflop solver — 코드 흐름 1→10\nEXACT=정확/결정적 · MODEL=근사 모델 · MC=몬테카를로 · ALGO=알고리즘',
            fontsize=11, color=INK, va='center')

    # right top: terminal CPU share (pilot + mr3)
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor(SURF)
    kinds = ['mw_5plus', 'mw_4way', 'mw_3way', 'hu_static', 'dead_seat', 'zero_reach', 'fold_win']
    labels = ['multiway 5+', 'multiway 4', 'multiway 3', 'HU table', 'dead seat', 'zero reach', 'fold win']

    def shares(p, iters):
        rows = {r['kind']: r['cpu_ms'] for r in p['profile_iterations']['terminal']}
        cpu = p['profile_iterations']['traverse_wall_ms'] * p['threads']
        term = [rows.get(k, 0.0) for k in kinds]
        other = max(0.0, cpu - sum(term))
        return [100 * x / cpu for x in term] + [100 * other / cpu]
    s2, s3 = shares(p2, 5), shares(p3, 1)
    labs = labels + ['기타 traverse']
    y = range(len(labs))
    ax2.barh([v + 0.2 for v in y], s2, 0.38, color=C_EXACT, label='pilot max_raises 2 (75.7k nodes)')
    ax2.barh([v - 0.2 for v in y], s3, 0.38, color=C_MODEL, label='max_raises 3 (1.75M nodes)')
    for v, a2, a3 in zip(y, s2, s3):
        ax2.text(a2 + 0.8, v + 0.2, '%.1f%%' % a2, va='center', fontsize=8, color=INK)
        ax2.text(a3 + 0.8, v - 0.2, '%.1f%%' % a3, va='center', fontsize=8, color=INK)
    ax2.set_yticks(list(y))
    ax2.set_yticklabels(labs, fontsize=9)
    ax2.set_xlim(0, 85)
    ax2.set_ylim(len(labs) - 0.4, -0.7)
    ax2.set_xlabel('iteration CPU 중 비율 (%)', fontsize=9, color=MUTED)
    ax2.legend(fontsize=8, frameon=False, loc='lower right')
    ax2.set_title('실측: CFR 반복 CPU 분해 (30bb, 4 threads)', fontsize=11, loc='left', color=INK)
    for sp in ('top', 'right'):
        ax2.spines[sp].set_visible(False)

    # right bottom: seconds per iteration vs nodes
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor(SURF)
    it2 = sum(p2['per_iter_ms'][1:]) / len(p2['per_iter_ms'][1:]) / 1000
    it3 = p3['per_iter_ms'][0] / 1000
    n2, n3, n4 = 75669, 1751033, 16081351
    it4 = it3 * n4 / n3
    xs = [n2, n3, n4]
    ys = [it2, it3, it4]
    ax3.plot(xs[:2], ys[:2], 'o-', color=C_EXACT, ms=8, lw=2, label='실측')
    ax3.plot(xs[1:], ys[1:], 'o--', color=C_MODEL, ms=8, lw=2, label='선형 외삽 (max_raises 4 = 30bb 전체 합법 트리)')
    for x_, y_, t in zip(xs, ys, ['pilot %.0fs' % it2, 'mr3 %.0fs' % it3, 'mr4 ≈%.0f min\narena 21.7GB + meta ≈5.7GB' % (it4 / 60)]):
        ax3.text(x_ * 1.15, y_, t, fontsize=8.5, va='center', color=INK)
    ax3.set_xscale('log')
    ax3.set_yscale('log')
    ax3.set_xlim(3e4, 2e8)
    ax3.set_xlabel('tree nodes (log)', fontsize=9, color=MUTED)
    ax3.set_ylabel('초 / DCFR iteration (log)', fontsize=9, color=MUTED)
    ax3.grid(color=GRID, lw=0.8)
    ax3.legend(fontsize=8, frameon=False, loc='upper left')
    ax3.set_title('반복 1회 비용 스케일 (4 threads)', fontsize=11, loc='left', color=INK)
    for sp in ('top', 'right'):
        ax3.spines[sp].set_visible(False)
    fig.savefig(a.out, facecolor=SURF, bbox_inches='tight')
    print('wrote', a.out)


if __name__ == '__main__':
    main()
