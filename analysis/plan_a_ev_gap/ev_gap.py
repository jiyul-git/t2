import sys, json, os, time
import numpy as np
sys.path.insert(0, '/home/user/t2/tools/gto_spot')
import grade_spot as G
spec_id, k = sys.argv[1], int(sys.argv[2])
spec = json.load(open('/home/user/t2/data/gto_spot/plan_a/specs/%s.json' % spec_id))
wd = '/home/user/gto_ckpt/spots/%s/step%d/' % (spec_id, k)
tabs = json.load(open(wd + 'tables_used.json'))
mf = wd + 'matrices_used.json'
mats = json.load(open(mf)) if os.path.exists(mf) else {}
t = time.time()
sp = G.solve_with(spec, tabs, mats)
ev = sp.node_evs()
out = {'spot': spec_id, 'k': k, 'solve_s': round(time.time() - t, 1), 'nodes': []}
def rec(i, reach):
    node = sp.nodes[i]; actor = node['actor']; s = sp.avg[i]; E = ev[i]
    acts = [x[2] for x in node['acts']]
    rr = reach[actor]; w = rr * 1326
    hands = {}
    for h in range(169):
        if w[h] > 0.05:
            order = np.argsort(-E[:, h])
            hands[sp.lab169[h]] = {'combos': round(float(w[h]), 2),
                'freq': [round(float(s[a, h]), 3) for a in range(len(acts))],
                'ev': [round(float(E[a, h]), 3) for a in range(len(acts))],
                'gap': round(float(E[order[0], h] - E[order[1], h]), 4), 'best': acts[order[0]]}
    out['nodes'].append({'actor': sp.pos[actor], 'actions': acts, 'reach_combos': round(float(w.sum()), 1), 'hands': hands})
    for a, ch in enumerate(node['children']):
        if ch[0] == 'node':
            r2 = {kk: v.copy() for kk, v in reach.items()}; r2[actor] = reach[actor] * s[a]; rec(ch[1], r2)
rec(sp.root_idx, {kk: v.copy() for kk, v in sp.reach0.items()})
os.makedirs(os.path.dirname(sys.argv[3]), exist_ok=True)
json.dump(out, open(sys.argv[3], 'w'))
print(spec_id, k, 'solve', out['solve_s'], 's')
