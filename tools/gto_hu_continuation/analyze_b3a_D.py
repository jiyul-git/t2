#!/usr/bin/env python3
"""B3a diagnostic D + sealed B3a verdict: analysis and figure (definitions: b3a_diag_D_prereg.json).

    python3 tools/gto_hu_continuation/analyze_b3a_D.py [--png docs/GTO_TERMINAL_B3A_V2.png]
"""
import argparse
import json
import re
import sys

sys.path.insert(0, 'tools/gto_hu_continuation')
import compare_b3a as c  # noqa: E402

O = c.O
INK, MUTED, SURF, GRID = c.INK, c.MUTED, c.SURF, c.GRID
SEAT = c.SEAT
COL = {'A': INK, "A'": '#8a5cd1', 'B': '#c9a227', 'Dfresh': '#c0392b', 'Dhist': '#1f7a8c'}


def log_points(path):
    pts = []
    for line in open(path):
        m = re.match(r'it (\d+) expl ([\d.]+)% pot', line)
        if m:
            pts.append((int(m.group(1)), float(m.group(2))))
    return pts


def residual_summary(rows, pot, fresh_expl_pct):
    tot_mass = sum(r['mass'] for r in rows)
    gap = lambda r: sum(g['gap_bb'] for g in r['gaps'])
    total = sum(gap(r) for r in rows)
    per = [(r, gap(r) / r['mass'] if r['mass'] > 0 else 0.0) for r in rows]
    wmean = sum(r['mass'] * x for r, x in per) / tot_mass
    srt = sorted(rows, key=lambda r: -r['mass'])
    cum, detail = 0.0, []
    for r in srt:
        if cum >= 0.95 * tot_mass:
            break
        detail.append(r)
        cum += r['mass']
    by_street = {}
    for s in (0, 1, 2):
        rs = [r for r in rows if r['street'] == s]
        by_street[['flop', 'turn', 'river'][s]] = {'frontiers': len(rs), 'mass': sum(r['mass'] for r in rs),
                                                   'gap_total_bb': sum(gap(r) for r in rs)}
    total_pct = total / 3 / pot * 100
    return {'frontiers': len(rows), 'mass_total': tot_mass, 'gap_total_bb': total, 'gap_total_pct_pot_expl_scale': total_pct,
            'share_of_fresh_exploitability': total_pct / fresh_expl_pct if fresh_expl_pct > 0 else None,
            'gap_per_mass_weighted_mean_bb': wmean, 'gap_per_mass_max_bb': max(x for _, x in per),
            'by_street': by_street,
            'detail_95pct_mass': {'count': len(detail), 'mass': cum,
                                  'rows': [{k: r[k] for k in ('tpl', 'node', 'inst', 'street', 'folder', 'mass')} | {'gap_bb': gap(r), 'gap_per_mass_bb': gap(r) / r['mass']} for r in detail]},
            'rest_aggregate': {'count': len(rows) - len(detail), 'mass': tot_mass - cum,
                               'gap_total_bb': total - sum(gap(r) for r in detail)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--png', default='docs/GTO_TERMINAL_B3A_V2.png')
    a = ap.parse_args()
    A, A2, B50 = c.load('b3a_A_mono_alt.json'), c.load('b3a_A2_mono_sim.json'), c.load('b3a_rerun_B_1.json')
    D = c.load('b3a_D_diag.json') or c.load('b3a_D_diag.json.partial')
    pot = A['final']['pot']
    blog = log_points(O + 'b3a_B_factor_stopped_at_it100.log')
    res = {'verdict': json.load(open(O + 'b3a_verdict.json'))['verdict'], 'B_registered_log': blog, 'checkpoints': []}
    # determinism: D reproduces B's trunk path
    dlog = {t['iteration']: t['eval']['exploitability_pct_pot'] for t in D['trace']}
    res['D_reproduces_B'] = {str(i): {'B_log': e, 'D_fresh': dlog.get(i)} for i, e in blog}
    for t in D['trace']:
        fresh, hist = t['eval'], t['eval_cfrd_avg']
        pl = lambda ev: {D['positions'][p['player']]: p['br_gain_bb'] for p in ev['players']}
        row = {'iteration': t['iteration'], 'fresh_expl_pct': fresh['exploitability_pct_pot'], 'hist_expl_pct': hist['exploitability_pct_pot'],
               'fresh_br_gain': pl(fresh), 'hist_br_gain': pl(hist),
               'fresh_conservation': fresh['conservation_error'], 'hist_conservation': hist['conservation_error'],
               'residual_checkpoint_fresh_solve': residual_summary(t['frontier_residual_checkpoint_resolve'], pot, fresh['exploitability_pct_pot']),
               'residual_iteration_solve': residual_summary(t['frontier_residual_iteration_solve'], pot, fresh['exploitability_pct_pot']),
               'time_split': t['time_split'], 'seconds': t['seconds']}
        for tag, ev in (('fresh', fresh), ('hist', hist)):
            run = D | {'final': ev, 'root_mix': ev.get('root_mix', t['root_mix']) if tag == 'hist' else t['root_mix'], 'trace': [t]}
            r = c.compare(A, run)
            row[f'{tag}_vs_A400'] = {'range_ev_diff_bb': {p: v['range_value_diff_bb'] for p, v in r['players'].items()},
                                     'class_mean_abs_diff_bb': {p: v['class_mean_abs_diff_bb'] for p, v in r['players'].items()},
                                     'strategy_max_abs_diff': max(s['max_abs_diff'] for s in r['strategy'])}
        res['checkpoints'].append(row)
    ck = res['checkpoints']
    dec = lambda xs: all(y < x for x, y in zip(xs, xs[1:]))
    fr, hi = [r['fresh_expl_pct'] for r in ck], [r['hist_expl_pct'] for r in ck]
    share = ck[-1]['residual_iteration_solve']['share_of_fresh_exploitability']
    if dec(hi) and not dec(fr):
        cause = 'assembly_or_evaluation'
    elif not dec(hi) and not dec(fr):
        cause = 'reset_solve_approximation' if share >= 0.25 else 'decomposition_itself'
    else:
        cause = 'mixed'
    res['judgement'] = {'fresh_decreasing': dec(fr), 'hist_decreasing': dec(hi), 'iteration_residual_share_last': share,
                        'cause': cause, 'rules': json.load(open(O + 'b3a_diag_D_prereg.json'))['judgement_rules']}
    ts = D['trace'][-1]['time_split']
    it = D['trace'][-1]['iteration']
    res['runtime'] = {'threads': 4, 'per_trunk_iteration_s': {k: ts[k] / it for k in ('collect', 'frontier_solve', 'trunk_update')},
                      'hu_share': ts['frontier_solve'] / (ts['collect'] + ts['frontier_solve'] + ts['trunk_update']),
                      'evaluation_total_s': ts['evaluation'], 'peak_rss_kb': D['peak_rss_kb'], 'counters': D['counters']}
    fr = c.load('b3a_build_frontiers_node46_Kc7d4h.json')
    fs = {r['street']: r for r in fr['frontiers']['by_street']}
    val2 = lambda s: fs[s]['value_store_bytes_f32_3players'] * 2 / 3
    mem = {'monolithic_gb': fr['bytes_regret_plus_strategy_f32'] / 1e9, 'trunk_gb': fr['bytes_if_2_active_subtrees_delegated'] / 1e9,
           'largest_frontier_gb': max(r['max_frontier_bytes'] for r in fs.values()) / 1e9,
           'values_flop_turn_gb': (val2('flop') + val2('turn')) / 1e9, 'values_river_gb': val2('river') / 1e9}
    mem['factorized_stored_river_values_gb'] = mem['trunk_gb'] + mem['largest_frontier_gb'] + mem['values_flop_turn_gb'] + mem['values_river_gb']
    mem['factorized_river_on_the_fly_gb'] = mem['trunk_gb'] + mem['largest_frontier_gb'] + mem['values_flop_turn_gb']
    res['full_node46_memory'] = mem
    json.dump(res, open(O + 'b3a_D_analysis.json', 'w'), indent=1)
    for r in ck:
        print(r['iteration'], 'fresh', round(r['fresh_expl_pct'], 4), 'hist', round(r['hist_expl_pct'], 4),
              '| resid ck', round(r['residual_checkpoint_fresh_solve']['gap_total_pct_pot_expl_scale'], 4),
              'iter', round(r['residual_iteration_solve']['gap_total_pct_pot_expl_scale'], 4),
              'detail', r['residual_iteration_solve']['detail_95pct_mass']['count'])
        print('   vs A400 fresh', {k: round(v, 3) for k, v in r['fresh_vs_A400']['class_mean_abs_diff_bb'].items()},
              'hist', {k: round(v, 3) for k, v in r['hist_vs_A400']['class_mean_abs_diff_bb'].items()})
    print(json.dumps(res['judgement'], indent=1)[:800])
    print(json.dumps(res['D_reproduces_B']))
    figure(res, A, A2, B50, D, a.png)


def figure(res, A, A2, B50, D, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(24, 12), dpi=110)
    fig.patch.set_facecolor(SURF)
    gs = fig.add_gridspec(2, 4)
    ax = [fig.add_subplot(gs[i // 4, i % 4]) for i in range(8)]
    ck = res['checkpoints']
    # (1) exploitability curves
    g = ax[0]
    for tag, run in (('A', A), ("A'", A2)):
        xs = [t['iteration'] for t in run['trace']]
        g.plot(xs, [t['eval']['exploitability_pct_pot'] for t in run['trace']], color=COL[tag], marker='o', ms=3, lw=1.5,
               label=c.SCHEME[tag][0])
    bl = res['B_registered_log']
    g.plot([x for x, _ in bl], [y for _, y in bl], color=COL['B'], marker='s', ms=6, lw=2.2, label='B registered (stopped at 100)')
    g.annotate(f'reversal {bl[0][1]:.2f}% → {bl[1][1]:.2f}%\n(sealed FAIL)', xy=bl[1], xytext=(bl[1][0] + 40, bl[1][1] * 1.6),
               fontsize=8.5, color='#c0392b', arrowprops=dict(arrowstyle='->', color='#c0392b'))
    xs = [r['iteration'] for r in ck]
    g.plot(xs, [r['fresh_expl_pct'] for r in ck], color=COL['Dfresh'], ls='--', marker='^', ms=5, label='D: fresh re-solve (= B evaluation)')
    g.plot(xs, [r['hist_expl_pct'] for r in ck], color=COL['Dhist'], ls='-', marker='D', ms=5, label='D: historical reach-weighted average')
    g.set_yscale('log')
    g.set_xlabel('iteration (B/D: trunk iteration)', fontsize=9, color=MUTED)
    g.set_ylabel('exploitability (% pot, log)', fontsize=9, color=MUTED)
    g.set_title('(1) convergence: B reversal and diagnostic D', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False)
    # (2) per-player BR gain fresh vs hist
    g = ax[1]
    for pos in SEAT:
        g.plot(xs, [r['fresh_br_gain'][pos] for r in ck], color=SEAT[pos], ls='--', marker='^', label=f'{pos} fresh')
        g.plot(xs, [r['hist_br_gain'][pos] for r in ck], color=SEAT[pos], ls='-', marker='D', label=f'{pos} historical')
    g.set_yscale('log')
    g.set_xlabel('trunk iteration', fontsize=9, color=MUTED)
    g.set_ylabel('BR gain (bb, log)', fontsize=9, color=MUTED)
    g.set_title('(2) per-player BR gain in D: fresh (dashed) vs historical (solid)', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7, frameon=False, ncol=2)
    # (3) inner residual per frontier
    g = ax[2]
    last = D['trace'][-1]
    sc = {0: '#1f1f1e', 1: '#8a5cd1', 2: '#2a78d6'}
    for s in (0, 1, 2):
        rows = [r for r in last['frontier_residual_iteration_solve'] if r['street'] == s and r['mass'] > 0]
        g.scatter([r['mass'] for r in rows], [sum(x['gap_bb'] for x in r['gaps']) / r['mass'] for r in rows], s=8, color=sc[s],
                  label=f"{['flop', 'turn', 'river'][s]} frontiers ({len(rows)})")
    g.set_xscale('log')
    g.set_yscale('symlog', linthresh=1e-3)
    g.set_xlabel('arriving mass of the frontier (fraction of deals)', fontsize=9, color=MUTED)
    g.set_ylabel('inner residual: BR gap per arriving deal (bb)', fontsize=9, color=MUTED)
    rs = ck[-1]['residual_iteration_solve']
    g.set_title(f"(3) inner-solve residual at {ck[-1]['iteration']}: total {rs['gap_total_pct_pot_expl_scale']:.3f}% pot "
                f"({rs['share_of_fresh_exploitability']:.0%} of fresh expl)", loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False)
    # (4) residual totals over checkpoints
    g = ax[3]
    w = 0.35
    g.bar([x - w / 2 for x in range(len(ck))], [r['residual_iteration_solve']['gap_total_pct_pot_expl_scale'] for r in ck], w,
          color='#2a78d6', label='in-iteration solve (vs trunk snapshot σt)')
    g.bar([x + w / 2 for x in range(len(ck))], [r['residual_checkpoint_fresh_solve']['gap_total_pct_pot_expl_scale'] for r in ck], w,
          color=COL['Dfresh'], label='checkpoint fresh solve (vs trunk average)')
    g.plot(range(len(ck)), [r['fresh_expl_pct'] for r in ck], color=INK, marker='o', label='D fresh exploitability (whole game)')
    g.set_xticks(range(len(ck)))
    g.set_xticklabels([str(r['iteration']) for r in ck])
    g.set_xlabel('checkpoint (trunk iteration)', fontsize=9, color=MUTED)
    g.set_ylabel('% pot (exploitability scale)', fontsize=9, color=MUTED)
    g.set_title('(4) frontier inner residual, summed over 1332 frontiers', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False)
    # (5) values vs A@400
    g = ax[4]
    pa = c.players(A)
    dh = {D['positions'][p['player']]: p for p in last['eval_cfrd_avg']['players']}
    lo = 1e9
    hi = -1e9
    for pos in pa:
        x = [u for u, v in zip(pa[pos]['class_gross'], dh[pos]['class_gross']) if u is not None and v is not None]
        y = [v for u, v in zip(pa[pos]['class_gross'], dh[pos]['class_gross']) if u is not None and v is not None]
        lo, hi = min(lo, min(x)), max(hi, max(x))
        cm = ck[-1]['hist_vs_A400']['class_mean_abs_diff_bb'][pos]
        g.scatter(x, y, s=8, color=SEAT[pos], label=f'{pos}: class mean |Δ| {cm:.3f} bb')
    g.plot([lo, hi], [lo, hi], color=MUTED, ls=':', lw=1)
    g.set_xlabel('A monolithic @400: class value (bb)', fontsize=9, color=MUTED)
    g.set_ylabel(f"D historical average @{ck[-1]['iteration']} (bb)", fontsize=9, color=MUTED)
    g.set_title('(5) values: monolithic reference vs factorized (historical average)', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False)
    # (6) strategy
    g = ax[5]
    refs = [('A@400', A['root_mix'], COL['A']), ("A'@400", A2['root_mix'], COL["A'"]), ('B@50', B50['root_mix'], COL['B']),
            (f"D hist@{ck[-1]['iteration']}", last['eval_cfrd_avg'].get('root_mix', []), COL['Dhist']),
            (f"D fresh@{ck[-1]['iteration']}", last['root_mix'], COL['Dfresh'])]
    labels = [f"{m['line'] or 'root'}: {A['positions'][m['player']]} {act.split('(')[0]}" for m in A['root_mix'] for act in m['actions']]
    n = len(refs)
    for k, (lab, mix, col) in enumerate(refs):
        vals = [v for m in mix for v in m['mix']]
        if len(vals) != len(labels):
            continue
        g.barh([i + (k - n / 2) * 0.16 + 0.08 for i in range(len(labels))], vals, 0.16, color=col, label=lab)
    g.set_yticks(range(len(labels)))
    g.set_yticklabels(labels, fontsize=7)
    g.invert_yaxis()
    g.set_xlabel('aggregate frequency', fontsize=9, color=MUTED)
    g.set_title('(6) strategy on the flop lines', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7, frameon=False, loc='lower right')
    # (7) memory
    mem = res['full_node46_memory']
    g = ax[6]
    bars = [('monolithic', [(mem['monolithic_gb'], '#9b9a93', 'all nodes')]),
            ('factorized,\nriver values stored', [(mem['trunk_gb'], INK, 'trunk (3 active)'), (mem['largest_frontier_gb'], COL['B'], 'largest frontier'),
                                                  (mem['values_flop_turn_gb'], '#8a5cd1', 'flop/turn frontier values'), (mem['values_river_gb'], '#2a78d6', 'river frontier values')]),
            ('factorized,\nriver re-solved in pass', [(mem['trunk_gb'], INK, None), (mem['largest_frontier_gb'], COL['B'], None), (mem['values_flop_turn_gb'], '#8a5cd1', None)])]
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
    g.set_xticks(range(3))
    g.set_xticklabels([b[0] for b in bars], fontsize=8.5)
    g.set_ylabel('GB (regret + strategy sum, f32)', fontsize=9, color=MUTED)
    g.set_title('(7) memory, full node 46 Kc7d4h (build counts)', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False, loc='upper right')
    # (8) runtime
    g = ax[7]
    items = [('A mono-alt\n(1 thread)', {'trunk_update': A['time_split']['trunk_update'] / 400}, 1),
             ("A' mono-sim\n(1 thread)", {'trunk_update': A2['time_split']['trunk_update'] / 400}, 1),
             ('B registered\n(2 threads)', {k: B50['time_split'][k] / 50 for k in ('collect', 'frontier_solve', 'trunk_update')}, 2),
             ('D diagnostic\n(4 threads)', res['runtime']['per_trunk_iteration_s'], 4)]
    comp = [('trunk_update', INK, '3-way trunk / full update'), ('frontier_solve', COL['B'], 'HU frontier re-solves (100 inner)'), ('collect', '#8a5cd1', 'arriving-reach collection')]
    for i, (name, pi, th) in enumerate(items):
        bot = 0
        for k, col, lab in comp:
            v = pi.get(k, 0)
            g.bar(i, v, 0.6, bottom=bot, color=col, label=lab if i == 2 else None)
            bot += v
        g.text(i, bot, f'{bot:.1f} s', ha='center', va='bottom', fontsize=9, color=INK)
    g.set_yscale('log')
    g.set_xticks(range(len(items)))
    g.set_xticklabels([x[0] for x in items], fontsize=8)
    g.set_ylabel('wall seconds per iteration (measured, log)', fontsize=9, color=MUTED)
    g.set_title(f"(8) runtime: HU re-solve share {res['runtime']['hu_share']:.1%} (D)", loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False, loc='upper left')
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    j = res['judgement']
    fig.suptitle(f"B3a (reduced node 46 game): registered B = FAIL (sealed at trunk iteration 100)  |  diagnostic D cause: {j['cause']}  "
                 f"(historical decreasing {j['hist_decreasing']}, fresh decreasing {j['fresh_decreasing']}, inner residual share {j['iteration_residual_share_last']:.0%})",
                 fontsize=11.5, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
