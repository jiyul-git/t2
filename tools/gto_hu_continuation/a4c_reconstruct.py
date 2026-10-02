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


if __name__ == '__main__':
    main()
