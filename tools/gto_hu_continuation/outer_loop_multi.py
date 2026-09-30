#!/usr/bin/env python3
"""Synchronous multi-terminal damped outer fixed point (A3).

    python3 tools/gto_hu_continuation/outer_loop_multi.py --out data/gto_terminal_expansion/outer_m28_6 \
        --terminal 28=fold,raise,fold,call --terminal 6=fold,fold,raise,call \
        --init 28=data/gto_hu_continuation/panel72/outer_v2_damped_a05/k9/table.json \
        --init 6=data/gto_terminal_expansion/node6_72/table72.json --k0 9 --steps 3

M_k = manifest of the injected tables (one per terminal). One outer step k -> k+1:
  1. P_{k+1}: preflop solve with T2_CONT_FILE = M_k; every terminal's arriving ranges are exported
     from the SAME solve state (one t2_cont_terminal run per terminal; the runs must agree bit for bit
     on gaps / evs / first-in frequencies, else the step stops);
  2. census of all flop-reaching terminals with the same manifest (reach of 28 / 6 / 46 / 246 ...);
  3. per terminal: the 72-flop panel at its P_{k+1} ranges (solve_panel.py), aggregate.py
     (ht_rho, B = 2000, guard 0.05 bb; if rejected, the J1/J2 fixed normaliser from the same ranges,
     the rejection kept);
  4. V_used = alpha * V_measured + (1 - alpha) * V_used(previous step), guard-checked at P_{k+1};
     M_{k+1} = manifest of the V_used tables.
No terminal is updated before another: all ranges come from P_{k+1}, all tables enter M_{k+1} together.
Resumable: finished files are reused only through the provenance checks of the tools.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.environ.get('T2_BIN_DIR', os.path.join(ROOT, 'vendor/gtopen/target/release/examples'))
PANEL = os.path.join(ROOT, 'data/gto_hu_continuation/panel_v2_72.json')
MENU = os.path.join(ROOT, 'data/gto_hu_continuation/menu_m2_single_v1.json')
CFG = os.path.join(ROOT, 'data/gto_hu_continuation/cfg_4h_mr4_30bb.json')
ENV = {'PREFLOP_EQ_SEED': '202', 'PREFLOP_MULTIWAY_SEED': '202', 'PREFLOP_EQ_SAMPLES': '1200'}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import class_combos, parse_board  # noqa: E402


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env={**os.environ, **ENV, **(env or {})})


def manifest(path, tables):
    json.dump({'schema': 't2_hu_continuation_manifest_v1',
               'tables': [{'file': os.path.abspath(tables[n])} for n in sorted(tables)]}, open(path, 'w'), indent=1)


def fixed_norm_panel(term, out):
    p = json.load(open(PANEL))
    combos = [class_combos(l) for l in term['class_labels']]
    st = {}
    for f in p['panel']:
        st.setdefault(f['stratum'], []).append(f)
    norm = {}
    for pl in term['players']:
        r = pl['class_reach_normalized']
        tot = 0.0
        for s, fs in st.items():
            for f in fs:
                bc = parse_board(f['board'])
                c = [sum(1 for x in cc if x[0] not in bc and x[1] not in bc) / len(cc) for cc in combos]
                tot += p['strata'][s]['probability'] / len(fs) * sum(r[h] * c[h] for h in range(169))
        norm[pl['position']] = tot
    p['fixed_normaliser'] = norm
    json.dump(p, open(out, 'w'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--terminal', action='append', required=True, help='node=path-spec')
    ap.add_argument('--init', action='append', required=True, help='node=table.json used for M_k0')
    ap.add_argument('--init-measured', action='append', default=[], help='node=measured table at P_k0 (for the first step change)')
    ap.add_argument('--init-terminal', action='append', default=[], help='node=terminal export at P_k0 (for the first range L1)')
    ap.add_argument('--k0', type=int, required=True)
    ap.add_argument('--steps', type=int, default=3)
    ap.add_argument('--alpha', type=float, default=0.5)
    ap.add_argument('--workers', default='4')
    ap.add_argument('--threads', default='1')
    ap.add_argument('--preflop-only-final', action='store_true', help='also solve P_{k0+steps+1} (no panel)')
    a = ap.parse_args()
    terms = dict(x.split('=', 1) for x in a.terminal)
    init = dict(x.split('=', 1) for x in a.init)
    assert set(terms) == set(init)
    os.makedirs(a.out, exist_ok=True)
    k0 = a.k0
    d0 = os.path.join(a.out, f'k{k0}')
    os.makedirs(d0, exist_ok=True)
    used = {}
    for n, src in init.items():
        dst = os.path.join(d0, f'used_node{n}.json')
        if not os.path.exists(dst):
            shutil.copy(src, dst)
        used[n] = dst
    man = os.path.join(d0, 'manifest.json')
    if not os.path.exists(man):
        manifest(man, used)
    log_path = os.path.join(a.out, 'loop_log.json')
    log = json.load(open(log_path)) if os.path.exists(log_path) else {'k0': k0, 'init': init, 'terminals': terms, 'steps': []}
    prev_meas = {n: json.load(open(p_)) for n, p_ in (x.split('=', 1) for x in a.init_measured)}
    prev_terms = {n: json.load(open(p_)) for n, p_ in (x.split('=', 1) for x in a.init_terminal)}
    last = k0 + a.steps + (1 if a.preflop_only_final else 0)
    for k in range(k0 + 1, last + 1):
        d = os.path.join(a.out, f'k{k}')
        os.makedirs(d, exist_ok=True)
        man_in = os.path.join(a.out, f'k{k - 1}', 'manifest.json')
        # 1. preflop P_k and exports
        tj = {}
        for n, spec in terms.items():
            out = os.path.join(d, f'terminal_node{n}.json')
            if not os.path.exists(out):
                run([os.path.join(BIN, 't2_cont_terminal'), CFG, '400', spec, out], {'T2_CONT_FILE': man_in})
            tj[n] = json.load(open(out))
            assert tj[n]['t2_cont_file'] == man_in, f'k{k} node {n}: solved with {tj[n]["t2_cont_file"]}'
        ref = next(iter(tj.values()))
        for n, t in tj.items():
            same = t['gaps'] == ref['gaps'] and t['evs'] == ref['evs'] and t['frequencies']['rfi_CO'] == ref['frequencies']['rfi_CO'] \
                and t['frequencies']['rfi_BTN'] == ref['frequencies']['rfi_BTN'] and t['frequencies']['rfi_SB'] == ref['frequencies']['rfi_SB']
            if not same:
                raise SystemExit(f'k{k}: terminal exports disagree on the preflop state (node {n})')
        # 2. census
        cen = os.path.join(d, 'census.json')
        if not os.path.exists(cen):
            run([os.path.join(BIN, 't2_cont_census'), CFG, '400', cen], {'T2_CONT_FILE': man_in})
        census = json.load(open(cen))
        assert census['gap_total'] == ref['gap_total']
        reach = {r['terminal_node']: r for r in census['terminals']}
        step = {'k': k, 'manifest_in': man_in, 'gap_total': ref['gap_total'],
                'frequencies': {'rfi_CO': ref['frequencies']['rfi_CO']['mix'], 'rfi_BTN': ref['frequencies']['rfi_BTN']['mix'],
                                'rfi_SB': ref['frequencies']['rfi_SB']['mix']},
                'bb_response': {n: tj[n]['frequencies']['terminal_parent']['mix'] for n in tj},
                'reach': {str(x): (reach[x]['reach_probability'] if x in reach else None) for x in (28, 6, 46, 246, 228)},
                'flop_share': {str(x): (reach[x]['share_of_flop_reach'] if x in reach else None) for x in (28, 6, 46, 246, 228)},
                'hu_share_of_flop_reach': census['summary']['hu_share_of_flop_reach'],
                'ranges_hash': {n: tj[n]['ranges_hash_fnv1a64'] for n in tj}, 'terminals': {}}
        if k == last and a.preflop_only_final:
            log['steps'] = [s for s in log['steps'] if s['k'] != k] + [step]
            json.dump(log, open(log_path, 'w'), indent=1)
            print(f'k{k}: preflop only', flush=True)
            break
        # 3. panels and measured tables
        new_used = {}
        for n, t in tj.items():
            fd = os.path.join(d, f'node{n}', 'flops')
            meas = os.path.join(d, f'node{n}', 'table_measured.json')
            if not os.path.exists(meas):
                run(['python3', os.path.join(ROOT, 'tools/gto_hu_continuation/solve_panel.py'), os.path.join(d, f'terminal_node{n}.json'),
                     MENU, PANEL, fd, '--workers', a.workers, '--threads', a.threads])
                r = subprocess.run(['python3', os.path.join(ROOT, 'tools/gto_hu_continuation/aggregate.py'), os.path.join(d, f'terminal_node{n}.json'),
                                    PANEL, fd, meas, '--outer', str(k), '--boot', '2000'], env={**os.environ, **ENV})
                if r.returncode != 0:
                    # pre-registered fallback: J1/J2 fixed normaliser from these ranges (rejection file kept)
                    fp = os.path.join(d, f'node{n}', 'panel_fixed_norm.json')
                    fixed_norm_panel(t, fp)
                    run(['python3', os.path.join(ROOT, 'tools/gto_hu_continuation/aggregate.py'), os.path.join(d, f'terminal_node{n}.json'),
                         fp, fd, meas, '--outer', str(k), '--boot', '2000', '--estimator', 'fixed_norm'])
            vm = json.load(open(meas))
            vp = json.load(open(used[n]))
            vb = json.loads(json.dumps(vm))
            for sb, so in zip(vb['seats'], vp['seats']):
                assert sb['position'] == so['position']
                for fld in ('gross', 'gross_ci95_lo', 'gross_ci95_hi', 'gross_br'):
                    sb[fld] = [a.alpha * x + (1 - a.alpha) * y for x, y in zip(sb[fld], so[fld])]
            tot = sum(sum(pl['class_reach_normalized'][h] * next(x for x in vb['seats'] if x['position'] == pl['position'])['gross'][h]
                          for h in range(169)) for pl in t['players'])
            vb['invariant'] = {'sum_range_weighted_gross': tot, 'pot': t['pot_bb'], 'unallocated_bb': t['pot_bb'] - tot,
                               'note': 'blended table at this step\'s arriving ranges'}
            vb['damping'] = {'alpha': a.alpha, 'measured': meas, 'previous_used': used[n]}
            if abs(vb['invariant']['unallocated_bb']) > 0.05:
                raise SystemExit(f'k{k} node {n}: blended table unallocated {vb["invariant"]["unallocated_bb"]:.4f} bb exceeds guard')
            un = os.path.join(d, f'used_node{n}.json')
            json.dump(vb, open(un, 'w'))
            new_used[n] = un
            row = {'measured_unallocated_bb': vm['invariant']['unallocated_bb'], 'used_unallocated_bb': vb['invariant']['unallocated_bb'],
                   'estimator': vm.get('estimator'), 'ci_halfwidth_mean': {s['position']: s['mean_ci95_halfwidth_bb'] for s in vm['seats']},
                   'expl_max_pct_pot': vm['provenance']['exploitability_pct_pot_max'], 'expl_mean_pct_pot': vm['provenance']['exploitability_pct_pot_mean']}
            if n in prev_meas:
                row['measured_change'] = {s['position']: {'mean_abs': sum(abs(x - y) for x, y in zip(s['gross'], o['gross'])) / 169,
                                                           'max_abs': max(abs(x - y) for x, y in zip(s['gross'], o['gross']))}
                                          for s, o in zip(vm['seats'], prev_meas[n]['seats'])}
            if n in prev_terms:
                row['range_L1'] = {p['position']: sum(abs(x - y) for x, y in zip(p['class_reach_normalized'], q['class_reach_normalized']))
                                   for p, q in zip(t['players'], prev_terms[n]['players'])}
            step['terminals'][n] = row
            prev_meas[n] = vm
        prev_terms = {**prev_terms, **tj}
        used = new_used
        man = os.path.join(d, 'manifest.json')
        manifest(man, used)
        log['steps'] = [s for s in log['steps'] if s['k'] != k] + [step]
        json.dump(log, open(log_path, 'w'), indent=1)
        print(f"k{k}: gap {step['gap_total']:.5f} reach {step['reach']} terminals {json.dumps(step['terminals'])[:400]}", flush=True)


if __name__ == '__main__':
    main()
