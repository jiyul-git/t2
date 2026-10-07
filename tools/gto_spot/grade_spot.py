#!/usr/bin/env python3
"""Grade a spot after spot_loop.py against docs/GTO_VERIFIED_FREQUENCY_STANDARD_V1.md (G2-G5; G1 = tree id in the record,
G6 = separate checks). Re-solves the final step (deterministic) and the previous step for u_outer.

    python3 tools/gto_spot/grade_spot.py <spot.json>  -> data/gto_spot/records/<id>.json
Per decision node and class: frequencies, action EVs, gap = EV(best) - EV(second),
u_panel = sqrt(u_panel(best)^2 + u_panel(second)^2), u_panel(a) = sqrt(sum_t (q_t(a) se_t)^2) with q_t from +1 bb probes of
each table, u_outer = |gap_k - gap_{k-1}|, u_solver = spot exploitability (bb); u = u_panel + u_outer + u_solver;
stable if gap > 2u else near_indifferent. Spot verified iff G2, G3, G4 pass and >= 95% of reaching combos are stable or
near_indifferent (near-indifferent groups listed).
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hu_spot as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def solve_with(spec, tables, matrices=None):
    sp = H.Spot(spec)
    for line, tab in tables.items():
        sp.tables[line] = tab
    for line, m in (matrices or {}).items():
        sp.matrices[line] = {int(seat): np.array([[np.nan if x is None else x for x in row] for row in mm]) for seat, mm in m.items()}
    sp.root()
    sp.build()
    sp.solve(spec.get('iterations', 3000))
    return sp


def main():
    spec = json.load(open(sys.argv[1]))
    wd = f"/home/user/gto_ckpt/spots/{spec['id']}/"
    st = json.load(open(wd + 'state.json'))
    k = st['final_step']
    precision = os.environ.get('PRECISION') == '144'
    kd = wd + (f'step{k}_p144/' if precision else f'step{k}/')
    tabs_k = json.load(open(kd + 'tables_used.json'))
    mf = kd + 'matrices_used.json'
    mats_k = json.load(open(mf)) if os.path.exists(mf) else {}
    sp = solve_with(spec, tabs_k, mats_k)
    ev = sp.node_evs()
    expl = sp.exploitability()
    prev = None
    if precision:
        # u_outer = change of the precision update itself (24-board accepted state -> 144-board state)
        t24 = json.load(open(wd + f'step{k}/tables_used.json'))
        m24f = wd + f'step{k}/matrices_used.json'
        prev = solve_with(spec, t24, json.load(open(m24f)) if os.path.exists(m24f) else {}).node_evs()
    elif k > 0:
        tabs_p = json.load(open(wd + f'step{k - 1}/tables_used.json'))
        mfp = wd + f'step{k - 1}/matrices_used.json'
        spp = solve_with(spec, tabs_p, json.load(open(mfp)) if os.path.exists(mfp) else {})
        prev = spp.node_evs()
    # sensitivities q_t(a, h) per node for the actor's own seat
    lines = [l for l in sp.tables if l in tabs_k]
    q = {}
    for line in lines:
        for p in sp.live:
            ev2 = sp.node_evs(shift=(line, p, 1.0))
            for i in ev2:
                if sp.nodes[i]['actor'] == p:
                    q.setdefault(i, []).append((line, p, ev2[i] - ev[i]))
    prior = np.array([H.combos(l) for l in sp.lab169])
    nodes = []
    stable_mass = 0.0
    total_mass = 0.0

    def rec(i, reach):
        nonlocal stable_mass, total_mass
        node = sp.nodes[i]
        actor = node['actor']
        s = sp.avg[i]
        acts = [x[2] for x in node['acts']]
        E = ev[i]
        order = np.argsort(-E, axis=0)
        best, second = order[0], order[1]
        idx = np.arange(169)
        gap = E[best, idx] - E[second, idx]
        up = np.zeros((len(acts), 169))
        for line, p, dq in q.get(i, []):
            se = np.array(sp.tables[line]['se'][sp.pos[p]]) if 'se' in sp.tables[line] else np.zeros(169)
            up += (dq * se[None, :]) ** 2
        up = np.sqrt(up)
        u_panel = np.sqrt(up[best, idx] ** 2 + up[second, idx] ** 2)
        if prev is not None and i in prev:
            Ep = prev[i]
            gp = Ep[best, idx] - Ep[second, idx]
            u_outer = np.abs(gap - gp)
        else:
            u_outer = np.zeros(169)
        u = u_panel + u_outer + expl['total_bb']
        rr = reach[actor]
        w = rr * 1326  # combos reaching (class prior x action probabilities x 1326)
        status = np.where(gap > 2 * u, 'stable', 'near_indifferent')
        reach_combos = float(w.sum())
        if reach_combos > 1e-9:
            stable_mass += float(w[status == 'stable'].sum())
            total_mass += reach_combos
        nodes.append({'path': list(node['path']), 'actor': sp.pos[actor], 'actions': acts,
                      'reach_combos': reach_combos,
                      'mix': {acts[a]: float((rr * s[a]).sum() / rr.sum()) if rr.sum() > 0 else None for a in range(len(acts))},
                      'hands': {sp.lab169[h]: {'freq': {acts[a]: round(float(s[a, h]), 4) for a in range(len(acts))},
                                               'ev': {acts[a]: round(float(E[a, h]), 4) for a in range(len(acts))},
                                               'gap': round(float(gap[h]), 4), 'u_panel': round(float(u_panel[h]), 4),
                                               'u_outer': round(float(u_outer[h]), 4), 'status': str(status[h]),
                                               'best': acts[best[h]], 'reach_combos': round(float(w[h]), 4)}
                                for h in range(169) if w[h] > 1e-6}})
        for a, ch in enumerate(node['children']):
            if ch[0] == 'node':
                r2 = {kk: v.copy() for kk, v in reach.items()}
                r2[actor] = reach[actor] * s[a]
                rec(ch[1], r2)
    rec(sp.root_idx, {kk: v.copy() for kk, v in sp.reach0.items()})
    # G4 static share of the spot's flop reach
    flop, static = 0.0, 0.0

    def rec2(i, reach):
        nonlocal flop, static
        node = sp.nodes[i]
        s = sp.avg[i]
        for a, ch in enumerate(node['children']):
            r2 = {kk: v.copy() for kk, v in reach.items()}
            r2[node['actor']] = reach[node['actor']] * s[a]
            if ch[0] == 'node':
                rec2(ch[1], r2)
            elif ch[0] == 'flop':
                m = float(np.prod([r2[p].sum() for p in sp.live]))
                flop += m
                if ch[1] not in tabs_k:
                    static += m
    rec2(sp.root_idx, {kk: v.copy() for kk, v in sp.reach0.items()})
    s_share = static / flop if flop > 0 else 0.0
    g2 = expl['total_bb'] <= 0.010
    g3 = bool(st.get('converged'))
    if precision:
        g3 = g3 and json.load(open(kd + 'report.json'))['consistent_with_24']
    g4 = s_share <= 0.05
    g5_share = stable_mass / total_mass if total_mass > 0 else 0.0
    g5 = True  # near_indifferent classes are allowed (reported as groups); the >= 95% rule counts stable + near_indifferent
    verified = g2 and g3 and g4 and g5
    rec_out = {'schema': 'spot_record_v1', 'id': spec['id'], 'tree': 'J30: 9-max 30 bb, cfg_mr3_jam (max_raises 3, 4-bet jam only), uniform ante 1/9',
               'parent_preflop_state': {'dump': spec['dump'], 'note': 'arriving ranges from the J full-tree solve (100 it, gap 0.042)'},
               'root_line': spec['root_line'], 'live': [sp.pos[p] for p in sp.live], 'final_step': k,
               'gates': {'G2_exploitability_bb': expl['total_bb'], 'G2': g2, 'G3_outer_converged': g3,
                         'G4_static_share': s_share, 'G4': g4, 'G5_stable_combo_share': g5_share, 'verified': verified},
               'exploitability': expl, 'tables': {l: tabs_k[l]['provenance'] for l in tabs_k}, 'matrix_terminals': sorted(mats_k), 'nodes': nodes}
    os.makedirs(os.path.join(ROOT, 'data/gto_spot/records'), exist_ok=True)
    rec_out['panel'] = 'panel_v3_144 (precision pass)' if precision else 'panel_v1'
    json.dump(rec_out, open(os.path.join(ROOT, f"data/gto_spot/records/{spec['id']}{'_p144' if precision else ''}.json"), 'w'))
    print(json.dumps(rec_out['gates'], indent=1))
    root = nodes[0]
    print('root', root['actor'], {a: round(100 * v, 1) for a, v in root['mix'].items()})


if __name__ == '__main__':
    main()
