#!/usr/bin/env python3
"""`quick` grade of a Plan A HU spot (user decision 2026-10-19: fill fast, refine later).

  converged 24-board loop  -> the final step's state (one re-solve)
  cycling / not converged  -> mean of the last 4 steps: each step's subgame is re-solved from its saved tables / matrices and
                              the behaviour strategies are averaged with the actor's own reach as weight (per node and class);
                              per node the record keeps the reach-weighted EV loss of that mean strategy against each step's EVs
No P144. Status `quick` (never verified / conditional_verified; refinement target). Symmetric-stack assumption (all seats 60 bb).
Node scope: the subgame root (opener facing the 3-bet) is the 3-bet response; every later node (after a 4-bet or a jam) is marked
`deep` (research for connection). Nodes the opponent reaches with < 1 combo are marked `off_path` (frequencies there are arbitrary).

    python3 tools/gto_spot/quick_spot.py <spot_id> <step_dir_root> [k1,k2,...]   -> data/gto_spot/quick/<spot_id>.json
step_dir_root holds step<k>/tables_used.json (+ matrices_used.json) and state.json (final_step / converged).
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_spot as G  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OFF_PATH_COMBOS = 1.0      # same fixed threshold as standard amendment 8
REACH_FLOOR = 1e-3         # combos; below it a class is not reported at a node
MEAN_STEPS = 4


def solve_step(spec, d):
    tabs = json.load(open(d + 'tables_used.json'))
    mf = d + 'matrices_used.json'
    mats = json.load(open(mf)) if os.path.exists(mf) else {}
    return G.solve_with(spec, tabs, mats)


def walk(sp):
    """per node path: actor, actions, own reach (169), opponent arriving combos, avg strategy, action EVs"""
    ev = sp.node_evs()
    out = {}

    def rec(i, reach, opp_arr):
        node = sp.nodes[i]
        actor = node['actor']
        out[tuple(node['path'])] = {'actor': sp.pos[actor], 'actions': [x[2] for x in node['acts']],
                                    'reach': reach[actor] * 1326, 'opp_arriving': opp_arr,
                                    'avg': np.array(sp.avg[i]), 'ev': np.array(ev[i]), 'lab': sp.lab169}
        for a, ch in enumerate(node['children']):
            if ch[0] == 'node':
                r2 = {k: v.copy() for k, v in reach.items()}
                r2[actor] = reach[actor] * sp.avg[i][a]
                rec(ch[1], r2, float(r2[actor].sum() * 1326))
    rec(sp.root_idx, {k: v.copy() for k, v in sp.reach0.items()}, None)
    return out


def main():
    sid, sroot = sys.argv[1], sys.argv[2].rstrip('/') + '/'
    spec = json.load(open(os.path.join(ROOT, 'data/gto_spot/plan_a/specs', sid + '.json')))
    st = json.load(open(sroot + 'state.json'))
    converged = bool(st.get('converged'))
    last = int(st.get('final_step', st.get('k')))
    rl = sroot + f'step{last}/report.json'
    capped = (not converged) and os.path.exists(rl) and str(json.load(open(rl)).get('decision', '')).startswith('stop: not converged after')
    if capped:
        MEAN_STEPS_ = 2   # user decision 2026-10-20: stopped at the step cap -> mean of the last 2 steps
    else:
        MEAN_STEPS_ = MEAN_STEPS
    if len(sys.argv) > 3:
        steps = [int(x) for x in sys.argv[3].split(',')]
    else:
        steps = [last] if converged else list(range(max(0, last - MEAN_STEPS_ + 1), last + 1))
    method = 'converged_final_step' if converged and len(steps) == 1 else f'mean_of_last_{len(steps)}_steps'
    t0 = time.time()
    walks = []
    for k in steps:
        walks.append(walk(solve_step(spec, sroot + f'step{k}/')))
        print(sid, 'step', k, 'solved', flush=True)
    paths = [p for p in walks[-1] if all(p in w for w in walks)]
    root_len = min(len(p) for p in paths)
    nodes = []
    for p in sorted(paths, key=lambda x: (len(x), x)):
        ws = [w[p] for w in walks]
        R = np.array([w['reach'] for w in ws])                       # steps x 169
        S = np.array([w['avg'] for w in ws])                         # steps x A x 169
        E = np.array([w['ev'] for w in ws])
        Rs = R.sum(0)
        mean = np.where(Rs > 0, (S * R[:, None, :]).sum(0) / np.where(Rs > 0, Rs, 1), S.mean(0))
        reach = R.mean(0)
        losses = []
        for j in range(len(ws)):
            w = R[j]
            br = E[j].max(0)
            val = (mean * E[j]).sum(0)
            losses.append(float((w * (br - val)).sum() / w.sum()) if w.sum() > 0 else None)
        flip = (np.abs(S - mean[None]).max((0, 1)) > 0.10) if len(ws) > 1 else np.zeros(169, bool)
        evm = E.mean(0)
        order = np.argsort(-evm, axis=0)
        gap = np.take_along_axis(evm, order[:1], 0)[0] - np.take_along_axis(evm, order[1:2], 0)[0]
        opp = [w['opp_arriving'] for w in ws]
        off = opp[0] is not None and min(opp) < OFF_PATH_COMBOS
        hands = {}
        for h in range(169):
            if reach[h] < REACH_FLOOR:
                continue
            hands[ws[0]['lab'][h]] = {'combos': round(float(reach[h]), 3),
                             'freq': {ws[0]['actions'][a]: round(float(mean[a, h]), 4) for a in range(mean.shape[0])},
                             'ev_bb': {ws[0]['actions'][a]: round(float(evm[a, h]), 3) for a in range(mean.shape[0])},
                             'gap_bb': round(float(gap[h]), 4),
                             'unstable_across_steps': bool(flip[h])}
        tot = reach.sum()
        nodes.append({'path': list(p), 'actor': ws[0]['actor'], 'actions': ws[0]['actions'],
                      'scope': '3-bet response' if len(p) == root_len else 'deep (after 4-bet / jam): research',
                      'off_path': off, 'opp_arriving_combos': [None if x is None else round(x, 4) for x in opp],
                      'reach_combos': round(float(tot), 2),
                      'mix': {ws[0]['actions'][a]: round(float((reach * mean[a]).sum() / tot), 4) for a in range(mean.shape[0])} if tot > 0 else None,
                      'ev_loss_of_mean_vs_each_step_bb': [None if x is None else round(x, 4) for x in losses],
                      'unstable_combos': round(float(reach[flip].sum()), 2),
                      'hands': hands})
    rec = {'schema': 'spot_quick_v1', 'id': sid, 'status': 'quick', 'db_promotion': 'forbidden',
           'decision': 'user 2026-10-19: fill fast first (24-board loop; cycling -> mean of the last 4 steps; no P144), refine later',
           'tree': spec.get('tree_label'), 'stack_assumption': 'symmetric stacks (all seats at the bucket stack); lookup by effective stack',
           'method': method, 'steps': steps, 'loop_converged': converged, 'final_step': last,
           'stop_reason': st.get('stop_reason'),
           'stopped_at_step_cap': bool(capped),
           'status_note': ('stopped at the step cap (' + str(last + 1) + ' steps), not converged; mean of the last ' + str(len(steps)) + ' steps (user decision 2026-10-20)') if capped else None,
           'notes': ['frequencies at off_path nodes are not meaningful (opponent arrives with < 1 combo)',
                     'deep nodes (after the 4-bet) are research; connection uses the 3-bet response only',
                     'unstable_across_steps: class moved > 10 pp between the averaged steps (near-indifferent or cycling)',
                     'never GTO-verified; refinement target (P144 etc.) where T2 bots differ most'],
           'solve_s': round(time.time() - t0, 1), 'nodes': nodes}
    out = os.path.join(ROOT, 'data/gto_spot/quick')
    os.makedirs(out, exist_ok=True)
    json.dump(rec, open(os.path.join(out, sid + '.json'), 'w'), indent=1)
    r = nodes[0]
    print(sid, method, steps, 'root', r['actor'], r['mix'], 'unstable', r['unstable_combos'], 'loss', r['ev_loss_of_mean_vs_each_step_bb'])


if __name__ == '__main__':
    main()
