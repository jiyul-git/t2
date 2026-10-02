#!/usr/bin/env python3
"""A4c analysis (prereg data/gto_terminal_expansion/a4c/prereg.json). Called by `a4c_run.py analyze`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4c_run as C  # noqa: E402
from a4c_influence import NODES, node_data  # noqa: E402
from a4c_reconstruct import regret_l1  # noqa: E402
from analyze_a3 import MAIN  # noqa: E402

E, OUT = C.E, C.OUT
PRE = E + 'a4c_preanalysis/'
SEAT3 = ('BTN', 'SB', 'BB')
BETA_FOR = {'BTN first-in': 'BTN', 'SB vs BTN': 'SB', 'BB vs BTN': 'BB', 'SB first-in': 'SB', 'BB vs SB': 'BB'}
PROXY = {'BTN': 0.0005, 'SB': 0.0034, 'BB': 0.0022}


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]


def mean(xs):
    return sum(xs) / len(xs)


def hand_level(gdir_a, gdir_b):
    """per node: class strategies / action EVs of two point solves, argmax switches, mixed flags, cross regrets per class."""
    A, Bn = node_data(gdir_a), node_data(gdir_b)
    out = {}
    for nd in NODES:
        a, b = A[nd], Bn[nd]
        na = len(a['s'])
        w = b['r']
        tw = sum(w)
        classes = []
        sw = mixa = mixb = 0.0
        for h in range(169):
            fa = [a['s'][k][h] for k in range(na)]
            fb = [b['s'][k][h] for k in range(na)]
            eva = [a['ev'][k][h] for k in range(na)]
            evb = [b['ev'][k][h] for k in range(na)]
            ra = max(evb) - sum(fa[k] * evb[k] for k in range(na))   # 144 strategy under the ext game's action EVs
            rb = max(eva) - sum(fb[k] * eva[k] for k in range(na))   # ext strategy under the 144 game's action EVs
            arg_a, arg_b = max(range(na), key=lambda k: fa[k]), max(range(na), key=lambda k: fb[k])
            reach = w[h] > 1e-9
            switch = reach and arg_a != arg_b
            ma, mb = reach and max(fa) < 0.99, reach and max(fb) < 0.99
            sw += w[h] * switch
            mixa += w[h] * ma
            mixb += w[h] * mb
            classes.append({'h': h, 'reach_ext': w[h], 'freq_144': fa, 'freq_ext': fb, 'ev_144': eva, 'ev_ext': evb, 'regret_144_in_ext': ra,
                            'regret_ext_in_144': rb, 'argmax_switch': switch, 'mixed_144': ma, 'mixed_ext': mb,
                            'L1': sum(abs(x - y) for x, y in zip(fa, fb))})
        out[nd] = {'actions_n': na, 'reach_weighted': {'argmax_switch_share': sw / tw, 'mixed_share_144': mixa / tw, 'mixed_share_ext': mixb / tw,
                                                       'regret_144_in_ext': sum(c['reach_ext'] * c['regret_144_in_ext'] for c in classes) / tw,
                                                       'regret_ext_in_144': sum(c['reach_ext'] * c['regret_ext_in_144'] for c in classes) / tw,
                                                       'L1': sum(c['reach_ext'] * c['L1'] for c in classes) / tw},
                   'classes': classes}
    return out


def main():
    pre = json.load(open(OUT + 'prereg.json'))
    pred = pre['out_of_sample_test']['predicted']
    P = json.load(open(OUT + 'points.json'))
    R = json.load(open(OUT + 'boot.json'))
    tc = json.load(open(OUT + 'tables_check.json'))
    reps = [r for r in R['reps'].values() if r.get('done')]
    gdir = {'G144': E + 'a4b_panel144/points/V144', 'Gext': OUT + 'points/Gext'}
    res = {'integrity': tc, 'replicates_usable': len(reps), 'G144_resolve_identical': P['G144_resolve_identical']}
    # 1. refinement point shift
    res['D_point'] = {f'{nm}|{ac}': P['Gext']['aggregates'][nm][ac] - P['G144']['aggregates'][nm][ac] for nm, (_, acts) in MAIN.items() for ac in acts}
    res['aggregates'] = {'G144': P['G144']['aggregates'], 'Gext': P['Gext']['aggregates']}
    os.makedirs(OUT + 'analysis', exist_ok=True)
    base = R['base_regret']
    res['point_swaps'] = {'sigma144->Gext': C.swap_metrics(P['Gext'], gdir['Gext'], P['G144'], gdir['G144'], OUT + 'analysis/s144_to_Gext', base['Gext']),
                          'sigmaext->G144': C.swap_metrics(P['G144'], gdir['G144'], P['Gext'], gdir['Gext'], OUT + 'analysis/sext_to_G144', base['G144'])}
    # 2. measured panel-error estimates and out-of-sample comparison
    ls = json.load(open(PRE + 'loss_scaling.json'))['summary']['seats']
    beta = {s: ls[s]['loss_vs_variance_exponent_beta'] for s in SEAT3}
    rows = {}
    for key in [f'seat:{s}' for s in SEAT3] + [f'regret:{n}' for n in NODES]:
        t, name = key.split(':')
        get = (lambda r, sz: r[f'err{sz}']['seat_dEV'][name]) if t == 'seat' else (lambda r, sz: r[f'err{sz}']['regret_excess'][name])
        L144 = mean([get(r, '144') for r in reps])
        Lext = mean([get(r, 'ext') for r in reps])
        b = beta[name] if t == 'seat' else beta[BETA_FOR[name]]
        pr = pred[key]
        eq24_pred = pr['calibrated_abs_bb'] / pr['ratio_vs_equal24_raw'] ** b
        rows[key] = {'measured_L144': L144, 'measured_Lext': Lext, 'measured_ratio_ext_over_144': Lext / L144 if L144 else None,
                     'predicted_ratio_calibrated': pr['ratio_vs_144_calibrated'], 'predicted_ratio_raw': pr['ratio_vs_144_raw'],
                     'prediction_error_ratio': (Lext / L144 - pr['ratio_vs_144_calibrated']) if L144 else None,
                     'predicted_abs_ext': pr['calibrated_abs_bb'], 'predicted_equal24_abs': eq24_pred,
                     'measured_ext_over_predicted_equal24': Lext / eq24_pred if eq24_pred else None,
                     'diagnostic_only': key == 'regret:SB vs BTN',
                     'q05_q50_q95_ext': [q([get(r, 'ext') for r in reps], p) for p in (0.05, 0.5, 0.95)]}
    res['out_of_sample'] = rows
    # 3. FPC +-2% sensitivity on paired strata (analytic through influence shares)
    infl = json.load(open(PRE + 'influence/summary.json'))
    sens = {}
    for s in SEAT3:
        tot = sum(v.get(f'seat_dEV:{s}', 0) for v in infl.values())
        paired = sum(v.get(f'seat_dEV:{s}', 0) for k, v in infl.items() if k.split('|')[1].startswith('paired'))
        share = paired / tot if tot else 0
        sens[s] = {'paired_share_of_contribution': share, 'loss_change_pct_for_+-2pct_variance': 100 * beta[s] * 0.02 * share}
    res['fpc_paired_sensitivity'] = sens
    # 4. classification continuity (amendment 3) + numerical checks
    E0, Er = {}, {}
    allchk = []
    for d, pk, rk in (('144->ext', 'sigma144->Gext', 's144_to_Gext_r'), ('ext->144', 'sigmaext->G144', 'sext_to_G144_r')):
        for s in ('CO',) + SEAT3:
            pt = res['point_swaps'][pk]
            E0[(s, d)] = max(pt['seat_dEV'][s], 0) - pt['own_gap'][s]
            Er[(s, d)] = [max(r[rk]['seat_dEV'][s], 0) - r[rk]['own_gap'][s] for r in reps]
    for r in reps:
        for k in ('err144', 'errext', 's144_to_Gext_r', 'sext_to_G144_r'):
            allchk.append(r[k]['max_check'])
    allchk += [res['point_swaps'][k]['max_check'] for k in res['point_swaps']]
    def classify(eps):
        stab = all(E0[k] + eps <= 0 and q(Er[k], .95) + eps <= 0 for k in E0)
        sens_ = [f'{k[0]} {k[1]}' for k in E0 if E0[k] - eps > 0 and q(Er[k], .05) - eps > 0]
        return 'EV-stable' if stab else ('EV-sensitive' if sens_ else 'precision-limited'), sens_
    lab, sl = classify(0.0)
    lab_p, _ = classify(1e-9)
    lab_m, _ = classify(-1e-9)
    res['classification'] = {'label': lab, 'sensitive_seat_directions': sl, 'stable_under_pm1e-9': lab == lab_p == lab_m,
                             'E0': {f'{k[0]} {k[1]}': v for k, v in E0.items()},
                             'E_q05_q95': {f'{k[0]} {k[1]}': [q(v, .05), q(v, .95)] for k, v in Er.items()},
                             'expected_before_results': 'EV-sensitive likely'}
    res['numerical'] = {'max_floating_check': max(allchk), 'floating_rule_pass': max(allchk) <= 1e-9}
    # 5. hand level
    hl = hand_level(gdir['G144'], gdir['Gext'])
    json.dump(hl, open(OUT + 'hand_level.json', 'w'))
    res['hand_level_summary'] = {nd: v['reach_weighted'] for nd, v in hl.items()}
    # 6. panel error vs frozen-range proxy
    res['panel_vs_frozen_range_proxy'] = {s: {'measured_Lext': rows[f'seat:{s}']['measured_Lext'], 'measured_L144': rows[f'seat:{s}']['measured_L144'],
                                              'frozen_range_proxy': PROXY[s], 'ratio_ext_to_proxy': rows[f'seat:{s}']['measured_Lext'] / PROXY[s]} for s in SEAT3}
    C.atomic(res, OUT + 'analysis.json')
    for k, v in rows.items():
        print(f"{k:22s} L144={v['measured_L144']:.5f} Lext={v['measured_Lext']:.5f} ratio={v['measured_ratio_ext_over_144']:.3f} "
              f"pred={v['predicted_ratio_calibrated']:.3f} (raw {v['predicted_ratio_raw']:.3f}) err={v['prediction_error_ratio']:+.3f} "
              f"vs_pred_eq24={v['measured_ext_over_predicted_equal24']:.3f}{' [diagnostic]' if v['diagnostic_only'] else ''}")
    print(json.dumps({k: res[k] for k in ('classification', 'numerical', 'fpc_paired_sensitivity', 'panel_vs_frozen_range_proxy', 'hand_level_summary', 'G144_resolve_identical', 'replicates_usable')}, indent=1)[:4000])
    figure(res)


def figure(res):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
    rows = res['out_of_sample']
    keys = list(rows)
    lab = [k.split(':')[1] + (' (diagnostic)' if rows[k]['diagnostic_only'] else '') for k in keys]
    fig, ax = plt.subplots(1, 3, figsize=(22, 7), dpi=115)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    y = list(range(len(keys)))
    g.barh([t - 0.2 for t in y], [rows[k]['predicted_ratio_calibrated'] for k in keys], 0.38, color='#c9a227', label='predicted (pre-registered, calibrated)')
    g.barh([t + 0.2 for t in y], [rows[k]['measured_ratio_ext_over_144'] for k in keys], 0.38, color='#2a78d6', label='measured (60 FPC bootstrap replicates)')
    g.axvline(1, color=MUTED, lw=0.8)
    g.set_yticks(y)
    g.set_yticklabels(lab, fontsize=8)
    g.invert_yaxis()
    g.set_xlabel('panel-error ratio  extended / 144', fontsize=9, color=MUTED)
    g.set_title('(1) out-of-sample test: predicted vs measured error reduction', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.09), ncol=1)
    g = ax[1]
    S = ('BTN', 'SB', 'BB')
    x = list(range(3))
    g.bar([t - 0.27 for t in x], [res['panel_vs_frozen_range_proxy'][s]['measured_L144'] * 100 for s in S], 0.26, color='#c9a227', label='panel error at 144 (measured)')
    g.bar(x, [res['panel_vs_frozen_range_proxy'][s]['measured_Lext'] * 100 for s in S], 0.26, color='#2a78d6', label='panel error extended (measured)')
    g.bar([t + 0.27 for t in x], [res['panel_vs_frozen_range_proxy'][s]['frozen_range_proxy'] * 100 for s in S], 0.26, color='#1baf7a', label='frozen-range / outer-step proxy (A3 k13→k14)')
    g.set_xticks(x)
    g.set_xticklabels(S, fontsize=9)
    g.set_ylabel('seat EV loss (bb / 100 hands)', fontsize=9, color=MUTED)
    g.set_title('(2) panel error vs outer-loop proxy', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.09), ncol=1)
    g = ax[2]
    hl = res['hand_level_summary']
    nds = list(hl)
    yy = list(range(len(nds)))
    g.barh([t - 0.2 for t in yy], [hl[n]['regret_144_in_ext'] * 100 for n in nds], 0.38, color='#c9a227', label='144 strategy regret in the extended game')
    g.barh([t + 0.2 for t in yy], [hl[n]['regret_ext_in_144'] * 100 for n in nds], 0.38, color='#2a78d6', label='extended strategy regret in the 144 game')
    for t, n in zip(yy, nds):
        g.text(0, t + 0.42, f"  argmax switch {hl[n]['argmax_switch_share']*100:.1f}% of reach, L1 {hl[n]['L1']:.2f}", fontsize=7, color=MUTED, va='center')
    g.set_yticks(yy)
    g.set_yticklabels(nds, fontsize=8)
    g.invert_yaxis()
    g.set_xlabel('reach-weighted class regret (bb / 100 at the node)', fontsize=9, color=MUTED)
    g.set_title('(3) hand-level 144 ↔ extended (point solves)', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.09), ncol=1)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    c = res['classification']
    fig.suptitle(f"A4c: 144 → 232 / 218 boards (node 6 / node 28), downstream-aware nested extension at P14 ranges — continuity label {c['label']} "
                 f"(expected before results: EV-sensitive)", fontsize=11, color=INK, x=0.01, ha='left')
    fig.text(0.01, 0.002, 'Panel error = mean seat-swap EV loss / class-regret excess of the bootstrap policy in the point game (FPC-rescaled nested paired bootstrap). '
             'The frozen-range proxy is a consecutive-outer-state sensitivity, not the true fixed-point residual.', fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    fig.savefig(os.path.join(C.ROOT, 'docs/GTO_TERMINAL_A4C_V2.png'), facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
