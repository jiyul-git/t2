#!/usr/bin/env python3
"""After A3: final census (5-1), node 6 re-check (5-2), next-terminal ranking (5-3), figure.

    python3 tools/gto_hu_continuation/final_census.py [--final-k K] [--png docs/GTO_TERMINAL_FINAL_CENSUS_V2.png]

Final state P* = the last preflop state of A3 (outer_m28_6/k{K}); its census was run by the driver with the
manifest M_{K-1} (nodes 28 and 6 solved, everything else legacy). No new solve is started here.
Ranking = reach(P*) x mean |solved - legacy| (bb per class, both/all seats). Sources are labelled:
  measured (six-flop pilot, legacy at P9 ranges) for nodes 228 and 1371;
  proxy (stated, untested transfer assumption, mw_legacy/transfer_proxy.json) for nodes 46 and 246;
  the others are reach-only. Nothing is injected anywhere.
"""
import argparse
import json

E = 'data/gto_terminal_expansion/'
A3 = E + 'outer_m28_6/'
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'


def summarize(c, solved):
    T = c['terminals']
    tot = sum(r['reach_probability'] for r in T)
    by_live = {f'{lc}-way': sum(r['reach_probability'] for r in T if r['live_count'] == lc) for lc in (2, 3, 4)}
    by_pot = {}
    for r in T:
        by_pot[r['pot_type']] = by_pot.get(r['pot_type'], 0.0) + r['reach_probability']
    reach = {r['terminal_node']: r['reach_probability'] for r in T}
    solved_reach = sum(reach.get(n, 0.0) for n in solved)
    top = sorted(T, key=lambda r: -r['reach_probability'])[:15]
    return {'flop_reach_total': tot, 'share_by_live': {k: v / tot for k, v in by_live.items()}, 'reach_by_live': by_live,
            'share_by_pot_type': {k: v / tot for k, v in sorted(by_pot.items())},
            'reach': {str(n): reach.get(n) for n in (28, 6, 46, 246, 228, 1371)},
            'solved_terminals': sorted(solved), 'solved_flop_reach': solved_reach, 'solved_share_of_flop_reach': solved_reach / tot,
            'solved_share_of_hu_flop_reach': solved_reach / by_live['2-way'],
            'legacy_hu_flop_reach': by_live['2-way'] - solved_reach, 'legacy_multiway_flop_reach': by_live['3-way'] + by_live['4-way'],
            'top15': [{'node': r['terminal_node'], 'path': ' -> '.join(r['path_labels']), 'live': r['live_count'], 'pot_type': r['pot_type'],
                       'reach': r['reach_probability'], 'share': r['reach_probability'] / tot, 'solved': r['terminal_node'] in solved} for r in top]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--final-k', type=int, default=None)
    ap.add_argument('--png', default='docs/GTO_TERMINAL_FINAL_CENSUS_V2.png')
    a = ap.parse_args()
    log = json.load(open(A3 + 'loop_log.json'))
    K = a.final_k or max(s['k'] for s in log['steps'])
    measured_ks = sorted(s['k'] for s in log['steps'] if s.get('terminals'))
    KV = max(measured_ks)
    c9 = json.load(open(E + 'census_p9.json'))
    cf = json.load(open(A3 + f'k{K}/census.json'))
    res = {'final_state': f'P{K}', 'last_measured_tables': f'V{KV} (at P{KV})', 'note': 'nodes 28 and 6 solved, all other terminals legacy; not a finished GTO DB',
           'P9': summarize(c9, {28}), 'Pfinal': summarize(cf, {28, 6})}
    # 5-2: node 6 re-check
    labels = json.load(open(E + 'terminals/p9_node6.json'))['class_labels']
    v1 = json.load(open(E + 'node6_72/table72.json'))
    vK = json.load(open(A3 + f'k{KV}/node6/table_measured.json'))
    tK = json.load(open(A3 + f'k{KV}/terminal_node6.json'))
    t9 = json.load(open(E + 'terminals/p9_node6.json'))
    pa = json.load(open(E + 'a25_routing_probe/probe.json'))
    tf = json.load(open(A3 + f'k{K}/terminal_node6.json'))
    node6 = {'tables': {'A1': 'node6_72/table72.json (P9 ranges)', 'final': f'outer_m28_6/k{KV}/node6/table_measured.json (P{KV} ranges)'}, 'seats': {}}
    for pl9, plK in zip(t9['players'], tK['players']):
        pos = pl9['position']
        s1 = next(s for s in v1['seats'] if s['position'] == pos)['gross']
        sK = next(s for s in vK['seats'] if s['position'] == pos)['gross']
        r9, rK = pl9['class_reach_normalized'], plK['class_reach_normalized']
        d = [x - y for x, y in zip(sK, s1)]
        node6['seats'][pos] = {
            'range_ev_shift_vs_legacy_A1_at_P9': sum(r * (x - y) for r, x, y in zip(r9, s1, pl9['legacy_gross'])),
            'range_ev_shift_vs_legacy_final_at_P%d' % KV: sum(r * (x - y) for r, x, y in zip(rK, sK, plK['legacy_gross'])),
            'class_mean_abs_final_minus_A1': sum(abs(x) for x in d) / 169,
            'class_reach_weighted_abs_final_minus_A1': sum(r * abs(x) for r, x in zip(rK, d)),
            'largest_class_changes': sorted(({'class': labels[h], 'delta_bb': d[h]} for h in range(169)), key=lambda z: -abs(z['delta_bb']))[:10]}
    mix = lambda t, key: t['frequencies'][key]['mix']
    bb = lambda t: next(p for p in t['path_nodes'] if p['actor'] == 'BB')['mix']
    node6['sb_open_and_bb_response'] = {
        'P9': {'SB': mix(t9, 'rfi_SB'), 'BB_vs_SB': bb(t9)},
        'P10_frozen_table_A2.5': {'SB': pa['P10']['frequencies']['rfi_SB'], 'BB_vs_SB': pa['P10']['frequencies']['node6_path:BB@4']},
        f'P{K}_final': {'SB': mix(tf, 'rfi_SB'), 'BB_vs_SB': bb(tf)}}
    res['node6_recheck'] = node6
    # 5-3: ranking
    pil = json.load(open(E + 'pilot6/analysis.json'))['terminals']
    prox = json.load(open(E + 'mw_legacy/transfer_proxy.json'))['nodes']
    impact = {228: (pil['228']['impact']['mean_abs_delta_both_seats'], 'measured six-flop pilot'),
              1371: (pil['1371']['impact']['mean_abs_delta_both_seats'], 'measured six-flop pilot')}
    for n in ('46', '246'):
        pl = prox[n]['players']
        vals = [v['mean_abs_delta'] for v in (pl.values() if isinstance(pl, dict) else pl)]
        impact[int(n)] = (sum(vals) / len(vals), 'PROXY (untested transfer assumption)')
    rows = []
    tot = res['Pfinal']['flop_reach_total']
    for r in cf['terminals']:
        n = r['terminal_node']
        if n in (28, 6):
            continue
        d, src = impact.get(n, (None, 'reach-only'))
        rows.append({'node': n, 'path': ' -> '.join(r['path_labels']), 'live': r['live_count'], 'pot_type': r['pot_type'], 'reach': r['reach_probability'],
                     'flop_share': r['reach_probability'] / tot, 'mean_abs_delta_bb': d, 'impact_source': src,
                     'priority': r['reach_probability'] * d if d is not None else None})
    scored = sorted([x for x in rows if x['priority'] is not None], key=lambda x: -x['priority'])
    reach_only = sorted([x for x in rows if x['priority'] is None], key=lambda x: -x['reach'])[:10]
    res['ranking'] = {'rule': 'priority = reach(P*) x mean |solved - legacy| (bb/class); proposal only, nothing injected; node 228 not injected; node 1371 not enlarged',
                      'scored': scored, 'top_reach_only_unscored': reach_only}
    json.dump(res, open(A3 + 'final_census.json', 'w'), indent=1)
    for k in ('P9', 'Pfinal'):
        s = res[k]
        print(k, 'flop', round(s['flop_reach_total'], 4), {x: round(v, 3) for x, v in s['share_by_live'].items()}, {x: round(v, 3) for x, v in s['share_by_pot_type'].items()},
              'solved share', round(s['solved_share_of_flop_reach'], 3), 'legacy HU', round(s['legacy_hu_flop_reach'], 4), 'legacy MW', round(s['legacy_multiway_flop_reach'], 4))
    print(json.dumps(node6['sb_open_and_bb_response'], indent=0)[:900])
    for x in scored:
        print('rank', x['node'], round(x['reach'], 4), x['mean_abs_delta_bb'], x['impact_source'], round(x['priority'], 4))
    figure(res, a.png)


def figure(res, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(22, 6.2), dpi=115)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    for i, k in enumerate(('P9', 'Pfinal')):
        s = res[k]
        parts = [(s['solved_flop_reach'], '#1baf7a', 'solved HU (injected tables)'), (s['legacy_hu_flop_reach'], '#9cc3ef', 'legacy HU'),
                 (s['reach_by_live']['3-way'], '#eb6834', 'legacy 3-way'), (s['reach_by_live']['4-way'], '#8a5cd1', 'legacy 4-way')]
        bot = 0
        for v, col, lab in parts:
            g.bar(i, v, 0.55, bottom=bot, color=col, label=lab if i == 0 else None)
            if v > 0.02:
                g.text(i, bot + v / 2, f'{v:.3f}\n({v / s["flop_reach_total"]:.0%})', ha='center', va='center', fontsize=8, color='white' if col != '#9cc3ef' else INK)
            bot += v
    g.set_xticks([0, 1])
    g.set_xticklabels(['P9 (node 28 solved)', f"{res['final_state']} (nodes 28 + 6 solved)"])
    g.set_ylabel('flop reach probability', fontsize=9, color=MUTED)
    g.set_title('(1) solved vs legacy flop-reach coverage', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper left')
    g = ax[1]
    nodes = sorted({t['node'] for k in ('P9', 'Pfinal') for t in res[k]['top15']}, key=lambda n: -max(
        [t['reach'] for k in ('P9', 'Pfinal') for t in res[k]['top15'] if t['node'] == n]))[:15]
    lab = {}
    for k in ('P9', 'Pfinal'):
        for t in res[k]['top15']:
            lab[t['node']] = f"{t['node']}: {t['path'].replace('Fold', 'F').replace('Raise', 'R').replace('Call', 'C')}"
    y = range(len(nodes))
    for j, (k, col) in enumerate((('P9', '#b5b3aa'), ('Pfinal', INK))):
        rr = {t['node']: t['reach'] for t in res[k]['top15']}
        g.barh([t + (j - 0.5) * 0.4 for t in y], [rr.get(n, 0) for n in nodes], 0.38, color=col, label='P9' if k == 'P9' else res['final_state'])
    g.set_yticks(list(y))
    g.set_yticklabels([lab[n] for n in nodes], fontsize=6.5)
    g.invert_yaxis()
    g.set_xlabel('reach probability', fontsize=9, color=MUTED)
    g.set_title('(2) top flop-reaching terminals: P9 vs final', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[2]
    sc = res['ranking']['scored']
    cols = ['#eb6834' if 'PROXY' in x['impact_source'] else '#2a78d6' for x in sc]
    g.barh(range(len(sc)), [x['priority'] for x in sc], color=cols)
    g.set_yticks(range(len(sc)))
    g.set_yticklabels([f"node {x['node']} ({x['live']}-way): reach {x['reach']:.3f} × {x['mean_abs_delta_bb']:.2f} bb" for x in sc], fontsize=8)
    g.invert_yaxis()
    from matplotlib.patches import Patch
    g.legend(handles=[Patch(color='#2a78d6', label='measured |Δ| (six-flop pilot)'), Patch(color='#eb6834', label='proxy |Δ| (untested transfer)')], fontsize=8, frameon=False)
    g.set_xlabel('priority = reach × mean |solved − legacy| (bb)', fontsize=9, color=MUTED)
    g.set_title('(3) next-terminal ranking (proposal only)', loc='left', fontsize=10, color=INK)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.suptitle('Final census after A3 — nodes 28 + 6 solved continuation, all else legacy (not a finished GTO DB)', fontsize=11, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
