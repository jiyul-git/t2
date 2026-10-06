#!/usr/bin/env python3
"""Flop-reach coverage from a whole-tree dump: terminal reach = parent node reach_prob x mix(last action); terminal structure
(action indices, live count, pot type, node id) from a 0-iteration census of the same tree.
    python3 tools/gto_validation/pilot9_dump_coverage.py <dump.jsonl> <census_0it.json> <solved_node_map.json|manifest_dir> <out.json>"""
import json
import os
import sys

dump, census, solved, out = sys.argv[1:5]
d = {}
for line in open(dump):
    r = json.loads(line)
    d[tuple(r['path'])] = r
if os.path.isdir(solved):
    nodes = {int(t['file'][4:-5]) for t in json.load(open(os.path.join(solved, 'manifest.json')))['tables']}
else:
    nodes = set(json.load(open(solved)).values())
cat, sol, miss = {}, 0.0, 0
tot = 0.0
for e in json.load(open(census))['terminals']:
    idx = tuple(a['action_index'] for a in e['actions'])
    par = d.get(idx[:-1])
    if par is None:
        miss += 1
        continue
    m0 = sum(par['actor_reach'])
    a = idx[-1]
    mix = sum(par['actor_reach'][h] * par['sigma'][a][h] for h in range(169)) / m0
    reach = par['reach_prob'] * mix
    k = (e['pot_type'], 'hu' if e['live_count'] == 2 else 'mw')
    cat[k] = cat.get(k, 0.0) + reach
    tot += reach
    if e['terminal_node'] in nodes:
        sol += reach
res = {'flop_reach': tot, 'terminals_without_parent_in_dump': miss,
       'share_of_flop_reach': {f'{a}/{b}': v / tot for (a, b), v in cat.items()},
       'solved_share': sol / tot, 'static_share': 1 - sol / tot}
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res, indent=1))
