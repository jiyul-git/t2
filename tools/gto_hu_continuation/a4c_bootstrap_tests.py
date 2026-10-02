#!/usr/bin/env python3
"""A4c amendment 1 validation (before any bootstrap replicate): structure assertions on the real panels, synthetic covariance
tests of the joint draw, marginal check against the old terminal-wise scheme, and a table-level A4b continuity diagnostic."""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4c_run as C  # noqa: E402

OUT = C.OUT


def corr(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    return sxy / (sx * sy) if sx and sy else float('nan')


def var(x):
    m = sum(x) / len(x)
    return sum((a - m) ** 2 for a in x) / (len(x) - 1)


def strat(y, draws, p):
    return sum(p[s] * sum(y[b] for b in bs) / len(bs) for s, bs in draws.items() if bs) / sum(p[s] for s, bs in draws.items() if bs)


def struct_from_panels():
    st = {}
    for n in (6, 28):
        p, old, new = C.panel(n)
        st[n] = {'old': old, 'new': new, 'p': {s: v['probability'] for s, v in p['strata'].items()}}
    return st


def indep_draw(rng, st):
    d = {}
    for n in (6, 28):
        o, w = {}, {}
        for s in sorted(st[n]['old']):
            o[s] = [rng.choice(st[n]['old'][s]) for _ in st[n]['old'][s]]
            w[s] = [rng.choice(st[n]['new'][s]) for _ in st[n]['new'][s]] if st[n]['new'][s] else []
        d[n] = (o, w)
    return d


def ext(o, w):
    return {s: o[s] + w[s] for s in o}


def main():
    res = {}
    st = struct_from_panels()
    J = C.joint_structure(st)       # raises on any failed assertion
    res['structure'] = {'old_identical_all_strata': True, 'new_prefix_all_strata': True,
                        'per_stratum': {s: {'S': len(j['S']), 'E6': len(j['E6']), 'E28': len(j['E28'])} for s, j in J.items()}}
    p = st[6]['p']
    # A / B: identical panels and identical values for both terminals -> identical perturbations, correlation 1
    rng = random.Random(1)
    allb = sorted({b for s in J for b in J[s]['old'] + J[s]['S'] + J[s]['E6'] + J[s]['E28']})
    y = {b: rng.gauss(0, 1) for b in allb}
    Jid = {s: {'old': J[s]['old'], 'S': J[s]['S'], 'E6': [], 'E28': []} for s in J}
    r = random.Random(2)
    a6, a28 = [], []
    for _ in range(2000):
        d, _ = C.joint_draw(r, Jid)
        a6.append(strat(y, ext(*d[6]), p))
        a28.append(strat(y, ext(*d[28]), p))
    res['A_identity_max_abs_diff'] = max(abs(u - v) for u, v in zip(a6, a28))
    res['B_perfect_correlation'] = corr(a6, a28)
    # C: shared parts carry no variance (constant values), tails only -> independent perturbations
    yc = dict(y)
    for s in J:
        for b in J[s]['old'] + J[s]['S']:
            yc[b] = 0.0
    Jt = {s: {'old': J[s]['old'], 'S': [], 'E6': J[s]['S'] + J[s]['E6'], 'E28': J[s]['S'] + J[s]['E28']} for s in J}
    c6, c28 = [], []
    for _ in range(4000):
        d, _ = C.joint_draw(r, Jt)
        c6.append(strat(yc, ext(*d[6]), p))
        c28.append(strat(yc, ext(*d[28]), p))
    res['C_independent_tails_correlation'] = corr(c6, c28)
    res['C_expected_sd_of_null_correlation'] = 1 / 4000 ** 0.5
    # D: marginal per-terminal variance, joint vs old terminal-wise scheme (same synthetic values per terminal)
    y6 = {b: rng.gauss(0, 1) for b in allb}
    y28 = {b: 0.7 * y6[b] + 0.3 * rng.gauss(0, 1) for b in allb}
    jv = {6: [], 28: []}
    iv = {6: [], 28: []}
    for _ in range(4000):
        d, _ = C.joint_draw(r, J)
        jv[6].append(strat(y6, ext(*d[6]), p))
        jv[28].append(strat(y28, ext(*d[28]), p))
        d2 = indep_draw(r, st)
        iv[6].append(strat(y6, ext(*d2[6]), p))
        iv[28].append(strat(y28, ext(*d2[28]), p))
    res['D_marginal'] = {n: {'var_joint': var(jv[n]), 'var_terminalwise': var(iv[n]), 'ratio': var(jv[n]) / var(iv[n]),
                             'mean_joint': sum(jv[n]) / len(jv[n]), 'mean_terminalwise': sum(iv[n]) / len(iv[n])} for n in (6, 28)}
    res['D_cross_correlation'] = {'joint': corr(jv[6], jv[28]), 'terminalwise': corr(iv[6], iv[28])}
    # A4b continuity (table level, real 144-board values): cross-terminal correlation of the reach-weighted table perturbation
    import a4b_panel144 as B
    strata, p_str, compat = B.load_panel(144)
    vals = {n: B.flop_values(n, strata) for n in (6, 28)}
    reach = {n: {pl['position']: pl['class_reach_normalized'] for pl in json.load(open(C.A3 + f'k14/terminal_node{n}.json'))['players']} for n in (6, 28)}
    yb = {n: {b: sum(sum(reach[n][pos][h] * compat[b][h] * (vals[n][b][pos][h] or 0.0) for h in range(169)) for pos in reach[n]) for b in vals[n]} for n in (6, 28)}
    sh, ind = ([], []), ([], [])
    r = random.Random(3)
    for _ in range(4000):
        dr = {s: [r.choice(bs) for _ in bs] for s, bs in strata.items()}
        sh[0].append(strat(yb[6], dr, p_str))
        sh[1].append(strat(yb[28], dr, p_str))
        d6 = {s: [r.choice(bs) for _ in bs] for s, bs in strata.items()}
        d28 = {s: [r.choice(bs) for _ in bs] for s, bs in strata.items()}
        ind[0].append(strat(yb[6], d6, p_str))
        ind[1].append(strat(yb[28], d28, p_str))
    res['A4b_continuity_table_level'] = {'cross_terminal_corr_shared_draw (A4b scheme)': corr(*sh), 'cross_terminal_corr_independent_draws': corr(*ind),
                                         'note': 'reach-weighted terminal value (sum over seats) on the 144 panel; diagnostic only, A4b results unchanged'}
    ok = (res['A_identity_max_abs_diff'] == 0 and abs(res['B_perfect_correlation'] - 1) < 1e-12 and abs(res['C_independent_tails_correlation']) < 4 / 4000 ** 0.5
          and all(abs(v['ratio'] - 1) < 0.1 for v in res['D_marginal'].values()))
    res['all_pass'] = ok
    C.atomic(res, OUT + 'amendment1_validation.json')
    print(json.dumps({k: v for k, v in res.items() if k != 'structure'}, indent=1))
    print('structure', res['structure']['per_stratum'])
    if not ok:
        raise SystemExit('validation failed')


if __name__ == '__main__':
    main()
