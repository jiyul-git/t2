#!/usr/bin/env python3
"""Undamped outer fixed point for the HU continuation prototype.

    python3 tools/gto_hu_continuation/outer_loop.py --out data/gto_hu_continuation/outer_v1 --max-outer 4

P0 = preflop solve with the existing payoff; V0 = panel continuation at P0's arriving ranges;
P1 = preflop solve with V0 injected at the one terminal; V1 = panel at P1's ranges; ...
No damping (decision C0/C4): oscillation is observed first; under-relaxation would be a
separate, explicitly labelled A/B run.
Per outer step it records: max class-frequency change at the first-in nodes and at the
terminal's parent (BB response), range L1/L2 distance of both arriving ranges, value change
of the table (max/mean |dV|, and relative to the bootstrap CI), preflop gap, postflop
exploitability (max/mean over the panel), and the table's unallocated chips.
Every step is resumable: finished files are reused only through the same provenance checks
the tools already enforce.
"""
import argparse
import json
import math
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.environ.get('T2_BIN_DIR', '')


def run(cmd, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, env={**os.environ, **(env or {})})


def class_strats(t):
    out = {}
    for k, v in t['frequencies'].items():
        out[k] = v['class_strategy']
    return out


def metrics(prev_t, cur_t, prev_v, cur_v):
    m = {'preflop_gap_total': cur_t['gap_total']}
    # aggregate mixes
    m['mix'] = {k: v['mix'] for k, v in cur_t['frequencies'].items()}
    if prev_t is not None:
        ps, cs = class_strats(prev_t), class_strats(cur_t)
        dmax = {}
        for k in cs:
            if k in ps and len(ps[k]) == len(cs[k]):
                dmax[k] = max(abs(a - b) for pa, ca in zip(ps[k], cs[k]) for a, b in zip(pa, ca))
        m['max_class_frequency_delta'] = dmax
        m['max_class_frequency_delta_all'] = max(dmax.values())
        agg = {}
        for k, v in cur_t['frequencies'].items():
            if k in prev_t['frequencies']:
                pm = prev_t['frequencies'][k]['mix']
                agg[k] = max(abs(v['mix'][a] - pm.get(a, 0.0)) for a in v['mix'])
        m['max_aggregate_frequency_delta'] = agg
        rd = {}
        for pp, cp in zip(prev_t['players'], cur_t['players']):
            a, b = pp['class_reach_normalized'], cp['class_reach_normalized']
            rd[cp['position']] = {'L1': sum(abs(x - y) for x, y in zip(a, b)),
                                  'L2': math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))}
        m['range_distance'] = rd
    if prev_v is not None and cur_v is not None:
        vd = {}
        for ps_, cs_ in zip(prev_v['seats'], cur_v['seats']):
            d = [abs(x - y) for x, y in zip(ps_['gross'], cs_['gross'])]
            hw = [(h - l) / 2 for l, h in zip(cs_['gross_ci95_lo'], cs_['gross_ci95_hi'])]
            vd[cs_['position']] = {'max_abs_dV_bb': max(d), 'mean_abs_dV_bb': sum(d) / len(d),
                                   'share_of_classes_dV_gt_ci_halfwidth': sum(1 for x, w in zip(d, hw) if x > w) / len(d)}
        m['value_delta'] = vd
    if cur_v is not None:
        m['postflop_exploitability_pct_pot'] = {'max': cur_v['provenance']['exploitability_pct_pot_max'],
                                                'mean': cur_v['provenance']['exploitability_pct_pot_mean']}
        m['table_unallocated_bb'] = cur_v['invariant']['unallocated_bb']
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-outer', type=int, default=4)
    ap.add_argument('--config', default=os.path.join(ROOT, 'data/gto_hu_continuation/cfg_4h_mr4_30bb.json'))
    ap.add_argument('--menu', default=os.path.join(ROOT, 'data/gto_hu_continuation/menu_m2_single_v1.json'))
    ap.add_argument('--panel', default=os.path.join(ROOT, 'data/gto_hu_continuation/panel_v1.json'))
    ap.add_argument('--preflop-iters', default='400')
    ap.add_argument('--postflop', nargs=3, default=['1000', '0.3', '25'], metavar=('MAX_ITERS', 'TARGET_PCT', 'EVERY'))
    ap.add_argument('--boot', default='2000')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    env = {'PREFLOP_EQ_SEED': '202', 'PREFLOP_MULTIWAY_SEED': '202', 'PREFLOP_EQ_SAMPLES': '1200'}
    commit = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    log_path = os.path.join(a.out, 'outer_log.json')
    log = json.load(open(log_path)) if os.path.exists(log_path) else {'steps': []}
    prev_t = prev_v = None
    for k in range(a.max_outer + 1):
        d = os.path.join(a.out, f'k{k}')
        os.makedirs(d, exist_ok=True)
        term = os.path.join(d, 'terminal.json')
        table_in = os.path.join(a.out, f'k{k-1}', 'table.json') if k > 0 else None
        if not os.path.exists(term):
            e = dict(env)
            if table_in:
                e['T2_CONT_FILE'] = table_in
            run([os.path.join(BIN, 't2_cont_terminal'), a.config, a.preflop_iters, 'fold,raise,fold,call', term], e)
        cur_t = json.load(open(term))
        if table_in and cur_t.get('t2_cont_file') != table_in:
            raise SystemExit(f'k{k}: terminal was solved with {cur_t.get("t2_cont_file")}, expected {table_in}')
        table = os.path.join(d, 'table.json')
        if not os.path.exists(table):
            run([os.path.join(BIN, 't2_cont_panel'), term, a.menu, a.panel, os.path.join(d, 'flops'), *a.postflop],
                {'T2_SOURCE_COMMIT': commit})
            run(['python3', os.path.join(ROOT, 'tools/gto_hu_continuation/aggregate.py'), term, a.panel,
                 os.path.join(d, 'flops'), table, '--outer', str(k), '--boot', a.boot])
        cur_v = json.load(open(table))
        step = {'k': k, 'metrics': metrics(prev_t, cur_t, prev_v, cur_v), 'injected_table': table_in,
                'ranges_hash': cur_t['ranges_hash_fnv1a64']}
        log['steps'] = [s for s in log['steps'] if s['k'] != k] + [step]
        json.dump(log, open(log_path, 'w'), indent=1)
        mm = step['metrics']
        print(f"k{k}: gap {mm['preflop_gap_total']:.5f} "
              f"maxdF {mm.get('max_class_frequency_delta_all', float('nan')):.4f} "
              f"BBmix {mm['mix'].get('terminal_parent')} unalloc {mm.get('table_unallocated_bb'):.4f}", flush=True)
        prev_t, prev_v = cur_t, cur_v


if __name__ == '__main__':
    main()
