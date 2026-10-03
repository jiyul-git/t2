#!/usr/bin/env python3
"""H1 analysis (full HU SRP set): states at 100 iterations, same config / seeds / tree.
  O = original dynamic static payoff                       (O checkpoint exports)
  S = 4 solved tables (BTN / CO / HJ / UTG -> BB)           (C3 exports + S-state exports of the 4 new paths)
  H = 8 solved tables (+ SB / LJ / UTG+2 / UTG+1 -> BB)     (h1/H exports)
H - S = effect of adding the 4 new tables (table content + freezing; C1b bounded freezing at <= 0.15 pp except one 1.1 pp cell).
Expected direction is judged on H - S for the 4 new nodes, per node; the 4 old nodes are reported for interaction.
Near-references (audit v1): PreflopRanges 9-max RFI, Matthiola 8-max mapped vs-open rows (combo shares of 1326).
    python3 tools/gto_validation/pilot9_h1_analyze.py
"""
import json
import os

R = '/home/user/gto_ckpt/'
OUT = '/home/user/t2/data/gto_validation/pilot9/h1/'
NEW = ['sb', 'lj', 'utg2', 'utg1']
OLD = ['btn', 'co', 'hj', 'utg']
ALL = OLD + NEW
OPENER = {'btn': 'BTN', 'co': 'CO', 'hj': 'HJ', 'utg': 'UTG', 'sb': 'SB', 'lj': 'LJ', 'utg2': 'UTG+2', 'utg1': 'UTG+1'}
NODE = {'btn': 24, 'co': 73, 'hj': 242, 'utg': 24726, 'sb': 11, 'lj': 795, 'utg2': 2548, 'utg1': 7997}
FOCUS = ['A5s', 'K9s', 'KQo', '55', '98s', '22', 'AKo', 'T8s', 'Q9o', 'J7s']
POS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB')


def f_of(state, n):
    if state == 'O':
        return R + (f'c1/legacy_{n}.json' if n in OLD else f'h1/O/export_{n}.json')
    if state == 'S':
        return R + (f'c3/export_{n}.json' if n in OLD else f'h1/terminals/s_{n}.json')
    return R + f'h1/H/export_{n}.json'


def pn(t, actor):
    return next(p for p in t['path_nodes'] if p['actor'] == actor)


def mixd(p):
    out = {'fold': 0.0, 'call': 0.0, 'raise': 0.0, 'jam': 0.0}
    for k, v in p['mix'].items():
        out['fold' if k == 'Fold' else 'jam' if k.startswith('All-in') else 'call' if k.startswith('Call') else 'raise'] += v
    return out


def metrics(state):
    t = {}
    for n in ALL:
        f = f_of(state, n)
        if not os.path.exists(f):
            return None
        t[n] = json.load(open(f))
        assert t[n]['terminal_node'] == NODE[n], (state, n)
    lab = t['btn']['class_labels']
    m = {'rfi': {}, 'vs_open': {}, 'terminal': {}, 'focus': {}, 'gap_total': t['btn']['gap_total']}
    for pos in POS:
        x = mixd(pn(t['sb' if pos == 'SB' else 'btn'], pos))
        m['rfi'][pos] = {'open': 1 - x['fold'], 'jam': x['jam'], 'jam_share_of_opens': x['jam'] / max(1e-12, 1 - x['fold'])}
    for n in ALL:
        r = {'BB': mixd(pn(t[n], 'BB'))}
        if n != 'sb':
            r['SB'] = mixd(pn(t[n], 'SB'))
        m['vs_open'][n] = r
        m['terminal'][n] = {'reach_probability': t[n].get('reach_probability'), 'ranges_hash': t[n]['ranges_hash_fnv1a64']}
        op = pn(t[n], OPENER[n])
        m['focus'][n] = {h: {'actions': op['actions'], 'freq': [round(op['class_strategy'][k][lab.index(h)], 3) for k in range(len(op['actions']))]}
                         for h in FOCUS}
    return m


def delta(a, b):
    return {'rfi_open_pp': {p: 100 * (b['rfi'][p]['open'] - a['rfi'][p]['open']) for p in POS},
            'jam_share_of_opens_pp': {p: 100 * (b['rfi'][p]['jam_share_of_opens'] - a['rfi'][p]['jam_share_of_opens']) for p in POS},
            'vs_open_pp': {n: {w: {k: 100 * (b['vs_open'][n][w][k] - a['vs_open'][n][w][k]) for k in a['vs_open'][n][w]} for w in a['vs_open'][n]} for n in ALL},
            'terminal_reach_rel': {n: b['terminal'][n]['reach_probability'] / a['terminal'][n]['reach_probability'] - 1 for n in ALL}}


def refs():
    a = json.load(open('/home/user/t2/data/gto_validation/30bb_solver_reference_audit_v1.json'))
    rfi = {p: {'preflopranges_9max': v.get('preflopranges_9max'), 'matthiola_8max_mapped': v.get('matthiola_8max_mapped')} for p, v in a['aggregate_rfi'].items()}
    bb = {}
    for r in a['vs_open_comparison']['rows']:
        op, who = r['solver_spot_9max'].split('->')
        if who == 'BB':
            bb[op] = {'ref_node_8max': r['ref_node_8max'], **r['ref']}
    return {'rfi': rfi, 'bb_vs_open': bb, 'note': 'near-references only (other tree / stack / table size); never a target'}


def main():
    O, S, H = (metrics(s) for s in 'OSH')
    res = {'schema': 'pilot9_h1_analysis_v1', 'metrics': {'O': O, 'S': S, 'H': H}, 'near_references': refs()}
    if S and H:
        d = delta(S, H)
        res['H_minus_S'] = d
        res['direction_checks_new_nodes'] = {n: {'opener_rfi_pp': d['rfi_open_pp'][OPENER[n]], 'opener_rfi_up': d['rfi_open_pp'][OPENER[n]] > 0,
                                                 'bb_fold_pp': d['vs_open_pp'][n]['BB']['fold'], 'bb_fold_up': d['vs_open_pp'][n]['BB']['fold'] > 0,
                                                 'bb_call_pp': d['vs_open_pp'][n]['BB']['call'], 'bb_call_down': d['vs_open_pp'][n]['BB']['call'] < 0,
                                                 'opener_jam_share_pp': d['jam_share_of_opens_pp'][OPENER[n]]} for n in NEW}
        res['focus_S_vs_H'] = {n: {h: {'actions': S['focus'][n][h]['actions'], 'S': S['focus'][n][h]['freq'], 'H': H['focus'][n][h]['freq']} for h in S['focus'][n]} for n in ALL}
    if O and H:
        res['H_minus_O_total'] = delta(O, H)
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(OUT + 'h1_analysis.json', 'w'), indent=1)
    for st, m in (('O', O), ('S', S), ('H', H)):
        if m:
            print(st, 'RFI', {p: round(100 * m['rfi'][p]['open'], 1) for p in POS})
            print('  BB fold', {OPENER[n]: round(100 * m['vs_open'][n]['BB']['fold'], 1) for n in ALL})
            print('  BB call', {OPENER[n]: round(100 * m['vs_open'][n]['BB']['call'], 1) for n in ALL})
    if 'direction_checks_new_nodes' in res:
        print(json.dumps(res['direction_checks_new_nodes'], indent=1))


if __name__ == '__main__':
    main()
