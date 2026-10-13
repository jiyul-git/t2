#!/usr/bin/env python3
"""Grade a spot after spot_loop.py against docs/GTO_VERIFIED_FREQUENCY_STANDARD_V1.md (amendment 4: label semantics).
Re-solves the final step (deterministic) and the previous step for u_outer.

    python3 tools/gto_spot/grade_spot.py <spot.json>          -> data/gto_spot/records/<id>[_p144].json
    python3 tools/gto_spot/grade_spot.py --relabel <rec.json>  re-derive the labels of a stored record (no solve)
Per decision node and class: frequencies, action EVs, gap = EV(best) - EV(second),
u_panel = sqrt(u_panel(best)^2 + u_panel(second)^2), u_panel(a) = sqrt(sum_t (q_t(a) se_t)^2) with q_t from +1 bb probes of
each table, u_outer = |gap_k - gap_{k-1}|, u_solver = spot exploitability (bb); u = u_panel + u_outer + u_solver;
stable if gap > 2u else near_indifferent (listed in uncertainty groups, never a verified frequency); classes reaching a node
with < 1e-3 combos are `unreached` there (average strategy at ~zero reach is solver noise: no frequency reported, not graded).

Two layers (amendment 4):
- solution_status in research < provisional < conditional_verified < verified
  spot gates: spot_exploitability <= 0.010 bb (local HU subgame, NOT G2), G3, G4 <= 0.05, G6, precision pass (P144) graded;
  global gate G2 = parent full-tree gap_total <= 0.010 bb. Spot gates pass + G2 fail -> conditional_verified (conditional on the
  parent's arriving ranges); `verified` only with G2 as well.
- hand_frequency_status: blocked_by_solution / partial / complete (stable combo share >= 0.95); per class `stable` or
  `uncertainty_group`.
DB promotion stays forbidden whatever the label (`db_promotion: forbidden`).
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


# ---------------- labels (standard amendment 4) ----------------
STATUS_ORDER = ['research', 'provisional', 'conditional_verified', 'verified']
G2_MAX_BB = 0.010          # parent full-tree gap_total per hand (doc G2)
SPOT_EXPL_MAX_BB = 0.010   # local HU subgame exploitability (separate gate, not G2)
G4_MAX = 0.05
G4_PARTIAL_MAX = 0.25
HANDFREQ_COMPLETE = 0.95   # stable combo share for hand_frequency_status = complete
MATERIAL = 0.05            # G6b: a clearly dominated action played at >= 5% of a class is a violation
REACH_FLOOR = 1e-3          # combos; below it a class is `unreached` at the node: no frequency reported, not graded
T2_FIRST_GAP_MAX_BB = 0.05  # standard amendment 5: first T2 connection
CHIP_TOL_BB = 0.010        # G6b: |sum of the two seats' EVs - dead money| per hand
TREE_J30 = 'J30: 9-max, cfg_mr3_jam (max_raises 3, 4-bet jam only), cfg.stack 30 behind a uniform ante 1/9 (30bb-labelled, not exact 30bb)'
PARENT_STATES = {
    'J_dump.jsonl': {'parent': 'J full-tree solve (cfg_mr3_jam)', 'iterations': 100, 'gap_total_bb': 0.042,
                     'source': 'docs/GTO_MR3_JAM_9MAX_J_RESULT_V1.md'},
}
REPO_CFG = {'cfg_mr3_jam.json': 'data/gto_validation/pilot9/step3/cfg_mr3_jam.json'}


def load_cfg(path):
    if os.path.exists(path):
        return json.load(open(path))
    return json.load(open(os.path.join(ROOT, REPO_CFG[os.path.basename(path)])))


def stack_label(cfg):
    ante, stack = cfg['ante'], cfg['stack']
    start = stack + ante
    target = round(stack)  # the depth the run is named after
    exact = abs(start - target) < 1e-9
    return {'label': f'{target:g}bb exact' if exact else f'{target:g}bb-labelled (hand-start {start:.3f}bb)',
            'cfg_stack_bb': stack, 'ante_per_seat_bb': ante, 'hand_start_bb': round(start, 6), 'exact': exact,
            'exact_rerun_cfg_stack_bb': None if exact else round(target - ante, 12),
            'note': 'hand-start stack = cfg.stack + ante (the ante is posted on top of cfg.stack); key DB rows by hand_start_bb'}


def g6a_parent_reproduction(spec):
    """Plan A G6(a) (docs/GTO_PLAN_A_60BB_V1.md amendment A1): subgame with the parent's menu and static terminals vs the dump"""
    s2 = {k: v for k, v in spec.items() if k != 'menu'}
    s2['tables_dir'] = None
    sp = H.Spot(s2)
    sp.root()
    sp.build()
    sp.solve(3000)
    ev = sp.node_evs()
    nodes, ok = [], True

    def rec_(i, reach):
        nonlocal ok
        node = sp.nodes[i]
        actor = node['actor']
        dr = node.get('dump')
        if dr is None:
            return
        par = np.array(dr['sigma'])
        w = reach[actor] * 1326
        reached = w >= REACH_FLOOR
        d = np.abs(par - sp.avg[i]).max(0)
        loss = ev[i].max(0) - (par * ev[i]).sum(0)
        mean = float((w[reached] * d[reached]).sum() / w[reached].sum()) if reached.any() else 0.0
        big = [{'class': sp.lab169[h], 'delta': round(float(d[h]), 4), 'ev_loss_bb': round(float(loss[h]), 4)}
               for h in np.where(reached & (d > 0.10))[0]]
        node_ok = mean <= 0.02 and all(b['ev_loss_bb'] <= 0.05 for b in big)
        ok = ok and node_ok
        nodes.append({'path': list(node['path']), 'actor': sp.pos[actor], 'mean_abs_delta': round(mean, 5), 'over_0.10': big,
                      'pass': node_ok})
        for a, ch in enumerate(node['children']):
            if ch[0] == 'node':
                r2 = {k: v.copy() for k, v in reach.items()}
                r2[actor] = reach[actor] * sp.avg[i][a]
                rec_(ch[1], r2)
    rec_(sp.root_idx, {k: v.copy() for k, v in sp.reach0.items()})
    return {'status': 'pass' if ok else 'fail', 'definition': 'Plan A amendment A1: parent-menu reproduction',
            'subgame_exploitability_bb': sp.exploitability()['total_bb'], 'nodes': nodes}


def g6_checks(rec, cfg):
    """G6 on a stored record: (a) subgame vs full tree, (b) dominated material actions + chip conservation."""
    u_solver = rec['exploitability']['total_bb']
    viol, unreached = [], 0
    for n in rec['nodes']:
        for h, x in n['hands'].items():
            if x['reach_combos'] < REACH_FLOOR:
                ev, fr = x['ev'], x['freq']
                best = max(ev, key=ev.get)
                u = x['u_panel'] + x['u_outer'] + u_solver
                unreached += any(f >= MATERIAL and ev[best] - ev[a] > 2 * u for a, f in fr.items())
                continue
            ev, fr = x['ev'], x['freq']
            best = max(ev, key=ev.get)
            u = x['u_panel'] + x['u_outer'] + u_solver
            for a, f in fr.items():
                if f >= MATERIAL and ev[best] - ev[a] > 2 * u:
                    viol.append({'path': n['path'], 'actor': n['actor'], 'class': h, 'action': a, 'freq': f,
                                 'ev_loss_bb': round(ev[best] - ev[a], 4), 'u': round(u, 4)})
    premium_fold = [{'path': n['path'], 'class': h, 'fold': n['hands'][h]['freq'].get('Fold', 0.0)}
                    for n in rec['nodes'] for h in ('AA', 'KK') if h in n['hands'] and n['hands'][h]['reach_combos'] >= REACH_FLOOR
                    and n['hands'][h]['freq'].get('Fold', 0.0) > 0.01]
    live = rec['live']
    pos = cfg['positions']
    dead = sum(cfg['posts'][i] + cfg['ante'] for i, name in enumerate(pos) if name not in live)
    ev_sum = sum(rec['exploitability']['per_seat'][p]['ev'] for p in live)
    chip = {'ev_sum_bb': ev_sum, 'dead_money_bb': dead, 'abs_diff_bb': abs(ev_sum - dead), 'tol_bb': CHIP_TOL_BB,
            'pass': abs(ev_sum - dead) <= CHIP_TOL_BB,
            'scope': 'spot level (both seats net EV vs folded seats\' posts + antes); export-level conservation of t2_tree_values not run here'}
    a = rec.get('G6a_result') or {'status': 'not_run',
                                  'reason': 'needs the parent full-tree average strategy at this node with the same tables (J dump + a '
                                            'full-tree re-solve on the spot tables); not run'}
    b_pass = not viol and not premium_fold and chip['pass']
    return {'a_subgame_vs_full_tree': a,
            'b_invariants': {'dominated_material': viol[:50], 'n_dominated_material': len(viol),
                             'n_dominated_at_unreached_classes': unreached, 'reach_floor_combos': REACH_FLOOR,
                             'premium_fold': premium_fold,
                             'chip_conservation': chip, 'pass': b_pass},
            'c_near_reference': 'orientation only, never pass / fail',
            'pass': a['status'] == 'pass' and b_pass}


def uncertainty_groups(rec):
    out = []
    for n in rec['nodes']:
        groups = {}
        for h, x in n['hands'].items():
            if x['status'] != 'near_indifferent' or x['reach_combos'] < REACH_FLOOR:
                continue
            ev = x['ev']
            ranked = sorted(ev, key=ev.get, reverse=True)
            groups.setdefault(' ~ '.join(sorted(ranked[:2])), []).append(h)
        for key, members in sorted(groups.items()):
            out.append({'path': n['path'], 'actor': n['actor'], 'actions': key, 'classes': members,
                        'reach_combos': round(sum(n['hands'][h]['reach_combos'] for h in members), 3),
                        'note': 'raw mix kept in nodes[].hands; not a verified frequency'})
    return out


def label(rec, cfg):
    """Fill gates / status / hand_frequency of a record from its stored nodes and grade_inputs."""
    gi = rec['grade_inputs']
    expl = rec['exploitability']['total_bb']
    parent = rec['parent_preflop_state']
    pgap = parent.get('gap_total_bb')
    s_share = gi['static_share']
    spot_conv = gi['spot_converged'] and (gi['p144_consistent_with_24'] is not False)
    g4_state = 'pass' if s_share <= G4_MAX else ('partial' if s_share <= G4_PARTIAL_MAX else 'static_dependent')
    g6 = g6_checks(rec, cfg)
    stable_mass = sum(x['reach_combos'] for n in rec['nodes'] for x in n['hands'].values() if x['status'] == 'stable')
    total_mass = sum(x['reach_combos'] for n in rec['nodes'] for x in n['hands'].values())
    stable_share = stable_mass / total_mass if total_mass > 0 else 0.0
    gates = {
        'G1_tree': rec['tree'], 'G1': True,
        'spot_exploitability_bb': expl, 'spot_exploitability_max_bb': SPOT_EXPL_MAX_BB, 'spot_solver': expl <= SPOT_EXPL_MAX_BB,
        'G2_parent_gap_total_bb': pgap, 'G2_max_bb': G2_MAX_BB, 'G2': pgap is not None and pgap <= G2_MAX_BB,
        'G3_outer_converged': spot_conv, 'G3': spot_conv,
        'G4_static_share': s_share, 'G4': g4_state == 'pass', 'G4_state': g4_state,
        'G5_stable_combo_share': stable_share,
        'G6': g6['pass'],
        'precision_final': bool(gi['precision_final']),
    }
    blockers = []
    if gi.get('superseded'):
        blockers.append(f"superseded: {gi['superseded']}")
    if not gates['spot_solver']:
        blockers.append('spot_exploitability > 0.010 bb')
    if gi.get('stop_reason'):
        blockers.append(f"stop: {gi['stop_reason']}")
    if not spot_conv:
        blockers.append('G3: spot outer loop not converged' + (' (P144 D144 > U24)' if gi['p144_consistent_with_24'] is False else ''))
    if g4_state != 'pass':
        blockers.append(f'G4: static share {s_share:.3f} ({g4_state})')
    research = bool(blockers) and (gi.get('superseded') or not gates['spot_solver'] or not spot_conv or g4_state == 'static_dependent')
    prov = []
    if not gates['precision_final']:
        prov.append('precision pass (P144) not graded')
    if not g6['pass']:
        prov.append('G6: ' + ('(a) not run' if g6['a_subgame_vs_full_tree']['status'] != 'pass' else '') +
                    ('' if g6['b_invariants']['pass'] else ' (b) invariant violation'))
    glob = []
    if not gates['G2']:
        glob.append(f"G2: parent full-tree gap_total {pgap} bb > {G2_MAX_BB} bb -> global / full-game verified FAIL")
    if research:
        status = 'research'
    elif blockers or prov:
        status = 'provisional'
    elif glob:
        status = 'conditional_verified'
    else:
        status = 'verified'
    cap = gi.get('status_cap')
    if cap and STATUS_ORDER.index(status) > STATUS_ORDER.index(cap):
        status = cap
        glob.append(f"status capped at {cap}: {gi.get('status_cap_reason')}")
    if status in ('conditional_verified', 'verified'):
        hf = 'complete' if stable_share >= HANDFREQ_COMPLETE else 'partial'
    else:
        hf = 'blocked_by_solution'
    for n in rec['nodes']:
        for x in n['hands'].values():
            x['frequency_label'] = ('unreached' if x['reach_combos'] < REACH_FLOOR else
                                    'stable' if x['status'] == 'stable' else 'uncertainty_group')
    rec['schema'] = 'spot_record_v2'
    rec['stack'] = stack_label(cfg)
    rec['gates'] = gates
    rec['G6'] = g6
    rec['status'] = status
    rec['verified'] = status == 'verified'
    rec['status_reasons'] = {'research_or_spot': blockers, 'provisional': prov, 'global': glob}
    rec['interpretation'] = ('HU subgame equilibrium of the two live seats GIVEN the arriving ranges of the parent preflop state '
                             f"({parent.get('parent', parent.get('dump'))}); not a full 9-max verified solution unless status == verified")
    rec['hand_frequency'] = {'status': hf, 'stable_combo_share': stable_share, 'complete_min': HANDFREQ_COMPLETE,
                             'verified': rec['verified'] and hf == 'complete',
                             'rule': 'only `stable` classes carry point frequencies at the solution status; near-indifferent '
                                     'classes are uncertainty groups (raw mix kept, never called verified frequency)',
                             'uncertainty_groups': uncertainty_groups(rec)}
    sens = os.path.join(ROOT, 'data/gto_spot/plan_a/sensitivity', rec['id'] + ('_p144' if gi['precision_final'] else '') + '.json')
    rs = json.load(open(sens))['range_sensitive'] if os.path.exists(sens) else None
    if rs is not None:
        for n in rec['nodes']:
            flagged = set(rs.get(f"{n['actor']}@{n['path']}", []))
            for h, x in n['hands'].items():
                x['range_sensitive'] = h in flagged
    elig = (status == 'conditional_verified' and pgap is not None and pgap <= T2_FIRST_GAP_MAX_BB and rs is not None)
    un = rec.get('amendment8_unsupported_nodes') or []
    unp = {(tuple(u['path']), u['actor']) for u in un}
    for n in rec['nodes']:
        if (tuple(n['path']), n['actor']) in unp:
            n['t2_connection'] = 'unsupported (standard amendment 8: depends on a low-reach exempt terminal)'
    rec['t2_connection'] = {'status': 'eligible_first' if elig else 'not_eligible',
                            'unsupported_nodes': un,
                            'rule': 'standard v1 amendment 5: conditional_verified, parent exact gap <= 0.05 bb, sensitivity report',
                            'parent_gap_bb': pgap, 'sensitivity_report': os.path.relpath(sens, ROOT) if rs is not None else None}
    rec['db_promotion'] = 'forbidden'
    rec['label_standard'] = 'docs/GTO_VERIFIED_FREQUENCY_STANDARD_V1.md amendment 4'
    return rec


def relabel(path):
    rec = json.load(open(path))
    if 'grade_inputs' not in rec:  # spot_record_v1: derive inputs from the old gates
        g = rec['gates']
        rec['grade_inputs'] = {'config': '/home/user/gto_ckpt/step3/j/cfg_mr3_jam.json',
                               'rule': 'v1' if 'rule_v1' in os.path.basename(path) else ('v3' if rec['id'].endswith('_v3') else 'v2'),
                               'spot_converged': bool(g['G3_outer_converged']), 'precision_final': 'p144' in (rec.get('panel') or ''),
                               'p144_consistent_with_24': None, 'static_share': g['G4_static_share']}
        if 'rule_v1' in os.path.basename(path):
            rec['grade_inputs']['superseded'] = 'spot loop rule v1 (unconverged), replaced by *_v3'
        rec['grade_inputs']['relabelled_from'] = {'schema': rec.get('schema'), 'gates': g}
        rec.setdefault('panel', 'panel_v1')
    dump = rec['parent_preflop_state']['dump']
    if os.path.basename(dump) in PARENT_STATES:
        rec['tree'] = TREE_J30
        rec['parent_preflop_state'] = {'dump': dump, **PARENT_STATES[os.path.basename(dump)]}
    label(rec, load_cfg(rec['grade_inputs']['config']))
    json.dump(rec, open(path, 'w'))
    print(path, rec['status'], 'verified' if rec['verified'] else 'not verified', json.dumps(rec['status_reasons'], ensure_ascii=False))


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
    rec_out = {'schema': 'spot_record_v2', 'id': spec['id'], 'tree': spec.get('tree_label', TREE_J30),
               'parent_preflop_state': {'dump': spec['dump'], **(spec.get('parent') or PARENT_STATES.get(os.path.basename(spec['dump']), {}))},
               'root_line': spec['root_line'], 'live': [sp.pos[p] for p in sp.live], 'final_step': k,
               'grade_inputs': {'config': spec['config'], 'rule': spec.get('rule', 'v1'), 'spot_converged': bool(st.get('converged')),
                                'precision_final': precision,
                                'p144_consistent_with_24': json.load(open(kd + 'report.json'))['consistent_with_24'] if precision else None,
                                'static_share': s_share,
                                'status_cap': spec.get('status_cap'), 'status_cap_reason': spec.get('status_cap_reason'),
                                'converged_strict': st.get('converged_strict'), 'exempt_used': st.get('exempt_used'),
                                'stop_reason': st.get('stop_reason') or (json.load(open(kd + 'report.json')).get('flop_failures') and
                                                                         'P144 flop solver did not converge' if precision else None)},
               'exploitability': expl, 'tables': {l: tabs_k[l]['provenance'] for l in tabs_k}, 'matrix_terminals': sorted(mats_k), 'nodes': nodes}
    rec_out['panel'] = 'panel_v3_144 (precision pass)' if precision else 'panel_v1'
    # standard amendment 8 (accepted 2026-10-13 with conditions): exempt terminal-seats -> the actor's decision nodes that lead
    # into that terminal are unsupported for T2 connection (their value at that terminal is not trusted)
    rep_k = json.load(open(kd + 'report.json')) if os.path.exists(kd + 'report.json') else {}
    exempt = [(line, pos, sd_.get('opp_arriving_combos')) for line, t_ in rep_k.get('terminals', {}).items()
              for pos, sd_ in t_.get('seats', {}).items() if sd_.get('exempt')]
    unsup = []
    for line, pos, mass in exempt:
        for nd in sp.nodes:
            if sp.pos[nd['actor']] == pos and any(ch[0] == 'flop' and ch[1] == line for ch in nd['children']):
                unsup.append({'path': list(nd['path']), 'actor': pos, 'terminal': line, 'opp_arriving_combos': mass})
    rec_out['amendment8_unsupported_nodes'] = unsup
    if spec.get('menu'):
        rec_out['G6a_result'] = g6a_parent_reproduction(spec)
    label(rec_out, sp.cfg)
    os.makedirs(os.path.join(ROOT, 'data/gto_spot/records'), exist_ok=True)
    json.dump(rec_out, open(os.path.join(ROOT, f"data/gto_spot/records/{spec['id']}{'_p144' if precision else ''}.json"), 'w'))
    print(json.dumps({kk: rec_out[kk] for kk in ('status', 'verified', 'gates', 'hand_frequency')}, indent=1)[:4000])
    root = nodes[0]
    print('root', root['actor'], {a: round(100 * v, 1) for a, v in root['mix'].items()})


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--relabel':
        relabel(sys.argv[2])
    else:
        main()
