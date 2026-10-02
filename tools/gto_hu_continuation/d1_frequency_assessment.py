#!/usr/bin/env python3
"""D1 (docs/GTO_EXPANSION_DESIGN_V1.md): class-level frequency assessment of the 5 sealed A4c nodes from the stored point (Gext)
and the 60 stored ext bootstrap replicates. No solve. Output: data/gto_terminal_expansion/a4c/d1_frequency_assessment.json
(research evidence; A4c stays sealed and is not exported).

Per class: point freq / EV for every action (no merging), EV gap best - second, u_panel = SD over replicates of the same action
pair's EV gap (each replicate's own game), u_solver = the class's own regret in the point solve, u_outer not measured (E1 will
provide it), freq q05/q50/q95 over replicates, modal-action consistency, L1 dispersion vs the point, status with Z = 2, A = 0.95.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gto_db_v2'))
import hand_records as HR  # noqa: E402
from a4c_influence import NODES, node_data  # noqa: E402

E = 'data/gto_terminal_expansion/a4c/'


def main():
    labels = json.load(open('data/gto_terminal_expansion/terminals/p9_node6.json'))['class_labels']
    seal = json.load(open(E + 'SEALED.json'))
    R = json.load(open(E + 'boot.json'))['reps']
    reps = sorted(R, key=int)
    assert reps == [str(i) for i in range(1, 61)] and json.load(open(E + 'boot_verify.json'))['ok']
    point = node_data(E + 'points/Gext')
    rep_nodes = [node_data(E + f'boot/r{int(k):02d}/ext') for k in reps]
    actions = {}
    for n in (6, 28):
        t = json.load(open(E + f'points/Gext/terminal_node{n}.json'))
        for p in t['path_nodes']:
            actions[f"{p['actor']}@{p['node']}"] = p['actions']
    out = {'schema': 'a4c_d1_frequency_assessment', 'source': 'A4c Gext point + 60 ext bootstrap replicates (boot_verify PASS)',
           'parameters': {'Z': HR.Z, 'A': HR.A, 'modal_threshold_of_60': 57}, 'u_outer': 'not measured (E1)',
           'sealed_node_flags': seal['frequency_status'], 'nodes': {}}
    for nd, (_, tag) in NODES.items():
        acts = actions[tag]
        g = point[nd]
        na = len(acts)
        hands = {}
        for h in range(169):
            fp = [g['s'][k][h] for k in range(na)]
            ep = [g['ev'][k][h] for k in range(na)]
            fr = [[rn[nd]['s'][k][h] for k in range(na)] for rn in rep_nodes]
            er = [[rn[nd]['ev'][k][h] for k in range(na)] for rn in rep_nodes]
            rec = HR.record(acts, fp, ep, fr, er)
            rec['reach_prior'] = g['r'][h]
            hands[labels[h]] = rec
        strat = {'format': 'hand_records_v1', 'actions': acts, 'hands': hands}
        HR.validate(strat)
        tw = sum(r['reach_prior'] for r in hands.values())
        summ = {s: {'classes': sum(1 for r in hands.values() if r['status'] == s),
                    'reach_share': sum(r['reach_prior'] for r in hands.values() if r['status'] == s) / tw} for s in HR.STATUSES}
        mixed = [r for r in hands.values() if max(r['freq'].values()) < 0.99]
        out['nodes'][nd] = {'actions': acts, 'summary': summ,
                            'mixed_classes_point': len(mixed),
                            'mixed_classes_status': {s: sum(1 for r in mixed if r['status'] == s) for s in HR.STATUSES},
                            'mean_l1_dispersion_reach_weighted': sum(r['reach_prior'] * r['l1_dispersion']['mean'] for r in hands.values()) / tw,
                            'strategy': strat}
    json.dump(out, open(E + 'd1_frequency_assessment.json.tmp', 'w'))
    os.replace(E + 'd1_frequency_assessment.json.tmp', E + 'd1_frequency_assessment.json')
    for nd, v in out['nodes'].items():
        print(nd, {s: (x['classes'], round(x['reach_share'], 3)) for s, x in v['summary'].items()}, 'mixed', v['mixed_classes_point'], v['mixed_classes_status'],
              'L1disp', round(v['mean_l1_dispersion_reach_weighted'], 3))


if __name__ == '__main__':
    main()
