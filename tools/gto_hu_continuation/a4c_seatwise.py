#!/usr/bin/env python3
"""A4c design analysis 5 (no solve): seat-wise and regret-wise predictions per allocation; budget path; scalar vs minimax vs
constrained allocations; minimal new-board count keeping every seat (and every regret node) at or below equal-24.

Model (same as allocation_downstream.json): metric_i(alloc) = sum_{n,s} c_{n,s,i} * (144/11)(1 - m/K_s)/m  (FPC-aware, additive),
c = mean isolated contribution at 12 boards (seat-swap dEV per seat; class-regret excess per node).
Calibrated seat loss = observed pooled 144 * (metric/metric_144)^beta_seat (beta from loss_scaling.json). The calibration is
monotone per metric, so 'not worse than equal-24' is decided identically on raw and calibrated values.
Scalar objective of allocation_downstream.json = unweighted sum of the BTN, SB and BB seat dEV (bb per hand dealt; terminal reach
is already inside the seat EV); regret was not in it.
"""
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_panel as mp  # noqa: E402
from a4c_reconstruct import regret_l1  # noqa: E402
from a4c_influence import NODES, node_data  # noqa: E402

E = 'data/gto_terminal_expansion/'
O = E + 'a4c_preanalysis/'
SEATS = ('BTN', 'SB', 'BB')
BETA_FOR = {'BTN first-in': 'BTN', 'SB vs BTN': 'SB', 'BB vs BTN': 'BB', 'SB first-in': 'SB', 'BB vs SB': 'BB'}


def load():
    iso = json.load(open(O + 'influence/results.json'))
    groups = {}
    for v in iso.values():
        groups.setdefault((v['n'], v['stratum']), []).append(v)
    K = {}
    for f in itertools.combinations([(r, s) for r in range(13) for s in range(4)], 3):
        K.setdefault(mp.stratum(f), set()).add(mp.canon(f))
    K = {s: len(v) for s, v in K.items()}
    gn = node_data(E + 'a4b_panel144/points/V144')
    base = {n: regret_l1(gn[n], {'class_strategy': gn[n]['s']})[0] for n in NODES}
    mean = lambda xs: sum(xs) / len(xs)
    c = {}
    for k, g in groups.items():
        c[k] = {f'seat:{s}': max(mean([r['seat_dEV'][s] for r in g]), 0.0) for s in SEATS}
        c[k].update({f'regret:{n}': max(mean([r['regret'][n] - base[n] for r in g]), 0.0) for n in NODES})
    return c, K


def main():
    c, K = load()
    metrics = list(next(iter(c.values())))
    fac = lambda k, m: (144 / 11) * (1 - m / K[k[1]]) / m
    pred = lambda a: {i: sum(c[k][i] * fac(k, a[k]) for k in c) for i in metrics}
    rec = json.load(open(O + 'reconstruction.json'))['reconstruction']
    ls = json.load(open(O + 'loss_scaling.json'))['summary']['seats']
    beta = {s: ls[s]['loss_vs_variance_exponent_beta'] for s in SEATS}
    obs = {f'seat:{s}': rec[f'seat_dEV:{s}']['observed_pooled_mean'] for s in SEATS}
    obs.update({f'regret:{n}': rec[f'regret_excess:{n}']['observed_pooled_mean'] for n in NODES})
    bet = {f'seat:{s}': beta[s] for s in SEATS}
    bet.update({f'regret:{n}': beta[BETA_FOR[n]] for n in NODES})
    cur = {k: 12 for k in c}
    p144 = pred(cur)
    calib = lambda p: {i: obs[i] * (p[i] / p144[i]) ** bet[i] if p144[i] > 0 else 0.0 for i in metrics}
    eq = {k: 24 for k in c}
    peq = pred(eq)

    def greedy(budget, score):
        a = dict(cur)
        path = {}
        for b in range(1, budget + 1):
            best = None
            for k in c:
                if a[k] >= K[k[1]]:
                    continue
                a2 = dict(a)
                a2[k] += 1
                s = score(a, a2, k)
                if best is None or s > best[0]:
                    best = (s, k)
            a[best[1]] += 1
            path[b] = dict(a)
        return path

    seat_ids = [f'seat:{s}' for s in SEATS]
    all_ids = metrics
    # (A) scalar sum (the existing objective)
    def scalar(a, a2, k):
        return sum(c[k][i] for i in seat_ids) * (fac(k, a[k]) - fac(k, a2[k]))
    # (B) minimax over seats normalized by equal-24; tie-break normalized sum
    def minimax_factory(ids):
        def f(a, a2, k):
            p1 = {i: sum(c[kk][i] * fac(kk, a[kk]) for kk in c) for i in ids}
            d = {i: c[k][i] * (fac(k, a[k]) - fac(k, a2[k])) for i in ids}
            r1 = {i: p1[i] / peq[i] for i in ids}
            r2 = {i: (p1[i] - d[i]) / peq[i] for i in ids}
            return (max(r1.values()) - max(r2.values()), sum(r1.values()) - sum(r2.values()))
        return f
    paths = {'scalar_sum': greedy(288, scalar), 'minimax_seats': greedy(288, minimax_factory(seat_ids)),
             'minimax_seats_and_regrets': greedy(288, minimax_factory(all_ids))}
    # (C) constrained via Lagrangian weight sweep over seat weights (normalized by equal-24)
    best_c = None
    grid = [i / 10 for i in range(11)]
    for w in itertools.product(grid, repeat=3):
        if abs(sum(w) - 1) > 1e-9 or min(w) == 0:
            continue
        ww = dict(zip(seat_ids, w))
        sc = lambda a, a2, k, ww=ww: sum(ww[i] * c[k][i] / peq[i] for i in seat_ids) * (fac(k, a[k]) - fac(k, a2[k]))
        pth = greedy(288, sc)
        for b in range(1, 289):
            p = pred(pth[b])
            if all(p[i] <= peq[i] for i in seat_ids):
                if best_c is None or b < best_c[0]:
                    best_c = (b, w, pth[b])
                break
    out = {'objective_definition': 'scalar_sum = unweighted sum of BTN+SB+BB seat-swap dEV (bb per hand dealt; terminal reach included via seat EV); regret not included',
           'equal24': {'raw': peq, 'calibrated': calib(peq)}, 'current144': {'calibrated': calib(p144)}}
    def first_feasible(path, ids):
        for b in range(1, 289):
            p = pred(path[b])
            if all(p[i] <= peq[i] for i in ids):
                return b
        return None
    out['min_budget'] = {
        'scalar_sum: all seats <= equal24': first_feasible(paths['scalar_sum'], seat_ids),
        'scalar_sum: seats+regrets <= equal24': first_feasible(paths['scalar_sum'], all_ids),
        'minimax_seats: all seats <= equal24': first_feasible(paths['minimax_seats'], seat_ids),
        'minimax_seats_and_regrets: all 8 <= equal24': first_feasible(paths['minimax_seats_and_regrets'], all_ids),
        'constrained (weight sweep): all seats <= equal24': best_c[0] if best_c else None,
        'constrained weights': best_c[1] if best_c else None}
    # B' 124 as reported (scalar path at 124) - seat-wise
    def row(a):
        p = pred(a)
        cb = calib(p)
        return {'new': sum(v - 12 for v in a.values()), 'new_by_terminal': {n: sum(v - 12 for k, v in a.items() if k[0] == n) for n in (6, 28)},
                'calibrated': cb, 'ratio_vs_equal24': {i: p[i] / peq[i] for i in metrics}}
    out['B_prime_124_scalar'] = row(paths['scalar_sum'][124])
    out['budget_path'] = {name: {b: row(pth[b]) for b in (48, 108, 124, 144, 192, 288)} for name, pth in paths.items()}
    mb = out['min_budget']
    for key, pth in (('minimax_seats', paths['minimax_seats']), ('minimax_seats_and_regrets', paths['minimax_seats_and_regrets'])):
        b = mb[f"{key}: all seats <= equal24" if key == 'minimax_seats' else 'minimax_seats_and_regrets: all 8 <= equal24']
        if b:
            out[f'min_alloc_{key}'] = {**row(pth[b]), 'alloc': {f'{k[0]}|{k[1]}': v for k, v in pth[b].items() if v > 12}}
    if best_c:
        out['min_alloc_constrained_seats'] = {**row(best_c[2]), 'alloc': {f'{k[0]}|{k[1]}': v for k, v in best_c[2].items() if v > 12}}
    cost = json.load(open(O + 'allocation_downstream.json'))['cpu_min_per_flop']
    for key in [k for k in out if k.startswith('min_alloc') or k == 'B_prime_124_scalar']:
        nb = out[key]['new_by_terminal']
        out[key]['cpu_h'] = (nb[6] * cost['6'] + nb[28] * cost['28']) / 60
        out[key]['wall_h_4cores'] = out[key]['cpu_h'] / 4
    json.dump(out, open(O + 'seatwise.json', 'w'), indent=1)
    fmt = lambda d: ' '.join(f"{i.split(':')[1][:10]}={v:.3f}" for i, v in d.items())
    print('objective:', out['objective_definition'])
    print('min budgets:', json.dumps(mb))
    print("B' 124 ratios vs equal24:", fmt(out['B_prime_124_scalar']['ratio_vs_equal24']))
    print("B' 124 calibrated seats:", {i: round(v, 5) for i, v in out['B_prime_124_scalar']['calibrated'].items() if i.startswith('seat')})
    print('equal24 calibrated seats:', {i: round(v, 5) for i, v in out['equal24']['calibrated'].items() if i.startswith('seat')})
    for name in paths:
        print('path', name)
        for b, r in out['budget_path'][name].items():
            print(f'  {b:3d}', fmt(r['ratio_vs_equal24']))
    for key in [k for k in out if k.startswith('min_alloc')]:
        r = out[key]
        print(key, 'new', r['new'], r['new_by_terminal'], f"cpu {r['cpu_h']:.1f}h wall {r['wall_h_4cores']:.1f}h", fmt(r['ratio_vs_equal24']))
        print('   ', r['alloc'])


if __name__ == '__main__':
    main()
