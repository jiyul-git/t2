#!/usr/bin/env python3
"""A4 acceptance audit of the sealed A3 run (data/gto_terminal_expansion/a4_audit/prereg.json).

    python3 tools/gto_hu_continuation/a4_audit.py run [--reps 30] [--workers 4]
    python3 tools/gto_hu_continuation/a4_audit.py analyze [--png docs/GTO_TERMINAL_A4_AUDIT_V2.png]

Panel bootstrap: one stratified resample of the 72 boards is applied to every A3 step (k10..k14); the
used-table chain is rebuilt with the recorded accept/reject flags; one frozen-table preflop solve per
replicate gives the replicate P15 aggregates. No new postflop solve.
"""
import argparse
import json
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import class_combos, parse_board  # noqa: E402
from analyze_a3 import MAIN  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
A3 = E + 'outer_m28_6/'
OUT = E + 'a4_audit/'
BIN = os.path.join(ROOT, 'vendor/gtopen/target/release/examples')
CFG = os.path.join(ROOT, 'data/gto_hu_continuation/cfg_4h_mr4_30bb.json')
ENV = {'PREFLOP_EQ_SEED': '202', 'PREFLOP_MULTIWAY_SEED': '202', 'PREFLOP_EQ_SAMPLES': '1200'}
SPEC = {28: 'fold,raise,fold,call', 6: 'fold,fold,raise,call'}
KS = [10, 11, 12, 13, 14]
START = {n: A3 + f'k9/used_node{n}.json' for n in (28, 6)}


def load_panel():
    panel = json.load(open(os.path.join(ROOT, 'data/gto_hu_continuation/panel_v2_72.json')))
    strata = {}
    for f in panel['panel']:
        strata.setdefault(f['stratum'], []).append(f['board'])
    p_str = {s: panel['strata'][s]['probability'] for s in strata}
    labels = json.load(open(E + 'terminals/p9_node6.json'))['class_labels']
    combos = [class_combos(l) for l in labels]
    compat = {b: [sum(1 for c in cc if c[0] not in parse_board(b) and c[1] not in parse_board(b)) / len(cc) for cc in combos]
              for bs in strata.values() for b in bs}
    return strata, p_str, compat


def per_flop(k, n, strata):
    out = {}
    for bs in strata.values():
        for b in bs:
            d = json.load(open(A3 + f'k{k}/node{n}/flops/{b}.json'))
            out[b] = {pl['position']: pl['gross_eps'] for pl in d['players']}
    return out


def estimate(vals, pos, draw, p_str, compat):
    rho = 19600 / 22100
    res = []
    for h in range(169):
        tot = 0.0
        for s, bs in draw.items():
            num = sum(compat[b][h] * vals[b][pos][h] for b in bs if vals[b][pos][h] is not None)
            tot += p_str[s] * num / len(bs)
        res.append(tot / sum(p_str.values()) / rho)
    return res


def accepted(n):
    log = json.load(open(A3 + 'loop_log.json'))
    return {s['k']: s['terminals'][str(n)]['blend_candidate_accepted'] for s in log['steps'] if s.get('terminals')}


def chain(n, draw, cache, p_str, compat, acc):
    used = {s['position']: s['gross'] for s in json.load(open(START[n]))['seats']}
    for k in KS:
        v = {pos: estimate(cache[(k, n)], pos, draw, p_str, compat) for pos in used}
        used = {pos: [0.5 * a + 0.5 * b for a, b in zip(v[pos], used[pos])] for pos in used} if acc[k] else v
    return used


def aggregates(t28, t6):
    """Same extraction as analyze_a3.state()."""
    out = {}
    for name, (key, acts) in MAIN.items():
        if key.startswith('rfi'):
            mix = t28['frequencies'][key]['mix']
        else:
            n, pos = key.split(':')
            tt = t28 if n == '28' else t6
            mix = next(p for p in tt['path_nodes'] if f"{p['actor']}@{p['node']}" == pos)['mix']
        out[name] = {a: mix.get(a, 0.0) for a in acts}
    return out


def solve(d, tables):
    os.makedirs(d, exist_ok=True)
    files = {}
    for n, gross in tables.items():
        tab = json.load(open(A3 + f'k14/used_node{n}.json'))
        for s in tab['seats']:
            s['gross'] = gross[s['position']]
        tab['a4_replicate'] = True
        f = os.path.join(d, f'used_node{n}.json')
        json.dump(tab, open(f, 'w'))
        files[n] = f
    man = os.path.join(d, 'manifest.json')
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': [{'file': os.path.basename(files[n])} for n in sorted(files)]}, open(man, 'w'))
    res = {}
    for n in (6, 28):
        f = os.path.join(d, f'terminal_node{n}.json')
        if not os.path.exists(f):
            subprocess.run([BIN + '/t2_cont_terminal', CFG, '400', SPEC[n], f], check=True, env={**os.environ, **ENV, 'T2_CONT_FILE': man},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        res[n] = json.load(open(f))
    assert res[6]['gaps'] == res[28]['gaps']
    return {'aggregates': aggregates(res[28], res[6]), 'gap_total': res[6]['gap_total']}


def run(a):
    strata, p_str, compat = load_panel()
    cache = {(k, n): per_flop(k, n, strata) for k in KS for n in (28, 6)}
    acc = {n: accepted(n) for n in (28, 6)}
    ident = {s: list(bs) for s, bs in strata.items()}
    # validation 1: identity draw reproduces the A3 used tables
    base = {n: chain(n, ident, cache, p_str, compat, acc[n]) for n in (28, 6)}
    val = {}
    for n in (28, 6):
        ref = {s['position']: s['gross'] for s in json.load(open(A3 + f'k14/used_node{n}.json'))['seats']}
        val[n] = max(abs(x - y) for pos in ref for x, y in zip(ref[pos], base[n][pos]))
    print('identity chain max |d gross| vs A3 used_14:', val, flush=True)
    if max(val.values()) > 1e-9:
        raise SystemExit('identity chain does not reproduce the A3 used tables')
    rng = random.Random(20261001)
    draws = [{s: [rng.choice(bs) for _ in bs] for s, bs in strata.items()} for _ in range(a.reps)]
    jobs = [('identity', 0, base)]
    for variant in ('both', 'only28', 'only6'):
        for i, dr in enumerate(draws, 1):
            t = {}
            for n in (28, 6):
                use = variant == 'both' or variant == f'only{n}'
                t[n] = chain(n, dr, cache, p_str, compat, acc[n]) if use else base[n]
            jobs.append((variant, i, t))
    print(f'{len(jobs)} preflop replicates', flush=True)

    def one(job):
        v, i, t = job
        r = solve(OUT + f'{v}/r{i:02d}', t)
        print(v, i, round(r['aggregates']['SB first-in']['raise_2.5'], 4), flush=True)
        return v, i, r
    results = {}
    with ThreadPoolExecutor(a.workers) as ex:
        for v, i, r in ex.map(one, jobs):
            results.setdefault(v, {})[i] = r
    json.dump({'identity_chain_max_abs_diff': val, 'results': results}, open(OUT + 'replicates.json', 'w'), indent=1)


def analyze(a):
    rep = json.load(open(OUT + 'replicates.json'))
    an = json.load(open(A3 + 'analysis.json'))
    st = {s['tag']: s['freq'] for s in an['states']}
    p15, p14 = st['P15'], st['P14']
    ident = rep['results']['identity']['0']['aggregates']
    # validation 2: identity replicate reproduces P15
    val2 = max(abs(ident[nm][ac] - p15[nm][ac]) for nm in p15 for ac in p15[nm])
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
    rows = []
    for nm in p15:
        for ac in p15[nm]:
            hw = {}
            for v in ('both', 'only28', 'only6'):
                xs = [r['aggregates'][nm][ac] for r in rep['results'][v].values()]
                hw[v] = {'half_width_95': (q(xs, 0.975) - q(xs, 0.025)) / 2, 'sd': (sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5,
                         'lo': q(xs, 0.025), 'hi': q(xs, 0.975), 'mean': sum(xs) / len(xs), 'min': min(xs), 'max': max(xs),
                         'P15_rank_below': sum(x < p15[nm][ac] for x in xs)}
                hw[v]['d_over_sd'] = abs(p15[nm][ac] - p14[nm][ac]) / hw[v]['sd'] if hw[v]['sd'] > 0 else None
                hw[v]['mean_minus_P15'] = hw[v]['mean'] - p15[nm][ac]
            seq = [st[f'P{k}'][nm][ac] for k in (12, 13, 14, 15)]
            amp = sum(abs(y - x) for x, y in zip(seq, seq[1:])) / len(seq[1:]) / 2
            rows.append({'aggregate': nm, 'action': ac, 'P14': p14[nm][ac], 'P15': p15[nm][ac], 'd_P14_P15': abs(p15[nm][ac] - p14[nm][ac]),
                         'period2_half_amplitude_P12_P15': amp, 'h': hw})
    hmax = max(r['h']['both']['half_width_95'] for r in rows)
    pass_ = all(r['d_P14_P15'] <= 0.005 for r in rows)
    beyond = [r for r in rows if r['d_P14_P15'] > r['h']['both']['half_width_95']]
    cls = 'PASS' if pass_ else ('true_not_converged' if beyond else ('precision_limited' if hmax > 0.005 else 'true_not_converged'))
    per_terminal = {}
    for term, names, var in (('node 28', ['BB vs BTN (node 28 parent)'], 'only28'), ('node 6', ['SB first-in', 'BB vs SB (node 6 parent)'], 'only6')):
        rr = [r for r in rows if r['aggregate'] in names]
        b = [r for r in rr if r['d_P14_P15'] > r['h'][var]['half_width_95']]
        per_terminal[term] = {'beyond_own_noise': [(r['aggregate'], r['action'], round(r['d_P14_P15'], 4), round(r['h'][var]['half_width_95'], 4)) for r in b],
                              'max_d': max(r['d_P14_P15'] for r in rr), 'max_h_own': max(r['h'][var]['half_width_95'] for r in rr),
                              'classification': 'PASS' if all(r['d_P14_P15'] <= 0.005 for r in rr) else ('true_not_converged' if b else 'precision_limited')}
    res = {'validation': {'identity_chain_max_abs_diff': rep['identity_chain_max_abs_diff'], 'identity_replicate_vs_P15_max_abs': val2},
           'replicates': {v: len(rep['results'][v]) for v in rep['results']}, 'rows': rows, 'max_half_width_both': hmax,
           'classification': cls, 'aggregates_beyond_noise': [(r['aggregate'], r['action'], round(r['d_P14_P15'], 4), round(r['h']['both']['half_width_95'], 4)) for r in beyond],
           'per_terminal': per_terminal,
           'gap_total': {v: {'mean': sum(r['gap_total'] for r in rep['results'][v].values()) / len(rep['results'][v]),
                             'max': max(r['gap_total'] for r in rep['results'][v].values())} for v in rep['results']},
           'limitation': 'the bootstrap measures the board-sampling sensitivity of P15 (one frozen-table preflop solve per resampled used table); it does not directly measure the noise of a fully re-converged outer fixed point'}
    mt = OUT + 'mean_table_check.json'
    if os.path.exists(mt):
        res['diagnostic_mean_table_solve'] = {'note': 'NOT pre-registered; one extra preflop solve on the mean of the 30 both-replicate used tables, run after the classification to isolate why the replicate distribution is not centred on P15',
                                              **json.load(open(mt))}
    json.dump(res, open(OUT + 'audit.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, indent=1))
    for r in rows:
        print(f"{r['aggregate'][:26]:26s} {r['action']:10s} d={r['d_P14_P15']:.4f} amp={r['period2_half_amplitude_P12_P15']:.4f} "
              f"h(both)={r['h']['both']['half_width_95']:.4f} h(28)={r['h']['only28']['half_width_95']:.4f} h(6)={r['h']['only6']['half_width_95']:.4f}")
    figure(res, a.png)


def figure(res, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
    rows = [r for r in res['rows'] if max(r['P15'], r['P14']) > 0.005]
    lab = [f"{r['aggregate'].replace(' (node 28 parent)', '').replace(' (node 6 parent)', '')}: {r['action']}" for r in rows]
    y = list(range(len(rows)))
    fig, ax = plt.subplots(1, 2, figsize=(20, 0.42 * len(rows) + 2.5), dpi=115)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    g.barh([t - 0.3 for t in y], [r['d_P14_P15'] for r in rows], 0.2, color=INK, label='|P15 − P14| (A3 last step)')
    g.barh([t - 0.1 for t in y], [r['period2_half_amplitude_P12_P15'] for r in rows], 0.2, color='#8a5cd1', label='period-2 half-amplitude P12–P15')
    g.barh([t + 0.1 for t in y], [r['h']['both']['half_width_95'] for r in rows], 0.2, color='#c9a227', label='panel 95% half-width (both terminals)')
    g.barh([t + 0.3 for t in y], [r['h']['only28']['half_width_95'] for r in rows], 0.1, color='#2a78d6', label='… node 28 only')
    g.barh([t + 0.4 for t in y], [r['h']['only6']['half_width_95'] for r in rows], 0.1, color='#1baf7a', label='… node 6 only')
    g.axvline(0.005, color='#c0392b', ls='--', lw=1)
    g.text(0.0055, -0.9, 'A3 criterion 0.005', color='#c0392b', fontsize=8)
    g.set_yticks(y)
    g.set_yticklabels(lab, fontsize=8)
    g.invert_yaxis()
    g.set_xlabel('frequency', fontsize=9, color=MUTED)
    g.set_title('(1) last-step change vs the 72-flop panel resolution, per main aggregate', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.07), ncol=3)
    g = ax[1]
    for i, r in enumerate(rows):
        h = r['h']['both']
        g.plot([h['lo'], h['hi']], [i, i], color='#c9a227', lw=4, solid_capstyle='butt')
        g.scatter([r['P15']], [i], color=INK, zorder=3, s=25)
        g.scatter([r['P14']], [i], color='#8a5cd1', marker='x', zorder=3, s=30)
        g.scatter([h['mean']], [i], color='#c0392b', marker='|', zorder=4, s=120)
    g.set_yticks(y)
    g.set_yticklabels(lab, fontsize=8)
    g.invert_yaxis()
    g.set_xlabel('frequency', fontsize=9, color=MUTED)
    from matplotlib.lines import Line2D
    g.legend(handles=[Line2D([0], [0], color='#c9a227', lw=4, label='P15 panel-bootstrap 95% interval'),
                      Line2D([0], [0], marker='o', color=INK, lw=0, label='P15 (A3)'), Line2D([0], [0], marker='x', color='#8a5cd1', lw=0, label='P14 (A3)'),
                      Line2D([0], [0], marker='|', color='#c0392b', lw=0, markersize=12, label='bootstrap mean (30 replicates)')],
             fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.07), ncol=2)
    g.set_title('(2) P14 and P15 against the P15 bootstrap interval', loc='left', fontsize=10, color=INK)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.suptitle(f"A4 acceptance audit of A3 (panel bootstrap through the used-table chain): classification {res['classification']}; "
                 f"node 28 {res['per_terminal']['node 28']['classification']}, node 6 {res['per_terminal']['node 6']['classification']}",
                 fontsize=11, color=INK, x=0.01, ha='left')
    fig.text(0.01, 0.002, 'Bootstrap = 30 stratified resamples of the 72 panel boards, one draw applied to every A3 step k10..k14, used-table chain rebuilt with the recorded '
             'accept flags, one frozen-table preflop solve per replicate. It measures the board-sampling sensitivity of P15, not the noise of a fully re-converged fixed point. '
             'Rows with both P14 and P15 below 0.005 are omitted.', fontsize=7.5, color=MUTED, wrap=True)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'analyze'])
    ap.add_argument('--reps', type=int, default=30)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--png', default=os.path.join(ROOT, 'docs/GTO_TERMINAL_A4_AUDIT_V2.png'))
    a = ap.parse_args()
    run(a) if a.cmd == 'run' else analyze(a)
