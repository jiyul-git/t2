#!/usr/bin/env python3
"""A4c design analysis 2 (no solve): exact design bias of the equal-weight estimator under sequential PPS without
replacement, and exact integer allocations with the finite-population correction, per terminal and joint.

Estimand per stratum: raw-flop mean mu_s = sum_k n_k y_k / N_s (n_k = raw flops of canonical class k). Raw flops of one class
are suit-isomorphic, so per-class (169-class) values are equal across them: raw-flop mean = multiplicity-weighted class mean.
Equal-weight mean of m sequential PPSWOR draws has expectation sum_k (pi_k / m) y_k (pi_k = inclusion probability), so its
bias is sum_k (pi_k/m - n_k/N_s) y_k; it is zero when all n_k in the stratum are equal (PPSWOR = SRSWOR).
"""
import itertools, json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_panel as mp
E = 'data/gto_terminal_expansion/'
OUT = E + 'a4c_preanalysis/'


def pools():
    deck = [(r, s) for r in range(13) for s in range(4)]
    cl = {}
    for f in itertools.combinations(deck, 3):
        k = mp.canon(f)
        cl.setdefault(k, [0, mp.stratum(f)])
        cl[k][0] += 1
    out = {}
    for k, (n, s) in cl.items():
        out.setdefault(s, {})[mp.fmt(k)] = n
    return out


def incl_share(pool, m, sims=200000, seed=1):
    """share of trips (multiplicity-4) classes among m sequential PPSWOR draws vs their raw-flop mass share."""
    rng = random.Random(seed)
    items = list(pool.items())
    small = {b for b, n in items if n == 4}
    tot_small = 0
    for _ in range(sims):
        pl = list(items)
        for _ in range(m):
            t = sum(n for _, n in pl)
            x = rng.uniform(0, t)
            acc = 0
            for i, (b, n) in enumerate(pl):
                acc += n
                if x <= acc:
                    tot_small += b in small
                    pl.pop(i)
                    break
    return tot_small / (sims * m), sum(n for b, n in items if b in small) / sum(pool.values())


def main():
    P = pools()
    d = json.load(open(OUT + 'design.json'))
    panel = json.load(open('data/gto_hu_continuation/panel_v3_144.json'))
    pr = {s: v['probability'] for s, v in panel['strata'].items()}
    # 1. bias in the paired strata (the only ones with unequal multiplicities)
    bias = {}
    for s in ('paired/A', 'paired/KQ', 'paired/J_or_lower'):
        sd = d['strata'][s]['sd_reachweighted_value_bb']
        for m in (12, 24, 36):
            share, mass = incl_share(P[s], m, sims=20000)
            # |bias| <= |share - mass| * |ybar_trips - ybar_rest|; bound the gap by 4 within-stratum SDs (no trips board is in the panel)
            bias[f'{s} m={m}'] = {'trips_share_in_sample': share, 'trips_raw_mass_share': mass,
                                  'bias_bound_bb_stratum': abs(share - mass) * 4 * sd,
                                  'bias_bound_bb_total_contribution': pr[s] * abs(share - mass) * 4 * sd}
    # 2. exact integer allocations with FPC (SRSWOR on K_s classes), greedy marginal variance reduction from 12 per stratum
    K = {s: len(P[s]) for s in P}
    sdj = {s: d['strata'][s]['sd_reachweighted_value_bb'] for s in P}
    def var(sd, alloc):
        return sum((pr[s] * sd[s]) ** 2 / alloc[s] * (1 - alloc[s] / K[s]) * K[s] / (K[s] - 1) for s in alloc)
    def greedy(sd, total):
        a = {s: 12 for s in P}
        while sum(a.values()) < total:
            best = max(P, key=lambda s: var(sd, a) - var(sd, {**a, s: a[s] + 1}))
            a[best] += 1
        return a
    eq = {s: 24 for s in P}
    out = {'estimand': 'raw-flop mean per stratum (= multiplicity-weighted canonical-class mean), stratified by P(s); card removal by ranges handled per class by compat / rho as before',
           'design_bias': bias, 'allocations_table_level_joint': {}}
    v_eq = var(sdj, eq)
    for T in (198, 216, 240, 288):
        a = greedy(sdj, T)
        out['allocations_table_level_joint'][T] = {'alloc': a, 'total': sum(a.values()), 'new_per_terminal': sum(a.values()) - 144,
                                                   'var_ratio_vs_equal24_fpc': var(sdj, a) / v_eq,
                                                   'max_sampling_fraction': max(a[s] / K[s] for s in a)}
    out['equal24_var_fpc'] = v_eq
    json.dump(out, open(OUT + 'design2.json', 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
