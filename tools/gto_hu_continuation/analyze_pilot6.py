#!/usr/bin/env python3
"""T2-A: six-flop solved-vs-legacy impact pilot for HU terminals (P9 state).

    python3 tools/gto_hu_continuation/analyze_pilot6.py --out-json data/gto_terminal_expansion/pilot6/analysis.json \
        --out-png docs/GTO_TERMINAL_PILOT6_V2.png

Per terminal (P9 arriving ranges, M2 f32, eps-tremble, target 0.3% pot, panel_sub6 boards/weights,
the terminal's fixed normaliser fixed before the solves):
  V_solved[p,h] = sum_f w_f c_hf v_hf / norm_p          (same functional as J1/J2)
  V_legacy[p,h] = the solver's own terminal payoff at P9 (injection bypassed), gross share
  delta = V_solved - V_legacy
Reported: mean |delta| (all classes; in-range classes), reach-weighted sum_h r_h |delta| per seat,
signed range-EV shift sum_h r_h delta, conservation of both tables, postflop exploitability,
runtime; preflop decisions with the other strategies fixed at P9: the caller's EV of calling
moves by delta (q = 1), the aggressor's raise EV by q * delta; classes whose best action flips.
Impact = reach x mean |delta|, two variants:
  (a) unweighted: mean over the 169 classes and both seats;
  (b) reach-weighted: sum over seats of sum_h r_ph |delta_ph| (design doc formula).
Pilot noise reference: node 28 six-flop solved vs the 72-flop k9 measured table at the same P9 ranges.
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import class_combos, parse_board  # noqa: E402

D = 'data/gto_terminal_expansion/'
NODES = [28, 6, 228, 1371]
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'


def pl(t, pos):
    return next(p for p in t['players'] if p['position'] == pos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-png', required=True)
    a = ap.parse_args()
    census = json.load(open(D + 'census_p9.json'))
    creach = {r['terminal_node']: r for r in census['terminals']}
    k9 = json.load(open('data/gto_hu_continuation/panel72/outer_v2_damped_a05/k9/table_measured.json'))
    res = {'terminals': {}}
    for n in NODES:
        term = json.load(open(f'{D}terminals/p9_node{n}.json'))
        panel = json.load(open(f'{D}pilot6/panel_node{n}.json'))
        L = term['class_labels']
        combos = [class_combos(l) for l in L]
        flops = {}
        for f in panel['panel']:
            d = json.load(open(f'{D}pilot6/node{n}/flops/{f["board"]}.json'))
            k = d['provenance_key']
            assert k['ranges_hash_fnv1a64'] == term['ranges_hash_fnv1a64'] and k['panel_hash_sha256'] == panel['panel_hash_sha256']
            flops[f['board']] = d
        row = {'reach_probability': term['reach_probability'], 'share_of_flop_reach': creach[term['terminal_node']]['share_of_flop_reach'],
               'path': term['path_spec'], 'pot_bb': term['pot_bb'], 'spr': term['spr'], 'postflop_order': term['postflop_order'],
               'per_flop': {b: {'iterations': d['iterations'], 'exploitability_pct_pot': d['exploitability_pct_pot'],
                                'solve_s': d['cost']['solve_ms'] / 1e3, 'invariant_error_bb': d['invariant']['error'],
                                'peak_rss_mb': (d['cost'].get('peak_rss_kb') or 0) / 1024} for b, d in flops.items()},
               'seats': {}}
        V = {}
        for p in term['players']:
            pos = p['position']
            vals, br = [], []
            for h in range(169):
                s = sb = 0.0
                for f in panel['panel']:
                    x = next(q for q in flops[f['board']]['players'] if q['position'] == pos)
                    bc = parse_board(f['board'])
                    c = sum(1 for cc in combos[h] if cc[0] not in bc and cc[1] not in bc) / len(combos[h])
                    if x['gross_eps'][h] is not None:
                        s += f['weight'] * c * x['gross_eps'][h]
                        sb += f['weight'] * c * x['gross_br'][h]
                vals.append(s / panel['fixed_normaliser'][pos])
                br.append(sb / panel['fixed_normaliser'][pos])
            V[pos] = vals
            leg = p['legacy_gross']
            r = p['class_reach_normalized']
            inr = [h for h in range(169) if p['class_keep_fraction'][h] > 1e-6]
            dl = [v - l for v, l in zip(vals, leg)]
            row['seats'][pos] = {
                'solved': vals, 'solved_br': br, 'legacy': leg, 'static_r': p['static_r'],
                'mean_abs_delta': sum(abs(x) for x in dl) / 169,
                'mean_abs_delta_in_range': sum(abs(dl[h]) for h in inr) / len(inr), 'in_range_classes': len(inr),
                'reach_weighted_abs_delta': sum(r[h] * abs(dl[h]) for h in range(169)),
                'range_ev_shift': sum(r[h] * dl[h] for h in range(169)),
                'max_abs_delta': max(abs(x) for x in dl), 'argmax_class': L[max(range(169), key=lambda h: abs(dl[h]))],
                'br_minus_eps_max': max(b - v for b, v in zip(br, vals)),
                'realization_solved_over_legacy_reach_weighted': sum(r[h] * vals[h] for h in range(169)) / sum(r[h] * leg[h] for h in range(169)),
            }
        cons = {}
        for name in ('solved', 'legacy'):
            tot = sum(sum(pl(term, pos)['class_reach_normalized'][h] * row['seats'][pos][name][h] for h in range(169)) for pos in row['seats'])
            cons[name] = term['pot_bb'] - tot
        row['unallocated_bb'] = cons
        seats = list(row['seats'].values())
        row['impact'] = {
            'mean_abs_delta_both_seats': sum(s['mean_abs_delta'] for s in seats) / 2,
            'reach_weighted_abs_delta_sum_seats': sum(s['reach_weighted_abs_delta'] for s in seats),
        }
        row['impact']['score_unweighted'] = row['reach_probability'] * row['impact']['mean_abs_delta_both_seats']
        row['impact']['score_reach_weighted'] = row['reach_probability'] * row['impact']['reach_weighted_abs_delta_sum_seats']
        # preflop decisions, other strategies fixed at P9
        dec = {}
        for pn in term['path_nodes']:
            actor = pn['actor']
            if actor not in row['seats'] or not pn['ev_bb']:
                continue
            a_on = pn['chosen']
            if pn['k'] == len(term['path_nodes']) - 1:
                q = 1.0
            else:
                q = next((v['terminal_sensitivity_q'] for v in term['action_values'].values() if v['path'] == term['path'][:pn['k']]), None)
                if q is None:
                    continue
            dl = [x - y for x, y in zip(row['seats'][actor]['solved'], row['seats'][actor]['legacy'])]
            if n == 28:  # at P9 node 28 already carries the injected k8 table: shift from what the node pays now
                used = pl(term, actor)['model_gross']
                dl = [x - y for x, y in zip(row['seats'][actor]['solved'], used)]
            ev = pn['ev_bb']
            flips = []
            margins_before = []
            for h in range(169):
                if pn['class_reach_before'][h] <= 0:
                    continue
                e0 = [ev[i][h] for i in range(len(ev))]
                e1 = list(e0)
                e1[a_on] += q * dl[h]
                b0 = max(range(len(e0)), key=lambda i: e0[i])
                b1 = max(range(len(e1)), key=lambda i: e1[i])
                if b0 != b1:
                    flips.append({'class': L[h], 'from': pn['actions'][b0], 'to': pn['actions'][b1],
                                  'shift_bb': q * dl[h], 'reach_before': pn['class_reach_before'][h]})
                margins_before.append(e0[a_on] - max(e0[i] for i in range(len(e0)) if i != a_on))
            flip_mass = sum(f['reach_before'] for f in flips) / sum(pn['class_reach_before'])
            dec[f"k{pn['k']}_{actor}"] = {'actions': pn['actions'], 'on_path_action': pn['actions'][a_on], 'q': q,
                                          'mix_P9': pn['mix'], 'flips': flips, 'flip_count': len(flips),
                                          'flip_share_of_actor_mass': flip_mass,
                                          'on_path_margin_median_P9': statistics.median(margins_before)}
        row['decisions_other_strategies_fixed'] = dec
        res['terminals'][n] = row
    # pilot noise reference: node 28 six-flop vs 72-flop k9 measured table at the same ranges
    t28 = res['terminals'][28]
    ref = {}
    for pos, s in t28['seats'].items():
        v72 = next(x for x in k9['seats'] if x['position'] == pos)
        r = pl(json.load(open(f'{D}terminals/p9_node28.json')), pos)['class_reach_normalized']
        d = [x - y for x, y in zip(s['solved'], v72['gross'])]
        ref[pos] = {'mean_abs_6flop_minus_72flop': sum(abs(x) for x in d) / 169,
                    'reach_weighted_abs': sum(r[h] * abs(d[h]) for h in range(169)),
                    'range_ev_diff': sum(r[h] * d[h] for h in range(169)),
                    'k9_72flop_ci_halfwidth_mean': v72['mean_ci95_halfwidth_bb']}
    res['pilot_noise_reference_node28'] = ref
    res['ranking'] = {
        'by_score_unweighted': sorted(((n, r['impact']['score_unweighted']) for n, r in res['terminals'].items() if n != 28), key=lambda x: -x[1]),
        'by_score_reach_weighted': sorted(((n, r['impact']['score_reach_weighted']) for n, r in res['terminals'].items() if n != 28), key=lambda x: -x[1]),
        'node28_reference': {'score_unweighted': t28['impact']['score_unweighted'], 'score_reach_weighted': t28['impact']['score_reach_weighted']},
    }
    json.dump(res, open(a.out_json, 'w'), indent=1)
    for n, r in res['terminals'].items():
        print(f"node {n} reach {r['reach_probability']:.5f} share {r['share_of_flop_reach']:.3f} spr {r['spr']:.2f} unalloc solved {r['unallocated_bb']['solved']:+.4f} legacy {r['unallocated_bb']['legacy']:+.4f}"
              f" expl max {max(x['exploitability_pct_pot'] for x in r['per_flop'].values()):.3f} solve_s {sum(x['solve_s'] for x in r['per_flop'].values()):.0f}")
        for pos, s in r['seats'].items():
            print(f"   {pos}: mean|d| {s['mean_abs_delta']:.3f} in-range {s['mean_abs_delta_in_range']:.3f} rw|d| {s['reach_weighted_abs_delta']:.3f} range-EV shift {s['range_ev_shift']:+.3f}"
                  f" max {s['max_abs_delta']:.2f} ({s['argmax_class']}) solved/legacy {s['realization_solved_over_legacy_reach_weighted']:.3f} br-eps {s['br_minus_eps_max']:.3f}")
        print('   impact', {k: round(v, 5) for k, v in r['impact'].items()})
        for k, d in r['decisions_other_strategies_fixed'].items():
            print(f"   {k} q {d['q']:.3f} flips {d['flip_count']} ({d['flip_share_of_actor_mass']:.1%} of mass):", [(f['class'], f['from'][:5], f['to'][:5], round(f['shift_bb'], 2)) for f in d['flips'][:14]])
    print('noise ref node 28 (6 vs 72 flops):', {p: {k: round(v, 3) for k, v in x.items()} for p, x in ref.items()})
    print('ranking', res['ranking'])
    figure(res, a.out_png)


def figure(res, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    T = res['terminals']
    names = {28: 'node 28\nBTN–BB SRP\n(solved; ref)', 6: 'node 6\nSB–BB SRP', 228: 'node 228\nCO–BB SRP', 1371: 'node 1371\nCO–BTN 3bet'}
    fig, ax = plt.subplots(1, 3, figsize=(18, 5.5), dpi=120)
    fig.patch.set_facecolor(SURF)
    xs = list(range(len(NODES)))
    g = ax[0]
    for j, (key, col, lab) in enumerate((('mean_abs_delta', C1, 'mean |solved − legacy|, all classes'),
                                         ('reach_weighted_abs_delta', C2, 'reach-weighted |solved − legacy|'))):
        vals = [sum(T[n]['seats'][p][key] for p in T[n]['seats']) / 2 for n in NODES]
        g.bar([x + (j - 0.5) * 0.36 for x in xs], vals, 0.34, color=col, label=lab + ' (mean of seats)')
    ref = res['pilot_noise_reference_node28']
    nr = sum(v['mean_abs_6flop_minus_72flop'] for v in ref.values()) / 2
    g.axhline(nr, color=MUTED, ls='--', lw=1)
    g.text(-0.45, nr + 0.03, f'6-flop pilot noise (node 28: 6 vs 72 flops) = {nr:.2f}', ha='left', va='bottom', fontsize=8, color=MUTED)
    g.set_xticks(xs)
    g.set_xticklabels([names[n] for n in NODES], fontsize=8)
    g.set_ylabel('bb per class', fontsize=9, color=MUTED)
    g.set_title('(1) legacy payoff error per class', loc='left', fontsize=11, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[1]
    for j, (key, col, lab) in enumerate((('score_unweighted', C1, 'reach × mean |Δ|'), ('score_reach_weighted', C2, 'reach × Σ_seats reach-weighted |Δ|'))):
        g.bar([x + (j - 0.5) * 0.36 for x in xs], [T[n]['impact'][key] for n in NODES], 0.34, color=col, label=lab)
    g.set_xticks(xs)
    g.set_xticklabels([names[n] for n in NODES], fontsize=8)
    g.set_title('(2) impact score (bb per hand dealt)', loc='left', fontsize=11, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[2]
    for j, n in enumerate(NODES):
        order = T[n]['postflop_order']  # OOP first
        for k, pos in enumerate(order):
            s = T[n]['seats'][pos]
            x = j + (k - 0.5) * 0.36
            v = s['range_ev_shift']
            g.bar([x], [v], 0.34, color=C3 if k == 0 else C1)
            g.text(x, v, pos, ha='center', va='bottom' if v >= 0 else 'top', fontsize=8, color=INK)
    g.axhline(0, color=INK, lw=1)
    g.set_xticks(xs)
    g.set_xticklabels([names[n] for n in NODES], fontsize=8)
    g.set_ylabel('bb (reach-weighted over the arriving range)', fontsize=9, color=MUTED)
    g.set_title('(3) signed range-EV shift, solved − legacy (OOP green / IP blue)', loc='left', fontsize=11, color=INK)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
