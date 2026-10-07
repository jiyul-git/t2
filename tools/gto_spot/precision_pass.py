#!/usr/bin/env python3
"""Precision pass P144 for a spot that converged under the spot loop (standard amendment 3).

At the accepted step k, the step-k terminal ranges are re-solved on the nested panel_v3_144 (the 24 panel_v1 boards are reused, the
120 extension boards are solved at target 0.6% pot); tables (A4c estimator) and 3-bet-pot matrices (ratio estimator) are re-estimated
on 144 boards; the spot is re-solved with them. Output step<k>_p144/: tables_used.json, matrices_used.json, spot.json, report.json
(D144 = weighted |value_144 - value_24| at the step-k ranges per terminal-seat, U24, U144).
    python3 tools/gto_spot/precision_pass.py <spot.json>
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spot_loop as L  # noqa: E402
import hu_spot as H  # noqa: E402

ROOT = L.ROOT
P144 = os.path.join(ROOT, 'data/gto_hu_continuation/panel_v3_144.json')


def main():
    spec = json.load(open(sys.argv[1]))
    lp = L.Loop(spec)
    st = lp.load_state()
    assert st.get('converged'), 'precision pass only after a converged spot loop'
    k = st['final_step']
    sd = lp.dir + f'step{k}/'
    od = lp.dir + f'step{k}_p144/'
    os.makedirs(od, exist_ok=True)
    tabs24 = json.load(open(sd + 'tables_used.json'))
    mats24 = json.load(open(sd + 'matrices_used.json')) if os.path.exists(sd + 'matrices_used.json') else {}
    sp24 = lp.spot(tabs24, mats24)
    terms = lp.terminals(sp24)
    new_t, new_m = dict(tabs24), dict(mats24)
    rep = {'k': k, 'panel': 'panel_v3_144', 'terminals': {}}
    for j, (line, t) in enumerate(sorted(terms.items())):
        tf = sd + f'term{j}.json'
        tj = json.load(open(tf))
        assert tj['line'] == line
        fd = sd + f'term{j}_flops'
        is_m = lp.v3 and lp.is_matrix_line(line)
        if not os.path.exists(fd + '/done144'):
            env = dict(os.environ)
            if is_m:
                env.update({'T2_PANEL_MATRIX': '1', 'T2_BIN_DIR': '/home/user/gto_ckpt/target_multi/release/examples'})
            subprocess.run([sys.executable, os.path.join(ROOT, 'tools/gto_hu_continuation/solve_panel.py'), tf, L.MENU, P144, fd,
                            '--exclude-origin', 'panel_v1', '--postflop', '1000', '0.6', '25', '--workers', '4', '--threads', '1'],
                           check=True, stdout=open(od + 'solve.log', 'a'), stderr=subprocess.STDOUT, env=env)
            open(fd + '/done144', 'w').write('ok')
        L.PANEL = P144
        bv = L.board_values(fd)
        raw, se = L.stratified(bv)
        M = lp.matrix_from(fd, sp24) if is_m else None
        L.PANEL = os.path.join(ROOT, 'data/gto_hu_continuation/panel_v1.json')
        prior = np.array([H.combos(l) for l in sp24.lab169])
        seats = {}
        tab = json.loads(json.dumps(tabs24[line]))
        tab['se'] = {pos: se[pos] for pos in se}
        tab['provenance'] = {'kind': f'spot {spec["id"]} step {k} precision P144', 'raw_from': fd}
        for pl in tj['players']:
            pos = pl['position']
            w = prior * np.array(pl['class_keep_fraction'])
            W = w.sum()
            q = [x for x in sp24.live if sp24.pos[x] != pos][0]
            dist = t['reach'][q] / t['reach'][q].sum()
            ch = ('flop', line, t['state'], t['pot'])
            v24 = sp24.gross_at(line, ch, pl['seat'], dist)
            if is_m:
                use = dist > 0
                v144 = M[pos][:, use] @ dist[use]
            else:
                v144 = np.array(raw[pos])
            u24 = np.array(tabs24[line].get('se', {}).get(pos, [np.nan] * 169))
            seats[pos] = {'D144': float((w * np.abs(v144 - v24)).sum() / W), 'signed': float((w * (v144 - v24)).sum() / W),
                          'U24': float((w * u24).sum() / W), 'U144': float((w * np.array(se[pos])).sum() / W)}
            for s_ in tab['seats']:
                if s_['position'] == pos:
                    s_['gross'] = raw[pos]
        new_t[line] = tab
        if is_m:
            new_m[line] = {str(pl['seat']): [[None if np.isnan(x) else float(x) for x in row] for row in M[pl['position']]] for pl in tj['players']}
        rep['terminals'][line] = {'mode': 'matrix' if is_m else 'table', 'seats': seats}
    rep['consistent_with_24'] = all(s['D144'] <= s['U24'] for t in rep['terminals'].values() for s in t['seats'].values())
    sp = lp.spot(new_t, new_m)
    L.atomic(new_t, od + 'tables_used.json')
    L.atomic(new_m, od + 'matrices_used.json')
    L.atomic({'exploitability': sp.exploitability(), 'nodes': sp.report(), 'class_labels': sp.lab169,
              'live': [sp.pos[p] for p in sp.live]}, od + 'spot.json')
    L.atomic(rep, od + 'report.json')
    print(json.dumps({l[-40:]: {p: {k2: round(v, 3) for k2, v in s.items()} for p, s in t['seats'].items()} for l, t in rep['terminals'].items()}, indent=1))
    print('consistent_with_24', rep['consistent_with_24'])


if __name__ == '__main__':
    main()
