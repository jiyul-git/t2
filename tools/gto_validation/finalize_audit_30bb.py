#!/usr/bin/env python3
"""Assemble data/gto_validation/30bb_solver_reference_audit_v1.{json,md} from
  - 30bb_solver_reference_audit_v1.raw.json (audit_30bb_solver_reference.py: comparability, aggregates, families, hand rows, BB defence)
  - the 9-max reproduction runs (pilot config, 20 and 100 iterations; action EVs from path_nodes)
  - the 4-handed same-engine small A/B (realization raw, max_raises 2, no jam option)
Read-only with respect to solver code and DB values."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = os.path.join(ROOT, 'data/gto_validation/')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_30bb_solver_reference import family, combos, FOCUS_HANDS  # noqa: E402

LAB = json.load(open(os.path.join(ROOT, 'data/gto_terminal_expansion/terminals/p9_node6.json')))['class_labels']


def nodes(f):
    t = json.load(open(f))
    return t, {p['actor']: p for p in t['path_nodes']}


def ev_rows(pn, pos, hands):
    p = pn[pos]
    out = {}
    for h in hands:
        i = LAB.index(h)
        out[h] = {'actions': p['actions'], 'freq': [round(p['class_strategy'][k][i], 4) for k in range(len(p['actions']))],
                  'ev_bb': [round(p['ev_bb'][k][i], 4) for k in range(len(p['actions']))]}
    return out


def consistency(pn, pos):
    """share of combos whose most-frequent action is not the highest-EV action, and the combo-weighted regret (bb)."""
    p = pn[pos]
    na = len(p['actions'])
    mis = reg = tot = 0.0
    big = []
    for i, h in enumerate(LAB):
        c = combos(h)
        f = [p['class_strategy'][k][i] for k in range(na)]
        e = [p['ev_bb'][k][i] for k in range(na)]
        best = max(range(na), key=lambda k: e[k])
        modal = max(range(na), key=lambda k: f[k])
        r = max(e) - sum(f[k] * e[k] for k in range(na))
        tot += c
        reg += c * r
        if modal != best:
            mis += c
            big.append((h, round(r, 3), p['actions'][modal], p['actions'][best], round(e[best] - e[modal], 3)))
    big.sort(key=lambda x: -x[1])
    return {'modal_not_best_ev_combo_share': mis / tot, 'mean_class_regret_bb': reg / tot, 'top': big[:8]}


def rfi_of(pn, pos):
    p = pn[pos]
    a = p['actions']
    return sum(combos(h) * sum(p['class_strategy'][k][i] for k in range(len(a)) if a[k] != 'Fold') for i, h in enumerate(LAB)) / 1326


def main():
    raw = json.load(open(V + '30bb_solver_reference_audit_v1.raw.json'))
    S = '/tmp/claude-0/-home-user-t2/0f5a154b-8ae8-5a6f-a261-583af56cff70/scratchpad/'
    res = {k: v for k, v in raw.items() if k != 'ab_small'}
    # 9-max reproduction (20 and 100 iterations, identical config)
    rep = {}
    for it, f in ((20, S + 'audit9/t_btn20.json'), (100, S + 'audit9/t_btn100.json')):
        if not os.path.exists(f):
            continue
        t, pn = nodes(f)
        rep[it] = {'gap_total': t['gap_total'], 'rfi': {p: rfi_of(pn, p) for p in ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN')},
                   'bb_vs_btn': pn['BB']['mix'], 'consistency': {p: consistency(pn, p) for p in ('UTG', 'HJ', 'CO', 'BTN', 'BB')},
                   'ev_focus': {p: ev_rows(pn, p, FOCUS_HANDS + ['72o', 'T7s', 'Q9o']) for p in ('UTG', 'HJ', 'CO', 'BTN', 'BB')}}
    res['reproduction_9max'] = {'config': 'data/gto_9max_solver_pilot_30bb.json config, t2_cont_terminal path BTN open / BB call, seeds 202', 'runs': rep}
    # attach action EVs (20-iteration reproduction) to the hand rows
    if 20 in rep:
        for pos, blk in res['hand_level'].items():
            t, pn = nodes(S + 'audit9/t_btn20.json')
            for r in blk['rows']:
                r['action_ev_reproduction20'] = ev_rows(pn, pos, [r['hand']])[r['hand']]
    # 4-handed A/B
    ab = {}
    for v in ('base_static_mr4', 'raw_realization', 'max_raises_2', 'no_jam_option', 'mr2_no_jam'):
        f28, f6 = S + f'ab4/{v}_n28.json', S + f'ab4/{v}_n6.json'
        if not (os.path.exists(f28) and os.path.exists(f6)):
            continue
        _, p28 = nodes(f28)
        _, p6 = nodes(f6)
        ab[v] = {'CO_rfi': rfi_of(p28, 'CO'), 'BTN_rfi': rfi_of(p28, 'BTN'), 'CO_jam': p28['CO']['mix'].get('All-in 30', 0.0), 'BTN_jam': p28['BTN']['mix'].get('All-in 30', 0.0),
                 'SB_rfi': rfi_of(p6, 'SB'), 'BB_vs_BTN_fold': p28['BB']['mix'].get('Fold'), 'BB_vs_SB_fold': p6['BB']['mix'].get('Fold'),
                 'BB_vs_BTN': p28['BB']['mix']}
    ab['A4c_solved_continuation_nodes_6_28'] = {
        'CO_rfi': 1 - raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['CO@0']['Fold'],
        'BTN_rfi': 1 - raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['BTN@1']['Fold'],
        'BB_vs_BTN_fold': raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['BB@26']['Fold'],
        'BB_vs_SB_fold': raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['BB@4']['Fold']}
    res['ab_small_4handed'] = {'engine': 'same GTOpen preflop engine, 4-handed CO/BTN/SB/BB 30bb (cfg_4h_mr4_30bb), 400 iterations, one factor changed per arm', 'arms': ab}
    json.dump(res, open(V + '30bb_solver_reference_audit_v1.json', 'w'), indent=1)
    print(json.dumps({'reproduction': {it: {'gap': r['gap_total'], 'rfi': {k: round(x, 3) for k, x in r['rfi'].items()}, 'bb_vs_btn': {k: round(x, 3) for k, x in r['bb_vs_btn'].items()},
                                             'consistency': {p: (round(c['modal_not_best_ev_combo_share'], 3), round(c['mean_class_regret_bb'], 4)) for p, c in r['consistency'].items()}} for it, r in rep.items()},
                      'ab': {k: {x: (round(y, 3) if isinstance(y, float) else y) for x, y in v.items() if x != 'BB_vs_BTN'} for k, v in ab.items()}}, indent=1))


if __name__ == '__main__':
    main()
