#!/usr/bin/env python3
"""Aggregate per-flop continuation artifacts into one injectable terminal table.

    python3 tools/gto_hu_continuation/aggregate.py <terminal.json> <panel.json> <flop_dir> <out_table.json> \
        [--outer K] [--boot 2000]

value_convention = gross_share (bb, zero rake). Per class h and player (primary,
estimator = "ht_rho", Horvitz-Thompson with the exact full-deck normaliser):
  v_h = (1/rho) * sum_s P(s) * mean_{f in panel_s} [c_hf v_hf],   rho = C(50,3)/C(52,3)
where c_hf = share of class-h combos not blocked by board f (draws within a stratum are
already proportional to raw-flop count). For the full 1,755-flop set this equals the
class-conditional mean; on a small panel it keeps sum_players sum_h range_h v_h = pot up to
the preflop model's missing inter-player card removal (the ratio estimator
sum c v / sum c, kept as "gross_ratio" for sensitivity, does not: its per-class panel
normaliser varies, 0.77-0.97 on panel_v1, which created 0.35 bb of chips at k0).
Guard: exits non-zero if |unallocated| > --max-unallocated (default 0.05 bb).
95% CI: stratified bootstrap (resample flops within each stratum), fixed seed.
Invariant (at the terminal's ACTUAL arriving ranges, which differ from the EPS-floored
ranges the solves used by <= EPS per class):
  sum_player sum_h range_h * v_h = pot  ->  reported as 'unallocated_bb'.
A per-flop artifact is accepted only if its provenance ranges hash equals the terminal's.
"""
import argparse
import glob
import json
import os
import random

RANKS = '23456789TJQKA'


def class_combos(label):
    r1, r2 = RANKS.index(label[0]), RANKS.index(label[1])
    out = []
    for s1 in range(4):
        for s2 in range(4):
            if len(label) == 2:
                if s2 > s1:
                    out.append(((r1, s1), (r2, s2)))
            elif label[2] == 's':
                if s1 == s2:
                    out.append(((r1, s1), (r2, s2)))
            elif s1 != s2:
                out.append(((r1, s1), (r2, s2)))
    return out


def parse_board(b):
    return {(RANKS.index(b[i]), 'cdhs'.index(b[i + 1])) for i in range(0, len(b), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('terminal')
    ap.add_argument('panel')
    ap.add_argument('flop_dir')
    ap.add_argument('out')
    ap.add_argument('--outer', type=int, default=0)
    ap.add_argument('--boot', type=int, default=2000)
    ap.add_argument('--max-unallocated', type=float, default=0.05)
    a = ap.parse_args()
    term = json.load(open(a.terminal))
    panel = json.load(open(a.panel))
    labels = term['class_labels']
    combos = [class_combos(l) for l in labels]
    flops = {}
    for f in panel['panel']:
        path = os.path.join(a.flop_dir, f['board'] + '.json')
        d = json.load(open(path))
        key = d['provenance_key']
        if key['ranges_hash_fnv1a64'] != term['ranges_hash_fnv1a64']:
            raise SystemExit(f"{f['board']}: ranges hash {key['ranges_hash_fnv1a64']} != terminal {term['ranges_hash_fnv1a64']}")
        if key['panel_hash_sha256'] != panel['panel_hash_sha256']:
            raise SystemExit(f"{f['board']}: panel hash mismatch")
        flops[f['board']] = d
    keys = {json.dumps(d['provenance_key'], sort_keys=True) for d in flops.values()}
    if len(keys) != 1:
        raise SystemExit('flop artifacts disagree on provenance key')
    strata = {}
    for f in panel['panel']:
        strata.setdefault(f['stratum'], []).append(f['board'])
    p_str = {s: panel['strata'][s]['probability'] for s in strata}
    # compatibility weights c_hf
    compat = {}
    for b in flops:
        bc = parse_board(b)
        compat[b] = [sum(1 for c in cc if c[0] not in bc and c[1] not in bc) / len(cc) for cc in combos]
    positions = [p['position'] for p in term['players']]
    table = {(b, pl['position'], fld): pl[fld] for b, d in flops.items() for pl in d['players']
             for fld in ('gross_eps', 'gross_br', 'equity')}

    rho = 19600 / 22100

    def estimate(field, pos, strata_draw, estimator='ht_rho'):
        vals = []
        for h in range(169):
            tot = 0.0
            for s, boards in strata_draw.items():
                num = den = 0.0
                for b in boards:
                    v = table[(b, pos, field)][h]
                    if v is None:
                        continue
                    num += compat[b][h] * v
                    den += compat[b][h]
                if estimator == 'ht_rho':
                    tot += p_str[s] * num / len(boards)
                elif den > 0:
                    tot += p_str[s] * num / den
            vals.append(tot / sum(p_str.values()) / (rho if estimator == 'ht_rho' else 1.0))
        return vals

    rng = random.Random(20260928 + a.outer)
    seats = []
    for pl in term['players']:
        pos = pl['position']
        v = estimate('gross_eps', pos, strata)
        vbr = estimate('gross_br', pos, strata)
        veq = estimate('equity', pos, strata)
        vratio = estimate('gross_eps', pos, strata, 'ratio')
        boots = []
        for _ in range(a.boot):
            draw = {s: [rng.choice(bs) for _ in bs] for s, bs in strata.items()}
            boots.append(estimate('gross_eps', pos, draw))
        lo = [sorted(bb[h] for bb in boots)[int(0.025 * a.boot)] for h in range(169)]
        hi = [sorted(bb[h] for bb in boots)[int(0.975 * a.boot) - 1] for h in range(169)]
        seats.append({'seat': pl['seat'], 'position': pos, 'gross': v, 'gross_ci95_lo': lo, 'gross_ci95_hi': hi,
                      'gross_br': vbr, 'equity_panel': veq, 'gross_ratio': vratio,
                      'realization_vs_equity': [v[h] / (term['pot_bb'] * veq[h]) if veq[h] > 1e-9 else None for h in range(169)],
                      'max_br_minus_eps_bb': max(vbr[h] - v[h] for h in range(169)),
                      'mean_ci95_halfwidth_bb': sum((hi[h] - lo[h]) / 2 for h in range(169)) / 169})
    # invariant at the actual terminal ranges
    total = total_ratio = 0.0
    for pl, st in zip(term['players'], seats):
        r = pl['class_reach_normalized']
        total += sum(r[h] * st['gross'][h] for h in range(169))
        total_ratio += sum(r[h] * st['gross_ratio'][h] for h in range(169))
    key = json.loads(next(iter(keys)))
    out = {
        'schema': 't2_hu_continuation_table_v1', 'value_convention': 'gross_share', 'zero_reach_definition': key['zero_reach_definition'],
        'node': term['terminal_node'], 'live': term['terminal_live_mask'], 'pot_bb': term['pot_bb'],
        'outer_iteration': a.outer, 'seats': seats,
        'estimator': 'ht_rho',
        'invariant': {'sum_range_weighted_gross': total, 'pot': term['pot_bb'], 'unallocated_bb': term['pot_bb'] - total,
                      'ratio_estimator_unallocated_bb': term['pot_bb'] - total_ratio},
        'provenance': {'terminal_file': a.terminal, 'ranges_hash_fnv1a64': term['ranges_hash_fnv1a64'],
                       'panel_hash_sha256': panel['panel_hash_sha256'], 'flop_key': key,
                       'solver_commits': sorted({d['solver_commit'] for d in flops.values()}),
                       'flops': len(flops), 'exploitability_pct_pot_max': max(d['exploitability_pct_pot'] for d in flops.values()),
                       'exploitability_pct_pot_mean': sum(d['exploitability_pct_pot'] for d in flops.values()) / len(flops),
                       'per_flop_invariant_error_max': max(abs(d['invariant']['error']) for d in flops.values()),
                       'iterations_mean': sum(d['iterations'] for d in flops.values()) / len(flops),
                       'preflop_terminal_gap_total': term['gap_total'], 'bootstrap': a.boot},
        'scope': 'one HU terminal of the 4-handed CO/BTN/SB/BB 30bb full tree; other terminals keep the existing payoff',
    }
    if abs(out['invariant']['unallocated_bb']) > a.max_unallocated:
        json.dump(out, open(a.out + '.rejected', 'w'))
        raise SystemExit('unallocated %.4f bb exceeds %.3f: table rejected (written to %s.rejected)'
                         % (out['invariant']['unallocated_bb'], a.max_unallocated, a.out))
    json.dump(out, open(a.out, 'w'))
    print('table', a.out, 'unallocated %.4f bb' % out['invariant']['unallocated_bb'],
          'expl max %.3f%%' % out['provenance']['exploitability_pct_pot_max'],
          ' '.join('%s ci±%.3f br-eps max %.3f' % (s['position'], s['mean_ci95_halfwidth_bb'], s['max_br_minus_eps_bb']) for s in seats))


if __name__ == '__main__':
    main()
