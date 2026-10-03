#!/usr/bin/env python3
"""pilot9 S analysis: three states at 100 iterations, same config / seeds / tree.
  O = original dynamic static payoff        (/home/user/gto_ckpt/c1/legacy_*.json, the 100-iteration checkpoint)
  F = C1b frozen static tables at the 4 nodes (/home/user/gto_ckpt/c1b/export_*.json)
  S = C3 frozen solved tables at the 4 nodes  (/home/user/gto_ckpt/c3/export_*.json)
Reported deltas: F - O = table-freezing effect; S - F = solved-continuation content effect (the pilot's main estimate).
S - O is total change for reference only. Expected direction is judged on S - F, per node / position (no pooling).
    python3 tools/gto_validation/pilot9_analyze.py
"""
import json
import os

R = '/home/user/gto_ckpt/'
OUT = '/home/user/t2/data/gto_validation/pilot9/'
STATES = {'O': R + 'c1/legacy_{}.json', 'F': R + 'c1b/export_{}.json', 'S': R + 'c3/export_{}.json'}
PATHS = ['btn', 'co', 'hj', 'utg', 'utg1_ctrl']
OPENER = {'btn': 'BTN', 'co': 'CO', 'hj': 'HJ', 'utg': 'UTG', 'utg1_ctrl': 'UTG+1'}
SELECTED = ['btn', 'co', 'hj', 'utg']
FOCUS = ['A5s', 'K9s', 'KQo', '55', '98s', '22', 'AKo']
RANKS = '23456789TJQKA'


def combos(h):
    return 6 if len(h) == 2 else (4 if h[2] == 's' else 12)


def load(state, n):
    f = STATES[state].format(n)
    return json.load(open(f)) if os.path.exists(f) else None


def pn(t, actor):
    return next(p for p in t['path_nodes'] if p['actor'] == actor)


def mixd(p):
    m = p['mix']
    out = {'fold': 0.0, 'call': 0.0, 'raise': 0.0, 'jam': 0.0}
    for k, v in m.items():
        k2 = 'fold' if k == 'Fold' else 'jam' if k.startswith('All-in') else 'call' if k.startswith('Call') else 'raise'
        out[k2] += v
    return out


def state_metrics(state):
    t = {n: load(state, n) for n in PATHS}
    if any(v is None for v in t.values()):
        return None
    lab = t['btn']['class_labels']
    m = {'gap_total': t['btn']['gap_total']}
    # RFI per position from the BTN path (all first-in nodes UTG..BTN are on it)
    m['rfi'] = {}
    for pos in ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN'):
        x = mixd(pn(t['btn'], pos))
        m['rfi'][pos] = {'open': 1 - x['fold'], 'raise': x['raise'], 'jam': x['jam'], 'jam_share_of_opens': x['jam'] / max(1e-12, 1 - x['fold'])}
    # responses to each opener
    m['vs_open'] = {}
    for n in PATHS:
        r = {'BB': mixd(pn(t[n], 'BB')), 'SB': mixd(pn(t[n], 'SB'))}
        if OPENER[n] != 'BTN':
            r['BTN'] = mixd(pn(t[n], 'BTN'))
        m['vs_open'][n] = r
    # selected terminal: reach and ranges
    m['terminal'] = {}
    for n in PATHS:
        x = t[n]
        m['terminal'][n] = {'node': x['terminal_node'], 'reach_probability': x.get('reach_probability'),
                            'keep': {p['position']: p['class_keep_fraction'] for p in x['players']},
                            'ranges_hash': x['ranges_hash_fnv1a64']}
    # focus hands at the opener RFI nodes and at BB facing each opener
    m['focus'] = {}
    for n in PATHS:
        op = pn(t[n], OPENER[n])
        bb = pn(t[n], 'BB')
        f = {}
        for h in FOCUS:
            i = lab.index(h)
            f[h] = {'opener': {'actions': op['actions'], 'freq': [op['class_strategy'][k][i] for k in range(len(op['actions']))], 'ev': [op['ev_bb'][k][i] for k in range(len(op['actions']))]},
                    'bb': {'actions': bb['actions'], 'freq': [bb['class_strategy'][k][i] for k in range(len(bb['actions']))], 'ev': [bb['ev_bb'][k][i] for k in range(len(bb['actions']))]}}
        m['focus'][n] = f
    return m


def l1_keep(a, b):
    return {pos: sum(combos(h) * abs(x - y) for h, x, y in zip(LABELS, a[pos], b[pos])) / 1326 for pos in a}


def delta(a, b):
    """b - a for the headline metrics"""
    d = {'rfi_open_pp': {p: 100 * (b['rfi'][p]['open'] - a['rfi'][p]['open']) for p in a['rfi']},
         'rfi_jam_pp': {p: 100 * (b['rfi'][p]['jam'] - a['rfi'][p]['jam']) for p in a['rfi']},
         'jam_share_of_opens_pp': {p: 100 * (b['rfi'][p]['jam_share_of_opens'] - a['rfi'][p]['jam_share_of_opens']) for p in a['rfi']},
         'vs_open_pp': {n: {who: {k: 100 * (b['vs_open'][n][who][k] - a['vs_open'][n][who][k]) for k in a['vs_open'][n][who]} for who in a['vs_open'][n]} for n in a['vs_open']},
         'terminal_reach_rel': {n: (b['terminal'][n]['reach_probability'] / a['terminal'][n]['reach_probability'] - 1) if a['terminal'][n]['reach_probability'] else None for n in a['terminal']},
         'terminal_range_l1': {n: l1_keep(a['terminal'][n]['keep'], b['terminal'][n]['keep']) for n in a['terminal']}}
    return d


def direction_checks(dSF):
    """expected direction on S - F, per node / position"""
    out = {}
    for n in SELECTED:
        op = OPENER[n]
        v = dSF['vs_open_pp'][n]
        out[n] = {'opener_rfi_up': dSF['rfi_open_pp'][op] > 0, 'opener_rfi_pp': dSF['rfi_open_pp'][op],
                  'bb_fold_up': v['BB']['fold'] > 0, 'bb_fold_pp': v['BB']['fold'],
                  'bb_call_down': v['BB']['call'] < 0, 'bb_call_pp': v['BB']['call'],
                  'opener_jam_share_down': dSF['jam_share_of_opens_pp'][op] < 0, 'opener_jam_share_pp': dSF['jam_share_of_opens_pp'][op]}
    return out


def focus_moves(F, S):
    out = {}
    for n in SELECTED:
        rows = {}
        for h in FOCUS:
            a, b = F['focus'][n][h]['opener'], S['focus'][n][h]['opener']
            acts = a['actions']
            rows[h] = {'actions': acts, 'freq_F': [round(x, 3) for x in a['freq']], 'freq_S': [round(x, 3) for x in b['freq']],
                       'ev_F': [round(x, 3) for x in a['ev']], 'ev_S': [round(x, 3) for x in b['ev']],
                       'raise_freq_change': round(b['freq'][1] - a['freq'][1], 3) if len(acts) > 1 else None}
        out[n] = rows
    return out


def main():
    global LABELS
    O, F, S = (state_metrics(s) for s in 'OFS')
    LABELS = json.load(open(STATES['O'].format('btn')))['class_labels']
    res = {'schema': 'pilot9_s_analysis_v1', 'states': {'O': 'original dynamic static payoff, 100 it', 'F': 'C1b frozen static tables at nodes 24/73/242/24726, 100 it',
                                                        'S': 'C3 frozen solved tables (panel_v1, 24 boards) at the same nodes, 100 it'},
           'metrics': {'O': O, 'F': F, 'S': S}}
    if O and F:
        res['F_minus_O_table_freezing'] = delta(O, F)
    if F and S:
        dsf = delta(F, S)
        res['S_minus_F_solved_content'] = dsf
        res['direction_checks_S_minus_F'] = direction_checks(dsf)
        res['focus_hands_F_vs_S'] = focus_moves(F, S)
    if O and S:
        res['S_minus_O_total_reference_only'] = delta(O, S)
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(OUT + 's_analysis.json', 'w'), indent=1)
    for k in ('F_minus_O_table_freezing', 'S_minus_F_solved_content'):
        if k in res:
            d = res[k]
            print(k, 'RFI pp', {p: round(x, 2) for p, x in d['rfi_open_pp'].items()})
            print('   BB vs opener pp', {n: {kk: round(x, 2) for kk, x in v['BB'].items()} for n, v in d['vs_open_pp'].items()})
            print('   reach rel', {n: (round(x, 3) if x is not None else None) for n, x in d['terminal_reach_rel'].items()})
    if 'direction_checks_S_minus_F' in res:
        print(json.dumps(res['direction_checks_S_minus_F'], indent=1))


if __name__ == '__main__':
    main()
