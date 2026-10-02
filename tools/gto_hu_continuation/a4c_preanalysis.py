#!/usr/bin/env python3
"""A4c design pre-analysis (no new flop or preflop solve; existing A4b artifacts only; does not alter any A4b/A4R result).

    python3 tools/gto_hu_continuation/a4c_preanalysis.py loss      # bootstrap estimate of the EV error of sigma_N vs truth, N = 72, 144
    python3 tools/gto_hu_continuation/a4c_preanalysis.py design    # allocation / estimator / FPC diagnostics of the panel

loss: for every paired replicate r, sigma_N*_r (the solve on resampled tables) is swapped seat by seat into the point game G_N
(own solve sigma_N); by the bootstrap principle the distribution of dEV(sigma_N*_r -> G_N) approximates that of dEV(sigma_N -> truth).
The 72 -> 144 ratio gives the empirical scaling of the panel-induced EV error, used only to project 288 (a projection, not a result).
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4r_robust as A  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
B = E + 'a4b_panel144/'
OUT = E + 'a4c_preanalysis/'
SEATS = {'CO': (0, 'all'), 'BTN': (1, 'all'), 'SB': (2, 'all'), 'BB': (3, 'all')}


def loss(a):
    R = json.load(open(B + 'paired_results.json'))
    P = R['points']
    jobs = []
    for k, rep in R['boot'].items():
        for size in (72, 144):
            jobs.append((k, size, P[f'V{size}'], rep[f'V{size}']))
    os.makedirs(OUT + 'evals', exist_ok=True)

    def one(j):
        k, size, game, donor = j
        rec = {}
        for name, (seat, root) in SEATS.items():
            s = A.splice(game, donor, seat, root, OUT + f'evals/r{int(k):02d}_N{size}_{name}.json')
            rec[name] = {'dEV': game['evs'][seat] - s['evs'][seat], 'gap_diff': s['gaps'][seat] - game['gaps'][seat], 'own_gap': game['gaps'][seat]}
        return k, size, rec
    res = {}
    with ThreadPoolExecutor(2) as ex:
        for k, size, rec in ex.map(one, jobs):
            res.setdefault(str(size), {})[k] = rec
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]
    summ = {}
    for name in SEATS:
        row = {}
        for size in ('72', '144'):
            xs = [r[name]['dEV'] for r in res[size].values()]
            row[size] = {'mean': sum(xs) / len(xs), 'q05': q(xs, .05), 'q50': q(xs, .5), 'q95': q(xs, .95), 'own_gap_median': q([r[name]['own_gap'] for r in res[size].values()], .5),
                         'max_abs_dEV_minus_gapdiff': max(abs(r[name]['dEV'] - r[name]['gap_diff']) for r in res[size].values())}
        if row['72']['mean'] > 1e-6:
            ratio = row['144']['mean'] / row['72']['mean']
            row['ratio_144_over_72_mean'] = ratio
            row['projected_288_mean_if_same_ratio'] = row['144']['mean'] * ratio
        summ[name] = row
    out = {'note': 'design pre-analysis; bootstrap estimate of the EV error of the panel-N policy relative to the panel-N game, used as a proxy for its error vs truth; 288 numbers are projections',
           'replicates': len(res['72']), 'seats': summ}
    json.dump({'summary': out, 'records': res}, open(OUT + 'loss_scaling.json', 'w'), indent=1)
    print(json.dumps(out, indent=1))


def design(a):
    import make_panel as mp
    import itertools
    from aggregate import class_combos, parse_board
    panel = json.load(open(os.path.join(ROOT, 'data/gto_hu_continuation/panel_v3_144.json')))
    deck = [(r, s) for r in range(13) for s in range(4)]
    classes = {}
    for f in itertools.combinations(deck, 3):
        k = mp.canon(f)
        classes.setdefault(k, [0, mp.stratum(f)])
        classes[k][0] += 1
    pool = {}
    for k, (n, st) in classes.items():
        pool.setdefault(st, {})[mp.fmt(k)] = n
    strata = {}
    for f in panel['panel']:
        strata.setdefault(f['stratum'], []).append(f['board'])   # list order = draw order (v1, then v2 extension, then v3 extension)
    p_str = {s: panel['strata'][s]['probability'] for s in strata}
    labels = json.load(open(E + 'terminals/p9_node6.json'))['class_labels']
    combos = [class_combos(l) for l in labels]
    compat = {b: [sum(1 for c in cc if c[0] not in parse_board(b) and c[1] not in parse_board(b)) / len(cc) for cc in combos] for bs in strata.values() for b in bs}
    term = {n: json.load(open(E + f'outer_m28_6/k14/terminal_node{n}.json')) for n in (28, 6)}
    reach = {n: {p['position']: p['class_reach_normalized'] for p in term[n]['players']} for n in term}
    vals = {}
    for n in (28, 6):
        for bs in strata.values():
            for b in bs:
                f = B + f'node{n}/flops/{b}.json'
                if not os.path.exists(f):
                    f = E + f'outer_m28_6/k14/node{n}/flops/{b}.json'
                for pl in json.load(open(f))['players']:
                    vals[(n, pl['position'], b)] = pl['gross_eps']
    rho = 19600 / 22100
    out = {'strata': {}}
    # per stratum: sampling fraction (classes and raw-flop mass), within-stratum SD of the reach-weighted value y_b, Des Raj vs equal-weight
    tot_var = {'equal_24': 0.0, 'equal_12': 0.0}
    sd_s = {}
    for s, bs in sorted(strata.items()):
        N = sum(pool[s].values())
        frac_cls = len(bs) / len(pool[s])
        frac_mass = sum(pool[s][b] for b in bs) / N
        ys, dr_diff = [], []
        for n in (28, 6):
            for pos, rr in reach[n].items():
                y = [sum(rr[h] * compat[b][h] * (vals[(n, pos, b)][h] or 0.0) for h in range(169)) / rho for b in bs]
                ys.append(y)
                # Des Raj (ordered PPS without replacement) estimate of the stratum mean vs the equal-weight mean
                t, cum_y, cum_p = [], 0.0, 0.0
                for b, yi in zip(bs, y):
                    p = pool[s][b] / N
                    t.append(cum_y + yi * (1 - cum_p))
                    cum_y += yi * p  # running sum of p_j y_j (mean units)
                    cum_p += p
                dr = sum(t) / len(t)
                dr_diff.append(dr - sum(y) / len(y))
        sd = sum((sum((x - sum(y) / len(y)) ** 2 for x in y) / (len(y) - 1)) ** 0.5 for y in ys) / len(ys)
        sd_s[s] = sd
        out['strata'][s] = {'P': p_str[s], 'pool_classes': len(pool[s]), 'boards': len(bs), 'sampling_fraction_classes': frac_cls,
                            'sampling_fraction_rawflop_mass': frac_mass, 'sd_reachweighted_value_bb': sd,
                            'desraj_minus_equalweight_bb_mean_abs': sum(abs(x) for x in dr_diff) / len(dr_diff)}
    # allocation comparison for a 288-board total with >= 12 per stratum (existing boards kept)
    def var(alloc):
        return sum((p_str[s] * sd_s[s]) ** 2 / alloc[s] for s in alloc)
    eq24 = {s: 24 for s in strata}
    # Neyman allocation subject to n_s >= 12, sum = 288 (water-filling)
    w = {s: p_str[s] * sd_s[s] for s in strata}
    fixed = {}
    while True:
        free = [s for s in strata if s not in fixed]
        budget = 288 - sum(fixed.values())
        tw = sum(w[s] for s in free)
        alloc = {s: budget * w[s] / tw for s in free}
        low = [s for s in free if alloc[s] < 12]
        if not low:
            break
        for s in low:
            fixed[s] = 12
    ney = {**fixed, **alloc}
    ney_int = {s: max(12, round(v)) for s, v in ney.items()}
    out['allocation_288'] = {'equal_24_variance': var(eq24), 'neyman_variance': var(ney_int), 'neyman_alloc': ney_int,
                             'variance_ratio_neyman_over_equal': var(ney_int) / var(eq24),
                             'equal_design_boards_for_same_variance_as_neyman288': 288 * var(eq24) / var(ney_int)}
    # boards needed (Neyman, >=12) for the same variance as equal-24
    for total in range(144, 289, 6):
        w2 = dict(w)
        fx = {}
        while True:
            fr = [s for s in strata if s not in fx]
            bud = total - sum(fx.values())
            tw = sum(w2[s] for s in fr)
            al = {s: bud * w2[s] / tw for s in fr}
            lo = [s for s in fr if al[s] < 12]
            if not lo:
                break
            for s in lo:
                fx[s] = 12
        a2 = {s: max(12, round(v)) for s, v in {**fx, **al}.items()}
        if var(a2) <= var(eq24):
            out['allocation_288']['neyman_total_boards_matching_equal_24'] = {'total': sum(a2.values()), 'alloc': a2}
            break
    json.dump(out, open(OUT + 'design.json', 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    {'loss': loss, 'design': design}[sys.argv[1]](None)
