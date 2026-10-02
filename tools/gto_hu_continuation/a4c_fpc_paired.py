#!/usr/bin/env python3
"""Design-based variance factor for the three paired strata (unequal multiplicity: trips 4 vs 12 raw flops).

For pseudo-populations y_k ~ iid N(0,1) over the stratum's classes, the sequential PPSWOR draw of m classes is repeated and the
variance of the equal-weight mean about the raw-flop mean is compared with the SRSWOR formula (1 - m/K) S^2 / m, S^2 the
population variance of y. ratio = E_pop[design MSE] / E_pop[SRSWOR variance]; lambda_paired^2 = ratio * (1 - f) * m/(m-1)
replaces the SRS factor in the A4c rescaled bootstrap. No solve; the true y of unsampled classes is not needed.
"""
import json, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a4c_design2 import pools

def main():
    P = pools()
    rng = random.Random(11)
    out = {}
    for s in ('paired/A', 'paired/KQ', 'paired/J_or_lower'):
        items = list(P[s].items())
        K, N = len(items), sum(n for _, n in items)
        for m in (12, 18, 24, 32, 36):
            mse = srs = 0.0
            npop, ndraw = 40, 1500
            for _ in range(npop):
                y = {b: rng.gauss(0, 1) for b, _ in items}
                mu = sum(n * y[b] for b, n in items) / N
                ybar = sum(y.values()) / K
                S2 = sum((v - ybar) ** 2 for v in y.values()) / (K - 1)
                srs += (1 - m / K) * S2 / m
                acc = 0.0
                for _ in range(ndraw):
                    pl = list(items)
                    tot = 0.0
                    for _ in range(m):
                        t = sum(n for _, n in pl)
                        x = rng.uniform(0, t)
                        a = 0
                        for i, (b, n) in enumerate(pl):
                            a += n
                            if x <= a:
                                tot += y[b]
                                pl.pop(i)
                                break
                    acc += (tot / m - mu) ** 2
                mse += acc / ndraw
            r = mse / srs
            out[f'{s} m={m}'] = {'K': K, 'ratio_design_mse_over_srswor': r, 'lambda_sq_paired': r * (1 - m / K) * m / (m - 1),
                                 'lambda_sq_srs': (1 - m / K) * m / (m - 1)}
            print(s, m, round(r, 3), flush=True)
    json.dump(out, open('data/gto_terminal_expansion/a4c_preanalysis/fpc_paired.json', 'w'), indent=1)

if __name__ == '__main__':
    main()
