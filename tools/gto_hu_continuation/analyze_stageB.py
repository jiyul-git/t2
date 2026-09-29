#!/usr/bin/env python3
"""Stage B of panel v2: the damped outer fixed point on the 72-flop panel (warm start at P6d).

    python3 tools/gto_hu_continuation/analyze_stageB.py --out-json data/gto_hu_continuation/panel72/outer_v2_damped_a05/analysis.json \
        --out-png docs/GTO_HU_V2_STAGEB_LOOP.png

Reports, with the same per-step metrics as outer_loop.py (no new threshold):
- per step: aggregate mixes, preflop gap, range L1 vs the previous step, measured table change,
  postflop exploitability, unallocated chips, max class-frequency change;
- the classes whose strategy still moves by > 0.1 between the last two steps (as in v1);
- CI half-width of the last measured 72-flop table at its own ranges (vs stage A at P6d);
- watch classes: 24-flop P6d strategy vs the last 72-flop step's strategy, with the last
  step's action EVs (read-only dump) and value/CI of the last measured table;
- BB classes folding > 50% at P6d vs at the last step.
"""
import argparse
import json
import os

D = 'data/gto_hu_continuation/'
J2_FLIPPERS = ['73o', 'A3o', '72s', 'J2s', 'Q3s', 'A3s']
WATCH = ['JTs', 'JTo', 'KQo', 'T7o', 'A2o', '85s', '43s', 'T7s']
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'


def seat(t, pos):
    return next(s for s in t['seats'] if s['position'] == pos)


def l1(a, b, pos):
    x = next(p for p in a['players'] if p['position'] == pos)['class_reach_normalized']
    y = next(p for p in b['players'] if p['position'] == pos)['class_reach_normalized']
    return sum(abs(i - j) for i, j in zip(x, y))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', default=D + 'panel72/outer_v2_damped_a05')
    ap.add_argument('--p6d', default=D + 'panel72/stageA/terminal_p6d.json')
    ap.add_argument('--t24', default=D + 'outer_v1_damped_a05/k6/table_measured.json')
    ap.add_argument('--stageA', default=D + 'panel72/stageA/analysis.json')
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-png', required=True)
    a = ap.parse_args()
    log = json.load(open(os.path.join(a.run, 'outer_log.json')))
    ks = sorted(s['k'] for s in log['steps'])
    T = {k: json.load(open(os.path.join(a.run, f'k{k}', 'terminal.json'))) for k in ks}
    V = {k: json.load(open(os.path.join(a.run, f'k{k}', 'table_measured.json'))) for k in ks}
    p6d = json.load(open(a.p6d))
    L = p6d['class_labels']
    steps = []
    for s in sorted(log['steps'], key=lambda s: s['k']):
        m = s['metrics']
        steps.append({'k': s['k'], 'gap': m['preflop_gap_total'], 'mix': m['mix'],
                      'range_L1': {p: v['L1'] for p, v in m.get('range_distance', {}).items()},
                      'measured_table_change': {p: {'mean': v['mean_abs_dV_bb'], 'max': v['max_abs_dV_bb']} for p, v in m.get('value_delta', {}).items()},
                      'max_class_frequency_delta': m.get('max_class_frequency_delta'),
                      'postflop_exploitability_pct_pot': m.get('postflop_exploitability_pct_pot'),
                      'unallocated_bb': m.get('table_unallocated_bb'),
                      'ci_halfwidth_mean': {p: seat(V[s['k']], p)['mean_ci95_halfwidth_bb'] for p in ('BTN', 'BB')}})
    kl, kp = ks[-1], ks[-2]
    # classes still moving between the last two preflop solves
    moving = {}
    for node in ('rfi_BTN', 'terminal_parent'):
        A, B = T[kp]['frequencies'][node], T[kl]['frequencies'][node]
        rows = []
        for h in range(169):
            d = max(abs(A['class_strategy'][i][h] - B['class_strategy'][i][h]) for i in range(len(A['actions'])))
            if d > 0.1:
                rows.append({'class': L[h], 'max_abs_change': d})
        moving[node] = sorted(rows, key=lambda r: -r['max_abs_change'])
    # watch classes: P6d (24-flop game) vs last step (72-flop game)
    last = T[kl]
    av = last['action_values']
    t24 = json.load(open(a.t24))
    watch = {'BB': [], 'BTN': []}
    for pos, node, names, lst in (('BB', 'terminal_parent', ['fold', 'call', '3bet', 'jam'], J2_FLIPPERS + WATCH),
                                  ('BTN', 'rfi_BTN', ['fold', 'raise', 'jam'], WATCH)):
        for c in lst:
            h = L.index(c)
            ev = [v[h] for v in av[node]['ev_bb']]
            o = sorted(range(len(ev)), key=lambda i: -ev[i])
            s24, s72 = seat(t24, pos), seat(V[kl], pos)
            watch[pos].append({
                'class': c, 'list': 'J2 flipper' if c in J2_FLIPPERS else 'watch',
                'strategy_p6d_24flop': dict(zip(names, (s[h] for s in p6d['frequencies'][node]['class_strategy']))),
                f'strategy_p{kl}_72flop': dict(zip(names, (s[h] for s in last['frequencies'][node]['class_strategy']))),
                f'strategy_p{kp}_72flop': dict(zip(names, (s[h] for s in T[kp]['frequencies'][node]['class_strategy']))),
                'ev_last': dict(zip(names, ev)), 'best_last': names[o[0]], 'margin_last': ev[o[0]] - ev[o[1]], 'second_last': names[o[1]],
                'V24_p6d': s24['gross'][h], 'ci24_halfwidth': (s24['gross_ci95_hi'][h] - s24['gross_ci95_lo'][h]) / 2,
                'V72_last': s72['gross'][h], 'ci72_halfwidth_last': (s72['gross_ci95_hi'][h] - s72['gross_ci95_lo'][h]) / 2,
            })
    fold = lambda t: {L[h]: t['frequencies']['terminal_parent']['class_strategy'][0][h] for h in range(169)
                      if t['frequencies']['terminal_parent']['class_strategy'][0][h] > 0.5}
    stA = json.load(open(a.stageA))
    res = {'run': a.run, 'steps': steps, 'last_step': kl,
           'aggregates': {'P6d_24flop': p6d['frequencies'], f'P{kl}_72flop': last['frequencies']},
           'range_L1_P6d_to_last': {p: l1(p6d, last, p) for p in ('BTN', 'BB')},
           'classes_moving_gt_0_1_last_two_steps': moving,
           'ci_halfwidth_last_step': {p: seat(V[kl], p)['mean_ci95_halfwidth_bb'] for p in ('BTN', 'BB')},
           'ci_halfwidth_stageA': {p: stA['seats'][p]['ci_halfwidth_72']['mean'] for p in ('BTN', 'BB')},
           'watch': watch, 'bb_fold_gt_half': {'P6d_24flop': fold(p6d), f'P{kl}_72flop': fold(last)},
           'provenance': {k: {'ranges_hash': T[k]['ranges_hash_fnv1a64'], 't2_cont_file': T[k]['t2_cont_file'],
                              'panel_hash': V[k]['provenance']['panel_hash_sha256'], 'solver_commits': V[k]['provenance']['solver_commits']}
                          for k in ks}}
    json.dump(res, open(a.out_json, 'w'), indent=1)
    for s in steps:
        print(s['k'], 'gap %.5f' % s['gap'], 'BB', {k: round(v, 3) for k, v in s['mix']['terminal_parent'].items()},
              'BTN', {k: round(v, 3) for k, v in s['mix']['rfi_BTN'].items()}, 'L1', {k: round(v, 3) for k, v in s['range_L1'].items()},
              'dV', {k: (round(v['mean'], 3), round(v['max'], 3)) for k, v in s['measured_table_change'].items()},
              'unalloc %.4f' % s['unallocated_bb'], 'CI', {k: round(v, 3) for k, v in s['ci_halfwidth_mean'].items()})
    print('moving', {k: [(r['class'], round(r['max_abs_change'], 2)) for r in v] for k, v in moving.items()})
    print('fold>0.5', {k: sorted(v) for k, v in res['bb_fold_gt_half'].items()})
    for pos in watch:
        for r in watch[pos]:
            print(pos, r['class'], 'P6d', {k: round(v, 2) for k, v in r['strategy_p6d_24flop'].items()},
                  f'P{kl}', {k: round(v, 2) for k, v in r[f'strategy_p{kl}_72flop'].items()},
                  'best', r['best_last'], 'm %.3f' % r['margin_last'], 'V %.3f±%.3f -> %.3f±%.3f' % (r['V24_p6d'], r['ci24_halfwidth'], r['V72_last'], r['ci72_halfwidth_last']))
    figure(res, a.out_png)


def figure(res, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    st = res['steps']
    ks = [s['k'] for s in st]
    fig, ax = plt.subplots(1, 3, figsize=(18, 5.5), dpi=120)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    for key, col, lab in (('fold', C2, 'BB fold'), ('jam_30', C3, 'BB jam')):
        g.plot(ks, [s['mix']['terminal_parent'][key] for s in st], marker='o', color=col, lw=2, label=lab)
    g.plot(ks, [s['mix']['rfi_BTN']['raise_2'] - 0.25 for s in st], marker='s', color=C1, lw=2, label='BTN open − 0.25')
    g.set_title('(1) aggregates per step (k6 = P6d, 24-flop game)', loc='left', fontsize=11, color=INK)
    g.set_xlabel('outer step k', fontsize=9, color=MUTED)
    g.legend(fontsize=8, frameon=False)
    g = ax[1]
    for pos, col in (('BTN', C1), ('BB', C2)):
        xs = [s['k'] for s in st if pos in s['range_L1']]
        g.plot(xs, [s['range_L1'][pos] for s in st if pos in s['range_L1']], marker='o', color=col, lw=2, label=f'{pos} range L1 vs previous step')
        g.plot(xs, [s['measured_table_change'][pos]['mean'] for s in st if pos in s['range_L1']], marker='s', ls='--', color=col, lw=1.5,
               label=f'{pos} mean |ΔV| measured (bb)')
    g.set_title('(2) step-to-step change', loc='left', fontsize=11, color=INK)
    g.set_xlabel('outer step k', fontsize=9, color=MUTED)
    g.legend(fontsize=8, frameon=False)
    g = ax[2]
    rows = res['watch']['BB']
    kl = res['last_step']
    xs = list(range(len(rows)))
    g.bar([x - 0.2 for x in xs], [r['strategy_p6d_24flop']['fold'] for r in rows], 0.38, color=C2, label='fold, P6d (24 flops)')
    g.bar([x + 0.2 for x in xs], [r[f'strategy_p{kl}_72flop']['fold'] for r in rows], 0.38, color=C1, label=f'fold, P{kl} (72 flops)')
    g.scatter([x + 0.2 for x in xs], [r[f'strategy_p{kl}_72flop']['jam'] for r in rows], marker='^', color=INK, s=24, zorder=3, label=f'jam, P{kl}')
    g.scatter([x - 0.2 for x in xs], [r['strategy_p6d_24flop']['jam'] for r in rows], marker='v', color=MUTED, s=24, zorder=3, label='jam, P6d')
    g.set_xticks(xs)
    g.set_xticklabels([r['class'] + ('*' if r['list'] == 'J2 flipper' else '') for r in rows], fontsize=8, rotation=45)
    g.set_title('(3) BB watch classes: fold / jam frequency (* = J2 flipper)', loc='left', fontsize=11, color=INK)
    g.legend(fontsize=7, frameon=False)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
