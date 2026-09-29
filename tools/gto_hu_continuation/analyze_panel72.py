#!/usr/bin/env python3
"""Stage A of panel v2: 24-flop vs 72-flop sampling error at identical (P6d) ranges.

    python3 tools/gto_hu_continuation/analyze_panel72.py --out-json data/gto_hu_continuation/panel72/stageA/analysis.json \
        --out-png docs/GTO_HU_V2_PANEL72_CI.png

Everything is computed exactly as pre-registered in docs/GTO_HU_CONTINUATION_V2.md (L0):
- CI half-width statistics come from the aggregate.py tables (same estimator, same bootstrap);
- per-class ESS = design-weighted flop-to-flop variance / unbiased stratified variance of the
  estimate; Kish design ESS of the flop weights;
- rescaled CI = half-width x sqrt(n/(n-1)) (diagnostic only);
- empirical 24-flop spread = SD of the estimate over random nested 2-of-6 sub-panels of the 72
  (x sqrt(1.25) to undo the finite-population factor of drawing 2 of 6), x 1.96;
- watch classes: action EVs at fixed P6d opponents (read-only dump of the P6d re-run);
- action abstraction / CI with J2's per-class M1-M2 values recomputed from the J2 artifacts.
"""
import argparse
import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import class_combos, parse_board  # noqa: E402

D = 'data/gto_hu_continuation/'
J2_FLIPPERS = ['73o', 'A3o', '72s', 'J2s', 'Q3s', 'A3s']
WATCH = ['JTs', 'JTo', 'KQo', 'T7o', 'A2o', '85s', '43s', 'T7s']
RHO = 19600 / 22100
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'


def seat(t, pos):
    return next(s for s in t['seats'] if s['position'] == pos)


def pl(d, pos):
    return next(p for p in d['players'] if p['position'] == pos)


def hw(s):
    return [(h - l) / 2 for l, h in zip(s['gross_ci95_lo'], s['gross_ci95_hi'])]


def stats(x):
    xs = sorted(x)
    return {'mean': sum(xs) / len(xs), 'median': statistics.median(xs), 'p90': xs[int(math.ceil(0.9 * len(xs))) - 1],
            'max': xs[-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--terminal', default=D + 'panel72/stageA/terminal_p6d.json')
    ap.add_argument('--t24', default=D + 'outer_v1_damped_a05/k6/table_measured.json')
    ap.add_argument('--t72', default=D + 'panel72/stageA/table72.json')
    ap.add_argument('--v5used', default=D + 'outer_v1_damped_a05/k5/table.json')
    ap.add_argument('--panel', default=D + 'panel_v2_72.json')
    ap.add_argument('--dirs', default=D + 'panel72/stageA/flops,' + D + 'outer_v1_damped_a05/k6/flops')
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-png', required=True)
    a = ap.parse_args()
    term = json.load(open(a.terminal))
    L = term['class_labels']
    t24, t72, v5 = json.load(open(a.t24)), json.load(open(a.t72)), json.load(open(a.v5used))
    panel = json.load(open(a.panel))
    assert t24['provenance']['ranges_hash_fnv1a64'] == t72['provenance']['ranges_hash_fnv1a64'] == term['ranges_hash_fnv1a64']
    combos = [class_combos(l) for l in L]
    strata = {}
    for f in panel['panel']:
        strata.setdefault(f['stratum'], []).append(f)
    P = {s: panel['strata'][s]['probability'] for s in strata}

    def load(b):
        for d in a.dirs.split(','):
            p = os.path.join(d, b + '.json')
            if os.path.exists(p):
                return json.load(open(p))
        raise SystemExit(b)
    art = {f['board']: load(f['board']) for f in panel['panel']}
    # per-flop contribution y_hf = c_hf v_hf / rho (0 if the class is absent on the board)
    y = {}
    for b, d in art.items():
        bc = parse_board(b)
        c = [sum(1 for x in cc if x[0] not in bc and x[1] not in bc) / len(cc) for cc in combos]
        for pos in ('BTN', 'BB'):
            v = pl(d, pos)['gross_eps']
            y[(b, pos)] = [c[h] * v[h] / RHO if v[h] is not None else 0.0 for h in range(169)]

    def est(pos, draw):
        return [sum(P[s] * sum(y[(b, pos)][h] for b in bs) / len(bs) for s, bs in draw.items()) for h in range(169)]

    full = {s: [f['board'] for f in fs] for s, fs in strata.items()}
    old = {s: [f['board'] for f in fs if f['origin'] == 'panel_v1'] for s, fs in strata.items()}
    res = {'provenance': {'terminal': a.terminal, 'ranges_hash': term['ranges_hash_fnv1a64'], 't24': a.t24, 't72': a.t72,
                          'panel_hash': panel['panel_hash_sha256'], 't72_flop_key': t72['provenance']['flop_key'],
                          't72_solver_commits': t72['provenance']['solver_commits']}, 'seats': {}}
    rng = random.Random(20260930)
    for pos in ('BTN', 'BB'):
        s24, s72 = seat(t24, pos), seat(t72, pos)
        # the analytic estimate on each design reproduces the tables' point values
        for draw, s_ in ((old, s24), (full, s72)):
            e = est(pos, draw)
            assert max(abs(x - z) for x, z in zip(e, s_['gross'])) < 1e-9
        h24, h72 = hw(s24), hw(s72)
        keep = pl(term, pos)['class_keep_fraction']
        inr = [h for h in range(169) if keep[h] > 1e-6]
        ess = {}
        for name, draw in (('24', old), ('72', full)):
            ess_h = []
            for h in range(169):
                mu = sum(P[s] * sum(y[(b, pos)][h] for b in bs) / len(bs) for s, bs in draw.items())
                pop = var = 0.0
                for s, bs in draw.items():
                    vals = [y[(b, pos)][h] for b in bs]
                    m = sum(vals) / len(vals)
                    s2 = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
                    pop += P[s] * (s2 + (m - mu) ** 2)
                    var += P[s] ** 2 * s2 / len(vals)
                ess_h.append(pop / var if var > 0 else None)
            w = [P[s] / len(bs) for s, bs in draw.items() for _ in bs]
            e_ = [x for x in ess_h if x is not None]
            ess[name] = {'kish_design': sum(w) ** 2 / sum(x * x for x in w), 'per_class_mean': sum(e_) / len(e_),
                         'per_class_median': statistics.median(e_), 'flops': len(w)}
        # empirical spread of nested 24-flop sub-panels drawn from the 72
        subs = []
        for _ in range(2000):
            subs.append(est(pos, {s: rng.sample(bs, 2) for s, bs in full.items()}))
        emp = [1.96 * statistics.pstdev([x[h] for x in subs]) * math.sqrt(1.25) for h in range(169)]
        # old-24 vs new-48 consistency: stratified difference / SE from the 6-flop within-stratum variance
        def old_new(vals_of):
            eo = en = var = 0.0
            for s, fs in strata.items():
                o = [vals_of(f['board']) for f in fs if f['origin'] == 'panel_v1']
                nw = [vals_of(f['board']) for f in fs if f['origin'] != 'panel_v1']
                al = o + nw
                m = sum(al) / len(al)
                s2 = sum((v - m) ** 2 for v in al) / (len(al) - 1)
                eo += P[s] * sum(o) / len(o)
                en += P[s] * sum(nw) / len(nw)
                var += P[s] ** 2 * s2 * (1 / len(o) + 1 / len(nw))
            return eo - en, math.sqrt(var)
        zs = []
        for h in range(169):
            dd, se = old_new(lambda b: y[(b, pos)][h])
            zs.append(dd / se if se > 0 else 0.0)
        r_ = pl(term, pos)['class_reach_normalized']
        dr, ser = old_new(lambda b: sum(r_[h] * y[(b, pos)][h] for h in range(169)))
        consistency = {'per_class_share_abs_z_gt_1_96': sum(1 for z in zs if abs(z) > 1.96) / 169,
                       'per_class_z_sd': math.sqrt(sum(z * z for z in zs) / 169), 'per_class_z_mean': sum(zs) / 169,
                       'range_ev_old24_minus_new48': dr, 'range_ev_se': ser, 'range_ev_z': dr / ser,
                       'note': 'expected under pure flop sampling: share ~0.05, z sd ~1'}
        dv = [z - x for x, z in zip(s24['gross'], s72['gross'])]
        res['seats'][pos] = {
            'ci_halfwidth_24': stats(h24), 'ci_halfwidth_72': stats(h72),
            'ci_halfwidth_24_in_range': stats([h24[h] for h in inr]), 'ci_halfwidth_72_in_range': stats([h72[h] for h in inr]),
            'in_range_classes': len(inr),
            'ratio_72_over_24': {'of_means': stats(h72)['mean'] / stats(h24)['mean'],
                                 'median_per_class': statistics.median(h72[h] / h24[h] for h in range(169) if h24[h] > 0),
                                 'pre_registered_prediction': 0.745, 'naive_1_over_sqrt3': 1 / math.sqrt(3)},
            'rescaled_ci_mean': {'24': stats(h24)['mean'] * math.sqrt(2), '72': stats(h72)['mean'] * math.sqrt(6 / 5)},
            'empirical_24flop_halfwidth_from_72': stats(emp),
            'ess': ess, 'old24_vs_new48': consistency,
            'value_change_24_to_72': {'mean_abs': sum(abs(x) for x in dv) / 169, 'max_abs': max(abs(x) for x in dv),
                                      'share_outside_24_ci': sum(1 for h in range(169) if abs(dv[h]) > h24[h]) / 169,
                                      'reach_weighted_mean_abs': sum(pl(term, pos)['class_reach_normalized'][h] * abs(dv[h]) for h in range(169)),
                                      'range_ev_shift': sum(pl(term, pos)['class_reach_normalized'][h] * dv[h] for h in range(169))},
            'estimator_ht_vs_ratio_mean_abs': {'24': sum(abs(x - z) for x, z in zip(s24['gross'], s24['gross_ratio'])) / 169,
                                               '72': sum(abs(x - z) for x, z in zip(s72['gross'], s72['gross_ratio'])) / 169},
            'br_minus_eps': {'24_mean': sum(b - e for b, e in zip(s24['gross_br'], s24['gross'])) / 169, '24_max': s24['max_br_minus_eps_bb'],
                             '72_mean': sum(b - e for b, e in zip(s72['gross_br'], s72['gross'])) / 169, '72_max': s72['max_br_minus_eps_bb']},
            '_h24': h24, '_h72': h72, '_emp': emp,
        }
    res['unallocated_bb'] = {'24': t24['invariant']['unallocated_bb'], '72': t72['invariant']['unallocated_bb']}
    res['per_flop'] = {b: {'stratum': next(f['stratum'] for f in panel['panel'] if f['board'] == b),
                           'origin': next(f['origin'] for f in panel['panel'] if f['board'] == b),
                           'iterations': d['iterations'], 'exploitability_pct_pot': d['exploitability_pct_pot'],
                           'converged': d['exploitability_pct_pot'] <= d['provenance_key']['target_exploitability_pct_pot'],
                           'solve_s': d['cost']['solve_ms'] / 1e3, 'invariant_error_bb': d['invariant']['error'],
                           'threads': d['cost'].get('threads'), 'peak_rss_mb': (d['cost'].get('peak_rss_kb') or 0) / 1024 or None}
                       for b, d in art.items()}

    # ---- J2 action abstraction per class (recomputed from the J2 artifacts, same function as compare_j2) ----
    p4 = json.load(open(D + 'panel_j2_4flop_v1.json'))
    jb = [f['board'] for f in p4['panel']]
    jw = {f['board']: f['weight'] for f in p4['panel']}
    def jload(dirs, b):
        for d in dirs:
            p = os.path.join(D, d, b + '.json')
            if os.path.exists(p):
                return json.load(open(p))
        raise SystemExit(b)
    M1 = {b: jload(['j2/m1_compressed', 'j2/m1_compressed_it400'], b) for b in jb}
    M2 = {b: jload(['j2/m2_compressed'], b) for b in jb}
    jc = {b: [sum(1 for c in cc if c[0] not in parse_board(b) and c[1] not in parse_board(b)) / len(cc) for cc in combos] for b in jb}
    def jagg(Dd, pos, field):
        return [sum(jw[b] * jc[b][h] * pl(Dd[b], pos)[field][h] for b in jb if pl(Dd[b], pos)[field][h] is not None)
                / p4['fixed_normaliser'][pos] for h in range(169)]
    j2ref = json.load(open(D + 'j2/compare_j2.json'))['players']
    res['abstraction_over_ci'] = {}
    for pos in ('BTN', 'BB'):
        de = [abs(x - z) for x, z in zip(jagg(M1, pos, 'gross_eps'), jagg(M2, pos, 'gross_eps'))]
        db = [abs(x - z) for x, z in zip(jagg(M1, pos, 'gross_br'), jagg(M2, pos, 'gross_br'))]
        assert abs(sum(de) / 169 - j2ref[pos]['menu_mean_abs_bb']) < 1e-9 and abs(sum(db) / 169 - j2ref[pos]['menu_br_mean_abs_bb']) < 1e-9
        S = res['seats'][pos]
        out = {}
        for ci in ('24', '72'):
            h_ = S['_h' + ci]
            m = stats(h_)['mean']
            out[ci] = {'eps_ratio_of_means': (sum(de) / 169) / m, 'br_ratio_of_means': (sum(db) / 169) / m,
                       'eps_mean_per_class_ratio': sum(de[h] / h_[h] for h in range(169) if h_[h] > 0) / sum(1 for x in h_ if x > 0),
                       'br_mean_per_class_ratio': sum(db[h] / h_[h] for h in range(169) if h_[h] > 0) / sum(1 for x in h_ if x > 0),
                       'share_classes_menu_gt_ci': sum(1 for h in range(169) if de[h] > h_[h]) / 169}
        out['menu_mean_abs'] = {'eps': sum(de) / 169, 'br': sum(db) / 169}
        r = out['72']['br_ratio_of_means']
        out['classification_72'] = ('< 0.25: sampling still clearly first' if r < 0.25 else
                                    '0.25-0.5: abstraction approaching' if r <= 0.5 else '> 0.5: abstraction next')
        res['abstraction_over_ci'][pos] = out

    # ---- watch classes at fixed P6d opponents ----
    av = term['action_values']
    tp, rb = av['terminal_parent'], av['rfi_BTN']
    v5btn = seat(v5, 'BTN')['gross']
    watch = {'BB': [], 'BTN': []}
    def best(evs, names):
        o = sorted(range(len(evs)), key=lambda i: -evs[i])
        return names[o[0]], evs[o[0]] - evs[o[1]], names[o[1]]
    for c in J2_FLIPPERS + WATCH:
        h = L.index(c)
        row = {'class': c, 'list': 'J2 flipper' if c in J2_FLIPPERS else 'watch'}
        for n, t in (('24', t24), ('72', t72)):
            s_ = seat(t, 'BB')
            V = s_['gross'][h]
            evs = [tp['ev_bb'][0][h], V - 2.25, tp['ev_bb'][2][h], tp['ev_bb'][3][h]]
            act, margin, second = best(evs, ['fold', 'call', '3bet', 'jam'])
            row[n] = {'V': V, 'ci': [s_['gross_ci95_lo'][h], s_['gross_ci95_hi'][h]], 'ci_halfwidth': (s_['gross_ci95_hi'][h] - s_['gross_ci95_lo'][h]) / 2,
                      'call_minus_fold': V - 1.0, 'call_minus_jam': V - 2.25 - tp['ev_bb'][3][h],
                      'best': act, 'second': second, 'margin': margin,
                      'margin_over_ci': margin / max(1e-12, (s_['gross_ci95_hi'][h] - s_['gross_ci95_lo'][h]) / 2) if act == 'call' or second == 'call' else None}
        row['judgment_changes'] = row['24']['best'] != row['72']['best']
        row['p6d_strategy'] = {a_: tp_ for a_, tp_ in zip(['fold', 'call', '3bet', 'jam'], (s[h] for s in term['frequencies']['terminal_parent']['class_strategy']))}
        watch['BB'].append(row)
    q = rb['terminal_sensitivity_q']
    for c in WATCH:
        h = L.index(c)
        row = {'class': c}
        for n, t in (('24', t24), ('72', t72)):
            s_ = seat(t, 'BTN')
            V = s_['gross'][h]
            evs = [rb['ev_bb'][0][h], rb['ev_bb'][1][h] + q * (V - v5btn[h]), rb['ev_bb'][2][h]]
            act, margin, second = best(evs, ['fold', 'raise', 'jam'])
            hw_ = (s_['gross_ci95_hi'][h] - s_['gross_ci95_lo'][h]) / 2
            row[n] = {'V': V, 'ci': [s_['gross_ci95_lo'][h], s_['gross_ci95_hi'][h]], 'ci_halfwidth': hw_,
                      'raise_minus_best_other': evs[1] - max(evs[0], evs[2]), 'best': act, 'margin': margin,
                      'margin_over_q_ci': (evs[1] - max(evs[0], evs[2])) / (q * hw_) if hw_ > 0 else None}
        row['judgment_changes'] = row['24']['best'] != row['72']['best']
        row['p6d_strategy'] = {a_: s[h] for a_, s in zip(['fold', 'raise', 'jam'], term['frequencies']['rfi_BTN']['class_strategy'])}
        watch['BTN'].append(row)
    res['watch'] = watch
    res['btn_terminal_sensitivity_q'] = q
    # BB fold/call boundary overall at 24 vs 72 (classes whose call-fold side differs)
    b24, b72 = seat(t24, 'BB')['gross'], seat(t72, 'BB')['gross']
    res['bb_call_fold_side_changes_24_to_72'] = [{'class': L[h], 'V24': b24[h], 'V72': b72[h], 'direction': 'up' if b72[h] >= 1.0 else 'down',
                                                   'p6d_fold': term['frequencies']['terminal_parent']['class_strategy'][0][h]}
                                                  for h in range(169) if (b24[h] < 1.0) != (b72[h] < 1.0)]
    res['bb_classes_below_fold_line'] = {'24': [L[h] for h in range(169) if b24[h] < 1.0], '72': [L[h] for h in range(169) if b72[h] < 1.0]}
    res['c3_whole_ci_below_line_classes'] = {c: {'V24': b24[L.index(c)], 'hi24': seat(t24, 'BB')['gross_ci95_hi'][L.index(c)],
                                                 'V72': b72[L.index(c)], 'lo72': seat(t72, 'BB')['gross_ci95_lo'][L.index(c)],
                                                 'hi72': seat(t72, 'BB')['gross_ci95_hi'][L.index(c)]} for c in ('72o', '82o', '92o', 'T2o')}

    out = json.loads(json.dumps(res))
    for pos in out['seats']:
        for k in ('_h24', '_h72', '_emp'):
            out['seats'][pos].pop(k)
    json.dump(out, open(a.out_json, 'w'), indent=1)
    figure(res, L, a.out_png)
    for pos, S in out['seats'].items():
        print(pos, 'CI24', {k: round(v, 3) for k, v in S['ci_halfwidth_24'].items()}, 'CI72', {k: round(v, 3) for k, v in S['ci_halfwidth_72'].items()},
              'ratio', {k: round(v, 3) for k, v in S['ratio_72_over_24'].items()}, 'emp24', round(S['empirical_24flop_halfwidth_from_72']['mean'], 3),
              'ESS', {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in S['ess'].items()})
        print('   dV', {k: round(v, 3) for k, v in S['value_change_24_to_72'].items()}, 'abstr/CI', json.dumps(out['abstraction_over_ci'][pos]))
    print('unallocated', out['unallocated_bb'], 'BB side changes', [(x['class'], x['direction']) for x in out['bb_call_fold_side_changes_24_to_72']])
    print('old24 vs new48', {p_: out['seats'][p_]['old24_vs_new48'] for p_ in out['seats']})
    print('C3 whole-CI-below classes', out['c3_whole_ci_below_line_classes'])
    for pos in ('BB', 'BTN'):
        for r in watch[pos]:
            print(pos, r['class'], ' '.join(f"{n}:V={r[n]['V']:.3f}±{r[n]['ci_halfwidth']:.3f} {r[n]['best']} m={r[n]['margin']:.3f}" for n in ('24', '72')),
                  'CHANGE' if r['judgment_changes'] else '')


def figure(res, L, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(15, 11), dpi=120)
    fig.patch.set_facecolor(SURF)
    for i, pos in enumerate(('BB', 'BTN')):
        S = res['seats'][pos]
        g = ax[0][i]
        h24, h72 = S['_h24'], S['_h72']
        g.scatter(h24, h72, s=12, color=C1, label='class (95% CI half-width)', zorder=3)
        m = max(max(h24), max(h72)) * 1.05
        g.plot([0, m], [0, m], color=MUTED, lw=1, ls=':', label='no change')
        g.plot([0, m], [0, 0.745 * m], color=C2, lw=2, label='pre-registered 0.745 (bootstrap n-bias)')
        g.plot([0, m], [0, m / math.sqrt(3)], color=C3, lw=2, ls='--', label='naive 1/√3 = 0.577')
        r = S['ratio_72_over_24']
        g.set_title(f"({i + 1}) {pos}: 72-flop vs 24-flop CI per class  (ratio of means {r['of_means']:.3f})", loc='left', fontsize=11, color=INK)
        g.set_xlabel('24-flop half-width (bb)', fontsize=9, color=MUTED)
        g.set_ylabel('72-flop half-width (bb)', fontsize=9, color=MUTED)
        e = S['old24_vs_new48']
        g.text(0.98, 0.03, f"calibration: empirical 24-flop half-width from nested 2-of-6 sub-panels\n"
                           f"= {stats(S['_emp'])['mean']:.3f} (bootstrap 24: {stats(h24)['mean']:.3f}); 72-flop bootstrap {stats(h72)['mean']:.3f}\n"
                           f"old24 vs new48: |z|>1.96 in {e['per_class_share_abs_z_gt_1_96']:.1%} of classes, z sd {e['per_class_z_sd']:.2f}",
               transform=g.transAxes, ha='right', va='bottom', fontsize=8, color=INK)
        g.legend(fontsize=8, frameon=False)
    # (3) watch classes BB: V - 1.0 with CI, 24 vs 72
    g = ax[1][0]
    rows = res['watch']['BB']
    xs = list(range(len(rows)))
    for j, (n, col) in enumerate((('24', C2), ('72', C1))):
        vals = [r[n]['V'] - 1.0 for r in rows]
        err = [r[n]['ci_halfwidth'] for r in rows]
        g.errorbar([x + (j - 0.5) * 0.3 for x in xs], vals, yerr=err, fmt='o', ms=5, color=col, capsize=3, lw=1.5, label=f'{n} flops: V − 1.0 ± 95% CI')
    g.axhline(0, color=INK, lw=1)
    g.set_xticks(xs)
    g.set_xticklabels([r['class'] + ('*' if r['list'] == 'J2 flipper' else '') for r in rows], fontsize=8, rotation=45)
    g.set_ylabel('BB call − fold EV (bb)  (0 = boundary)', fontsize=9, color=MUTED)
    g.set_title('(3) BB watch classes: distance to the call/fold line (* = J2 menu flipper)', loc='left', fontsize=11, color=INK)
    g.legend(fontsize=8, frameon=False)
    # (4) abstraction / CI
    g = ax[1][1]
    A = res['abstraction_over_ci']
    labels, v24, v72 = [], [], []
    for pos in ('BB', 'BTN'):
        for k, lab in (('br_ratio_of_means', 'BR, ratio of means'), ('eps_ratio_of_means', 'ε, ratio of means'),
                       ('br_mean_per_class_ratio', 'BR, per-class mean')):
            labels.append(f'{pos}\n{lab}')
            v24.append(A[pos]['24'][k])
            v72.append(A[pos]['72'][k])
    xs = list(range(len(labels)))
    g.bar([x - 0.18 for x in xs], v24, 0.34, color=C2, label='÷ 24-flop CI')
    g.bar([x + 0.18 for x in xs], v72, 0.34, color=C1, label='÷ 72-flop CI')
    for yv, lab in ((0.25, '0.25'), (0.5, '0.5')):
        g.axhline(yv, color=MUTED, lw=1, ls='--')
        g.text(len(xs) - 0.5, yv, lab, fontsize=8, color=MUTED, va='bottom', ha='right')
    for x, v in zip(xs, v72):
        g.text(x + 0.18, v, f'{v:.2f}', fontsize=8, color=INK, ha='center', va='bottom')
    g.set_xticks(xs)
    g.set_xticklabels(labels, fontsize=7)
    g.set_ylabel('J2 menu effect ÷ sampling CI half-width', fontsize=9, color=MUTED)
    g.set_title('(4) action abstraction ÷ sampling CI (thresholds 0.25 / 0.5)', loc='left', fontsize=11, color=INK)
    g.legend(fontsize=8, frameon=False)
    for row in ax:
        for g in row:
            g.set_facecolor(SURF)
            g.grid(color=GRID, lw=0.8)
            for sp in ('top', 'right'):
                g.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
