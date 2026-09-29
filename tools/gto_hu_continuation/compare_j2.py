#!/usr/bin/env python3
"""J2: postflop action-abstraction sensitivity (M1 two-size vs M2 single-size) at fixed ranges.

    python3 tools/gto_hu_continuation/compare_j2.py \
        --m1 data/gto_hu_continuation/j2/m1_compressed --m2c data/gto_hu_continuation/j2/m2_compressed \
        --m2f data/gto_hu_continuation/outer_v1_damped_a05/k6/flops \
        --terminal data/gto_hu_continuation/outer_v1_damped_a05/k6/terminal.json \
        --panel24 data/gto_hu_continuation/outer_v1_damped_a05/k6/table_measured.json \
        --panel data/gto_hu_continuation/panel_sub6_v1.json \
        --out-json data/gto_hu_continuation/j2/compare_j2.json --out-png docs/GTO_HU_J2_MENU_V1.png

All solves are at the same (P6d) ranges. The menu effect is M1 vs M2 in the SAME storage
(compressed); M2 f32 vs M2 compressed measures the storage band on the same 6 flops.
The decision metric compares |V_M1 - V_M2| (per class, panel-aggregated with the sub-panel
weights) with the 24-flop panel's per-class 95% CI half-width (flop-sampling error).
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import class_combos, parse_board  # noqa: E402

INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'
BOUNDARY = ['JTs', 'JTo', 'KQo', 'T7o', 'A2o', '85s', '43s', 'T7s']
WEAK = ['72o', '82o', '92o', 'T2o', '32o', '62o', 'J2o', 'Q2o', 'T5o', 'J5o', '85o']
PREMIUM = ['AA', 'KK', 'QQ', 'AKs', 'AKo']


def pl(d, pos):
    return next(p for p in d['players'] if p['position'] == pos)


def main():
    ap = argparse.ArgumentParser()
    for k in ('m1', 'm2c', 'm2f', 'terminal', 'panel24', 'panel', 'out_json', 'out_png'):
        ap.add_argument('--' + k.replace('_', '-'), required=True)
    a = ap.parse_args()
    term = json.load(open(a.terminal))
    panel = json.load(open(a.panel))
    p24 = json.load(open(a.panel24))
    L = term['class_labels']
    pot = term['pot_bb']
    combos = [class_combos(l) for l in L]
    boards = [f['board'] for f in panel['panel']]
    w = {f['board']: f['weight'] for f in panel['panel']}
    def load(dirs, b):
        for d in dirs.split(','):
            f = os.path.join(d, b + '.json')
            if os.path.exists(f):
                return json.load(open(f))
        raise SystemExit(f'{b}: not found in {dirs}')
    M1 = {b: load(a.m1, b) for b in boards}
    M2c = {b: load(a.m2c, b) for b in boards}
    M2f = {b: load(a.m2f, b) for b in boards}
    comp = {b: [sum(1 for c in cc if c[0] not in parse_board(b) and c[1] not in parse_board(b)) / len(cc) for cc in combos] for b in boards}

    def agg(D, pos, field='gross_eps'):
        norm = panel['fixed_normaliser'][pos]
        out = []
        for h in range(169):
            s = 0.0
            for b in boards:
                v = pl(D[b], pos)[field][h]
                if v is not None:
                    s += w[b] * comp[b][h] * v
            out.append(s / norm)
        return out

    res = {'boards': boards, 'ranges_hash': term['ranges_hash_fnv1a64'], 'per_flop': {}, 'players': {}}
    for b in boards:
        row = {'stratum': next(f['stratum'] for f in panel['panel'] if f['board'] == b)}
        for name, D in (('M1_compressed', M1), ('M2_compressed', M2c), ('M2_f32', M2f)):
            row[name] = {'iterations': D[b]['iterations'], 'exploitability_pct_pot': D[b]['exploitability_pct_pot'],
                         'solve_s': D[b]['cost']['solve_ms'] / 1000, 'tree_nodes': D[b]['cost']['tree_nodes'],
                         'arena_gb': D[b]['cost']['arena_bytes'] / 1e9}
        for pos in ('BB', 'BTN'):
            d = [abs(x - y) for x, y in zip(pl(M1[b], pos)['gross_eps'], pl(M2c[b], pos)['gross_eps']) if x is not None and y is not None]
            s = [abs(x - y) for x, y in zip(pl(M2f[b], pos)['gross_eps'], pl(M2c[b], pos)['gross_eps']) if x is not None and y is not None]
            row[f'{pos}_menu_mean_abs'] = sum(d) / len(d)
            row[f'{pos}_menu_max_abs'] = max(d)
            row[f'{pos}_storage_mean_abs'] = sum(s) / len(s)
            row[f'{pos}_storage_max_abs'] = max(s)
        res['per_flop'][b] = row
    for pos in ('BB', 'BTN'):
        v1, v2, vf = agg(M1, pos), agg(M2c, pos), agg(M2f, pos)
        b1, b2 = agg(M1, pos, 'gross_br'), agg(M2c, pos, 'gross_br')
        e1, e2 = agg(M1, pos, 'equity'), agg(M2c, pos, 'equity')
        r = pl(term, pos)['class_reach_normalized']
        s24 = next(s for s in p24['seats'] if s['position'] == pos)
        hw = [(hi - lo) / 2 for lo, hi in zip(s24['gross_ci95_lo'], s24['gross_ci95_hi'])]
        dmenu = [x - y for x, y in zip(v1, v2)]
        dmenu_br = [x - y for x, y in zip(b1, b2)]
        keep = pl(term, pos)['class_keep_fraction']
        inr = [h for h in range(169) if keep[h] > 1e-6]
        dstor = [x - y for x, y in zip(vf, v2)]
        real = lambda v, e, n: v[L.index(n)] / (pot * e[L.index(n)]) if e[L.index(n)] > 1e-9 else None
        res['players'][pos] = {
            'menu_mean_abs_bb': sum(abs(x) for x in dmenu) / 169, 'menu_max_abs_bb': max(abs(x) for x in dmenu),
            'menu_reach_weighted_mean_abs_bb': sum(r[h] * abs(dmenu[h]) for h in range(169)),
            'menu_range_ev_delta_bb': sum(r[h] * dmenu[h] for h in range(169)),
            'menu_br_mean_abs_bb': sum(abs(x) for x in dmenu_br) / 169, 'menu_br_max_abs_bb': max(abs(x) for x in dmenu_br),
            'menu_br_over_ci_ratio_mean': sum(abs(dmenu_br[h]) / hw[h] for h in range(169) if hw[h] > 0) / sum(1 for x in hw if x > 0),
            'menu_inrange_eps_mean_abs_bb': sum(abs(dmenu[h]) for h in inr) / len(inr), 'menu_inrange_eps_max_abs_bb': max(abs(dmenu[h]) for h in inr),
            'in_range_classes': len(inr),
            'storage_mean_abs_bb': sum(abs(x) for x in dstor) / 169, 'storage_max_abs_bb': max(abs(x) for x in dstor),
            'storage_inrange_mean_abs_bb': sum(abs(dstor[h]) for h in inr) / len(inr), 'storage_inrange_max_abs_bb': max(abs(dstor[h]) for h in inr),
            'panel24_ci_halfwidth_mean_bb': sum(hw) / 169,
            'menu_over_ci_ratio_mean': sum(abs(dmenu[h]) / hw[h] for h in range(169) if hw[h] > 0) / sum(1 for x in hw if x > 0),
            'share_classes_menu_gt_ci': sum(1 for h in range(169) if abs(dmenu[h]) > hw[h]) / 169,
            'br_minus_eps_max': {'M1': max(x - y for x, y in zip(b1, v1)), 'M2': max(x - y for x, y in zip(b2, v2))},
            'realization': {n: {'M1': real(v1, e1, n), 'M2': real(v2, e2, n)} for n in WEAK + PREMIUM},
            'boundary': {n: {'M1': v1[L.index(n)], 'M2': v2[L.index(n)], 'delta': dmenu[L.index(n)], 'ci_halfwidth_24': hw[L.index(n)]} for n in BOUNDARY},
            'largest': sorted(({'class': L[h], 'M1': round(v1[h], 3), 'M2': round(v2[h], 3), 'delta': round(dmenu[h], 3),
                                'ci_halfwidth_24': round(hw[h], 3)} for h in range(169)), key=lambda x: -abs(x['delta']))[:12],
            '_v1': v1, '_v2': v2, '_hw': hw,
        }
    # BB fold/call boundary: classes whose M2 gross is within 0.5 bb of the 1.0 bb threshold
    bb = res['players']['BB']
    near = [h for h in range(169) if abs(bb['_v2'][h] - 1.0) < 0.5]
    res['bb_fold_boundary'] = [{'class': L[h], 'M1': round(bb['_v1'][h], 3), 'M2': round(bb['_v2'][h], 3),
                                'side_changes': (bb['_v1'][h] < 1.0) != (bb['_v2'][h] < 1.0)} for h in near]
    res['bb_fold_boundary_side_changes'] = sum(1 for x in res['bb_fold_boundary'] if x['side_changes'])
    out = json.loads(json.dumps(res, default=float))
    for pos in out['players']:
        for k in ('_v1', '_v2', '_hw'):
            out['players'][pos].pop(k)
    json.dump(out, open(a.out_json, 'w'), indent=1)

    fig, ax = plt.subplots(1, 3, figsize=(18, 6), dpi=120)
    fig.patch.set_facecolor(SURF)
    for i, pos in enumerate(('BB', 'BTN')):
        g = ax[i]
        P = res['players'][pos]
        g.scatter(P['_v2'], [x - y for x, y in zip(P['_v1'], P['_v2'])], s=12, color=C1, label='M1 − M2 (same storage)')
        g.scatter(P['_v2'], P['_hw'], s=6, marker='_', color=C2, label='± 24-flop panel 95% CI half-width (same class)')
        g.scatter(P['_v2'], [-x for x in P['_hw']], s=6, marker='_', color=C2)
        g.axhline(0, color=MUTED, lw=1)
        for n in BOUNDARY:
            h = L.index(n)
            g.annotate(n, (P['_v2'][h], P['_v1'][h] - P['_v2'][h]), fontsize=7, color=INK)
        g.set_title(f'({i+1}) {pos}: menu effect per class vs sampling CI', loc='left', fontsize=11, color=INK)
        g.set_xlabel('M2 value (bb)', fontsize=9, color=MUTED)
        g.set_ylabel('M1 − M2 (bb)', fontsize=9, color=MUTED)
        g.legend(fontsize=8, frameon=False)
    g = ax[2]
    xs = range(len(boards))
    for j, (k, col, lab) in enumerate((('menu', C1, 'menu |M1−M2|'), ('storage', C3, 'storage |f32−compressed| (M2)'))):
        g.bar([x + j * 0.2 - 0.3 for x in xs], [res['per_flop'][b][f'BB_{k}_mean_abs'] for b in boards], 0.2, color=col, label=f'BB {lab}')
        g.bar([x + j * 0.2 + 0.1 for x in xs], [res['per_flop'][b][f'BTN_{k}_mean_abs'] for b in boards], 0.2, color=col, alpha=0.5, label=f'BTN {lab}')
    g.set_xticks(list(xs))
    g.set_xticklabels([f"{b}\n{res['per_flop'][b]['stratum']}" for b in boards], fontsize=8)
    g.set_ylabel('mean |Δ| per class (bb)', fontsize=9, color=MUTED)
    g.set_title('(3) per flop: menu vs storage effect', loc='left', fontsize=11, color=INK)
    g.legend(fontsize=7, frameon=False)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(a.out_png, facecolor=SURF, bbox_inches='tight')
    for pos, P in out['players'].items():
        print(pos, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in P.items() if k not in ('realization', 'boundary', 'largest')})
    print('BB boundary side changes:', out['bb_fold_boundary_side_changes'], 'of', len(out['bb_fold_boundary']))


if __name__ == '__main__':
    main()
