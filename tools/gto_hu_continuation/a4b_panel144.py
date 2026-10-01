#!/usr/bin/env python3
"""A4b: 72- vs 144-flop tables at the k14 ranges (data/gto_terminal_expansion/a4b_panel144/prereg.json + prereg_amendment_1.json).

Primary (amendment 1): every table goes through the A3 k14 update rule before the preflop solve:
candidate = 0.5 V + 0.5 M13 (M13 = outer_m28_6/k13/used_node{n}.json), guard |unallocated| <= 0.05 bb at the
P14 ranges, fallback measured undamped, measured also failing -> hard stop / replicate excluded.

    python3 tools/gto_hu_continuation/a4b_panel144.py tables      # V14_144 via aggregate.py + identity checks
    python3 tools/gto_hu_continuation/a4b_panel144.py run [--reps 30]
    python3 tools/gto_hu_continuation/a4b_panel144.py analyze [--png docs/GTO_TERMINAL_A4B_PANEL144_V2.png]
"""
import argparse
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import class_combos, parse_board  # noqa: E402
from analyze_a3 import MAIN  # noqa: E402
from a4_audit import aggregates, BIN, CFG, ENV, SPEC  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
A3 = E + 'outer_m28_6/'
OUT = E + 'a4b_panel144/'
PANELS = {72: os.path.join(ROOT, 'data/gto_hu_continuation/panel_v2_72.json'), 144: os.path.join(ROOT, 'data/gto_hu_continuation/panel_v3_144.json')}
TEMPLATE = {72: lambda n: A3 + f'k14/node{n}/table_measured.json', 144: lambda n: OUT + f'node{n}/table_measured_144.json'}
M13 = lambda n: A3 + f'k13/used_node{n}.json'
RANGES = lambda n: A3 + f'k14/terminal_node{n}.json'
ALPHA, GUARD = 0.5, 0.05


def unallocated(n, gross):
    t = json.load(open(RANGES(n)))
    return t['pot_bb'] - sum(sum(pl['class_reach_normalized'][h] * gross[pl['position']][h] for h in range(169)) for pl in t['players'])


def a3_rule(n, vm):
    """A3 k14 update (outer_loop_multi.py): returns (used table json, record)."""
    vp = json.load(open(M13(n)))
    vb = json.loads(json.dumps(vm))
    for sb, so in zip(vb['seats'], vp['seats']):
        assert sb['position'] == so['position']
        for fld in ('gross', 'gross_ci95_lo', 'gross_ci95_hi', 'gross_br'):
            sb[fld] = [ALPHA * x + (1 - ALPHA) * y for x, y in zip(sb[fld], so[fld])]
    g = lambda tab: {s_['position']: s_['gross'] for s_ in tab['seats']}
    cand, meas = unallocated(n, g(vb)), unallocated(n, g(vm))
    if abs(cand) <= GUARD:
        vb['damping'] = {'alpha': ALPHA, 'previous_used': M13(n), 'candidate_unallocated_bb': cand}
        return vb, {'accepted': True, 'candidate_unallocated_bb': cand, 'measured_unallocated_bb': meas, 'hard_stop': False}
    out = json.loads(json.dumps(vm))
    out['damping'] = {'alpha': 1.0, 'reason': 'candidate alpha blend rejected by the guard', 'candidate_unallocated_bb': cand}
    return out, {'accepted': False, 'candidate_unallocated_bb': cand, 'measured_unallocated_bb': meas, 'hard_stop': abs(meas) > GUARD}


def load_panel(size):
    panel = json.load(open(PANELS[size]))
    strata = {}
    for f in panel['panel']:
        strata.setdefault(f['stratum'], []).append(f['board'])
    p_str = {s: panel['strata'][s]['probability'] for s in strata}
    labels = json.load(open(E + 'terminals/p9_node6.json'))['class_labels']
    combos = [class_combos(l) for l in labels]
    compat = {b: [sum(1 for c in cc if c[0] not in parse_board(b) and c[1] not in parse_board(b)) / len(cc) for cc in combos]
              for bs in strata.values() for b in bs}
    return strata, p_str, compat


def flop_values(n, strata):
    out = {}
    for bs in strata.values():
        for b in bs:
            f = OUT + f'node{n}/flops/{b}.json'
            if not os.path.exists(f):
                f = A3 + f'k14/node{n}/flops/{b}.json'
            out[b] = {pl['position']: pl['gross_eps'] for pl in json.load(open(f))['players']}
    return out


def estimate(vals, pos, draw, p_str, compat):
    rho = 19600 / 22100
    res = []
    for h in range(169):
        tot = 0.0
        for s, bs in draw.items():
            tot += p_str[s] * sum(compat[b][h] * vals[b][pos][h] for b in bs if vals[b][pos][h] is not None) / len(bs)
        res.append(tot / sum(p_str.values()) / rho)
    return res


def table(n, draw, vals, p_str, compat):
    return {pos: estimate(vals, pos, draw, p_str, compat) for pos in next(iter(vals.values()))}


def tables(a):
    for n in (28, 6):
        out = TEMPLATE[144](n)
        if not os.path.exists(out):
            subprocess.run(['python3', os.path.join(ROOT, 'tools/gto_hu_continuation/aggregate.py'), A3 + f'k14/terminal_node{n}.json', PANELS[144],
                            OUT + f'node{n}/flops', out, '--outer', '14', '--boot', '2000', '--flop-dir-extra', A3 + f'k14/node{n}/flops'],
                           check=True, env={**os.environ, **ENV})
    check = {}
    for size in (72, 144):
        strata, p_str, compat = load_panel(size)
        for n in (28, 6):
            vals = flop_values(n, strata) if size == 144 else {b: v for b, v in flop_values(n, strata).items()}
            t = table(n, strata, vals, p_str, compat)
            ref = {s['position']: s['gross'] for s in json.load(open(TEMPLATE[size](n)))['seats']}
            check[f'{size}_node{n}'] = max(abs(x - y) for p in ref for x, y in zip(ref[p], t[p]))
    print('identity estimate vs table file max |d|:', check)
    if max(check.values()) > 1e-9:
        raise SystemExit('identity estimate does not reproduce the table files')
    json.dump(check, open(OUT + 'identity_check.json', 'w'), indent=1)


def solve(d, tabs, save=False):
    """tabs: {n: full table json}; one frozen-table preflop solve (optionally saving the .gtop profile)."""
    os.makedirs(d, exist_ok=True)
    files = []
    for n in (28, 6):
        f = os.path.join(d, f'table_node{n}.json')
        json.dump(tabs[n], open(f, 'w'))
        files.append({'file': os.path.basename(f)})
    man = os.path.join(d, 'manifest.json')
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': files}, open(man, 'w'))
    res = {}
    for n in (6, 28):
        f = os.path.join(d, f'terminal_node{n}.json')
        if not os.path.exists(f):
            extra = [os.path.join(d, 'profile.gtop')] if save and n == 6 else []
            subprocess.run([BIN + '/t2_cont_terminal', CFG, '400', SPEC[n], f, *extra], check=True, env={**os.environ, **ENV, 'T2_CONT_FILE': man},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        res[n] = json.load(open(f))
    assert res[6]['gaps'] == res[28]['gaps']
    return {'aggregates': aggregates(res[28], res[6]), 'gap_total': res[6]['gap_total'], 'gaps': res[6]['gaps'], 'evs': res[6]['evs'],
            'ranges_hash': {n: res[n]['ranges_hash_fnv1a64'] for n in res}}


def with_gross(n, size, gross):
    tab = json.load(open(TEMPLATE[size](n)))
    for s_ in tab['seats']:
        s_['gross'] = gross[s_['position']]
    tab['a4b_replicate'] = True
    return tab


def run(a):
    results = json.load(open(OUT + 'results.json')) if os.path.exists(OUT + 'results.json') else {}
    for size in (72, 144):
        strata, p_str, compat = load_panel(size)
        vals = {n: flop_values(n, strata) for n in (28, 6)}
        used, rec = {}, {}
        for n in (28, 6):
            used[n], rec[n] = a3_rule(n, json.load(open(TEMPLATE[size](n))))
            if rec[n]['hard_stop']:
                raise SystemExit(f'{size} node {n}: measured table also fails the guard')
            json.dump(used[n], open(OUT + f'node{n}/used_M14_{size}.json', 'w'))
        if size == 72:
            for n in (28, 6):
                ref = json.load(open(A3 + f'k14/used_node{n}.json'))
                if [s_['gross'] for s_ in used[n]['seats']] != [s_['gross'] for s_ in ref['seats']]:
                    raise SystemExit(f'M14_72 node {n} is not bit-identical to the A3 used_14 table')
        key = f'F{size}'
        if key not in results:
            results[key] = {**solve(OUT + f'{key}/point', used, save=True), 'rule': rec}
            if size == 72:
                p15 = {n: json.load(open(A3 + f'k15/terminal_node{n}.json')) for n in (6, 28)}
                if results[key]['aggregates'] != aggregates(p15[28], p15[6]) or results[key]['gaps'] != p15[6]['gaps'] \
                        or results[key]['evs'] != p15[6]['evs'] or results[key]['ranges_hash'] != {n: p15[n]['ranges_hash_fnv1a64'] for n in (6, 28)}:
                    raise SystemExit('F72 does not reproduce the A3 P15 state exactly')
                results['F72_reproduces_P15_exactly'] = True
            json.dump(results, open(OUT + 'results.json', 'w'), indent=1)
        print(key, 'SB raise', round(results[key]['aggregates']['SB first-in']['raise_2.5'], 4), rec, flush=True)
        dk = f'diag_measured_F{size}'
        if dk not in results:
            results[dk] = solve(OUT + f'diag_measured_F{size}', {n: json.load(open(TEMPLATE[size](n))) for n in (28, 6)})
            json.dump(results, open(OUT + 'results.json', 'w'), indent=1)
        rng = random.Random(20261001)
        draws = [{s_: [rng.choice(bs) for _ in bs] for s_, bs in strata.items()} for _ in range(a.reps)]
        bk = f'boot{size}'
        results.setdefault(bk, {})
        for i, dr in enumerate(draws, 1):
            if str(i) in results[bk]:
                continue
            tabs, rr = {}, {}
            for n in (28, 6):
                tabs[n], rr[n] = a3_rule(n, with_gross(n, size, table(n, dr, vals[n], p_str, compat)))
            if any(r['hard_stop'] for r in rr.values()):
                results[bk][str(i)] = {'guard_hard_stop': True, 'rule': rr}
            else:
                results[bk][str(i)] = {**solve(OUT + f'F{size}/r{i:02d}', tabs), 'rule': rr}
            print(bk, i, round(results[bk][str(i)].get('aggregates', {}).get('SB first-in', {}).get('raise_2.5', float('nan')), 4), flush=True)
            json.dump(results, open(OUT + 'results.json', 'w'), indent=1)


def analyze(a):
    R = json.load(open(OUT + 'results.json'))
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
    sd = lambda xs: (sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    rows = []
    for nm, (_, acts) in MAIN.items():
        for ac in acts:
            row = {'aggregate': nm, 'action': ac}
            for size in (72, 144):
                xs = [r['aggregates'][nm][ac] for r in R[f'boot{size}'].values() if 'aggregates' in r]
                pt = R[f'F{size}']['aggregates'][nm][ac]
                row[str(size)] = {'point': pt, 'mean': sum(xs) / len(xs), 'sd': sd(xs), 'lo': q(xs, 0.025), 'hi': q(xs, 0.975),
                                  'half_width_95': (q(xs, 0.975) - q(xs, 0.025)) / 2, 'mean_minus_point': sum(xs) / len(xs) - pt}
            row['panel_shift'] = abs(row['144']['point'] - row['72']['point'])
            row['h_ratio_144_72'] = row['144']['half_width_95'] / row['72']['half_width_95'] if row['72']['half_width_95'] > 1e-4 else None
            rows.append(row)
    beyond = [(r['aggregate'], r['action'], round(r['panel_shift'], 4), round(r['72']['half_width_95'], 4)) for r in rows if r['panel_shift'] > r['72']['half_width_95']]
    moving = [r for r in rows if r['72']['half_width_95'] > 1e-3]
    res = {'identity_check': json.load(open(OUT + 'identity_check.json')), 'reading': 'inconsistent' if beyond else 'consistent', 'beyond_h72': beyond,
           'h_ratio_144_72': {'median': sorted(r['h_ratio_144_72'] for r in moving)[len(moving) // 2], 'min': min(r['h_ratio_144_72'] for r in moving),
                              'max': max(r['h_ratio_144_72'] for r in moving)},
           'max_half_width_95': {s: max(r[s]['half_width_95'] for r in rows) for s in ('72', '144')},
           'gap_total': {k: (R[k]['gap_total'] if not k.startswith('boot') else max(r['gap_total'] for r in R[k].values() if 'gap_total' in r)) for k in R if isinstance(R[k], dict)},
           'bootstrap_guard': {k: {'n': len(R[k]), 'hard_stop': sum(1 for r in R[k].values() if r.get('guard_hard_stop')),
                                   'blend_rejected': sum(1 for r in R[k].values() for x in r['rule'].values() if not x['accepted'])} for k in ('boot72', 'boot144')},
           'point_rule': {k: R[k]['rule'] for k in ('F72', 'F144')},
           'F72_reproduces_P15_exactly': R.get('F72_reproduces_P15_exactly', False),
           'diagnostic_measured_only': {k: {nm: R[k]['aggregates'][nm] for nm in R[k]['aggregates']} for k in ('diag_measured_F72', 'diag_measured_F144')},
           'limitation': 'A3 k14 update rule applied to the 72- / 144-flop V14 at the P14 ranges, one frozen-table preflop solve; not a re-converged fixed point; 30 replicates per panel',
           'rows': rows}
    json.dump(res, open(OUT + 'analysis.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, indent=1))
    for r in moving:
        print(f"{r['aggregate'][:24]:24s} {r['action']:9s} F72={r['72']['point']:.3f} F144={r['144']['point']:.3f} shift={r['panel_shift']:.3f} "
              f"h72={r['72']['half_width_95']:.3f} h144={r['144']['half_width_95']:.3f} ratio={r['h_ratio_144_72']:.2f} "
              f"nl72={r['72']['mean_minus_point']:+.3f} nl144={r['144']['mean_minus_point']:+.3f}")
    figure(res, a.png)


def figure(res, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
    C72, C144 = '#c9a227', '#2a78d6'
    rows = [r for r in res['rows'] if r['72']['half_width_95'] > 1e-3]
    lab = [f"{r['aggregate'].replace(' (node 28 parent)', '').replace(' (node 6 parent)', '')}: {r['action']}" for r in rows]
    y = list(range(len(rows)))
    fig, ax = plt.subplots(1, 2, figsize=(20, 0.5 * len(rows) + 3), dpi=115)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    for i, r in enumerate(rows):
        for size, col, off in (('72', C72, -0.15), ('144', C144, 0.15)):
            s = r[size]
            g.plot([s['lo'], s['hi']], [i + off, i + off], color=col, lw=4, solid_capstyle='butt')
            g.scatter([s['point']], [i + off], color=INK, s=22, zorder=3)
            g.scatter([s['mean']], [i + off], color='#c0392b', marker='|', s=110, zorder=4)
    g.set_yticks(y)
    g.set_yticklabels(lab, fontsize=8)
    g.invert_yaxis()
    g.set_xlabel('frequency', fontsize=9, color=MUTED)
    g.set_title('(1) point estimate and panel-bootstrap 95% interval: 72 vs 144 flops (M14 = A3 rule on V14, P14 ranges)', loc='left', fontsize=10, color=INK)
    g.legend(handles=[Line2D([0], [0], color=C72, lw=4, label='72-flop interval'), Line2D([0], [0], color=C144, lw=4, label='144-flop interval'),
                      Line2D([0], [0], marker='o', color=INK, lw=0, label='point (frozen-table solve)'),
                      Line2D([0], [0], marker='|', color='#c0392b', lw=0, markersize=12, label='bootstrap mean')],
             fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.07), ncol=4)
    g = ax[1]
    g.barh([t - 0.25 for t in y], [r['panel_shift'] for r in rows], 0.25, color=INK, label='|F144 − F72| (panel shift)')
    g.barh(y, [r['72']['half_width_95'] for r in rows], 0.25, color=C72, label='72-flop 95% half-width')
    g.barh([t + 0.25 for t in y], [r['144']['half_width_95'] for r in rows], 0.25, color=C144, label='144-flop 95% half-width')
    g.axvline(0.005, color='#c0392b', ls='--', lw=1)
    g.text(0.0055, -0.8, '0.005', color='#c0392b', fontsize=8)
    g.set_yticks(y)
    g.set_yticklabels(lab, fontsize=8)
    g.invert_yaxis()
    g.set_xlabel('frequency', fontsize=9, color=MUTED)
    g.set_title('(2) panel shift vs the 72- and 144-flop resolution', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.07), ncol=3)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    hr = res['h_ratio_144_72']
    fig.suptitle(f"A4b: node 28 + node 6 at 144 flops — reading {res['reading']}; half-width ratio 144/72 median {hr['median']:.2f} "
                 f"(range {hr['min']:.2f}–{hr['max']:.2f}; sqrt-n expectation 0.71)", fontsize=11, color=INK, x=0.01, ha='left')
    fig.text(0.01, 0.002, 'V14 of both terminals on the 72-flop panel and on the nested 144-flop panel at the P14 ranges, through the A3 k14 rule (0.5 V + 0.5 M13, guard); one frozen-table preflop '
             'solve per point / replicate (30 stratified board resamples per panel). Not a re-converged fixed point. Aggregates with no spread are omitted.',
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['tables', 'run', 'analyze'])
    ap.add_argument('--reps', type=int, default=30)
    ap.add_argument('--png', default=os.path.join(ROOT, 'docs/GTO_TERMINAL_A4B_PANEL144_V2.png'))
    a = ap.parse_args()
    {'tables': tables, 'run': run, 'analyze': analyze}[a.cmd](a)
