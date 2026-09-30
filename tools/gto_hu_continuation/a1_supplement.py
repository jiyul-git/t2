#!/usr/bin/env python3
"""A1 supplement: bootstrap CI of the signed range-EV shift (solved - legacy) and of the reach-weighted |delta|
(same stratified bootstrap and estimator as aggregate.py, seed 20260928 + 9), and the sensitivity to the one
non-converged flop (AcKd8h dropped from its stratum). Writes data/gto_terminal_expansion/node6_72/supplement.json.
"""
import json
import os
import random
import sys

sys.path.insert(0, 'tools/gto_hu_continuation')
from aggregate import class_combos, parse_board  # noqa: E402

D = 'data/gto_terminal_expansion/'


def main():
    term = json.load(open(D + 'terminals/p9_node6.json'))
    panel = json.load(open('data/gto_hu_continuation/panel_v2_72.json'))
    combos = [class_combos(l) for l in term['class_labels']]
    flops = {f['board']: json.load(open(os.path.join(D + 'node6_72/flops', f['board'] + '.json'))) for f in panel['panel']}
    strata = {}
    for f in panel['panel']:
        strata.setdefault(f['stratum'], []).append(f['board'])
    p_str = {s: panel['strata'][s]['probability'] for s in strata}
    compat = {b: [sum(1 for c in cc if c[0] not in parse_board(b) and c[1] not in parse_board(b)) / len(cc) for cc in combos] for b in flops}
    val = {(b, pl['position']): pl['gross_eps'] for b, d in flops.items() for pl in d['players']}
    rho = 19600 / 22100

    def est(pos, draw):
        out = []
        for h in range(169):
            tot = 0.0
            for s, bs in draw.items():
                num = sum(compat[b][h] * val[(b, pos)][h] for b in bs if val[(b, pos)][h] is not None)
                tot += p_str[s] * num / len(bs)
            out.append(tot / sum(p_str.values()) / rho)
        return out

    pl = {p['position']: p for p in term['players']}
    stats = lambda pos, v: {'range_ev_shift': sum(r * (x - y) for r, x, y in zip(pl[pos]['class_reach_normalized'], v, pl[pos]['legacy_gross'])),
                            'reach_weighted_abs': sum(r * abs(x - y) for r, x, y in zip(pl[pos]['class_reach_normalized'], v, pl[pos]['legacy_gross'])),
                            'mean_abs': sum(abs(x - y) for x, y in zip(v, pl[pos]['legacy_gross'])) / 169}
    res = {'bootstrap': 2000, 'seed': 20260928 + 9, 'seats': {}}
    rng = random.Random(20260928 + 9)
    boots = {pos: [] for pos in pl}
    for _ in range(2000):
        draw = {s: [rng.choice(bs) for _ in bs] for s, bs in strata.items()}
        for pos in pl:
            boots[pos].append(stats(pos, est(pos, draw)))
    for pos in pl:
        pt = stats(pos, est(pos, strata))
        ci = {k: [sorted(b[k] for b in boots[pos])[50], sorted(b[k] for b in boots[pos])[1949]] for k in pt}
        frac_pos = sum(1 for b in boots[pos] if b['range_ev_shift'] > 0) / 2000
        drop = {s: [b for b in bs if b != 'AcKd8h'] for s, bs in strata.items()}
        res['seats'][pos] = {'point': pt, 'ci95': ci, 'bootstrap_share_shift_positive': frac_pos,
                             'without_AcKd8h': stats(pos, est(pos, {s: bs for s, bs in drop.items() if bs}))}
    res['nonconverged'] = {b: flops[b]['exploitability_pct_pot'] for b in flops if flops[b]['exploitability_pct_pot'] > flops[b]['provenance_key']['target_exploitability_pct_pot']}
    res['AcKd8h_stratum'] = next(f['stratum'] for f in panel['panel'] if f['board'] == 'AcKd8h')
    res['AcKd8h_stratum_size'] = len(strata[res['AcKd8h_stratum']])
    json.dump(res, open(D + 'node6_72/supplement.json', 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
