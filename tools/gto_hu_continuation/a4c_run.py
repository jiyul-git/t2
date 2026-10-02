#!/usr/bin/env python3
"""A4c pipeline (data/gto_terminal_expansion/a4c/prereg.json).

    python3 tools/gto_hu_continuation/a4c_run.py tables     # provenance checks, V144 identity, Vext tables
    python3 tools/gto_hu_continuation/a4c_run.py points     # G144 (A4b point, verified) and Gext solve
    python3 tools/gto_hu_continuation/a4c_run.py margdiag   # amendment-1 marginal diagnostic (before boot; diagnostic only)
    python3 tools/gto_hu_continuation/a4c_run.py lobo       # Kc9h9d leave-one-board-out (after points; diagnostic only)
    python3 tools/gto_hu_continuation/a4c_run.py boot       # 60-replicate nested paired FPC bootstrap + swaps + hand metrics (resumable)
    python3 tools/gto_hu_continuation/a4c_run.py analyze    # predicted vs measured, classification, hand-level, figure
"""
import argparse
import hashlib
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4b_panel144 as B  # noqa: E402
import a4r_robust as A  # noqa: E402
from aggregate import class_combos, parse_board  # noqa: E402
from a4c_influence import NODES, node_data  # noqa: E402
from a4c_reconstruct import regret_l1  # noqa: E402
from a4c_design2 import pools  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
OUT = E + 'a4c/'
A3 = E + 'outer_m28_6/'
PANEL = {n: os.path.join(ROOT, f'data/gto_hu_continuation/panel_v4_node{n}.json') for n in (6, 28)}
FLOP_DIRS = {n: [OUT + f'node{n}/flops/', E + f'a4b_panel144/node{n}/flops/', A3 + f'k14/node{n}/flops/'] for n in (6, 28)}
SEATS = {'CO': (0, 'all'), 'BTN': (1, 'all'), 'SB': (2, 'all'), 'BB': (3, 'all')}
RHO = 19600 / 22100
# user-approved solver-policy exceptions (a4c/exception_nonconverged_*.json): exact (node, board, artifact sha256) matches only
EXCEPTIONS = [json.load(open(os.path.join(OUT, f))) for f in sorted(os.listdir(OUT)) if f.startswith('exception_nonconverged_')] if os.path.isdir(OUT) else []
STATUS = {}   # (node, board) -> 'target_converged' | 'accepted_exception_nonconverged'


def exception_ok(n, b, path):
    sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    return any(x['status'] == 'accepted_exception_nonconverged' and x['terminal_node'] == n and x['board'] == b and x['artifact_sha256'] == sha
               for x in EXCEPTIONS)


def atomic(obj, path):
    json.dump(obj, open(path + '.tmp', 'w'))
    os.replace(path + '.tmp', path)


def panel(n):
    p = json.load(open(PANEL[n]))
    old, new = {}, {}
    for f in p['panel']:
        (old if f['in_panel_v3_144'] else new).setdefault(f['stratum'], []).append(f['board'])
    for s in old:
        new.setdefault(s, [])
    return p, old, new


_labels = None


def compat_of(boards):
    global _labels
    if _labels is None:
        _labels = [class_combos(l) for l in json.load(open(E + 'terminals/p9_node6.json'))['class_labels']]
    return {b: [sum(1 for c in cc if c[0] not in parse_board(b) and c[1] not in parse_board(b)) / len(cc) for cc in _labels] for b in boards}


def flop_file(n, b):
    for d in FLOP_DIRS[n]:
        f = d + b + '.json'
        if os.path.exists(f):
            return f
    raise SystemExit(f'node {n}: no artifact for {b}')


def load_values(n, boards):
    vals, keys = {}, {}
    p = json.load(open(PANEL[n]))
    ok_panels = {p['panel_hash_sha256'], *p['ancestor_panel_hashes']}
    term = json.load(open(A3 + f'k14/terminal_node{n}.json'))
    for b in boards:
        path = flop_file(n, b)
        d = json.load(open(path))
        k = d['provenance_key']
        if k['ranges_hash_fnv1a64'] != term['ranges_hash_fnv1a64']:
            raise SystemExit(f'{n} {b}: ranges hash {k["ranges_hash_fnv1a64"]} != P14 {term["ranges_hash_fnv1a64"]}')
        if k['panel_hash_sha256'] not in ok_panels:
            raise SystemExit(f'{n} {b}: panel hash not in this panel lineage')
        if d['converged'] and d['exploitability_pct_pot'] <= 0.3:   # the 0.300% target is never relaxed
            STATUS[(n, b)] = 'target_converged'
        elif exception_ok(n, b, path):
            STATUS[(n, b)] = 'accepted_exception_nonconverged'
        else:
            raise SystemExit(f'{n} {b}: not converged ({d["exploitability_pct_pot"]}) and no user-approved exact exception')
        keys[json.dumps({x: y for x, y in k.items() if x != 'panel_hash_sha256'}, sort_keys=True)] = b
        vals[b] = {pl['position']: pl['gross_eps'] for pl in d['players']}
    if len(keys) != 1:
        raise SystemExit(f'node {n}: provenance keys differ beyond the panel hash ({len(keys)} variants)')
    return vals


def estimate(vals, compat, draws, p_str, lam=None, ref=None):
    """stratified estimate per position; draws {stratum: [boards]}; optional FPC rescaling of each stratum mean about ref."""
    out = {}
    pos_list = next(iter(vals.values())).keys()
    for pos in pos_list:
        res = []
        for h in range(169):
            tot = 0.0
            for s, bs in draws.items():
                num = sum(compat[b][h] * vals[b][pos][h] for b in bs if vals[b][pos][h] is not None)
                if lam is None:
                    tot += p_str[s] * num / len(bs)   # same operation order as aggregate.py / a4b_panel144.estimate
                else:
                    tot += p_str[s] * (ref[s][pos][h] + lam[s] * (num / len(bs) - ref[s][pos][h]))
            res.append(tot / sum(p_str.values()) / RHO)
        out[pos] = res
    return out


def stratum_means(vals, compat, draws):
    return {s: {pos: [sum(compat[b][h] * vals[b][pos][h] for b in bs if vals[b][pos][h] is not None) / len(bs) for h in range(169)]
                for pos in next(iter(vals.values())).keys()} for s, bs in draws.items()}


def table_json(n, gross, note):
    tab = json.load(open(B.TEMPLATE[144](n)))
    for s in tab['seats']:
        s['gross'] = gross[s['position']]
    tab['a4c'] = note
    return tab


def setup():
    st = {}
    for n in (6, 28):
        p, old, new = panel(n)
        p_str = {s: v['probability'] for s, v in p['strata'].items()}
        boards = [f['board'] for f in p['panel']]
        st[n] = {'old': old, 'new': new, 'all': {s: old[s] + new[s] for s in old}, 'p_str': p_str,
                 'vals': load_values(n, boards), 'compat': compat_of(boards)}
    return st


def tables(a):
    st = setup()
    K = {s: len(v) for s, v in pools().items()}
    chk = {}
    for n in (6, 28):
        S = st[n]
        v144 = estimate(S['vals'], S['compat'], S['old'], S['p_str'])
        ref = {x['position']: x['gross'] for x in json.load(open(B.TEMPLATE[144](n)))['seats']}
        chk[f'V144_node{n}_vs_table_measured_144_max_abs'] = max(abs(x - y) for p in ref for x, y in zip(ref[p], v144[p]))
        vext = estimate(S['vals'], S['compat'], S['all'], S['p_str'])
        os.makedirs(OUT + f'node{n}', exist_ok=True)
        atomic(table_json(n, vext, 'Vext measured table (A4c estimator)'), OUT + f'node{n}/table_ext.json')
        chk[f'node{n}_boards'] = {'total': sum(len(v) for v in S['all'].values()), 'new': sum(len(v) for v in S['new'].values())}
        term = json.load(open(A3 + f'k14/terminal_node{n}.json'))
        un = lambda g: term['pot_bb'] - sum(sum(pl['class_reach_normalized'][h] * g[pl['position']][h] for h in range(169)) for pl in term['players'])
        chk[f'node{n}_unallocated_bb'] = {'V144': un(v144), 'Vext': un(vext)}
        fl = [json.load(open(OUT + f'node{n}/flops/{b}.json')) for s in S['new'] for b in S['new'][s]]
        chk[f'node{n}_new_flops'] = {'count': len(fl), 'max_expl_pct_pot': max(f['exploitability_pct_pot'] for f in fl),
                                     'mean_expl_pct_pot': sum(f['exploitability_pct_pot'] for f in fl) / len(fl),
                                     'cpu_h': sum(f['cost']['solve_ms'] for f in fl) / 3.6e6, 'iterations_mean': sum(f['iterations'] for f in fl) / len(fl)}
    new_status = [STATUS[(n, b)] for n in (6, 28) for s in st[n]['new'] for b in st[n]['new'][s]]
    chk['convergence_status_new_boards'] = {'target_converged': new_status.count('target_converged'),
                                            'accepted_exception_nonconverged': [f'node{n}/{b}' for (n, b), v in sorted(STATUS.items()) if v != 'target_converged'],
                                            'label': f"{new_status.count('target_converged')}/{len(new_status)} target-converged + "
                                                     f"{len(new_status) - new_status.count('target_converged')} prereg-approved capped exception(s)"}
    print(json.dumps(chk, indent=1))
    if max(v for k, v in chk.items() if k.endswith('max_abs')) != 0:
        raise SystemExit('V144 identity failed')
    atomic(chk, OUT + 'tables_check.json')


def joint_structure(st):
    """per stratum: old boards (asserted identical across terminals), shared new prefix S and terminal-only tails."""
    seqs = {n: json.load(open(PANEL[n]))['extension_sequence'] for n in (6, 28)}
    out = {}
    for s in sorted(st[6]['old']):
        assert st[6]['old'][s] == st[28]['old'][s], f'{s}: old 144 boards differ between terminals'
        n6, n28 = st[6]['new'][s], st[28]['new'][s]
        assert seqs[6][s][:len(n6)] == n6 and seqs[28][s][:len(n28)] == n28, f'{s}: new boards are not the drawn sequence prefix'
        short, long_ = (n6, n28) if len(n6) <= len(n28) else (n28, n6)
        assert long_[:len(short)] == short, f'{s}: shorter extension is not a prefix of the longer'
        S = list(short)
        out[s] = {'old': list(st[6]['old'][s]), 'S': S, 'E6': n6[len(S):], 'E28': n28[len(S):]}
        assert not (out[s]['E6'] and out[s]['E28'])
    return out


def joint_draw(rng, J):
    """one replicate: old and S resampled once and shared by both terminals; E6 / E28 resampled separately.
    RNG order per stratum (sorted): old, S, E6, E28."""
    d = {6: ({}, {}), 28: ({}, {})}
    man = {}
    for s in sorted(J):
        j = J[s]
        o = [rng.choice(j['old']) for _ in j['old']]
        sh = [rng.choice(j['S']) for _ in j['S']] if j['S'] else []
        e6 = [rng.choice(j['E6']) for _ in j['E6']] if j['E6'] else []
        e28 = [rng.choice(j['E28']) for _ in j['E28']] if j['E28'] else []
        d[6][0][s], d[6][1][s] = o, sh + e6
        d[28][0][s], d[28][1][s] = o, sh + e28
        man[s] = {'old': o, 'S': sh, 'E6': e6, 'E28': e28}
    return d, man


def solve(d, tabs):
    r = B.solve(d, tabs, save=True)
    r['profile'] = os.path.join(d, 'profile.gtop')
    r['manifest'] = os.path.join(d, 'manifest.json')
    return r


def points(a):
    P = json.load(open(OUT + 'points.json')) if os.path.exists(OUT + 'points.json') else {}
    g144 = json.load(open(E + 'a4b_panel144/paired_results.json'))['points']['V144']
    for n in (6, 28):
        used = json.load(open(E + f'a4b_panel144/points/V144/table_node{n}.json'))
        ref = json.load(open(B.TEMPLATE[144](n)))
        assert [s['gross'] for s in used['seats']] == [s['gross'] for s in ref['seats']], 'A4b G144 point was not solved on table_measured_144'
    P['G144'] = {k: g144[k] for k in ('aggregates', 'gap_total', 'gaps', 'evs', 'profile', 'manifest')}
    if 'Gext' not in P:
        tabs = {n: json.load(open(OUT + f'node{n}/table_ext.json')) for n in (28, 6)}
        P['Gext'] = solve(OUT + 'points/Gext', tabs)
    # structural identity: re-solving G144 into a scratch dir reproduces the stored A4b export exactly
    if 'G144_resolve_identical' not in P:
        tabs = {n: json.load(open(E + f'a4b_panel144/points/V144/table_node{n}.json')) for n in (28, 6)}
        r = solve(OUT + 'points/G144_resolve', tabs)
        P['G144_resolve_identical'] = r['gaps'] == g144['gaps'] and r['evs'] == g144['evs'] and r['aggregates'] == g144['aggregates']
    atomic(P, OUT + 'points.json')
    print('Gext SB raise', round(P['Gext']['aggregates']['SB first-in']['raise_2.5'], 4), 'G144 re-solve identical', P['G144_resolve_identical'])


def swap_metrics(game, gdir, donor, ddir, out_dir, base_reg):
    res = {'seat_dEV': {}, 'own_gap': {}, 'checks': []}
    for name, (seat, root) in SEATS.items():
        s = A.splice(game, donor, seat, root, os.path.join(out_dir, f'swap_{name}.json'))
        res['seat_dEV'][name] = game['evs'][seat] - s['evs'][seat]
        res['own_gap'][name] = game['gaps'][seat]
        res['checks'].append(abs(res['seat_dEV'][name] - (s['gaps'][seat] - game['gaps'][seat])))
        res['checks'].append(abs(s['br_values'][seat] - (game['gaps'][seat] + game['evs'][seat])))
    gn, dn = node_data(gdir), node_data(ddir)
    res['regret_excess'], res['L1'] = {}, {}
    for nd in NODES:
        reg, l1 = regret_l1(gn[nd], {'class_strategy': dn[nd]['s']})
        res['regret_excess'][nd] = reg - base_reg[nd]
        res['L1'][nd] = l1
    res['max_check'] = max(res['checks'])
    del res['checks']
    return res


def boot(a):
    st = setup()
    K = {s: len(v) for s, v in pools().items()}
    P = json.load(open(OUT + 'points.json'))
    gdir = {'G144': E + 'a4b_panel144/points/V144', 'Gext': OUT + 'points/Gext'}
    base = {g: {nd: regret_l1(node_data(gdir[g])[nd], {'class_strategy': node_data(gdir[g])[nd]['s']})[0] for nd in NODES} for g in gdir}
    path = OUT + 'boot.json'
    R = json.load(open(path)) if os.path.exists(path) else {'base_regret': base, 'reps': {}}
    ref = {n: {'144': stratum_means(st[n]['vals'], st[n]['compat'], st[n]['old']), 'ext': stratum_means(st[n]['vals'], st[n]['compat'], st[n]['all'])} for n in (6, 28)}
    lam = {n: {'144': {s: math.sqrt((1 - 12 / K[s]) * 12 / 11) for s in st[n]['old']},
               'ext': {s: math.sqrt((1 - len(st[n]['all'][s]) / K[s]) * len(st[n]['all'][s]) / (len(st[n]['all'][s]) - 1)) for s in st[n]['old']}} for n in (6, 28)}
    # amendment 1 (a4c/prereg_amendment_1.json): covariance-preserving joint draw across terminals
    J = joint_structure(st)
    rng = random.Random(20261005)
    draws, manifest = [], []
    for _ in range(a.reps):
        d, man = joint_draw(rng, J)
        draws.append(d)
        manifest.append(man)
    mtext = json.dumps(manifest, sort_keys=True)
    mpath = OUT + 'boot_draw_manifest.json'
    if os.path.exists(mpath):
        assert json.load(open(mpath))['sha256'] == hashlib.sha256(mtext.encode()).hexdigest(), 'draw manifest changed'
    else:
        atomic({'sha256': hashlib.sha256(mtext.encode()).hexdigest(), 'seed': 20261005, 'rng_order': 'per replicate, per stratum sorted: old, S, E6, E28', 'draws': manifest}, mpath)
    for i, d in enumerate(draws, 1):
        k = str(i)
        if k in R['reps'] and 'done' in R['reps'][k]:
            continue
        rep = R['reps'].get(k, {})
        rd = OUT + f'boot/r{i:02d}/'
        for size in ('144', 'ext'):
            if size in rep:
                continue
            tabs = {}
            for n in (28, 6):
                o, w = d[n]
                dr = o if size == '144' else {s: o[s] + w[s] for s in o}
                g = estimate(st[n]['vals'], st[n]['compat'], dr, st[n]['p_str'], lam[n][size], ref[n][size])
                tabs[n] = table_json(n, g, f'A4c bootstrap replicate {i} ({size})')
            rep[size] = solve(rd + size, tabs)
            R['reps'][k] = rep
            atomic(R, path)
        # panel-error estimate: sigma_N*_r into the point game G_N; continuity: cross swaps into the replicate games
        rep['err144'] = swap_metrics(P['G144'], gdir['G144'], rep['144'], rd + '144', rd + 'err144', base['G144'])
        rep['errext'] = swap_metrics(P['Gext'], gdir['Gext'], rep['ext'], rd + 'ext', rd + 'errext', base['Gext'])
        b144 = {nd: regret_l1(node_data(rd + '144')[nd], {'class_strategy': node_data(rd + '144')[nd]['s']})[0] for nd in NODES}
        bext = {nd: regret_l1(node_data(rd + 'ext')[nd], {'class_strategy': node_data(rd + 'ext')[nd]['s']})[0] for nd in NODES}
        rep['s144_to_Gext_r'] = swap_metrics(rep['ext'], rd + 'ext', rep['144'], rd + '144', rd + 's144_to_Gext', bext)
        rep['sext_to_G144_r'] = swap_metrics(rep['144'], rd + '144', rep['ext'], rd + 'ext', rd + 'sext_to_G144', b144)
        rep['done'] = True
        R['reps'][k] = rep
        atomic(R, path)
        print('rep', i, 'errext seat', {s: round(x, 5) for s, x in rep['errext']['seat_dEV'].items()}, flush=True)


def lobo(a):
    """Kc9h9d leave-one-board-out (a4c/lobo_Kc9h9d_plan.json): secondary, diagnostic only; primary results unchanged."""
    import a4c_analyze as AN
    st = setup()
    P = json.load(open(OUT + 'points.json'))
    out_path = OUT + 'lobo_Kc9h9d.json'
    S6 = st[6]
    assert 'Kc9h9d' in S6['all']['paired/KQ'] and all('Kc9h9d' not in v for v in st[28]['all'].values())
    dr = {s: [b for b in bs if b != 'Kc9h9d'] for s, bs in S6['all'].items()}
    assert len(dr['paired/KQ']) == 16 and all(dr[s] == S6['all'][s] for s in dr if s != 'paired/KQ')
    g = estimate(S6['vals'], S6['compat'], dr, S6['p_str'])
    tabs = {6: table_json(6, g, 'A4c LOBO Kc9h9d (diagnostic)'), 28: json.load(open(OUT + 'node28/table_ext.json'))}
    gd, ld = OUT + 'points/Gext', OUT + 'points/Gext_lobo_Kc9h9d'
    R = json.load(open(out_path)) if os.path.exists(out_path) else {}
    if 'point' not in R:
        R['point'] = solve(ld, tabs)
        atomic(R, out_path)
    L, G = R['point'], P['Gext']
    gn = node_data(gd)
    base = {nd: regret_l1(gn[nd], {'class_strategy': gn[nd]['s']})[0] for nd in NODES}
    sw = swap_metrics(G, gd, L, ld, OUT + 'points/lobo_swaps', base)
    hl = AN.hand_level(gd, ld)
    agg = {nd: {k: L['aggregates'][nd][k] - G['aggregates'][nd][k] for k in G['aggregates'][nd]} for nd in G['aggregates']}
    R['diagnostic'] = {'plan': 'a4c/lobo_Kc9h9d_plan.json', 'aggregates_lobo_minus_Gext': agg,
                       'seat_ev_lobo_minus_Gext': {nm: L['evs'][seat] - G['evs'][seat] for nm, (seat, _) in SEATS.items()},
                       'seat_swap_dEV_lobo_into_Gext': sw['seat_dEV'], 'regret_excess_lobo_in_Gext': sw['regret_excess'], 'L1': sw['L1'],
                       'max_check': sw['max_check'],
                       'argmax_switch': {nd: {'count': sum(1 for c in hl[nd]['classes'] if c['argmax_switch']), 'reach_share': hl[nd]['reach_weighted']['argmax_switch_share']} for nd in hl},
                       'note': 'practical sensitivity of the whole board, not a bound on its solver residual; primary results and panel unchanged'}
    atomic(R, out_path)
    print(json.dumps(R['diagnostic'], indent=1))


def margdiag(a):
    """amendment-1 marginal diagnostic (diagnostic only; registered before any Vext/point/bootstrap result, changes nothing).
    Exact (analytic) with-replacement bootstrap variance of each table cell under (i) the amendment-1 scheme (old, S, E resampled
    separately) and (ii) one pool of all new boards per terminal; FPC lambda_ext applied identically to both. Cell value
    y_b = compat * gross (None counted as 0, as in estimate()). Ratios: split / pooled, for the whole ext table and for its new part."""
    K = {s: len(v) for s, v in pools().items()}
    if a.partial:   # code check only: restrict to boards that already have artifacts; output to the scratch path given
        avail = lambda n, bs: [b for b in bs if any(os.path.exists(d + b + '.json') for d in FLOP_DIRS[n])]
        st = {}
        for n in (6, 28):
            p, old, new = panel(n)
            new = {s: avail(n, v) for s, v in new.items()}
            bs = [b for v in list(old.values()) + list(new.values()) for b in v]
            st[n] = {'old': old, 'new': new, 'p_str': {s: v['probability'] for s, v in p['strata'].items()}, 'vals': load_values(n, bs), 'compat': compat_of(bs)}
        Jp = joint_structure({n: {'old': panel(n)[1], 'new': panel(n)[2]} for n in (6, 28)})
        J = {s: {k: [b for b in v if all(b in st[n]['vals'] for n in ((6, 28) if k in ('old', 'S') else ((6,) if k == 'E6' else (28,))))]
                 for k, v in j.items()} for s, j in Jp.items()}
        J = {s: {**j, 'S6': [b for b in Jp[s]['S'] if b in st[6]['vals']], 'S28': [b for b in Jp[s]['S'] if b in st[28]['vals']]} for s, j in J.items()}
    else:
        st = setup()
        J = joint_structure(st)
    pvar = lambda xs: sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / len(xs) if xs else 0.0
    out = {'definition': margdiag.__doc__, 'partial_code_check': bool(a.partial), 'terminals': {}}
    for n in (6, 28):
        S_ = st[n]
        P = sum(S_['p_str'].values())
        term = json.load(open(A3 + f'k14/terminal_node{n}.json'))
        reach = {pl['position']: pl['class_reach_normalized'] for pl in term['players']}
        pos_list = list(next(iter(S_['vals'].values())).keys())
        def y(b, pos, h):
            v = S_['vals'][b][pos][h]
            return S_['compat'][b][h] * v if v is not None else 0.0
        def yr(b):
            return sum(reach[pos][h] * y(b, pos, h) for pos in pos_list for h in range(169))
        def var_parts(f):
            tot_split = tot_pool = new_split = new_pool = 0.0
            for s in S_['old']:
                old, newb = S_['old'][s], S_['new'][s]
                m = len(old) + len(newb)
                lam2 = (1 - m / K[s]) * m / (m - 1) if m > 1 else 0.0
                w2 = (S_['p_str'][s] / P / RHO) ** 2 * lam2 / m ** 2
                vo = len(old) * pvar([f(b) for b in old])
                tail = J[s]['E6'] if n == 6 else J[s]['E28']
                Sn = J[s].get(f'S{n}', J[s]['S'])   # partial check: S boards available for this terminal
                vs = len(Sn) * pvar([f(b) for b in Sn]) + len(tail) * pvar([f(b) for b in tail])
                assert sorted(Sn + tail) == sorted(newb)
                vp = len(newb) * pvar([f(b) for b in newb])
                tot_split += w2 * (vo + vs)
                tot_pool += w2 * (vo + vp)
                new_split += w2 * vs
                new_pool += w2 * vp
            return tot_split, tot_pool, new_split, new_pool
        cells = {'table': [], 'new_part': []}
        zero = 0
        for pos in pos_list:
            for h in range(169):
                ts, tp, ns, np_ = var_parts(lambda b: y(b, pos, h))
                if tp <= 0 or np_ <= 0:
                    zero += 1
                    continue
                cells['table'].append(ts / tp)
                cells['new_part'].append(ns / np_)
        def summ(xs):
            if not xs:
                return {'cells': 0}
            xs = sorted(xs)
            q = lambda f: xs[min(len(xs) - 1, int(f * (len(xs) - 1) + 0.5))]
            return {'cells': len(xs), 'median': q(0.5), 'q05': q(0.05), 'q95': q(0.95), 'min': xs[0], 'max': xs[-1]}
        ts, tp, ns, np_ = var_parts(yr)
        out['terminals'][str(n)] = {'cell_variance_ratio_split_over_pooled': {k: summ(v) for k, v in cells.items()}, 'cells_skipped_zero_variance': zero,
                                    'reach_weighted_value': {'var_split': ts, 'var_pooled': tp, 'ratio_table': ts / tp if tp else None, 'ratio_new_part': ns / np_ if np_ else None}}
    dest = a.out or OUT + 'marginal_diagnostic.json'
    atomic(out, dest)
    print(json.dumps(out['terminals'], indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['tables', 'points', 'boot', 'analyze', 'margdiag', 'lobo'])
    ap.add_argument('--partial', action='store_true')
    ap.add_argument('--out')
    ap.add_argument('--reps', type=int, default=60)
    a = ap.parse_args()
    if a.cmd == 'analyze':
        import a4c_analyze
        a4c_analyze.main()
    else:
        {'tables': tables, 'points': points, 'boot': boot, 'margdiag': margdiag, 'lobo': lobo}[a.cmd](a)
