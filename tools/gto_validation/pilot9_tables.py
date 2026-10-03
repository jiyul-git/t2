#!/usr/bin/env python3
"""Build t2_hu_continuation tables for the 4 pilot nodes.
    pilot9_tables.py legacy <export_dir> <out_dir>      gross = exported legacy_gross (static payoff at the export's profile)
    pilot9_tables.py solved <flops_root> <out_dir>      gross = A4c estimator over the solved panel_v1 flops of each node
"""
import json
import os
import sys

NODES = {'btn': 24, 'co': 73, 'hj': 242, 'utg': 24726}


def main():
    mode, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    if mode == 'solved':
        return solved(src, out)
    assert mode == 'legacy'
    files = []
    for n, node in NODES.items():
        t = json.load(open(os.path.join(src, f'legacy_{n}.json')))
        assert t['terminal_node'] == node, (n, t['terminal_node'])
        tab = {'schema': 't2_hu_continuation_table_v1', 'node': node, 'live': t['terminal_live_mask'], 'pot_bb': t['pot_bb'],
               'value_convention': 'gross_share', 'zero_reach_definition': 'eps_tremble_avg',
               'seats': [{'seat': p['seat'], 'position': p['position'], 'gross': p['legacy_gross']} for p in t['players']],
               'provenance': {'kind': 'C1a static payoff frozen at the 100-iteration profile', 'source': f'legacy_{n}.json'}}
        json.dump(tab, open(os.path.join(out, f'node{node}.json'), 'w'))
        files.append({'file': f'node{node}.json'})
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': files}, open(os.path.join(out, 'manifest.json'), 'w'))


def solved(root, out):
    """root/<name>/flops/<board>.json from solve_panel.py at the terminal root/terminals/legacy_<name>.json"""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gto_hu_continuation'))
    import a4c_run as C
    panel = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data/gto_hu_continuation/panel_v1.json')))
    boards = [f['board'] for f in panel['panel']]
    draws = {}
    for f in panel['panel']:
        draws.setdefault(f['stratum'], []).append(f['board'])
    p_str = {s: v['probability'] for s, v in panel['strata'].items()}
    compat = C.compat_of(boards)
    files = []
    rep = {}
    for n, node in NODES.items():
        term = json.load(open(os.path.join(root, 'terminals', f'legacy_{n}.json')))
        vals = {}
        expl = []
        for b in boards:
            d = json.load(open(os.path.join(root, n, 'flops', b + '.json')))
            k = d['provenance_key']
            assert k['ranges_hash_fnv1a64'] == term['ranges_hash_fnv1a64'] and k['panel_hash_sha256'] == panel['panel_hash_sha256'], (n, b)
            assert d['converged'] and d['exploitability_pct_pot'] <= 0.3, (n, b, d['exploitability_pct_pot'])
            vals[b] = {pl['position']: pl['gross_eps'] for pl in d['players']}
            expl.append(d['exploitability_pct_pot'])
        g = C.estimate(vals, compat, draws, p_str)
        legacy = {p['position']: p['legacy_gross'] for p in term['players']}
        tab = {'schema': 't2_hu_continuation_table_v1', 'node': node, 'live': term['terminal_live_mask'], 'pot_bb': term['pot_bb'],
               'value_convention': 'gross_share', 'zero_reach_definition': 'eps_tremble_avg',
               'seats': [{'seat': p['seat'], 'position': p['position'], 'gross': g[p['position']]} for p in term['players']],
               'provenance': {'kind': 'C2 solved continuation, panel_v1 (24 boards), A4c estimator', 'terminal': f'legacy_{n}.json',
                              'ranges_hash_fnv1a64': term['ranges_hash_fnv1a64'], 'max_expl_pct_pot': max(expl)}}
        json.dump(tab, open(os.path.join(out, f'node{node}.json'), 'w'))
        files.append({'file': f'node{node}.json'})
        rep[n] = {'node': node, 'max_expl_pct_pot': max(expl),
                  'mean_gross_minus_legacy_by_seat': {pos: sum(a - b for a, b in zip(g[pos], legacy[pos])) / 169 for pos in g}}
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': files}, open(os.path.join(out, 'manifest.json'), 'w'))
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
