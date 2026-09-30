#!/usr/bin/env python3
"""A1: node 6 (SB open -> BB call) on the 72-flop panel at P9 ranges vs legacy and vs the six-flop pilot.

    python3 tools/gto_hu_continuation/analyze_node6_72.py --out-json data/gto_terminal_expansion/node6_72/analysis.json \
        --out-png docs/GTO_TERMINAL_NODE6_72_V2.png

Pre-registration: data/gto_terminal_expansion/node6_72/prereg.json. The 72-flop table is the aggregate.py output
(ht_rho, B = 2000); legacy = the solver's own P9 payoff at node 6 (injection bypassed).
"""
import argparse
import json
import statistics

D = 'data/gto_terminal_expansion/'
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'


def seat(t, pos):
    return next(s for s in t['seats'] if s['position'] == pos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-png', required=True)
    a = ap.parse_args()
    term = json.load(open(D + 'terminals/p9_node6.json'))
    L = term['class_labels']
    tab = json.load(open(D + 'node6_72/table72.json'))
    pil = json.load(open(D + 'pilot6/analysis.json'))['terminals']['6']
    census = json.load(open(D + 'census_p9.json'))
    reach = next(r for r in census['terminals'] if r['terminal_node'] == 6)
    import glob
    flops = [json.load(open(f)) for f in sorted(glob.glob(D + 'node6_72/flops/*.json'))]
    res = {'reach_probability': term['reach_probability'], 'flop_share': reach['share_of_flop_reach'],
           'flops': len(flops), 'converged': sum(1 for f in flops if f['exploitability_pct_pot'] <= f['provenance_key']['target_exploitability_pct_pot']),
           'exploitability_pct_pot': {'max': max(f['exploitability_pct_pot'] for f in flops), 'mean': sum(f['exploitability_pct_pot'] for f in flops) / len(flops)},
           'per_flop_invariant_max_abs': max(abs(f['invariant']['error']) for f in flops),
           'solve_cpu_hours': sum(f['cost']['solve_ms'] for f in flops) / 3.6e6,
           'table': {'estimator': tab.get('estimator'), 'unallocated_bb': tab['invariant']['unallocated_bb']}, 'seats': {}}
    for p in term['players']:
        pos = p['position']
        s = seat(tab, pos)
        v72, leg, v6 = s['gross'], p['legacy_gross'], pil['seats'][pos]['solved']
        r = p['class_reach_normalized']
        hw = [(hi - lo) / 2 for lo, hi in zip(s['gross_ci95_lo'], s['gross_ci95_hi'])]
        d = [x - y for x, y in zip(v72, leg)]
        d6 = [x - y for x, y in zip(v6, v72)]
        res['seats'][pos] = {
            'role': 'OOP' if term['postflop_order'][0] == pos else 'IP',
            'aggressor_or_caller': 'aggressor' if pos == term['aggressor'] else 'caller',
            'ci_halfwidth': {'mean': sum(hw) / 169, 'median': statistics.median(hw), 'max': max(hw)},
            'mean_abs_solved_minus_legacy': sum(abs(x) for x in d) / 169,
            'reach_weighted_abs_solved_minus_legacy': sum(r[h] * abs(d[h]) for h in range(169)),
            'range_ev_shift': sum(r[h] * d[h] for h in range(169)),
            'solved_over_legacy_range_ev': sum(r[h] * v72[h] for h in range(169)) / sum(r[h] * leg[h] for h in range(169)),
            'share_classes_delta_outside_ci': sum(1 for h in range(169) if abs(d[h]) > hw[h]) / 169,
            'pilot6_minus_72': {'mean_abs': sum(abs(x) for x in d6) / 169, 'reach_weighted_abs': sum(r[h] * abs(d6[h]) for h in range(169)),
                                'range_ev_diff': sum(r[h] * d6[h] for h in range(169)),
                                'share_outside_72_ci': sum(1 for h in range(169) if abs(d6[h]) > hw[h]) / 169},
            'pilot6_range_ev_shift': pil['seats'][pos]['range_ev_shift'],
            'br_minus_eps_max': s['max_br_minus_eps_bb'],
            '_v72': v72, '_leg': leg, '_v6': v6, '_hw': hw, '_r': r,
        }
    sb, bb = res['seats']['SB'], res['seats']['BB']
    res['direction_check'] = {
        'rule': 'caller (BB) legacy overvalue = range-EV shift < 0; aggressor (SB) legacy undervalue = shift > 0 (six-flop pilot direction)',
        'pilot6': {'SB_shift': sb['pilot6_range_ev_shift'], 'BB_shift': bb['pilot6_range_ev_shift']},
        '72flop': {'SB_shift': sb['range_ev_shift'], 'BB_shift': bb['range_ev_shift']},
        'holds': sb['range_ev_shift'] > 0 and bb['range_ev_shift'] < 0,
    }
    res['impact'] = {'mean_abs_both_seats': (sb['mean_abs_solved_minus_legacy'] + bb['mean_abs_solved_minus_legacy']) / 2,
                     'reach_weighted_sum_seats': sb['reach_weighted_abs_solved_minus_legacy'] + bb['reach_weighted_abs_solved_minus_legacy']}
    res['impact']['score_unweighted'] = res['reach_probability'] * res['impact']['mean_abs_both_seats']
    res['impact']['score_reach_weighted'] = res['reach_probability'] * res['impact']['reach_weighted_sum_seats']
    res['impact']['pilot6'] = pil['impact']
    # action boundaries with the other strategies fixed at P9 (SB open node: q; BB response: q = 1)
    dec = {}
    for pn in term['path_nodes']:
        actor = pn['actor']
        if actor not in res['seats'] or not pn['ev_bb']:
            continue
        a_on = pn['chosen']
        if pn['k'] == len(term['path_nodes']) - 1:
            q = 1.0
        else:
            q = next(v['terminal_sensitivity_q'] for v in term['action_values'].values() if v['path'] == term['path'][:pn['k']])
        S = res['seats'][actor]
        dl = [x - y for x, y in zip(S['_v72'], S['_leg'])]
        flips = []
        for h in range(169):
            if pn['class_reach_before'][h] <= 0:
                continue
            e0 = [e[h] for e in pn['ev_bb']]
            e1 = list(e0)
            e1[a_on] += q * dl[h]
            b0 = max(range(len(e0)), key=lambda i: e0[i])
            b1 = max(range(len(e1)), key=lambda i: e1[i])
            if b0 != b1:
                margin = e1[b1] - sorted(e1)[-2]
                flips.append({'class': L[h], 'from': pn['actions'][b0], 'to': pn['actions'][b1], 'shift_bb': q * dl[h],
                              'new_margin_bb': margin, 'margin_over_ci': margin / max(1e-9, q * S['_hw'][h])})
        m = sum(pn['class_reach_before'])
        dec[f"{actor}"] = {'node_actions': pn['actions'], 'on_path': pn['actions'][a_on], 'q': q, 'mix_P9': pn['mix'],
                           'flip_count': len(flips), 'flip_share_of_mass': sum(pn['class_reach_before'][L.index(f['class'])] for f in flips) / m,
                           'flips_beyond_ci': sum(1 for f in flips if f['margin_over_ci'] > 1), 'flips': flips}
    res['decisions_other_strategies_fixed'] = dec
    out = json.loads(json.dumps(res))
    for pos in out['seats']:
        for k in ('_v72', '_leg', '_v6', '_hw', '_r'):
            out['seats'][pos].pop(k)
    json.dump(out, open(a.out_json, 'w'), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ('decisions_other_strategies_fixed',)}, indent=1)[:4000])
    for k, v in out['decisions_other_strategies_fixed'].items():
        print(k, v['on_path'], 'q', round(v['q'], 3), 'flips', v['flip_count'], f"{v['flip_share_of_mass']:.1%}", 'beyond CI', v['flips_beyond_ci'])
    figure(res, L, a.out_png)


def figure(res, L, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(19, 6), dpi=120)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    for pos, col in (('SB', C3), ('BB', C1)):
        S = res['seats'][pos]
        g.scatter(S['_v72'], S['_v6'], s=10, color=col, label=f"{pos} ({S['role']}, {S['aggressor_or_caller']}): mean |6−72| {S['pilot6_minus_72']['mean_abs']:.2f} bb")
    lo = min(min(res['seats'][p]['_v72']) for p in res['seats'])
    hi = max(max(res['seats'][p]['_v72']) for p in res['seats'])
    g.plot([lo, hi], [lo, hi], color=MUTED, lw=1, ls=':')
    g.set_xlabel('72-flop value (bb)', fontsize=9, color=MUTED)
    g.set_ylabel('six-flop pilot value (bb)', fontsize=9, color=MUTED)
    g.set_title('(1) node 6: six-flop pilot vs 72-flop, per class', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[1]
    for pos, col in (('SB', C3), ('BB', C1)):
        S = res['seats'][pos]
        d = [x - y for x, y in zip(S['_v72'], S['_leg'])]
        g.scatter(S['_leg'], d, s=10, color=col, label=f"{pos}: mean |solved − legacy| {S['mean_abs_solved_minus_legacy']:.2f} bb")
        g.scatter(S['_leg'], S['_hw'], s=4, marker='_', color=col, alpha=0.5)
        g.scatter(S['_leg'], [-x for x in S['_hw']], s=4, marker='_', color=col, alpha=0.5)
    g.axhline(0, color=INK, lw=1)
    g.set_xlabel('legacy value (bb)', fontsize=9, color=MUTED)
    g.set_ylabel('72-flop solved − legacy (bb); ticks = ± own 95% CI', fontsize=9, color=MUTED)
    g.set_title('(2) solved − legacy per class (72 flops)', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[2]
    xs = [0, 1]
    for j, (key, lab, col) in enumerate((('pilot6_range_ev_shift', 'six-flop pilot', C2), ('range_ev_shift', '72 flops', C1))):
        vals = [res['seats']['SB'][key], res['seats']['BB'][key]]
        g.bar([x + (j - 0.5) * 0.36 for x in xs], vals, 0.34, color=col, label=lab)
        for x, v in zip(xs, vals):
            g.text(x + (j - 0.5) * 0.36, v, f'{v:+.3f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=8, color=INK)
    g.axhline(0, color=INK, lw=1)
    g.set_xticks(xs)
    g.set_xticklabels(['SB (OOP, aggressor)', 'BB (IP, caller)'], fontsize=9)
    g.set_ylabel('signed range-EV shift, solved − legacy (bb)', fontsize=9, color=MUTED)
    g.set_title('(3) direction check: aggressor up, caller down?', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
