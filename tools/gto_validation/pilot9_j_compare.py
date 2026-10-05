#!/usr/bin/env python3
"""Plan J comparison (docs/GTO_MAX_RAISES_AUDIT_9MAX_V1.md section 5, pre-registered before any J solve).
T2 = state T (max_raises 2) exports; J = max_raises 3 / 4-bet jam only exports (same path specs; jam paths for the 3-bettor's
response to the 4-bet jam). Shared M4 (166): RFI (8), first-in jam share of opens (8), 3-bettor node fold/call/raise/jam (100),
opener-vs-3-bet fold and continue (50). D4 = max |M4(J) - M4(T2)| vs R = 4.33 pp. New-action report kept separate.
    python3 tools/gto_validation/pilot9_j_compare.py
"""
import json
import os

R_ = '/home/user/gto_ckpt/'
OUT = '/home/user/t2/data/gto_validation/pilot9/step3/'
SEL = json.load(open(OUT + 't3_selection.json'))['terminals']
R_REF = 0.04333948266241505
POS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB')
SRP = {'btn': 'fold,fold,fold,fold,fold,fold,raise,fold,call', 'sb': 'fold,fold,fold,fold,fold,fold,fold,raise,call'}
DIRS = {'T2': R_ + 'step3/t3/T/', 'J': R_ + 'step3/j/J/'}
KEYS = ('fold', 'call', 'raise', 'jam')


def mixd(p):
    out = dict.fromkeys(KEYS, 0.0)
    for k, v in p['mix'].items():
        out['fold' if k == 'Fold' else 'jam' if k.startswith('All-in') else 'call' if k.startswith('Call') else 'raise'] += v
    return out


def load(state, name):
    f = DIRS[state] + f'export_{name}.json'
    return json.load(open(f)) if os.path.exists(f) else None


def m4(state):
    m, new = {}, {}
    for name, idx in (('btn', range(7)), ('sb', [7])):
        t = load(state, name)
        if t is None:
            return None, None
        for i in idx:
            p = t['path_nodes'][i]
            assert p['actor'] == POS[i]
            x = mixd(p)
            m[f'rfi/{POS[i]}'] = 1 - x['fold']
            m[f'jamshare/{POS[i]}'] = x['jam'] / max(1e-12, 1 - x['fold'])
    for s in SEL:
        t = load(state, s['name'])
        if t is None:
            return None, None
        assert t['terminal_node'] is not None
        spec = s['spec'].split(',')
        pn = t['path_nodes']
        assert len(pn) == len(spec), (state, s['name'])
        r = [i for i, a in enumerate(spec) if a == 'raise']
        p3, po = pn[r[1]], pn[-1]
        for k, v in mixd(p3).items():
            m[f"{s['name']}/3bettor:{p3['actor']}/{k}"] = v
        xo = mixd(po)
        m[f"{s['name']}/opener_vs_3bet:{po['actor']}/fold"] = xo['fold']
        m[f"{s['name']}/opener_vs_3bet:{po['actor']}/continue"] = 1 - xo['fold']
        new[s['name']] = {'opener_vs_3bet': {k: v for k, v in xo.items()}, 'actions': po['actions']}
        if 'All-in 30' in po['actions']:
            k = po['actions'].index('All-in 30')
            lab = t['class_labels']
            new[s['name']]['opener_4bet_jam_classes'] = [lab[h] for h in range(169)
                                                         if po['class_reach_before'][h] > 1e-6 and po['class_strategy'][k][h] > 0.5]
        tj = load(state, s['name'] + '_jam')
        if tj is not None:
            pj = tj['path_nodes'][-1]
            new[s['name']]['three_bettor_vs_4bet_jam'] = {'actor': pj['actor'], **mixd(pj)}
    assert len(m) == 166, len(m)
    return m, new


def main():
    M2, N2 = m4('T2')
    MJ, NJ = m4('J')
    assert M2 is not None, 'T2 exports missing'
    res = {'schema': 'pilot9_j_compare_v1', 'R_reference': R_REF, 'n_shared': len(M2), 'M4': {'T2': M2, 'J': MJ}}
    if MJ is None:
        res['decision'] = 'pending: J exports missing'
    else:
        d = {k: abs(MJ[k] - M2[k]) for k in M2}
        k = max(d, key=d.get)
        res.update({'D4': d[k], 'D4_argmax': k, 'abs_J_minus_T2': d, 'n_above_R': sum(v > R_REF for v in d.values()),
                    'decision': ('D4 > R: missing 4-bet is a structural effect larger than the last HU outer-loop change' if d[k] > R_REF
                                 else 'D4 <= R (mr2 still not promoted if J has material 4-bet frequencies)'),
                    'new_actions_J': NJ})
        jam = {n: v['opener_vs_3bet']['jam'] for n, v in NJ.items()}
        res['opener_4bet_jam_freq'] = jam
    json.dump(res, open(OUT + 'j_compare.json', 'w'), indent=1)
    print(json.dumps({k: res[k] for k in ('D4', 'D4_argmax', 'n_above_R', 'decision') if k in res}, indent=1))


if __name__ == '__main__':
    main()
