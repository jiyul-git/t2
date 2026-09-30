#!/usr/bin/env python3
"""T2-B: what the legacy 3-way terminals (nodes 46, 246) do, and the P0 -> P9 reach decomposition.

    python3 tools/gto_hu_continuation/analyze_mw_legacy.py --out-json data/gto_terminal_expansion/mw_legacy/analysis.json

Inputs: t2_cont_terminal exports at P9 (T2_CONT_FILE = k8/table.json) and P0 (no table) for
nodes 28, 46 and 246 (data/gto_terminal_expansion/terminals/).
1. arriving ranges: mass, invested, behind, pot, SPR, aggressor, postflop order, in-range classes;
2. coupled_deck_v1 re-computed independently (coupled_deck_ref.py) vs the Rust f64 value and
   vs terminal_value (f32);
3. pot conservation of the legacy payoff: sum_p sum_h r_ph V_ph - pot (3-way and HU);
4. every decision on the path: mix, and per class the margin of the chosen action over the
   best alternative (class action EVs, read-only dump);
5. reach = product of the per-decision reach factors, so the P0 -> P9 change of log reach
   splits exactly into per-decision terms; the SB-flat term is split further by holding the
   BTN or the BB distribution at P0 in the node-46 legacy value of the SB (coupled deck).
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coupled_deck_ref as cd  # noqa: E402

D = 'data/gto_terminal_expansion/terminals/'


def load(state, node):
    return json.load(open(f'{D}{state}_node{node}.json'))


def pl(t, pos):
    return next(p for p in t['players'] if p['position'] == pos)


def ranges_summary(t):
    return {'terminal_node': t['terminal_node'], 'path': t['path_spec'], 'pot_bb': t['pot_bb'], 'spr': t['spr'],
            'effective_behind_bb': t['effective_behind_bb'], 'aggressor': t['aggressor'], 'postflop_order': t['postflop_order'],
            'reach_probability': t['reach_probability'], 'ranges_hash': t['ranges_hash_fnv1a64'],
            'players': [{'position': p['position'], 'invested_bb': p['invested_bb'], 'behind_bb': p['behind_bb'],
                         'range_mass': p['range_mass'], 'classes_in_range': p['classes_with_positive_reach'],
                         'static_r': p['static_r'], 'class_reach_normalized': p['class_reach_normalized']} for p in t['players']]}


def conservation(t, field='legacy_gross'):
    tot = sum(sum(r * v for r, v in zip(p['class_reach_normalized'], p[field])) for p in t['players'])
    return {'sum_range_weighted_gross': tot, 'pot': t['pot_bb'], 'unallocated_bb': t['pot_bb'] - tot,
            'per_player_range_ev': {p['position']: sum(r * v for r, v in zip(p['class_reach_normalized'], p[field])) for p in t['players']}}


def decisions(t):
    L = t['class_labels']
    out = []
    for pn in t['path_nodes']:
        a = pn['chosen']
        rb = pn['class_reach_before']
        mass = sum(rb)
        row = {'k': pn['k'], 'actor': pn['actor'], 'actions': pn['actions'], 'chosen': pn['actions'][a], 'mix': pn['mix'],
               'reach_factor': pn['reach_factor']}
        if pn['ev_bb']:
            ev = pn['ev_bb']
            margins = []
            for h in range(169):
                if rb[h] <= 0:
                    continue
                alt = max(ev[i][h] for i in range(len(ev)) if i != a)
                margins.append((ev[a][h] - alt, h))
            took = [(m, h) for m, h in margins if pn['class_strategy'][a][h] > 0.5]
            row['chosen_action_margin'] = {
                'classes_reached': len(margins),
                'classes_taking_it_gt_half': len(took),
                'reach_weighted_mean_margin_of_takers': (sum(m * rb[h] for m, h in took) / sum(rb[h] for m, h in took)) if took else None,
                'takers_with_margin_lt_0_05': sum(1 for m, h in took if m < 0.05),
                'takers_with_margin_lt_0_2': sum(1 for m, h in took if m < 0.2),
                'weakest_takers': [{'class': L[h], 'margin_bb': m} for m, h in sorted(took)[:8]],
                'nontakers_within_0_05': [L[h] for m, h in margins if -0.05 < m <= 0 and pn['class_strategy'][a][h] <= 0.5],
            }
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--seed', type=int, default=202)
    a = ap.parse_args()
    res = {'nodes': {}, 'decomposition': {}}
    table = cd.build(a.seed)
    for node in (46, 246):
        res['nodes'][node] = {}
        for state in ('P9', 'P0'):
            t = load(state.lower(), node)
            repro = {}
            for p in t['players']:
                opp = [q['class_reach_normalized'] for q in t['players'] if q['seat'] != p['seat']]
                g = [t['pot_bb'] * e for e in cd.equities(table, opp)]
                repro[p['position']] = {'bit_identical_to_rust_f64': g == p['coupled_deck_gross_f64'],
                                        'max_abs_diff_rust_f64': max(abs(x - y) for x, y in zip(g, p['coupled_deck_gross_f64'])),
                                        'max_abs_diff_terminal_value_f32': max(abs(x - y) for x, y in zip(g, p['legacy_gross']))}
            res['nodes'][node][state] = {'ranges': ranges_summary(t), 'coupled_deck_reproduction': repro,
                                         'conservation': conservation(t), 'decisions': decisions(t),
                                         'legacy_gross': {p['position']: p['legacy_gross'] for p in t['players']}}
    # HU legacy conservation for comparison (static realization weights)
    res['hu_legacy_conservation'] = {}
    for node in (28, 6, 228, 1371):
        t = load('p9', node)
        res['hu_legacy_conservation'][node] = conservation(t)
    # P0 -> P9 decomposition of log reach
    for node in (28, 46, 246):
        t9, t0 = load('p9', node), load('p0', node)
        terms = []
        for d9, d0 in zip(t9['path_nodes'], t0['path_nodes']):
            terms.append({'decision': f"{d9['actor']}:{d9['actions'][d9['chosen']]}", 'factor_P0': d0['reach_factor'], 'factor_P9': d9['reach_factor'],
                          'dlog': math.log(d9['reach_factor'] / d0['reach_factor'])})
        res['decomposition'][node] = {'reach_P0': t0['reach_probability'], 'reach_P9': t9['reach_probability'],
                                      'dlog_total': math.log(t9['reach_probability'] / t0['reach_probability']),
                                      'relative_change': t9['reach_probability'] / t0['reach_probability'] - 1, 'terms': terms}
    # the SB flat at node 46: SB's legacy node-46 value (reach-weighted over the SB's P9 flatting range)
    # with the opponents' distributions switched between P0 and P9 one at a time
    t9, t0 = load('p9', 46), load('p0', 46)
    sb9 = pl(t9, 'SB')['class_reach_normalized']
    d = {}
    for btn_state, bb_state in (('P0', 'P0'), ('P9', 'P0'), ('P0', 'P9'), ('P9', 'P9')):
        btn = pl(t9 if btn_state == 'P9' else t0, 'BTN')['class_reach_normalized']
        bb = pl(t9 if bb_state == 'P9' else t0, 'BB')['class_reach_normalized']
        g = [t9['pot_bb'] * e for e in cd.equities(table, [btn, bb])]
        d[f'BTN_{btn_state}_BB_{bb_state}'] = sum(r * v for r, v in zip(sb9, g))
    res['sb_flat_value_attribution'] = {
        'note': 'range-weighted legacy node-46 gross of the SB (P9 flatting range) with the BTN / BB arriving distributions at P0 or P9',
        'values_bb': d,
        'effect_btn_range_P0_to_P9': d['BTN_P9_BB_P0'] - d['BTN_P0_BB_P0'],
        'effect_bb_range_P0_to_P9': d['BTN_P0_BB_P9'] - d['BTN_P0_BB_P0'],
        'total': d['BTN_P9_BB_P9'] - d['BTN_P0_BB_P0']}
    json.dump(res, open(a.out_json, 'w'), indent=1)
    for node, st in res['nodes'].items():
        for state, v in st.items():
            r = v['ranges']
            print(f'node {node} {state}: reach {r["reach_probability"]:.5f} pot {r["pot_bb"]} spr {r["spr"]:.2f} order {r["postflop_order"]} '
                  + ' '.join(f'{p["position"]}(inv {p["invested_bb"]}, mass {p["range_mass"]:.3f}, cls {p["classes_in_range"]}, r {p["static_r"]:.3f})' for p in r['players']))
            print('   repro', {k: (x['bit_identical_to_rust_f64'], f"{x['max_abs_diff_terminal_value_f32']:.1e}") for k, x in v['coupled_deck_reproduction'].items()},
                  'unallocated %.4f' % v['conservation']['unallocated_bb'], {k: round(x, 3) for k, x in v['conservation']['per_player_range_ev'].items()})
            for dd in v['decisions']:
                cm = dd.get('chosen_action_margin') or {}
                print(f"   {dd['actor']:3s} {dd['chosen']:10s} factor {dd['reach_factor']:.4f} mix {{{', '.join(f'{k}: {x:.3f}' for k, x in dd['mix'].items())}}}"
                      + (f" | takers {cm['classes_taking_it_gt_half']}/{cm['classes_reached']} rw-margin {cm['reach_weighted_mean_margin_of_takers']:.3f} <0.05: {cm['takers_with_margin_lt_0_05']} weakest {[(w['class'], round(w['margin_bb'], 3)) for w in cm['weakest_takers'][:4]]}" if cm else ''))
    print('HU legacy conservation', {k: round(v['unallocated_bb'], 4) for k, v in res['hu_legacy_conservation'].items()})
    for node, v in res['decomposition'].items():
        print(f'decomp node {node}: reach {v["reach_P0"]:.5f} -> {v["reach_P9"]:.5f} ({v["relative_change"]:+.1%}), dlog {v["dlog_total"]:+.3f} =',
              ' + '.join(f'{x["decision"]} {x["dlog"]:+.3f} ({x["factor_P0"]:.3f}->{x["factor_P9"]:.3f})' for x in v['terms']))
    print('SB flat value attribution', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res['sb_flat_value_attribution'].items() if k != 'note'})


if __name__ == '__main__':
    main()
