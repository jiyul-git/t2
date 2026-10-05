#!/usr/bin/env python3
"""OL outer loop on the 8 HU SRP tables (docs/GTO_HU_FULL_OUTER_9MAX_DESIGN_V1.md).
    pilot9_ol.py prep <k>     link the 8 state-k terminal exports into ol/step<k>/terminals
    pilot9_ol.py step <k>     after the step-k panels: V_raw,k, D / U per node-seat, stop decision, damped tables of state k+1
State 0 = h1/H (tables h1/tables_all); state k >= 1 = ol/s<k> (tables ol/s<k>/tables). Panel panel_v1 fixed at every step.
T2_JOL=1: step-3a joint OL over 33 tables (8 SRP + 25 HU 3-bet), state 0 = step3/t3/T (tables step3/t3/tables_all), root jol/.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gto_hu_continuation'))
import pilot9_tables as PT  # noqa: E402

R = '/home/user/gto_ckpt/'
JOL = os.environ.get('T2_JOL') == '1'
OL = R + ('jol/' if JOL else 'ol/')
NAMES = ['btn', 'co', 'hj', 'utg', 'sb', 'lj', 'utg2', 'utg1']
NODES = {n: PT.ALL_NODES[n] for n in NAMES}
SRP_NAMES = list(NAMES)
if JOL:
    _sel = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data/gto_validation/pilot9/step3/t3_selection.json')))['terminals']
    NODES.update({t['name']: t['node'] for t in _sel})
    NAMES = list(NODES)
ALPHA = 0.5
MAX_STEPS = 3
PANEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data/gto_hu_continuation/panel_v1.json')


def state_dir(k):
    if k == 0:
        return R + ('step3/t3/T/' if JOL else 'h1/H/')
    return OL + f's{k}/'


def tables_dir(k):
    if k == 0:
        return R + ('step3/t3/tables_all/' if JOL else 'h1/tables_all/')
    return OL + f's{k}/tables/'


def combos(h):
    return 6 if len(h) == 2 else (4 if h[2] == 's' else 12)


def atomic(o, p):
    json.dump(o, open(p + '.tmp', 'w'), indent=1)
    os.replace(p + '.tmp', p)


def prep(k):
    d = OL + f'step{k}/terminals/'
    os.makedirs(d, exist_ok=True)
    for n in NAMES:
        src = state_dir(k) + f'export_{n}.json'
        assert os.path.exists(src), src
        dst = d + f'export_{n}.json'
        if not os.path.exists(dst):
            os.symlink(src, dst)


def panel_setup():
    import a4c_run as C
    panel = json.load(open(PANEL))
    boards = [f['board'] for f in panel['panel']]
    draws = {}
    for f in panel['panel']:
        draws.setdefault(f['stratum'], []).append(f['board'])
    p = {s: v['probability'] for s, v in panel['strata'].items()}
    return C, boards, draws, p, C.compat_of(boards)


def board_values(flops_dir):
    _, boards, _, _, _ = panel_setup()
    return {b: {pl['position']: [0.0 if x is None else x for x in pl['gross_eps']] for pl in json.load(open(os.path.join(flops_dir, b + '.json')))['players']}
            for b in boards}


def stratified(vals):
    """A4c estimator (None counted as 0, as in a4c_run.estimate) and its analytic stratified standard error per class / seat"""
    C, boards, draws, p, compat = panel_setup()
    ptot = sum(p.values())
    est, se = {}, {}
    for pos in vals[boards[0]]:
        e, u = [], []
        for h in range(169):
            tot, v2 = 0.0, 0.0
            for s, bs in draws.items():
                y = [compat[b][h] * vals[b][pos][h] for b in bs]
                m = sum(y) / len(y)
                tot += p[s] * m
                v2 += (p[s] / (ptot * C.RHO)) ** 2 * sum((x - m) ** 2 for x in y) / (len(y) - 1) / len(y)
            e.append(tot / ptot / C.RHO)
            u.append(math.sqrt(v2))
        est[pos], se[pos] = e, u
    return est, se


def eff_values(k, n):
    """per-board values whose A4c estimate is the state-k table (tables are linear in board values)"""
    if k == 0 and JOL:
        if n in SRP_NAMES:
            return json.load(open(R + f'ol/s2/eff/{n}.json'))   # T used the OL state-2 SRP tables unchanged
        return board_values(R + f'step3/t3/{n}/flops')
    if k == 0:
        src = R + ('c2/' if n in ('btn', 'co', 'hj', 'utg') else 'h1/') + n + '/flops'
        return board_values(src)
    return json.load(open(OL + f's{k}/eff/{n}.json'))


def step(k):
    sd = OL + f'step{k}/'
    raw_dir = sd + 'raw_tables/'
    os.makedirs(raw_dir, exist_ok=True)
    PT.solved(sd, raw_dir, NODES, 'export_')     # asserts ranges hash, panel hash, converged <= 0.3 on every board
    rep = {'schema': 'pilot9_ol_step_v1', 'k': k, 'alpha': ALPHA, 'panel': 'panel_v1 (24 boards, fixed)', 'nodes': {}}
    nxt = OL + f's{k + 1}/'
    os.makedirs(nxt + 'tables', exist_ok=True)
    os.makedirs(nxt + 'eff', exist_ok=True)
    files = []
    for n, node in NODES.items():
        cur = json.load(open(tables_dir(k) + f'node{node}.json'))
        raw = json.load(open(raw_dir + f'node{node}.json'))
        term = json.load(open(sd + f'terminals/export_{n}.json'))
        lab = term['class_labels']
        keep = {pl['position']: pl['class_keep_fraction'] for pl in term['players']}
        g_cur = {s['position']: s['gross'] for s in cur['seats']}
        bv_raw = board_values(sd + n + '/flops')
        bv_cur = eff_values(k, n)
        g_raw, se_raw = stratified(bv_raw)
        e_cur, _ = stratified(bv_cur)
        tab_raw = {s['position']: s['gross'] for s in raw['seats']}
        # integrity: the estimator here reproduces the raw table and the state-k table from their board values
        lin = max(max(abs(a - b) for a, b in zip(g_raw[pos], tab_raw[pos])) for pos in g_raw)
        lin_cur = max(max(abs(a - b) for a, b in zip(e_cur[pos], g_cur[pos])) for pos in g_cur)
        assert lin < 1e-9 and lin_cur < 1e-9, (n, lin, lin_cur)
        bv_diff = {b: {pos: [x - y for x, y in zip(bv_raw[b][pos], bv_cur[b][pos])] for pos in bv_raw[b]} for b in bv_raw}
        _, se_diff = stratified(bv_diff)
        r = {}
        for pos in g_raw:
            w = [combos(lab[h]) * keep[pos][h] for h in range(169)]
            W = sum(w)
            D = sum(w[h] * abs(g_raw[pos][h] - g_cur[pos][h]) for h in range(169)) / W
            sg = sum(w[h] * (g_raw[pos][h] - g_cur[pos][h]) for h in range(169)) / W
            U = sum(w[h] * se_raw[pos][h] for h in range(169)) / W
            Ud = sum(w[h] * se_diff[pos][h] for h in range(169)) / W
            r[pos] = {'D': D, 'signed': sg, 'U': U, 'D_over_U': D / U, 'pass': D <= U,
                      'U_paired_diff': Ud, 'D_over_U_paired_diff': D / Ud if Ud > 0 else None}
        rep['nodes'][n] = {'node': node, 'seats': r, 'max_expl_pct_pot': raw['provenance']['max_expl_pct_pot']}
        damp = json.loads(json.dumps(raw))
        for s in damp['seats']:
            s['gross'] = [(1 - ALPHA) * a + ALPHA * b for a, b in zip(g_cur[s['position']], tab_raw[s['position']])]
        damp['provenance'] = {'kind': f'OL state {k + 1}: damped {1 - ALPHA} x state-{k} table + {ALPHA} x step-{k} raw panel_v1 table',
                              'state_k_table': tables_dir(k) + f'node{node}.json', 'raw_table': raw_dir + f'node{node}.json'}
        json.dump(damp, open(nxt + f'tables/node{node}.json', 'w'))
        json.dump({b: {pos: [(1 - ALPHA) * x + ALPHA * y for x, y in zip(bv_cur[b][pos], bv_raw[b][pos])] for pos in bv_raw[b]} for b in bv_raw},
                  open(nxt + f'eff/{n}.json', 'w'))
        files.append({'file': f'node{node}.json'})
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': files}, open(nxt + 'tables/manifest.json', 'w'))
    worst = max(s['D_over_U'] for v in rep['nodes'].values() for s in v['seats'].values())
    rep['max_D_over_U'] = worst
    rep['max_D_over_U_paired_diff'] = max(s['D_over_U_paired_diff'] or 0 for v in rep['nodes'].values() for s in v['seats'].values())
    rep['all_pass'] = all(s['pass'] for v in rep['nodes'].values() for s in v['seats'].values())
    hist = []
    for j in range(k):
        f = OL + f'step{j}/report.json'
        if os.path.exists(f):
            hist.append(json.load(open(f))['max_D_over_U'])
    hist.append(worst)
    rep['max_D_over_U_history'] = hist
    if k == 0:
        rep['decision'] = ('continue: minimum one update (same rule as OL; the 25 3-bet tables were computed at state-2 ranges); stop test applies from step 1'
                           if JOL else 'continue: minimum one update (the 4 S-pilot tables were computed at O ranges); stop test applies from step 1')
    elif rep['all_pass']:
        rep['decision'] = 'stop: converged at panel_v1 resolution (value space); state k accepted, state k+1 not solved'
    elif len(hist) >= 3 and hist[-1] > hist[-2] > hist[-3]:
        rep['decision'] = 'stop: max D/U grew two steps in a row; report'
    elif k + 1 >= MAX_STEPS:
        rep['decision'] = f'stop: not yet converged after {MAX_STEPS} steps'
    else:
        rep['decision'] = f'continue: solve state {k + 1}'
    rep['wording'] = ('D <= U means the tables move by no more than the panel_v1 error of one estimate; it is not a best-response / '
                      'fixed-point proof. D / U_paired_diff (same boards, report only) shows whether the move is detectable at all.')
    atomic(rep, sd + 'report.json')
    print(json.dumps({'k': k, 'max_D_over_U': worst, 'decision': rep['decision'],
                      'D_over_U': {n: {p: round(s['D_over_U'], 2) for p, s in v['seats'].items()} for n, v in rep['nodes'].items()},
                      'D_over_U_paired': {n: {p: round(s['D_over_U_paired_diff'] or 0, 2) for p, s in v['seats'].items()} for n, v in rep['nodes'].items()},
                      'signed': {n: {p: round(s['signed'], 3) for p, s in v['seats'].items()} for n, v in rep['nodes'].items()}}, indent=1))


if __name__ == '__main__':
    {'prep': prep, 'step': step}[sys.argv[1]](int(sys.argv[2]))
