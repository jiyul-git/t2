#!/usr/bin/env python3
"""B2-2: 3-way engine in HU degeneration (SB out, non-blocking) vs the vendored HU solver.

    python3 tools/gto_hu_continuation/compare_hu_degen.py

Applies the criteria fixed in data/gto_terminal_expansion/threeway/b2_hu_degeneration_prereg.json.
"""
import json

O = 'data/gto_terminal_expansion/threeway/'


def main():
    pre = json.load(open(O + 'b2_hu_degeneration_prereg.json'))
    eng = json.load(open(O + 'b2_hu_degen_engine.json'))
    ven = json.load(open(O + 'hu_degen_vendored/Kc7d4h.json'))
    rm = json.load(open(O + 'hu_degen_vendored_rootmix.json'))
    pos = eng['positions']
    fin = eng['final']
    res = {'criteria': pre['pass_criteria_fixed_before_running'], 'players': {}, 'checks': {}}
    ok = True
    for row in fin['players']:
        p = pos[row['player']]
        ve = next(x for x in ven['players'] if x['position'] == p)
        d = [a - b for a, b in zip(row['class_gross'], ve['gross_eps']) if a is not None and b is not None]
        mean_abs = sum(abs(x) for x in d) / len(d)
        vi = ven['invariant']['range_mean_gross'][0 if ve['postflop_role'] == 'OOP' else 1]
        res['players'][p] = {'mean_abs_class_diff_bb': mean_abs, 'max_abs_class_diff_bb': max(abs(x) for x in d),
                             'range_value_engine': row['range_value'], 'range_value_vendored': vi,
                             'range_value_diff_bb': row['range_value'] - vi, 'engine_br_gain_pct_pot': row['br_gain_pct_pot']}
        ok &= mean_abs <= 0.05 and abs(row['range_value'] - vi) <= 0.02
    res['engine'] = {'exploitability_pct_pot': fin['exploitability_pct_pot'], 'conservation_error': fin['conservation_error'],
                     'iterations': eng['trace'][-1]['iteration'], 'seconds': eng['trace'][-1]['seconds'], 'bytes': eng['bytes'],
                     'peak_rss_kb': eng['peak_rss_kb']}
    res['vendored'] = {'exploitability_pct_pot': ven['exploitability_pct_pot'], 'iterations': ven['iterations'],
                       'rootmix_run_iterations': rm['iterations'], 'rootmix_run_expl': rm['exploitability_pct_pot']}
    ok &= abs(fin['conservation_error']) <= 1e-6 and fin['exploitability_pct_pot'] <= 0.30
    # aggregate strategy at the BB first decision and BTN after a check
    strat = []
    for e_node, v_node in zip(eng['root_mix'][:2], rm['root_mix'][:2]):
        # engine actions: Check / Bet(x); vendored labels: Check / Bet x
        em = e_node['mix']
        vm = v_node['mix']
        strat.append({'player_engine': pos[e_node['player']], 'player_vendored': v_node['player'], 'actions_engine': e_node['actions'],
                      'actions_vendored': v_node['actions'], 'mix_engine': em, 'mix_vendored': vm,
                      'max_abs_diff': max(abs(a - b) for a, b in zip(em, vm))})
        ok &= max(abs(a - b) for a, b in zip(em, vm)) <= 0.05
    res['aggregate_strategy'] = strat
    res['pass'] = bool(ok)
    json.dump(res, open(O + 'b2_hu_degen_compare.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'criteria'}, indent=1))


if __name__ == '__main__':
    main()
