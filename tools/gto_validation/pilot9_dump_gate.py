#!/usr/bin/env python3
"""Gate for t2_tree_dump: every decision node on the exported paths must appear in the dump with the same average strategy
(exact) and the same per-action class EVs as t2_action_values (path export ev_bb). Reports max abs differences.
    python3 tools/gto_validation/pilot9_dump_gate.py <dump.jsonl> <export_dir> <out.json>"""
import glob
import json
import sys

dump, exdir, out = sys.argv[1:4]
by_node = {}
for line in open(dump):
    r = json.loads(line)
    by_node[r['node']] = r
res = {'nodes_checked': 0, 'missing': [], 'sigma_max_abs': 0.0, 'ev_max_abs': 0.0, 'ev_max_rel': 0.0, 'path_mismatch': 0}
seen = set()
for f in sorted(glob.glob(exdir + '/export_*.json')):
    t = json.load(open(f))
    for k, pn in enumerate(t['path_nodes']):
        n = pn['node']
        if n in seen:
            continue
        seen.add(n)
        r = by_node.get(n)
        if r is None:
            res['missing'].append(n)
            continue
        if r['path'] != t['path'][:k]:
            res['path_mismatch'] += 1
        res['nodes_checked'] += 1
        for a in range(len(pn['actions'])):
            for h in range(169):
                res['sigma_max_abs'] = max(res['sigma_max_abs'], abs(r['sigma'][a][h] - pn['class_strategy'][a][h]))
                if pn['ev_bb'] is not None and pn['class_reach_before'][h] > 0:
                    d = abs(r['ev'][a][h] - pn['ev_bb'][a][h])
                    res['ev_max_abs'] = max(res['ev_max_abs'], d)
                    res['ev_max_rel'] = max(res['ev_max_rel'], d / max(1.0, abs(pn['ev_bb'][a][h])))
res['pass_sigma_exact'] = res['sigma_max_abs'] == 0.0
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res))
