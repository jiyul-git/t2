#!/usr/bin/env python3
"""Figure for DEFENSE_RESIDUAL_RESULT.md -> docs/DEFENSE_RESIDUAL_V1.png. Read-only.

  python3 tools/draw_defense_residual.py --replay <cap30.json from tmp_defense_residual_replay.py>

Palette: validated categorical slots 1-5 (light). Contrast WARN for slots 3-5 ->
every bar carries a visible value label.
"""
import argparse
import json
import pathlib

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
fm.fontManager.addfont(FONT)
matplotlib.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name()
matplotlib.rcParams['axes.unicode_minus'] = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
ARMS = ['current', 'compact', 'cand_def', 'cand_logit', 'cand_node_logit']
LABEL = {'current': 'current (test)', 'compact': 'compact 10bin+sem',
         'cand_def': 'cand_def (요청 후보)', 'cand_logit': 'cand_logit',
         'cand_node_logit': 'cand_node_logit'}
COL = dict(zip(ARMS, ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']))
INK, MUTED, GRID, SURF = '#1f1f1e', '#6b6a64', '#e6e5df', '#fcfcfb'


def style(ax):
    ax.set_facecolor(SURF)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis='y', color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def bars(ax, groups, vals, fmt, labels=None):
    n = len(ARMS)
    w = 0.8 / n
    for i, arm in enumerate(ARMS):
        xs = [g + (i - (n - 1) / 2) * w for g in range(len(groups))]
        ys = [vals[arm][k] for k in range(len(groups))]
        ax.bar(xs, ys, w * 0.9, color=COL[arm], label=LABEL[arm], linewidth=0)
        lab = labels[arm] if labels else [fmt % y for y in ys]
        for x, y, t in zip(xs, ys, lab):
            ax.text(x, y, t, ha='center', va='bottom', fontsize=7, color=INK,
                    rotation=90)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, fontsize=9, color=INK)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replay', required=True)
    ap.add_argument('--out', default=str(ROOT / 'docs' / 'DEFENSE_RESIDUAL_V1.png'))
    a = ap.parse_args()
    d = json.load(open(ROOT / 'data' / 'gto_public' / 'defense_residual_candidate_20260928.json'))
    rp = json.load(open(a.replay))['summary']
    R = d['results']

    fig, axs = plt.subplots(2, 2, figsize=(15, 10.5), dpi=130)
    fig.patch.set_facecolor(SURF)

    ax = axs[0][0]
    style(ax)
    keys = [('action_brier', 'action Brier'), ('attack_mae', 'attack MAE'),
            ('continue_mae', 'continue MAE')]
    bars(ax, [k[1] for k in keys],
         {m: [R[m]['holdout']['all'][k[0]] for k in keys] for m in ARMS}, '%.3f')
    ax.set_ylim(0, 0.19)
    ax.set_title('(a) 공개 차트 holdout (15/30/100bb) — 낮을수록 좋다', fontsize=11,
                 color=INK, loc='left')
    ax.legend(fontsize=8.5, frameon=False, ncol=2, loc='upper left')

    ax = axs[0][1]
    style(ax)
    st = [10, 15, 20, 30, 50, 100]
    rows = {r['stack']: r for r in d['check_82o'] if r['node'] == 'EP-vs-BB'}
    for m in ARMS:
        ys = [rows[s][m][0] + rows[s][m][1] for s in st]
        ax.plot(st, ys, color=COL[m], linewidth=2, marker='o', markersize=7,
                label=LABEL[m])
        ax.text(104, ys[-1], '%.2f' % ys[-1], fontsize=8, color=INK, va='center')
    ax.plot(st, [0] * len(st), color=INK, linestyle='--', linewidth=1.2,
            label='source (전 스택 fold 100%)')
    ax.set_xscale('log')
    ax.set_xticks(st)
    ax.set_xticklabels([str(s) for s in st])
    ax.set_xlim(9, 125)
    ax.set_ylim(-0.03, 0.65)
    ax.set_xlabel('스택 (bb)', color=MUTED, fontsize=9)
    ax.set_ylabel('continue 확률 (attack + call)', color=MUTED, fontsize=9)
    ax.set_title('(b) BB 82o vs EP — bin smoothing 오류가 남는가', fontsize=11,
                 color=INK, loc='left')
    ax.legend(fontsize=8, frameon=False, loc='upper left')

    ax = axs[1][0]
    style(ax)
    ge = d['gate_eval']
    hp = {m: R[m]['holdout']['pure'] for m in ARMS}
    groups = ['전 스택 pure-fold 모순\n(node×hand 642개 중)', 'pure-fold 셀 모순\n(holdout 2297셀, 높이/10)',
              'pure-continue 셀 모순\n(holdout 2549셀, 높이/10)', 'runtime pure-fold 상태\ncontinue≥0.5 (359개 중)']
    allpure = {m: len(d['allstack_pure_fold_contra'][m]) for m in ARMS}
    vals = {m: [allpure[m], hp[m].get('pure_fold_contra', 0) / 10.0,
                hp[m].get('pure_cont_contra', 0) / 10.0,
                rp['allstack_pure_fold_states']['continue_ge_0.5'][m]] for m in ARMS}
    raw = {m: ['%d' % allpure[m], '%d' % hp[m].get('pure_fold_contra', 0),
               '%d' % hp[m].get('pure_cont_contra', 0),
               '%d' % rp['allstack_pure_fold_states']['continue_ge_0.5'][m]] for m in ARMS}
    bars(ax, groups, vals, '%.1f', raw)
    ax.set_ylim(0, 80)
    ax.set_title('(c) 의미론 게이트 — 라벨은 실제 개수. 막대 높이는 /10 축척 포함', fontsize=11,
                 color=INK, loc='left')

    ax = axs[1][1]
    style(ax)
    ref = rp['vs_reference']
    groups = ['action Brier vs 차트보간\n(597상태)', 'argmax ≠ 차트보간 (개수)\n높이/1000',
              'argmax flip vs current (개수)\n높이/1000']
    vals = {m: [ref[m]['action_brier'], ref[m]['argmax_disagree'] / 1000.0,
                (rp['arms'][m]['all']['flips'] / 1000.0) if m != 'current' else 0.0]
            for m in ARMS}
    raw = {m: ['%.4f' % ref[m]['action_brier'], '%d' % ref[m]['argmax_disagree'],
               ('%d' % rp['arms'][m]['all']['flips']) if m != 'current' else '-'] for m in ARMS}
    bars(ax, groups, vals, '%.3f', raw)
    ax.set_ylim(0, 0.14)
    ax.set_title('(d) 동일 runtime state 재생 — 30시드, 적격 상태 627', fontsize=11,
                 color=INK, loc='left')

    fig.tight_layout()
    fig.savefig(a.out, facecolor=SURF, bbox_inches='tight')
    print('wrote', a.out)


if __name__ == '__main__':
    main()
