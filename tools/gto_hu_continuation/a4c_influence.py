#!/usr/bin/env python3
"""A4c design analysis: per-terminal, per-stratum downstream influence of panel noise (no flop solve).

    python3 tools/gto_hu_continuation/a4c_influence.py run [--reps 8]
    python3 tools/gto_hu_continuation/a4c_influence.py analyze

For terminal n and stratum s, replicate r resamples only stratum s's 12 boards of terminal n (with replacement, within the 144 panel);
every other stratum and the other terminal stay at their V144 point tables. One frozen-table preflop solve per replicate.
Downstream metrics against the point game G144 (= g(V144)):
  - seat-swap dEV of sigma_r into G144 per seat (exact EV difference, opponents fixed at G144's own solve),
  - per-class regret at the key nodes: max_a EV_G(a|h) - sum_a sigma_r(a|h) EV_G(a|h), reach-weighted by G's arriving reach,
  - reach-weighted class L1 of the strategy, aggregate frequency shifts.
Under independent strata and a locally quadratic loss, E[loss] is additive over strata, so c_{n,s} = mean_r loss estimates the
contribution of (n, s) at 12 boards; it scales as (12/m)(1 - m/K)/(1 - 12/K) under SRSWOR with m boards from K classes.
"""
import argparse
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4b_panel144 as B  # noqa: E402
import a4r_robust as A  # noqa: E402
from a4b_paired import KEY_NODES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
OUT = E + 'a4c_preanalysis/influence/'
SEATS = {'CO': (0, 'all'), 'BTN': (1, 'all'), 'SB': (2, 'all'), 'BB': (3, 'all')}
NODES = {'BTN first-in': (28, 'BTN@1'), 'SB vs BTN': (28, 'SB@25'), 'BB vs BTN': (28, 'BB@26'), 'SB first-in': (6, 'SB@2'), 'BB vs SB': (6, 'BB@4')}


def node_data(d):
    out = {}
    for name, (n, tag) in NODES.items():
        t = json.load(open(os.path.join(d, f'terminal_node{n}.json')))
        pn = next(p for p in t['path_nodes'] if f"{p['actor']}@{p['node']}" == tag)
        out[name] = {'s': pn['class_strategy'], 'r': pn['class_reach_before'], 'ev': pn['ev_bb']}
    return out


def metrics(game, gnodes, rep_dir, rep):
    res = {'seat_dEV': {}, 'regret': {}, 'L1': {}}
    for name, (seat, root) in SEATS.items():
        s = A.splice(game, rep, seat, root, os.path.join(rep_dir, f'swap_{name}.json'))
        res['seat_dEV'][name] = game['evs'][seat] - s['evs'][seat]
    rn = node_data(rep_dir)
    for name in NODES:
        g, a = gnodes[name], rn[name]
        w = g['r']
        tw = sum(w)
        reg = l1 = 0.0
        for h in range(169):
            evs = [g['ev'][k][h] for k in range(len(g['ev']))]
            reg += w[h] * (max(evs) - sum(a['s'][k][h] * evs[k] for k in range(len(evs))))
            l1 += w[h] * sum(abs(a['s'][k][h] - g['s'][k][h]) for k in range(len(evs)))
        res['regret'][name] = reg / tw
        res['L1'][name] = l1 / tw
    res['aggregates'] = rep['aggregates']
    return res


def run(a):
    os.makedirs(OUT, exist_ok=True)
    R = json.load(open(B.OUT + 'paired_results.json'))
    game = R['points']['V144']
    gnodes = node_data(B.OUT + 'points/V144')
    strata, p_str, compat = B.load_panel(144)
    vals = {n: B.flop_values(n, strata) for n in (28, 6)}
    point = {n: json.load(open(B.TEMPLATE[144](n))) for n in (28, 6)}
    # identity: full-panel estimate equals the point table
    rng = random.Random(20261003)
    jobs = []
    for n in (6, 28):
        for s in sorted(strata):
            for r in range(1, a.reps + 1):
                draw = {t: list(bs) for t, bs in strata.items()}
                draw[s] = [rng.choice(strata[s]) for _ in strata[s]]
                jobs.append((n, s, r, draw))
    path = OUT + 'results.json'
    res = json.load(open(path)) if os.path.exists(path) else {}

    def one(job):
        n, s, r, draw = job
        key = f'{n}|{s}|{r}'
        if key in res:
            return key, res[key]
        d = OUT + f"n{n}/{s.replace('/', '_')}/r{r}"
        tabs = dict(point)
        tabs[n] = B.with_gross(n, 144, B.table(n, draw, vals[n], p_str, compat))
        rep = B.solve(d, tabs, save=True)
        rep.update({'profile': os.path.join(d, 'profile.gtop'), 'manifest': os.path.join(d, 'manifest.json')})
        return key, {'n': n, 'stratum': s, 'r': r, **metrics(game, gnodes, d, rep)}
    with ThreadPoolExecutor(1) as ex:
        for key, v in ex.map(one, jobs):
            if key not in res:
                res[key] = v
                json.dump(res, open(path + '.tmp', 'w'))
                os.replace(path + '.tmp', path)
                print(key, {k: round(x, 5) for k, x in v['seat_dEV'].items()}, flush=True)


def analyze(a):
    res = json.load(open(OUT + 'results.json'))
    out = {}
    for v in res.values():
        g = out.setdefault(f"{v['n']}|{v['stratum']}", {'seat_dEV': {}, 'regret': {}, 'L1': {}, 'reps': 0})
        g['reps'] += 1
        for k in ('seat_dEV', 'regret', 'L1'):
            for m, x in v[k].items():
                g[k].setdefault(m, []).append(x)
    summ = {k: {'reps': g['reps'], **{f'{kind}:{m}': sum(xs) / len(xs) for kind in ('seat_dEV', 'regret', 'L1') for m, xs in g[kind].items()}} for k, g in out.items()}
    json.dump(summ, open(OUT + 'summary.json', 'w'), indent=1)
    print(json.dumps(summ, indent=1)[:3000])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'analyze'])
    ap.add_argument('--reps', type=int, default=8)
    a = ap.parse_args()
    run(a) if a.cmd == 'run' else analyze(a)
