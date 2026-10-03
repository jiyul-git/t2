#!/usr/bin/env python3
"""C1a comparison: legacy vs injected exports at the same fixed 100-iteration profile must be bit-identical
(gaps, evs, gap_total, every path node's mix / class_strategy / ev_bb, terminal pot / behind); the injected exports must also
report model_gross == the injected table. No tolerance: any difference is a failure to explain.
    python3 tools/gto_validation/pilot9_c1a_compare.py"""
import hashlib
import json
import os

D = '/home/user/gto_ckpt/c1/'
OUT = '/home/user/t2/data/gto_validation/pilot9/c1/'
NAMES = ['btn', 'co', 'hj', 'utg', 'utg1_ctrl']
NODES = {'btn': 24, 'co': 73, 'hj': 242, 'utg': 24726}


def h(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()


def main():
    res = {'schema': 'pilot9_c1a_v1', 'profile': D + 'ck_fixed.gtop (100-iteration checkpoint, no further iterations)',
           'checkpoint_sha256': hashlib.sha256(open(D + 'ck_fixed.gtop', 'rb').read()).hexdigest(), 'paths': {}, 'diffs': []}
    for n in NAMES:
        a = json.load(open(D + f'legacy_{n}.json'))
        b = json.load(open(D + f'injected_{n}.json'))
        r = {'terminal_node': a['terminal_node']}
        for k in ('gap_total', 'gaps', 'evs', 'pot_bb', 'effective_behind_bb', 'iterations'):
            same = a[k] == b[k]
            r[k + '_identical'] = same
            if not same:
                res['diffs'].append(f'{n}: {k} differs')
        pa, pb = a['path_nodes'], b['path_nodes']
        same_pn = len(pa) == len(pb) and all(x[k] == y[k] for x, y in zip(pa, pb) for k in ('mix', 'class_strategy', 'ev_bb', 'class_reach_before'))
        r['path_nodes_identical'] = same_pn
        if not same_pn:
            for x, y in zip(pa, pb):
                for k in ('mix', 'class_strategy', 'ev_bb', 'class_reach_before'):
                    if x[k] != y[k]:
                        res['diffs'].append(f"{n}: path node {x['actor']}@{x['node']} {k} differs")
        r['path_nodes_sha256'] = h(pa)
        if n in NODES:
            tab = json.load(open(D + f'static_tables/node{NODES[n]}.json'))
            g = {s['seat']: s['gross'] for s in tab['seats']}
            ok = all(p['model_gross'] == g[p['seat']] for p in b['players'])
            r['injected_model_gross_equals_table'] = ok
            r['injected_legacy_gross_equals_table'] = all(p['legacy_gross'] == g[p['seat']] for p in b['players'])
            if not ok:
                res['diffs'].append(f'{n}: injected model_gross != table')
            r['t2_cont_file'] = b.get('t2_cont_file')
        res['paths'][n] = r
    res['pass'] = not res['diffs']
    res['meaning'] = ('exact: the t2_cont injection reproduces the static payoff bit for bit at a fixed profile (node ids, seats, live masks, pot, '
                      'class order, value convention). Not tested here by design: a from-scratch solve with frozen tables differs from the dynamic '
                      'static payoff (tables do not react to the opponent reach inside CFR) -> measured separately as the C1b control arm.')
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(OUT + 'c1a_identity.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'paths'}, indent=1))
    print(json.dumps(res['paths'], indent=1)[:2500])


if __name__ == '__main__':
    main()
