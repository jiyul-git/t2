#!/usr/bin/env python3
"""A4b per amendment 2 (data/gto_terminal_expansion/a4b_panel144/prereg_amendment_2.json).

    python3 tools/gto_hu_continuation/a4b_paired.py run [--reps 60]
    python3 tools/gto_hu_continuation/a4b_paired.py analyze

Primary: D = g(V144) - g(V72), V = measured tables at the P14 ranges, g = frozen-table preflop solve.
Nested paired bootstrap: per stratum old (6 panel_v2_72 boards) and new (6 extension boards) are resampled
separately; V72* uses old* only, V144* uses old* + new*, D* = g(V144*) - g(V72*).
Secondary (A3 process, point only): g(M144) - P15 and staleness g(V72) - P15.
Every solve saves its .gtop profile (input to A4R; *.gtop is not committed, re-solves are deterministic).
"""
import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4b_panel144 as B  # noqa: E402
from analyze_a3 import MAIN  # noqa: E402

OUT = B.OUT
KEY_NODES = {6: {'SB first-in': 'SB@2', 'BB vs SB': 'BB@4'}, 28: {'BTN first-in': 'BTN@1', 'BB vs BTN': 'BB@26', 'SB vs BTN': 'SB@25'}}


def groups(size):
    panel = json.load(open(B.PANELS[144]))
    old, new = {}, {}
    for f in panel['panel']:
        (old if f.get('in_parent_v2_72') else new).setdefault(f['stratum'], []).append(f['board'])
    return old, new


def solve(d, tabs):
    r = B.solve(d, tabs, save=True)
    keep = {}
    for n, nodes in KEY_NODES.items():
        t = json.load(open(os.path.join(d, f'terminal_node{n}.json')))
        for name, tag in nodes.items():
            pn = next(p for p in t['path_nodes'] if f"{p['actor']}@{p['node']}" == tag)
            keep[name] = {'actions': pn['actions'], 'class_strategy': pn['class_strategy'], 'class_reach_before': pn['class_reach_before']}
    r['key_nodes'] = keep
    r['profile'] = os.path.join(d, 'profile.gtop')
    r['manifest'] = os.path.join(d, 'manifest.json')
    return r


def unalloc(tabs):
    return {n: B.unallocated(n, {s['position']: s['gross'] for s in tabs[n]['seats']}) for n in tabs}


def run(a):
    path = OUT + 'paired_results.json'
    R = json.load(open(path)) if os.path.exists(path) else {}
    def save():
        json.dump(R, open(path + '.tmp', 'w'))
        os.replace(path + '.tmp', path)
    strata, p_str, compat = B.load_panel(144)
    vals = {n: B.flop_values(n, strata) for n in (28, 6)}
    old, new = groups(144)
    # identity: V72 from the old group equals the k14 measured table; V144 from all boards equals table_measured_144
    ident = {}
    for n in (28, 6):
        for size, draw in ((72, old), (144, {s: old[s] + new[s] for s in old})):
            t = B.table(n, draw, vals[n], p_str, compat)
            ref = {s['position']: s['gross'] for s in json.load(open(B.TEMPLATE[size](n)))['seats']}
            ident[f'V{size}_node{n}'] = max(abs(x - y) for p in ref for x, y in zip(ref[p], t[p]))
    print('identity |d|:', ident, flush=True)
    if max(ident.values()) > 1e-9:
        raise SystemExit('identity estimate does not reproduce the measured tables')
    R['identity'] = ident
    # points
    pts = {'V72': {n: json.load(open(B.TEMPLATE[72](n))) for n in (28, 6)},
           'V144': {n: json.load(open(B.TEMPLATE[144](n))) for n in (28, 6)}}
    rule = {}
    m144 = {}
    for n in (28, 6):
        m144[n], rule[n] = B.a3_rule(n, pts['V144'][n])
        if rule[n]['hard_stop']:
            raise SystemExit(f'M144 node {n}: measured table also fails the guard')
    pts['M144'] = m144
    R.setdefault('points', {})
    for k, tabs in pts.items():
        if k not in R['points']:
            R['points'][k] = {**solve(OUT + f'points/{k}', tabs), 'unallocated': unalloc(tabs)}
            if k == 'M144':
                R['points'][k]['rule'] = rule
            save()
        print(k, 'SB raise', round(R['points'][k]['aggregates']['SB first-in']['raise_2.5'], 4), flush=True)
    if 'P15' not in R['points']:
        rv = OUT + 'review/F72_identity/'
        t6, t28 = (json.load(open(rv + f'terminal_node{n}.json')) for n in (6, 28))
        from a4_audit import aggregates
        keep = {}
        for n, t in ((6, t6), (28, t28)):
            for name, tag in KEY_NODES[n].items():
                pn = next(p for p in t['path_nodes'] if f"{p['actor']}@{p['node']}" == tag)
                keep[name] = {'actions': pn['actions'], 'class_strategy': pn['class_strategy'], 'class_reach_before': pn['class_reach_before']}
        R['points']['P15'] = {'aggregates': aggregates(t28, t6), 'gap_total': t6['gap_total'], 'gaps': t6['gaps'], 'evs': t6['evs'],
                              'key_nodes': keep, 'profile': rv + 'profile.gtop', 'manifest': rv + 'manifest.json'}
        save()
    # nested paired bootstrap
    rng = random.Random(20261001)
    draws = []
    for _ in range(a.reps):
        o, w = {}, {}
        for s in sorted(old):
            o[s] = [rng.choice(old[s]) for _ in old[s]]
            w[s] = [rng.choice(new[s]) for _ in new[s]]
        draws.append((o, w))
    R.setdefault('boot', {})
    for i, (o, w) in enumerate(draws, 1):
        k = str(i)
        rep = R['boot'].get(k, {})
        for size, draw in ((72, o), (144, {s: o[s] + w[s] for s in o})):
            if f'V{size}' in rep:
                continue
            tabs = {n: B.with_gross(n, size, B.table(n, draw, vals[n], p_str, compat)) for n in (28, 6)}
            rep[f'V{size}'] = {**solve(OUT + f'boot/r{i:02d}/V{size}', tabs), 'unallocated': unalloc(tabs)}
            R['boot'][k] = rep
            save()
        print('boot', i, 'D SB raise', round(rep['V144']['aggregates']['SB first-in']['raise_2.5'] - rep['V72']['aggregates']['SB first-in']['raise_2.5'], 4), flush=True)
    save()


def analyze(a):
    R = json.load(open(OUT + 'paired_results.json'))
    P = R['points']
    reps = [r for r in R['boot'].values() if 'V72' in r and 'V144' in r]
    sd = lambda xs: (sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
    rows = []
    for nm, (_, acts) in MAIN.items():
        for ac in acts:
            g = lambda r, k: r[k]['aggregates'][nm][ac]
            D = g(P, 'V144') - g(P, 'V72')
            Ds = [g(r, 'V144') - g(r, 'V72') for r in reps]
            x144 = [g(r, 'V144') for r in reps]
            x72 = [g(r, 'V72') for r in reps]
            rows.append({'aggregate': nm, 'action': ac, 'V72': g(P, 'V72'), 'V144': g(P, 'V144'), 'P15': g(P, 'P15'), 'M144': g(P, 'M144'),
                         'D': D, 'D_boot_mean': sum(Ds) / len(Ds), 'D_boot_sd': sd(Ds), 'D_boot_lo': q(Ds, 0.025), 'D_boot_hi': q(Ds, 0.975),
                         'bias_estimate': sum(Ds) / len(Ds) - D, 'D_bias_corrected': 2 * D - sum(Ds) / len(Ds),
                         'h72': (q(x72, 0.975) - q(x72, 0.025)) / 2, 'h144': (q(x144, 0.975) - q(x144, 0.025)) / 2, 'sd72': sd(x72), 'sd144': sd(x144),
                         'secondary_M144_minus_P15': g(P, 'M144') - g(P, 'P15'), 'staleness_V72_minus_P15': g(P, 'V72') - g(P, 'P15')})
    act = [r for r in rows if r['D_boot_sd'] > 1e-4]
    T = []
    for r_i, rep in enumerate(reps):
        T.append(max(abs((rep['V144']['aggregates'][r['aggregate']][r['action']] - rep['V72']['aggregates'][r['aggregate']][r['action']]) - r['D_boot_mean'])
                     / r['D_boot_sd'] for r in act))
    c = q(T, 0.95)
    m = len(act)
    zb = _phi_inv(1 - 0.05 / (2 * m))
    for r in rows:
        r['z'] = r['D'] / r['D_boot_sd'] if r['D_boot_sd'] > 1e-4 else None
        r['outside_simultaneous_band'] = r['z'] is not None and abs(r['z']) > c
        r['outside_bonferroni'] = r['z'] is not None and abs(r['z']) > zb
    res = {'identity': R['identity'], 'replicates_usable': len(reps), 'replicates_planned': len(R['boot']),
           'simultaneous': {'m': m, 'maxstat_c95': c, 'bonferroni_z': zb},
           'panel_detectable_shift': [(r['aggregate'], r['action'], round(r['D'], 4), round(r['z'], 2)) for r in rows if r['outside_simultaneous_band']],
           'max_h144': max(r['h144'] for r in rows), 'max_h72': max(r['h72'] for r in rows),
           'gap_total': {k: P[k]['gap_total'] for k in P}, 'point_unallocated': {k: P[k].get('unallocated') for k in P}, 'M144_rule': P['M144'].get('rule'),
           'limitations': ['frozen-table preflop response at the P14 ranges; not a re-converged fixed point',
                           'panel drawn without replacement proportional to raw-flop counts; bootstrap resamples with replacement within old / new groups'],
           'rows': rows}
    json.dump(res, open(OUT + 'a4b_paired_analysis.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, indent=1))
    for r in act:
        print(f"{r['aggregate'][:24]:24s} {r['action']:9s} V72={r['V72']:.3f} V144={r['V144']:.3f} D={r['D']:+.3f} sdD*={r['D_boot_sd']:.3f} z={r['z']:+.2f} "
              f"bias={r['bias_estimate']:+.3f} h72={r['h72']:.3f} h144={r['h144']:.3f} | P15={r['P15']:.3f} M144-P15={r['secondary_M144_minus_P15']:+.3f} V72-P15={r['staleness_V72_minus_P15']:+.3f}")


def _phi_inv(p):
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'analyze'])
    ap.add_argument('--reps', type=int, default=60)
    a = ap.parse_args()
    run(a) if a.cmd == 'run' else analyze(a)
