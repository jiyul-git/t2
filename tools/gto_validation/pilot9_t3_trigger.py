#!/usr/bin/env python3
"""Step 3a joint-OL trigger (docs/GTO_HU_FULL_OUTER_9MAX_DESIGN_V1.md, amendment fixed before any T result).
M = RFI open (8 positions) + opener jam share of opens (8) + for each of the 25 selected 3-bet paths the aggregate
fold / call / raise / jam at the 3-bettor's node and at the opener's node facing the 3-bet (200).
R = max |M(s2) - M(s1)|, D = max |M(T) - M(s2)|; D > R -> 33-table joint OL, else T accepted without it.
    python3 tools/gto_validation/pilot9_t3_trigger.py            (R only if T is missing)
"""
import json
import os

R_ = '/home/user/gto_ckpt/'
OUT = '/home/user/t2/data/gto_validation/pilot9/step3/'
SEL = json.load(open(OUT + 't3_selection.json'))['terminals']
POS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB')
SRP = {'btn': 'fold,fold,fold,fold,fold,fold,raise,fold,call', 'sb': 'fold,fold,fold,fold,fold,fold,fold,raise,call'}
SRC = {'s1': (R_ + 'ol/s1/export_{}.json', R_ + 'step3/s1_3bet/term_{}.json'),
       's2': (R_ + 'ol/s2/export_{}.json', R_ + 'step3/t3/terminals/term_{}.json'),
       'T': (R_ + 'step3/t3/T/export_{}.json', R_ + 'step3/t3/T/export_{}.json')}
KEYS = ('fold', 'call', 'raise', 'jam')


def mixd(p):
    out = dict.fromkeys(KEYS, 0.0)
    for k, v in p['mix'].items():
        out['fold' if k == 'Fold' else 'jam' if k.startswith('All-in') else 'call' if k.startswith('Call') else 'raise'] += v
    return out


def path_node(t, spec, idx):
    pn = t['path_nodes']
    assert len(pn) == len(spec), (t['terminal_node'], len(pn), len(spec))
    return pn[idx]


def metrics(state):
    fs, ft = SRC[state]
    files = [fs.format('btn'), fs.format('sb')] + [ft.format(s['name']) for s in SEL]
    if not all(os.path.exists(f) for f in files):
        return None
    m = {}
    for name, f in (('btn', fs.format('btn')), ('sb', fs.format('sb'))):
        t = json.load(open(f))
        spec = SRP[name].split(',')
        # first-in nodes: UTG..BTN are path indices 0..6 of the BTN path; SB first-in is index 7 of the SB path
        for i in (range(7) if name == 'btn' else [7]):
            p = path_node(t, spec, i)
            assert p['actor'] == POS[i], (name, i, p['actor'])
            x = mixd(p)
            m[f"rfi/{p['actor']}"] = 1 - x['fold']
            m[f"jamshare/{p['actor']}"] = x['jam'] / max(1e-12, 1 - x['fold'])
    for s in SEL:
        t = json.load(open(ft.format(s['name'])))
        assert t['terminal_node'] == s['node'], s['name']
        spec = s['spec'].split(',')
        raises = [i for i, a in enumerate(spec) if a == 'raise']
        i3, io = raises[1], len(spec) - 1
        p3, po = path_node(t, spec, i3), path_node(t, spec, io)
        assert po['actor'] == path_node(t, spec, raises[0])['actor'], s['name']
        for who, p in (('3bettor', p3), ('opener_vs_3bet', po)):
            for k, v in mixd(p).items():
                m[f"{s['name']}/{who}:{p['actor']}/{k}"] = v
    assert sum(k.startswith('rfi/') for k in m) == 8 and sum(k.startswith('jamshare/') for k in m) == 8, sorted(m)[:20]
    assert len(m) == 216, len(m)
    return m


def main():
    M1, M2, MT = metrics('s1'), metrics('s2'), metrics('T')
    assert M1 and M2, 'state-1 / state-2 exports missing'
    d12 = {k: abs(M2[k] - M1[k]) for k in M2}
    kR = max(d12, key=d12.get)
    res = {'schema': 'pilot9_t3_trigger_v1', 'rule': 'D > R -> 33-table joint OL; D <= R -> T accepted, no joint OL',
           'R': d12[kR], 'R_argmax': kR, 'n_elements': len(M2), 'abs_s2_minus_s1': d12}
    if MT:
        dT = {k: abs(MT[k] - M2[k]) for k in M2}
        kD = max(dT, key=dT.get)
        res.update({'D': dT[kD], 'D_argmax': kD, 'abs_T_minus_s2': dT,
                    'decision': 'run 33-table joint OL' if dT[kD] > d12[kR] else 'accept T; no joint OL'})
        groups = {}
        for k in M2:
            g = k.split('/')[0] if not k.startswith(('rfi/', 'jamshare/')) else k.split('/')[1]
            a = groups.setdefault(g, {'max_D': 0.0, 'max_R': 0.0})
            a['max_D'] = max(a['max_D'], dT[k])
            a['max_R'] = max(a['max_R'], d12[k])
        for a in groups.values():
            a['D_over_R'] = a['max_D'] / a['max_R'] if a['max_R'] > 0 else None
        res['by_position_or_path'] = groups
        res['M'] = {'s1': M1, 's2': M2, 'T': MT}
    else:
        res['decision'] = 'pending: T exports missing'
        res['M'] = {'s1': M1, 's2': M2}
    json.dump(res, open(OUT + 't3_trigger.json', 'w'), indent=1)
    print(json.dumps({k: res[k] for k in res if k in ('R', 'R_argmax', 'D', 'D_argmax', 'decision', 'n_elements')}, indent=1))


if __name__ == '__main__':
    main()
