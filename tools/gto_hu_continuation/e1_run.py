#!/usr/bin/env python3
"""E1 outer-loop step (data/gto_terminal_expansion/e1/prereg.json + amendment 1).   python3 tools/gto_hu_continuation/e1_run.py <k>

After the step-k panel (run_e1_flops.sh k) is complete:
  V_raw,k  = A4c estimator on the step-k board values (undamped)
  raw solve g(V_raw,k) -> sigma_raw,k (measurement only)
  Delta_raw,k: sigma_k in G_raw,k (seat swap dEV, class-regret excess over G_raw,k own residual), signed kept, primary = max(0, .)
  U_k: the A4c joint draw manifest (60 draws, seed 20261005) re-applied to the step-k values, FPC as A4c; loss_r = max(0, metric of
       sigma_r in G_raw,k); U_k = mean
  stop decision (all primary Delta_raw <= U_k -> "converged at current panel resolution"; partial pass otherwise)
  damped next state: V_{k+1} = 0.5 V_k + 0.5 V_raw,k (tables only) -> preflop solve -> sigma_{k+1}, R_{k+1} (prepared, not run further)
Resumable: every solve dir is reused by the solver's own export check; results are written atomically after each unit.
"""
import hashlib
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4c_run as C  # noqa: E402
from a4c_design2 import pools  # noqa: E402
from a4c_influence import NODES, node_data  # noqa: E402
from a4c_reconstruct import regret_l1  # noqa: E402

E = C.E
OUT = os.environ.get('E1_OUT', E + 'e1/')   # E1_OUT only for the identity self-test
PRIMARY_SEATS = ('BTN', 'SB', 'BB')
PRIMARY_NODES = ('BTN first-in', 'BB vs BTN', 'SB first-in', 'BB vs SB')
ALPHA = 0.5


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def atomic(o, p):
    C.atomic(o, p)


def step_values(k):
    st = {}
    for n in (6, 28):
        p, old, new = C.panel(n)
        term = json.load(open(OUT + f'step{k}/R/terminal_node{n}.json'))
        boards = [f['board'] for f in p['panel']]
        vals = {}
        if os.environ.get('E1_OUT'):   # identity self-test on the A4c artifacts (A4c checks incl. its approved exception)
            vals = C.load_values(n, boards)
            boards_iter = []
        else:
            boards_iter = boards
        for b in boards_iter:
            f = OUT + f'step{k}/node{n}/flops/{b}.json'
            d = json.load(open(f))
            kk = d['provenance_key']
            if kk['ranges_hash_fnv1a64'] != term['ranges_hash_fnv1a64'] or kk['panel_hash_sha256'] != p['panel_hash_sha256']:
                raise SystemExit(f'step {k} node {n} {b}: provenance mismatch')
            if not (d['converged'] and d['exploitability_pct_pot'] <= 0.3):
                raise SystemExit(f'step {k} node {n} {b}: not converged ({d["exploitability_pct_pot"]}) -> step decision stops, user decision needed')
            vals[b] = {pl['position']: pl['gross_eps'] for pl in d['players']}
        st[n] = {'old': old, 'new': new, 'all': {s: old[s] + new[s] for s in old}, 'p_str': {s: v['probability'] for s, v in p['strata'].items()},
                 'vals': vals, 'compat': C.compat_of(boards), 'flop_sha': {b: sha(OUT + f'step{k}/node{n}/flops/{b}.json') for b in boards}}
    return st


def tab_file(d, n):
    return d + f'table_node{n}.json'


def solve_tables(d, tabs):
    os.makedirs(d, exist_ok=True)
    return C.solve(d, tabs)


def metrics(game, gdir, donor, ddir, out_dir, base):
    m = C.swap_metrics(game, gdir, donor, ddir, out_dir, base)
    signed = {'seat': {s: m['seat_dEV'][s] for s in m['seat_dEV']}, 'node': dict(m['regret_excess'])}
    return {'signed': signed, 'loss': {'seat': {s: max(0.0, v) for s, v in signed['seat'].items()}, 'node': {nd: max(0.0, v) for nd, v in signed['node'].items()}},
            'L1': m['L1'], 'own_gap': m['own_gap'], 'max_check': m['max_check']}


def main():
    k = int(sys.argv[1])
    sd = OUT + f'step{k}/'
    res_path = sd + 'result.json'
    R = json.load(open(res_path)) if os.path.exists(res_path) else {'step': k}
    st = step_values(k)
    # current state x_k
    if k == 0:
        Vk = {n: json.load(open(E + f'a4c/node{n}/table_ext.json')) for n in (6, 28)}
        cur = json.load(open(E + 'a4c/points.json'))['Gext']
        cur_dir = E + 'a4c/points/Gext'
    else:
        Vk = {n: json.load(open(OUT + f'step{k - 1}/damped_point/table_node{n}.json')) for n in (6, 28)}
        cur = json.load(open(OUT + f'step{k - 1}/result.json'))['damped_point']
        cur_dir = OUT + f'step{k - 1}/damped_point'
    # V_raw,k
    vraw = {n: C.estimate(st[n]['vals'], st[n]['compat'], st[n]['all'], st[n]['p_str']) for n in (6, 28)}
    raw_tabs = {n: C.table_json(n, vraw[n], f'E1 step {k} V_raw (undamped panel estimate at R_{k})') for n in (6, 28)}
    raw_dir = sd + 'raw_point/'
    if 'raw_point' not in R:
        R['raw_point'] = solve_tables(raw_dir, raw_tabs)
        atomic(R, res_path)
    G = R['raw_point']
    gn = node_data(raw_dir)
    base = {nd: regret_l1(gn[nd], {'class_strategy': gn[nd]['s']})[0] for nd in NODES}
    R['raw_own_residual'] = base
    if 'delta_raw' not in R:
        R['delta_raw'] = metrics(G, raw_dir, cur, cur_dir, sd + 'delta_swaps', base)
        atomic(R, res_path)
    if os.environ.get('E1_STOP_AFTER_DELTA'):
        R['vraw_vs_V_k_max_abs'] = max(abs(a - b) for n in (6, 28) for s in Vk[n]['seats'] for a, b in zip(s['gross'], vraw[n][s['position']]))
        print(json.dumps({'vraw_vs_V_k_max_abs': R['vraw_vs_V_k_max_abs'], 'delta_signed': R['delta_raw']['signed'], 'max_check': R['delta_raw']['max_check']}, indent=1))
        return
    # U_k with the A4c joint draws
    J = C.joint_structure(st)
    rng = random.Random(20261005)
    draws, man = [], []
    for _ in range(60):
        d, m = C.joint_draw(rng, J)
        draws.append(d)
        man.append(m)
    msha = hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest()
    assert msha == json.load(open(E + 'a4c/boot_draw_manifest.json'))['sha256'], 'draw manifest differs from A4c'
    K = {s: len(v) for s, v in pools().items()}
    ref = {n: C.stratum_means(st[n]['vals'], st[n]['compat'], st[n]['all']) for n in (6, 28)}
    lam = {n: {s: math.sqrt((1 - len(st[n]['all'][s]) / K[s]) * len(st[n]['all'][s]) / (len(st[n]['all'][s]) - 1)) for s in st[n]['old']} for n in (6, 28)}
    R.setdefault('U_reps', {})
    for i, d in enumerate(draws, 1):
        if str(i) in R['U_reps']:
            continue
        rd = sd + f'boot/r{i:02d}/'
        tabs = {}
        for n in (28, 6):
            o, w = d[n]
            g = C.estimate(st[n]['vals'], st[n]['compat'], {s: o[s] + w[s] for s in o}, st[n]['p_str'], lam[n], ref[n])
            tabs[n] = C.table_json(n, g, f'E1 step {k} bootstrap replicate {i}')
        rep = solve_tables(rd + 'ext', tabs)
        R['U_reps'][str(i)] = metrics(G, raw_dir, rep, rd + 'ext', rd + 'swaps', base)
        atomic(R, res_path)
        print('U rep', i, {s: round(x, 5) for s, x in R['U_reps'][str(i)]['loss']['seat'].items()}, flush=True)
    reps = [R['U_reps'][str(i)] for i in range(1, 61)]
    U = {'seat': {s: sum(r['loss']['seat'][s] for r in reps) / 60 for s in reps[0]['loss']['seat']},
         'node': {nd: sum(r['loss']['node'][nd] for r in reps) / 60 for nd in reps[0]['loss']['node']}}
    D = R['delta_raw']['loss']
    checks = {f'seat:{s}': {'delta_raw': D['seat'][s], 'U': U['seat'][s], 'pass': D['seat'][s] <= U['seat'][s]} for s in PRIMARY_SEATS}
    checks.update({f'node:{nd}': {'delta_raw': D['node'][nd], 'U': U['node'][nd], 'pass': D['node'][nd] <= U['node'][nd]} for nd in PRIMARY_NODES})
    npass = sum(c['pass'] for c in checks.values())
    R['U'] = U
    R['stop_check'] = {'primary': checks, 'passed': npass, 'of': len(checks),
                       'diagnostic': {'CO': {'delta_raw': D['seat']['CO'], 'U': U['seat']['CO']},
                                      'SB vs BTN': {'delta_raw': D['node']['SB vs BTN'], 'U': U['node']['SB vs BTN']}},
                       'verdict': ('converged at current panel resolution' if npass == len(checks) else
                                   ('partial pass' if npass else 'not passed')) + f' at step {k}',
                       'wording': 'Delta_raw <= U_k is a bootstrap panel-error-scale criterion, not a proof of fixed-point convergence'}
    # damped next state x_{k+1} (prepared only)
    dn_dir = sd + 'damped_point/'
    if 'damped_point' not in R:
        dtabs = {}
        for n in (6, 28):
            vk = {s['position']: s['gross'] for s in Vk[n]['seats']}
            vd = {p: [ALPHA * a + (1 - ALPHA) * b for a, b in zip(vk[p], vraw[n][p])] for p in vraw[n]}
            dtabs[n] = C.table_json(n, vd, f'E1 step {k} damped V_{k + 1} = 0.5 V_{k} + 0.5 V_raw,{k}')
        R['damped_point'] = solve_tables(dn_dir, dtabs)
        atomic(R, res_path)
    R['provenance'] = {
        'panel_sha256': {n: sha(C.PANEL[n]) for n in (6, 28)},
        'R_k_ranges_hash': {n: json.load(open(sd + f'R/terminal_node{n}.json'))['ranges_hash_fnv1a64'] for n in (6, 28)},
        'flop_artifact_sha256': {n: st[n]['flop_sha'] for n in (6, 28)},
        'V_k_sha256': {n: (sha(E + f'a4c/node{n}/table_ext.json') if k == 0 else sha(OUT + f'step{k - 1}/damped_point/table_node{n}.json')) for n in (6, 28)},
        'V_raw_sha256': {n: sha(raw_dir + f'table_node{n}.json') for n in (6, 28)},
        'V_damped_sha256': {n: sha(dn_dir + f'table_node{n}.json') for n in (6, 28)},
        'raw_profile_sha256': sha(raw_dir + 'profile.gtop'), 'damped_profile_sha256': sha(dn_dir + 'profile.gtop'),
        'R_next_ranges_hash': {n: json.load(open(dn_dir + f'terminal_node{n}.json'))['ranges_hash_fnv1a64'] for n in (6, 28)},
        'draw_manifest_sha256': msha}
    R['note'] = 'step 1 is not started automatically (amendment 1); damped_point is x_{k+1}, prepared only'
    atomic(R, res_path)
    print(json.dumps(R['stop_check'], indent=1))


if __name__ == '__main__':
    main()
