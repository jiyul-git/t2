#!/usr/bin/env python3
"""Validate the bounded multiway skip (PREFLOP_MW_SKIP_BELOW): compare two whole-tree dumps of the same tree / tables / seeds
(exact solve vs skip solve), node by node for nodes reached with probability >= min_reach in the exact solve.
Reports the max and reach-weighted mean absolute difference of node mixes (aggregate action frequencies) and of class
frequencies weighted by the actor's class reach, plus the worst nodes.
    python3 tools/gto_validation/skip_validate.py <exact_dump.jsonl> <skip_dump.jsonl> <min_reach> <out.json>"""
import json
import sys

a_f, b_f, thr, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
A = {tuple(r['path']): r for r in map(json.loads, open(a_f))}
B = {tuple(r['path']): r for r in map(json.loads, open(b_f))}
rows = []
missing = 0
for k, r in A.items():
    if r['reach_prob'] < thr:
        continue
    s = B.get(k)
    if s is None:
        missing += 1
        continue
    ra, rb = r['actor_reach'], s['actor_reach']
    ma, mb = sum(ra), sum(rb)
    na = len(r['actions'])
    mix_a = [sum(ra[h] * r['sigma'][a][h] for h in range(169)) / ma for a in range(na)]
    mix_b = [sum(rb[h] * s['sigma'][a][h] for h in range(169)) / mb for a in range(na)]
    dmix = max(abs(x - y) for x, y in zip(mix_a, mix_b))
    dcls = sum(ra[h] * max(abs(r['sigma'][a][h] - s['sigma'][a][h]) for a in range(na)) for h in range(169)) / ma
    rows.append({'line': r['line'], 'reach_prob': r['reach_prob'], 'mix_max_abs_diff': dmix, 'class_reach_weighted_max_abs_diff': dcls})
W = sum(x['reach_prob'] for x in rows)
res = {'nodes': len(rows), 'missing_in_skip_dump': missing, 'min_reach': thr,
       'mix_max_abs_diff': max(x['mix_max_abs_diff'] for x in rows),
       'mix_reach_weighted_mean_abs_diff': sum(x['reach_prob'] * x['mix_max_abs_diff'] for x in rows) / W,
       'class_weighted_max': max(x['class_reach_weighted_max_abs_diff'] for x in rows),
       'worst': sorted(rows, key=lambda x: -x['mix_max_abs_diff'])[:10]}
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'worst'}, indent=1))
for w in res['worst'][:5]:
    print(round(100 * w['mix_max_abs_diff'], 2), 'pp', round(w['reach_prob'], 5), ' > '.join(w['line'][-4:]))
