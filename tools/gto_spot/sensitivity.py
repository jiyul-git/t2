#!/usr/bin/env python3
"""Arriving-range sensitivity of a solved spot (docs/GTO_PLAN_A_60BB_V1.md section 5). Report only, no pass / fail.

At the accepted state (final step, or the P144 state when PRECISION=144) the continuation is held fixed (tables, range-reactive
matrices) and the spot is re-solved with perturbed arriving ranges:
  S1 / S2  last raiser's classes below / above the reach-weighted median equity vs the other seat's arriving range, weight x 0.8, x 1.2
  S3       the other seat's classes whose parent probability of reaching the root is in (0.05, 0.95) of the class, weight x 0.8, x 1.2
Per node and class: max over actions |delta freq|; per node: reach-weighted mean |delta|, share of reaching combos whose best action
changes, mix change. Classes moving > 10 pp under any perturbation are listed as `range_sensitive`.

    python3 tools/gto_spot/sensitivity.py <spot.json>  -> data/gto_spot/plan_a/sensitivity/<id>[_p144].json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hu_spot as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FACTORS = (0.8, 1.2)
FLAG_PP = 0.10
REACH_FLOOR = 1e-3


def load_state(spec, precision):
    wd = f"/home/user/gto_ckpt/spots/{spec['id']}/"
    k = json.load(open(wd + 'state.json'))['final_step']
    kd = wd + (f'step{k}_p144/' if precision else f'step{k}/')
    tabs = json.load(open(kd + 'tables_used.json'))
    mf = kd + 'matrices_used.json'
    mats = json.load(open(mf)) if os.path.exists(mf) else {}
    return tabs, mats


def solve(spec, tabs, mats, reweight=None):
    sp = H.Spot(spec)
    for line, tab in tabs.items():
        sp.tables[line] = tab
    for line, m in mats.items():
        sp.matrices[line] = {int(seat): np.array([[np.nan if x is None else x for x in row] for row in mm]) for seat, mm in m.items()}
    sp.root()
    if reweight is not None:
        seat, w = reweight
        sp.reach0[seat] = sp.reach0[seat] * w
    sp.build()
    sp.solve(spec.get('iterations', 3000))
    return sp


def last_raiser(sp):
    return sp.live[0] if sp.first == sp.live[1] else sp.live[1]   # the root actor faces the other live seat's raise


def perturbations(sp):
    tb = last_raiser(sp)
    op = sp.first
    prior = np.array([H.combos(l) / 1326 for l in sp.lab169])
    dist_op = sp.reach0[op] / sp.reach0[op].sum()
    eq = sp.EQ @ dist_op
    w = sp.reach0[tb]
    order = np.argsort(eq)
    cum = np.cumsum(w[order]) / w.sum()
    med = eq[order][np.searchsorted(cum, 0.5)]
    low = (eq < med) & (w > 0)
    high = (eq >= med) & (w > 0)
    frac = np.where(prior > 0, sp.reach0[op] / prior, 0.0)
    marg = (frac > 0.05) & (frac < 0.95)
    out = []
    for f in FACTORS:
        out.append((f'S1_{sp.pos[tb]}_below_median_x{f}', tb, np.where(low, f, 1.0)))
        out.append((f'S2_{sp.pos[tb]}_above_median_x{f}', tb, np.where(high, f, 1.0)))
        out.append((f'S3_{sp.pos[op]}_marginal_x{f}', op, np.where(marg, f, 1.0)))
    return out, {'last_raiser': sp.pos[tb], 'other': sp.pos[op], 'median_equity': float(med),
                 'n_below': int(low.sum()), 'n_above': int(high.sum()), 'n_marginal': int(marg.sum())}


def node_reach(sp):
    out = {}

    def rec(i, reach):
        out[i] = reach
        node = sp.nodes[i]
        for a, ch in enumerate(node['children']):
            if ch[0] == 'node':
                r2 = {k: v.copy() for k, v in reach.items()}
                r2[node['actor']] = reach[node['actor']] * sp.avg[i][a]
                rec(ch[1], r2)
    rec(sp.root_idx, {k: v.copy() for k, v in sp.reach0.items()})
    return out


def compare(base, pert):
    rb = node_reach(base)
    evb, evp = base.node_evs(), pert.node_evs()
    idx_p = {tuple(n['path']): i for i, n in enumerate(pert.nodes)}
    nodes, moved = [], {}
    for i, n in enumerate(base.nodes):
        j = idx_p[tuple(n['path'])]
        actor = n['actor']
        acts = [x[2] for x in n['acts']]
        w = rb[i][actor] * 1326
        d = np.abs(pert.avg[j] - base.avg[i]).max(0)
        reached = w >= REACH_FLOOR
        flip = evb[i].argmax(0) != evp[j].argmax(0)
        tot = w[reached].sum()
        nodes.append({'path': list(n['path']), 'actor': base.pos[actor], 'reach_combos': float(w.sum()),
                      'mean_abs_delta': float((w[reached] * d[reached]).sum() / tot) if tot > 0 else None,
                      'max_abs_delta': float(d[reached].max()) if reached.any() else None,
                      'best_action_flip_share': float(w[reached & flip].sum() / tot) if tot > 0 else None,
                      'mix_delta': {acts[a]: float(((w * pert.avg[j][a]).sum() - (w * base.avg[i][a]).sum()) / w.sum())
                                    for a in range(len(acts))} if w.sum() > 0 else None})
        for h in np.where(reached & (d > FLAG_PP))[0]:
            moved.setdefault(f"{base.pos[actor]}@{list(n['path'])}", []).append(base.lab169[h])
    return nodes, moved


def main():
    spec = json.load(open(sys.argv[1]))
    precision = os.environ.get('PRECISION') == '144'
    tabs, mats = load_state(spec, precision)
    base = solve(spec, tabs, mats)
    perts, info = perturbations(base)
    res = {'schema': 'spot_sensitivity_v1', 'id': spec['id'], 'state': 'P144' if precision else 'final step', 'definition': info,
           'continuation': 'held fixed (tables / range-reactive matrices of the accepted state)', 'flag_pp': FLAG_PP,
           'perturbations': {}, 'range_sensitive': {}}
    for name, seat, w in perts:
        sp = solve(spec, tabs, mats, (seat, w))
        nodes, moved = compare(base, sp)
        res['perturbations'][name] = {'nodes': nodes, 'moved_over_flag': moved}
        for k, v in moved.items():
            res['range_sensitive'].setdefault(k, set()).update(v)
        print(name, json.dumps([(n['actor'], n['path'][-2:], round(n['mean_abs_delta'] or 0, 4), round(n['best_action_flip_share'] or 0, 4))
                                for n in nodes]), flush=True)
    res['range_sensitive'] = {k: sorted(v) for k, v in res['range_sensitive'].items()}
    out = os.path.join(ROOT, 'data/gto_spot/plan_a/sensitivity')
    os.makedirs(out, exist_ok=True)
    json.dump(res, open(os.path.join(out, spec['id'] + ('_p144' if precision else '') + '.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
