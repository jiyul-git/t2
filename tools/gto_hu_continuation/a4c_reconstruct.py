#!/usr/bin/env python3
"""A4c design analysis 3 (no solve): additive reconstruction of the pooled A4b panel uncertainty from the stratum-isolated
influence runs, replicate stability of the stratum ranking, and downstream-aware exact integer allocations.

    python3 tools/gto_hu_continuation/a4c_reconstruct.py

Pooled reference = the 60 nested paired A4b replicates at 144 boards (all strata of both terminals resampled at once):
seat-swap dEV of sigma144*_r into G144 (a4c_preanalysis/loss_scaling.json), class strategies / aggregates (paired_results.json).
Isolated = a4c_preanalysis/influence/results.json (one terminal, one stratum resampled, 8 replicates each).
Additivity being tested (independent strata):
  quadratic metrics (seat dEV, class regret):  E[pooled] ~ sum_{n,s} E[isolated_{n,s}]
  signed metrics (aggregate frequencies):      MSE[pooled] ~ sum_{n,s} MSE[isolated_{n,s}]   (MSE about the point solve)
  first-order distances (L1):                  E[pooled] ~ sqrt(sum_{n,s} E[isolated_{n,s}]^2)  (root-sum-square)
Caveat: the pooled bootstrap resampled old / new halves separately (6 + 6 per stratum); the isolated runs resample the 12 jointly.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a4c_influence import NODES, node_data  # noqa: E402

E = 'data/gto_terminal_expansion/'
B = E + 'a4b_panel144/'
OUT = E + 'a4c_preanalysis/'
SEATS = ('BTN', 'SB', 'BB')


def regret_l1(g, a):
    w = g['r']
    tw = sum(w)
    reg = l1 = 0.0
    for h in range(169):
        evs = [g['ev'][k][h] for k in range(len(g['ev']))]
        reg += w[h] * (max(evs) - sum(a['class_strategy'][k][h] * evs[k] for k in range(len(evs))))
        l1 += w[h] * sum(abs(a['class_strategy'][k][h] - g['s'][k][h]) for k in range(len(evs)))
    return reg / tw, l1 / tw


def mean(xs):
    return sum(xs) / len(xs)


def main():
    iso = json.load(open(OUT + 'influence/results.json'))
    pooled_loss = json.load(open(OUT + 'loss_scaling.json'))['records']['144']
    R = json.load(open(B + 'paired_results.json'))
    gnodes = node_data(B + 'points/V144')
    point_agg = R['points']['V144']['aggregates']
    # pooled metrics per replicate
    pooled = []
    for k, rep in R['boot'].items():
        v = rep['V144']
        m = {'seat_dEV': {s: pooled_loss[k][s]['dEV'] for s in SEATS}, 'regret': {}, 'L1': {}, 'agg': {}}
        for name in NODES:
            m['regret'][name], m['L1'][name] = regret_l1(gnodes[name], v['key_nodes'][name])
        for nm, acts in v['aggregates'].items():
            for ac, x in acts.items():
                m['agg'][f'{nm}|{ac}'] = x - point_agg[nm][ac]
        pooled.append(m)
    groups = {}
    for v in iso.values():
        groups.setdefault((v['n'], v['stratum']), []).append(v)
    out = {'n_isolated_groups': len(groups), 'reps_per_group': sorted({len(g) for g in groups.values()}), 'pooled_replicates': len(pooled), 'reconstruction': {}}
    # 1. reconstruction
    def iso_dev(v):
        return {f'{nm}|{ac}': x - point_agg[nm][ac] for nm, acts in v['aggregates'].items() for ac, x in acts.items()}
    rec = out['reconstruction']
    for s in SEATS:
        pred = sum(mean([max(r['seat_dEV'][s], 0.0) for r in g]) for g in groups.values())
        pred_signed = sum(mean([r['seat_dEV'][s] for r in g]) for g in groups.values())
        obs = mean([p['seat_dEV'][s] for p in pooled])
        rec[f'seat_dEV:{s}'] = {'predicted_sum': pred_signed, 'observed_pooled_mean': obs, 'ratio_pred_over_obs': pred_signed / obs if obs else None}
    base_reg = {name: regret_l1(gnodes[name], {'class_strategy': gnodes[name]['s']})[0] for name in NODES}
    out['baseline_regret_of_G144_own_strategy'] = base_reg
    for name in NODES:
        # excess over the baseline solve's own residual regret at that node (the baseline is counted once, not once per group)
        pred = sum(mean([r['regret'][name] - base_reg[name] for r in g]) for g in groups.values())
        obs = mean([p['regret'][name] for p in pooled]) - base_reg[name]
        rec[f'regret_excess:{name}'] = {'predicted_sum': pred, 'observed_pooled_mean': obs, 'ratio_pred_over_obs': pred / obs if obs else None}
        pl1 = sum(mean([r['L1'][name] for r in g]) ** 2 for g in groups.values()) ** 0.5
        ol1 = mean([p['L1'][name] for p in pooled])
        rec[f'L1:{name}'] = {'predicted_rss': pl1, 'observed_pooled_mean': ol1, 'ratio_pred_over_obs': pl1 / ol1 if ol1 else None}
    keys = [k for k in pooled[0]['agg'] if mean([p['agg'][k] ** 2 for p in pooled]) > 1e-8]
    for k in keys:
        pred = sum(mean([iso_dev(r)[k] ** 2 for r in g]) for g in groups.values())
        obs = mean([p['agg'][k] ** 2 for p in pooled])
        rec[f'agg_MSE:{k}'] = {'predicted_sum': pred, 'observed_pooled': obs, 'ratio_pred_over_obs': pred / obs}
    # pooled sampling uncertainty of the observed means (to judge the ratios)
    for s in SEATS:
        xs = [p['seat_dEV'][s] for p in pooled]
        m_ = mean(xs)
        rec[f'seat_dEV:{s}']['observed_se'] = (sum((x - m_) ** 2 for x in xs) / (len(xs) - 1) / len(xs)) ** 0.5
        rec[f'seat_dEV:{s}']['predicted_se'] = sum(
            (sum((r['seat_dEV'][s] - mean([q['seat_dEV'][s] for q in g])) ** 2 for r in g) / (len(g) - 1) / len(g)) for g in groups.values()) ** 0.5
    # 2. stability of the ranking (total seat EV contribution BTN+SB+BB per (terminal, stratum))
    def contrib(g):
        return mean([sum(r['seat_dEV'][s] for s in SEATS) for r in g])
    base = {k: contrib(g) for k, g in groups.items()}
    order = sorted(base, key=base.get, reverse=True)
    loo_changes = []
    for k, g in groups.items():
        for i in range(len(g)):
            alt = dict(base)
            alt[k] = contrib(g[:i] + g[i + 1:])
            o2 = sorted(alt, key=alt.get, reverse=True)
            loo_changes.append({'group': f'{k[0]}|{k[1]}', 'dropped': i, 'top5_same_set': set(o2[:5]) == set(order[:5]), 'top3_same_order': o2[:3] == order[:3]})
    rng = random.Random(7)
    top5_freq = {}
    for _ in range(2000):
        alt = {k: contrib([rng.choice(g) for _ in g]) for k, g in groups.items()}
        o2 = sorted(alt, key=alt.get, reverse=True)
        for k in o2[:5]:
            top5_freq[f'{k[0]}|{k[1]}'] = top5_freq.get(f'{k[0]}|{k[1]}', 0) + 1
    out['stability'] = {'ranking': [(f'{k[0]}|{k[1]}', base[k]) for k in order],
                        'loo_top5_set_unchanged_fraction': mean([c['top5_same_set'] for c in loo_changes]),
                        'loo_top3_order_unchanged_fraction': mean([c['top3_same_order'] for c in loo_changes]),
                        'bootstrap_top5_membership': {k: v / 2000 for k, v in sorted(top5_freq.items(), key=lambda kv: -kv[1])}}
    json.dump(out, open(OUT + 'reconstruction.json', 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__' and len(sys.argv) == 1:
    main()


def allocate():
    """Downstream-aware exact integer allocation over (terminal, stratum), FPC-aware.
    c_{n,s,metric} = mean isolated contribution at 12 boards under with-replacement resampling (bootstrap variance factor 11/144 s^2);
    the design contribution with m boards drawn without replacement from K classes is c * (144/11) * (1 - m/K) / m."""
    import itertools
    import make_panel as mp
    iso = json.load(open(OUT + 'influence/results.json'))
    groups = {}
    for v in iso.values():
        groups.setdefault((v['n'], v['stratum']), []).append(v)
    deck = [(r, s) for r in range(13) for s in range(4)]
    K = {}
    for f in itertools.combinations(deck, 3):
        K.setdefault(mp.stratum(f), set()).add(mp.canon(f))
    K = {s: len(v) for s, v in K.items()}
    gn = node_data(B + 'points/V144')
    base_reg = {name: regret_l1(gn[name], {'class_strategy': gn[name]['s']})[0] for name in NODES}
    metrics = {f'seat_dEV:{s}': (lambda r, s=s: r['seat_dEV'][s]) for s in SEATS}
    metrics.update({f'regret_excess:{n}': (lambda r, n=n: r['regret'][n] - base_reg[n]) for n in NODES})
    c = {k: {m: max(mean([f(r) for r in g]), 0.0) for m, f in metrics.items()} for k, g in groups.items()}
    fac = lambda k, m: (144 / 11) * (1 - m / K[k[1]]) / m
    def predict(alloc):
        return {m: sum(c[k][m] * fac(k, alloc[k]) for k in c) for m in metrics}
    obj = lambda k: c[k]['seat_dEV:BTN'] + c[k]['seat_dEV:SB'] + c[k]['seat_dEV:BB']
    def greedy(budget, start=12):
        a = {k: start for k in c}
        for _ in range(budget):
            cand = [k for k in c if a[k] < K[k[1]]]
            if not cand:
                break
            best = max(cand, key=lambda k: obj(k) * (fac(k, a[k]) - fac(k, a[k] + 1)))
            a[best] += 1
        return a
    cost = {}
    for n, d in ((6, B + 'node6/flops/'), (28, B + 'node28/flops/')):
        ms = [json.load(open(os.path.join(d, f)))['cost']['solve_ms'] for f in os.listdir(d) if f.endswith('.json') and f != 'run_ledger.jsonl']
        cost[n] = mean(ms) / 60000
    out = {'cpu_min_per_flop': cost, 'options': {}}
    cur = {k: 12 for k in c}
    out['options']['current_144'] = {'new_solves': 0, 'predicted': predict(cur)}
    eq = {k: 24 for k in c}
    out['options']['equal_24 (C0)'] = {'new_solves': 288, 'predicted': predict(eq)}
    for name, budget in (('D_small_48', 48), ('B_108', 108), ('C_144', 144), ('C_192', 192), ('A_288', 288)):
        a = greedy(budget)
        out['options'][name] = {'new_solves': budget, 'alloc': {f'{k[0]}|{k[1]}': v for k, v in a.items() if v > 12},
                                'new_by_terminal': {n: sum(v - 12 for k, v in a.items() if k[0] == n) for n in (6, 28)},
                                'predicted': predict(a)}
    for o in out['options'].values():
        nb = o.get('new_by_terminal', {6: o['new_solves'] // 2, 28: o['new_solves'] // 2})
        o['cpu_h'] = sum(nb[n] * cost[n] for n in nb) / 60
        o['wall_h_4cores'] = o['cpu_h'] / 4
    # which budget matches equal-24 on the downstream objective
    tgt = sum(out['options']['equal_24 (C0)']['predicted'][f'seat_dEV:{s}'] for s in SEATS)
    for budget in range(0, 289, 4):
        a = greedy(budget)
        if sum(predict(a)[f'seat_dEV:{s}'] for s in SEATS) <= tgt:
            out['matching_equal24_downstream'] = {'new_solves': budget, 'alloc': {f'{k[0]}|{k[1]}': v for k, v in a.items() if v > 12}}
            break
    json.dump(out, open(OUT + 'allocation_downstream.json', 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'allocate':
    allocate()
