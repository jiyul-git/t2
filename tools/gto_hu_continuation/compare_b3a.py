#!/usr/bin/env python3
"""B3a: reduced-game monolithic 3-way CFR (A, A') vs HU-frontier factorized (B), criteria from
data/gto_terminal_expansion/threeway/b3a_prereg.json (+ addendum), measurements, full node-46 projection, figure.

    python3 tools/gto_hu_continuation/compare_b3a.py [--png docs/GTO_TERMINAL_B3A_V2.png]
"""
import argparse
import json
import os

O = 'data/gto_terminal_expansion/threeway/'
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
SEAT = {'SB': '#1baf7a', 'BB': '#2a78d6', 'BTN': '#eb6834'}
SCHEME = {'A': ('A mono, alternating', INK, '-'), "A'": ("A' mono, simultaneous", '#8a5cd1', ':'), 'B': ('B factorized', '#c9a227', '--')}


def load(name):
    p = O + name
    return json.load(open(p)) if os.path.exists(p) else None


def players(run):
    return {run['positions'][r['player']]: r for r in run['final']['players']}


def compare(x, y):
    """criteria of b3a_prereg.json applied to runs x (reference) and y"""
    px, py = players(x), players(y)
    out = {'players': {}, 'strategy': [], 'checks': {}}
    ok_ev = ok_cls = True
    for pos in px:
        a, b = px[pos], py[pos]
        d = [u - v for u, v in zip(a['class_gross'], b['class_gross']) if u is not None and v is not None]
        mean_abs = sum(abs(t) for t in d) / len(d)
        out['players'][pos] = {'range_value_x': a['range_value'], 'range_value_y': b['range_value'],
                               'range_value_diff_bb': b['range_value'] - a['range_value'],
                               'class_mean_abs_diff_bb': mean_abs, 'class_max_abs_diff_bb': max(abs(t) for t in d),
                               'br_gain_bb_x': a['br_gain_bb'], 'br_gain_bb_y': b['br_gain_bb']}
        ok_ev &= abs(b['range_value'] - a['range_value']) <= 0.02
        ok_cls &= mean_abs <= 0.05
    ok_act = True
    my = {m['line']: m for m in y['root_mix']}
    for m in x['root_mix']:
        if m['line'] not in my:
            continue
        n = my[m['line']]
        dd = max(abs(u - v) for u, v in zip(m['mix'], n['mix']))
        out['strategy'].append({'line': m['line'] or 'root', 'player': x['positions'][m['player']], 'active': m['active'],
                                'actions': m['actions'], 'mix_x': m['mix'], 'mix_y': n['mix'], 'max_abs_diff': dd})
        ok_act &= dd <= 0.05
    cons = max(abs(x['final']['conservation_error']), abs(y['final']['conservation_error']))
    conv = {}
    ok_conv = True
    for tag, run in (('x', x), ('y', y)):
        for pos in px:
            g = [players_at(run, c)[pos]['br_gain_bb'] for c in run['trace']]
            inc = sum(1 for u, v in zip(g, g[1:]) if v > u)
            conv[f'{tag}_{pos}'] = {'first': g[0], 'last': g[-1], 'increases': inc, 'checkpoints': len(g)}
            ok_conv &= g[-1] < g[0]
    out['convergence'] = conv
    out['checks'] = {'conservation_max_abs': cons, 'conservation': cons <= 1e-6, 'range_ev': ok_ev, 'class_values': ok_cls,
                     'action_frequency': ok_act, 'br_gain_decreasing_both': ok_conv}
    out['pass'] = all(v for k, v in out['checks'].items() if isinstance(v, bool))
    return out


def players_at(run, c):
    return {run['positions'][r['player']]: r for r in c['eval']['players']}


def rerun_identical(r1, r2):
    if r1 is None or r2 is None:
        return None
    a, b = r1['final'], r2['final']
    diff = 0.0
    for u, v in zip(a['players'], b['players']):
        diff = max(diff, abs(u['range_value'] - v['range_value']), abs(u['br_gain_bb'] - v['br_gain_bb']),
                   max(abs(p - q) for p, q in zip(u['class_gross'], v['class_gross']) if p is not None and q is not None))
    return {'max_abs_diff': diff, 'identical': diff == 0.0}


def per_iter(run):
    it = run['trace'][-1]['iteration']
    ts = run['time_split']
    return {k: v / it for k, v in ts.items() if k != 'evaluation'} | {'evaluation_per_checkpoint': ts['evaluation'] / len(run['trace'])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--png', default='docs/GTO_TERMINAL_B3A_V2.png')
    a = ap.parse_args()
    A, A2, B = load('b3a_A_mono_alt.json'), load('b3a_A2_mono_sim.json'), load('b3a_B_factor.json')
    ev = load('b3a_evalcheck.json')
    fr = load('b3a_build_frontiers_node46_Kc7d4h.json')
    res = {'prereg': 'b3a_prereg.json + b3a_prereg_addendum.json', 'registered_A_vs_B': compare(A, B)}
    if A2:
        res['isolation_Aprime_vs_B'] = compare(A2, B)
        res['schedule_A_vs_Aprime'] = compare(A, A2)
    res['rerun'] = {'A': rerun_identical(load('b3a_rerun_A_1.json'), load('b3a_rerun_A_2.json')),
                    'B': rerun_identical(load('b3a_rerun_B_1.json'), load('b3a_rerun_B_2.json'))}
    res['pass'] = res['registered_A_vs_B']['pass'] and all(r and r['identical'] for r in res['rerun'].values())
    # measurements
    meas = {}
    for tag, run in (('A', A), ("A'", A2), ('B', B)):
        if run is None:
            continue
        c = run['counters']
        meas[tag] = {'iterations': run['trace'][-1]['iteration'], 'seconds_total': run['trace'][-1]['seconds'],
                     'per_iteration_s': per_iter(run), 'peak_rss_kb': run['peak_rss_kb'], 'bytes': run['bytes'],
                     'bytes_trunk': run['bytes_trunk'], 'bytes_frontier': run['bytes_frontier'], 'frontiers': run.get('frontiers'),
                     'showdown3_ms_per_call': 1e3 * c['showdown3_seconds'] / max(1, c['showdown3_calls']),
                     'den3_ms_per_call': 1e3 * c['den3_seconds'] / max(1, c['den3_calls']), 'counters': c,
                     'threads': 1 if tag != 'B' else 2}
    res['measurements'] = meas
    res['evaluator'] = ev
    # full node 46 (Kc7d4h) projection: memory from the build counts, time from measured per-iteration cost x runout ratio
    fs = {r['street']: r for r in fr['frontiers']['by_street']}
    trunk = fr['bytes_if_2_active_subtrees_delegated']
    mono = fr['bytes_regret_plus_strategy_f32']
    val2 = lambda s: fs[s]['value_store_bytes_f32_3players'] * 2 / 3  # full game: the folder keeps the shortcut
    mem = {'monolithic_gb': mono / 1e9, 'trunk_gb': trunk / 1e9,
           'largest_frontier_gb': max(r['max_frontier_bytes'] for r in fs.values()) / 1e9,
           'values_flop_turn_gb': (val2('flop') + val2('turn')) / 1e9, 'values_river_gb': val2('river') / 1e9}
    mem['factorized_stored_river_values_gb'] = mem['trunk_gb'] + mem['largest_frontier_gb'] + mem['values_flop_turn_gb'] + mem['values_river_gb']
    mem['factorized_river_on_the_fly_gb'] = mem['trunk_gb'] + mem['largest_frontier_gb'] + mem['values_flop_turn_gb']
    mem['note'] = ('regret + strategy sum f32; trunk = 3-active nodes of all runouts; frontiers solved one at a time (largest = a flop fold '
                   'subtree incl. its turn/river instances); river-frontier values either stored (f32, 2 active players) or re-solved inside '
                   'a single joint trunk pass (deterministic, same snapshot); process overhead and evaluator scratch not included')
    ratio = 49 * 48 / 9  # river runouts full / reduced (the evaluator calls sit at river showdowns and folds)
    proj = {'runout_ratio_river': ratio}
    for tag in meas:
        pi = meas[tag]['per_iteration_s']
        th = meas[tag]['threads']
        cpu = {k: v * th * ratio for k, v in pi.items() if k != 'evaluation_per_checkpoint'}
        proj[tag] = {'cpu_s_per_iteration': cpu, 'hours_100_iterations_4_threads': sum(cpu.values()) * 100 / 4 / 3600}
    proj['note'] = ('linear scaling of the measured reduced-game CPU time by the river-runout ratio (flop/turn work scales less, so this is '
                    'an upper-side estimate for the trunk and about right for the river-dominated HU re-solves); 4 threads assumed perfectly parallel')
    res['full_node46_projection'] = {'memory': mem, 'time': proj}
    json.dump(res, open(O + 'b3a_compare.json', 'w'), indent=1)
    show = {k: res[k] for k in ('pass', 'rerun')}
    show['A_vs_B'] = res['registered_A_vs_B']['checks'] | {p: {k: round(v, 5) for k, v in d.items()} for p, d in res['registered_A_vs_B']['players'].items()}
    if A2:
        show["A'_vs_B"] = res['isolation_Aprime_vs_B']['checks']
        show["A_vs_A'"] = res['schedule_A_vs_Aprime']['checks']
    show['strategy_A_vs_B_max'] = max(s['max_abs_diff'] for s in res['registered_A_vs_B']['strategy'])
    show['memory'] = mem
    show['time'] = proj
    show['meas'] = {t: {k: m[k] for k in ('seconds_total', 'per_iteration_s', 'peak_rss_kb', 'showdown3_ms_per_call', 'den3_ms_per_call')} for t, m in meas.items()}
    print(json.dumps(show, indent=1))
    figure(res, A, A2, B, a.png)


def figure(res, A, A2, B, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(21, 11), dpi=115)
    fig.patch.set_facecolor(SURF)
    gs = fig.add_gridspec(2, 3)
    ax = [fig.add_subplot(gs[i // 3, i % 3]) for i in range(6)]
    cmp_ = res['registered_A_vs_B']
    # (1) class values A vs B
    g = ax[0]
    pa, pb = players(A), players(B)
    lo, hi = 1e9, -1e9
    for pos in pa:
        xs = [u for u, v in zip(pa[pos]['class_gross'], pb[pos]['class_gross']) if u is not None and v is not None]
        ys = [v for u, v in zip(pa[pos]['class_gross'], pb[pos]['class_gross']) if u is not None and v is not None]
        lo, hi = min(lo, min(xs)), max(hi, max(xs))
        P = cmp_['players'][pos]
        g.scatter(xs, ys, s=9, color=SEAT[pos], label=f"{pos}: range EV A {P['range_value_x']:.3f} / B {P['range_value_y']:.3f} bb, "
                                                     f"class mean |A−B| {P['class_mean_abs_diff_bb']:.4f}")
    g.plot([lo, hi], [lo, hi], color=MUTED, lw=1, ls=':')
    g.set_xlabel('A monolithic: class value (bb, gross share)', fontsize=9, color=MUTED)
    g.set_ylabel('B factorized: class value (bb)', fontsize=9, color=MUTED)
    g.set_title('(1) values: monolithic vs HU-frontier factorized (169 classes)', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False, loc='upper left')
    # (2) strategy
    g = ax[1]
    rows = cmp_['strategy']
    labels, xa, xb = [], [], []
    for s in rows:
        for k, act in enumerate(s['actions']):
            labels.append(f"{s['line']}: {s['player']} {act.split('(')[0]}")
            xa.append(s['mix_x'][k])
            xb.append(s['mix_y'][k])
    y = list(range(len(labels)))
    g.barh([t - 0.2 for t in y], xa, 0.38, color=SCHEME['A'][1], label=SCHEME['A'][0])
    g.barh([t + 0.2 for t in y], xb, 0.38, color=SCHEME['B'][1], label=SCHEME['B'][0])
    if A2:
        m2 = {m['line']: m for m in A2['root_mix']}
        xs2 = [m2[s['line'] if s['line'] != 'root' else '']['mix'][k] for s in rows for k in range(len(s['actions']))]
        g.scatter(xs2, y, marker='|', s=90, color=SCHEME["A'"][1], label=SCHEME["A'"][0], zorder=3)
    g.set_yticks(y)
    g.set_yticklabels(labels, fontsize=7)
    g.invert_yaxis()
    g.set_xlabel('aggregate frequency (range-weighted average strategy)', fontsize=9, color=MUTED)
    g.set_title(f"(2) strategy on the flop lines, max |A−B| {max(s['max_abs_diff'] for s in rows):.3f} (limit 0.05)", loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False, loc='lower right')
    # (3) convergence
    g = ax[2]
    for tag, run in (('A', A), ("A'", A2), ('B', B)):
        if run is None:
            continue
        lab, col, ls = SCHEME[tag]
        for pos in pa:
            it = [c['iteration'] for c in run['trace']]
            gv = [max(1e-6, players_at(run, c)[pos]['br_gain_bb']) for c in run['trace']]
            g.plot(it, gv, color=SEAT[pos], ls=ls, lw=1.6, marker='o', ms=3, label=f'{tag} {pos}')
    g.set_yscale('log')
    g.set_xlabel('iteration (B: trunk iteration, each with 100-iteration frontier re-solves)', fontsize=9, color=MUTED)
    g.set_ylabel('BR gain per player (bb, log)', fontsize=9, color=MUTED)
    g.set_title('(3) convergence: best-response gain (solid A, dotted A\', dashed B)', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7, frameon=False, ncol=3)
    # (4) memory
    g = ax[3]
    mem = res['full_node46_projection']['memory']
    bars = [('monolithic', [(mem['monolithic_gb'], '#9b9a93', 'all nodes')]),
            ('factorized,\nriver values stored', [(mem['trunk_gb'], INK, 'trunk (3 active)'), (mem['largest_frontier_gb'], SCHEME['B'][1], 'largest frontier (solved one at a time)'),
                                                  (mem['values_flop_turn_gb'], '#8a5cd1', 'flop/turn frontier values'), (mem['values_river_gb'], '#2a78d6', 'river frontier values')]),
            ('factorized,\nriver re-solved in pass', [(mem['trunk_gb'], INK, None), (mem['largest_frontier_gb'], SCHEME['B'][1], None), (mem['values_flop_turn_gb'], '#8a5cd1', None)])]
    for i, (name, parts) in enumerate(bars):
        bot = 0
        for v, col, lab in parts:
            g.bar(i, v, 0.6, bottom=bot, color=col, label=lab)
            bot += v
        g.text(i, bot + 0.3, f'{bot:.2f} GB', ha='center', fontsize=9, color=INK)
    g.axhline(15, color='#c0392b', lw=1, ls='--')
    g.axhline(12, color='#c0392b', lw=1, ls=':')
    g.text(2.45, 15.2, 'limit 15 GB', fontsize=8, color='#c0392b', ha='right')
    g.text(2.45, 12.2, 'goal 12 GB', fontsize=8, color='#c0392b', ha='right')
    g.set_xticks(range(len(bars)))
    g.set_xticklabels([b[0] for b in bars], fontsize=8.5)
    g.set_ylabel('GB (regret + strategy sum, f32)', fontsize=9, color=MUTED)
    mb = res['measurements']
    g.set_title(f"(4) memory, full node 46 Kc7d4h (from build counts); reduced game RSS A {mb['A']['peak_rss_kb']/1e6:.2f} / B {mb['B']['peak_rss_kb']/1e6:.2f} GB",
                loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False, loc='upper right')
    # (5) runtime reduced game
    g = ax[4]
    comp = [('trunk_update', INK, 'trunk / full-tree update'), ('frontier_solve', SCHEME['B'][1], 'HU frontier re-solves'), ('collect', '#8a5cd1', 'frontier reach collection')]
    tags = [t for t in ('A', "A'", 'B') if t in mb]
    for i, t in enumerate(tags):
        bot = 0
        pi = mb[t]['per_iteration_s']
        for k, col, lab in comp:
            v = pi.get(k, 0) * mb[t]['threads']
            g.bar(i, v, 0.6, bottom=bot, color=col, label=lab if i == len(tags) - 1 else None)
            bot += v
        g.text(i, bot, f'{bot:.1f} s', ha='center', va='bottom', fontsize=9, color=INK)
    g.set_xticks(range(len(tags)))
    g.set_xticklabels([SCHEME[t][0] for t in tags], fontsize=8.5)
    g.set_ylabel('CPU seconds per iteration (measured, reduced game)', fontsize=9, color=MUTED)
    g.set_title(f"(5) runtime per iteration; evaluator {mb['A']['showdown3_ms_per_call']:.2f} ms/3-player showdown call", loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False)
    # (6) projection
    g = ax[5]
    tp = res['full_node46_projection']['time']
    hrs = [tp[t]['hours_100_iterations_4_threads'] for t in tags]
    g.bar(range(len(tags)), hrs, 0.6, color=[SCHEME[t][1] for t in tags])
    for i, h in enumerate(hrs):
        g.text(i, h, f'{h:,.0f} h', ha='center', va='bottom', fontsize=9, color=INK)
    g.set_yscale('log')
    g.set_xticks(range(len(tags)))
    g.set_xticklabels([SCHEME[t][0] for t in tags], fontsize=8.5)
    g.set_ylabel('projected hours for 100 iterations, 4 threads (log)', fontsize=9, color=MUTED)
    g.set_title(f"(6) full node 46 time projection (×{tp['runout_ratio_river']:.0f} river runouts)", loc='left', fontsize=10, color=INK)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    chk = cmp_['checks']
    fig.suptitle('B3a — reduced 3-way game (node 46, Kc7d4h, turns 2s/Qh/8c, rivers 3d/Js/6h): '
                 f"registered A vs B {'PASS' if res['pass'] else 'FAIL'}  |  " + ', '.join(f'{k} {v}' for k, v in chk.items() if isinstance(v, bool)),
                 fontsize=11, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
