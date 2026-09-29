#!/usr/bin/env python3
"""J1: damped outer fixed point vs joint CFR on the identical 6-flop game.

    python3 tools/gto_hu_continuation/compare_j1.py \
        --joint data/gto_hu_continuation/j1/joint_sub6_m2.json \
        --fp data/gto_hu_continuation/outer_sub6_fp_damped_a05 --fp-undamped data/gto_hu_continuation/outer_sub6_fp \
        --quant data/gto_hu_continuation/j2 --out-json data/gto_hu_continuation/j1/compare_j1.json \
        --out-png docs/GTO_HU_J1_COMPARE_V1.png

Separates (a) aggregate agreement, (b) class-level action differences (marginal vs not),
(c) continuation-value differences, (d) zero-reach handling, (e) cycle presence, and puts
every difference next to the storage-quantisation band measured in J2 (f32 vs compressed).
"""
import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
C_FP, C_J = '#2a78d6', '#eb6834'


def last_k(d):
    k = 0
    while os.path.exists(os.path.join(d, f'k{k+1}', 'terminal.json')):
        k += 1
    return k


def seat(obj, pos, key='players'):
    return next(p for p in obj[key] if p['position'] == pos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--joint', required=True)
    ap.add_argument('--fp', required=True)
    ap.add_argument('--fp-undamped', required=True)
    ap.add_argument('--quant', required=True)
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-png', required=True)
    a = ap.parse_args()
    J = json.load(open(a.joint))
    K = last_k(a.fp)
    FT = json.load(open(os.path.join(a.fp, f'k{K}', 'terminal.json')))
    FV = json.load(open(os.path.join(a.fp, f'k{K}', 'table_measured.json')))
    L = J['class_labels']
    res = {'fp_final_step': K, 'joint_iterations': J['checkpoints'][-1]['iteration']}
    # (a) aggregates
    agg = {}
    for node in ('rfi_CO', 'rfi_BTN', 'rfi_SB', 'terminal_parent'):
        agg[node] = {'fp': FT['frequencies'][node]['mix'], 'joint': J['frequencies'][node]['mix']}
    res['aggregates'] = agg
    # (b) class-level actions
    cls = {}
    for node in ('rfi_BTN', 'terminal_parent'):
        f = FT['frequencies'][node]['class_strategy']
        j = J['frequencies'][node]['class_strategy']
        acts = FT['frequencies'][node]['actions']
        reach = seat(FT, 'BTN' if node == 'rfi_BTN' else 'BB')['class_keep_fraction'] if node == 'terminal_parent' else [1.0] * 169
        diffs = []
        for h in range(169):
            d = max(abs(f[x][h] - j[x][h]) for x in range(len(acts)))
            diffs.append((d, L[h], [round(f[x][h], 3) for x in range(len(acts))], [round(j[x][h], 3) for x in range(len(acts))]))
        diffs.sort(reverse=True)
        cls[node] = {'actions': acts, 'max_class_diff': diffs[0][0],
                     'n_classes_diff_gt_0.1': sum(1 for d in diffs if d[0] > 0.1),
                     'n_classes_diff_gt_0.5': sum(1 for d in diffs if d[0] > 0.5),
                     'top': [{'class': d[1], 'diff': round(d[0], 3), 'fp': d[2], 'joint': d[3]} for d in diffs[:15]]}
    res['class_actions'] = cls
    # arriving ranges
    rng = {}
    for pos in ('BTN', 'BB'):
        x = seat(FT, pos)['class_reach_normalized']
        y = seat(J, pos)['class_reach_normalized']
        rng[pos] = {'L1': sum(abs(i - k) for i, k in zip(x, y)), 'L2': sum((i - k) ** 2 for i, k in zip(x, y)) ** 0.5}
    res['arriving_range_distance'] = rng
    # (c) continuation values: FP measured table (eps-tremble, f32) vs joint average (compressed)
    qa = json.load(open(os.path.join(a.quant, 'quant_f32', 'Kc7d4h.json')))
    qb = json.load(open(os.path.join(a.quant, 'quant_compressed', 'Kc7d4h.json')))
    qband = {}
    for pa, pb in zip(qa['players'], qb['players']):
        d = [abs(x - y) for x, y in zip(pa['gross_eps'], pb['gross_eps']) if x is not None and y is not None]
        qband[pa['position']] = {'mean': sum(d) / len(d), 'max': max(d)}
    val = {}
    for pos in ('BTN', 'BB'):
        fv = seat(FV, pos, 'seats')['gross']
        jv = seat(J, pos)['gross_avg']
        jb = seat(J, pos)['gross_br']
        keepj = seat(J, pos)['class_keep_fraction']
        inr = [h for h in range(169) if keepj[h] > 1e-6]
        zr = [h for h in range(169) if keepj[h] <= 1e-6]
        d_in = [abs(fv[h] - jv[h]) for h in inr]
        d_zr_avg = [abs(fv[h] - jv[h]) for h in zr]
        d_zr_br = [abs(fv[h] - jb[h]) for h in zr]
        rj = seat(J, pos)['class_reach_normalized']
        wdiff_avg = sum(rj[h] * abs(fv[h] - jv[h]) for h in range(169))
        wdiff_br = sum(rj[h] * abs(fv[h] - jb[h]) for h in range(169))
        d_br_all = [abs(fv[h] - jb[h]) for h in range(169)]
        top = sorted(range(169), key=lambda h: -abs(fv[h] - jv[h]))[:10]
        val[pos] = {'in_range_classes': len(inr), 'zero_reach_classes': len(zr),
                    'in_range_mean_abs_diff': sum(d_in) / max(1, len(d_in)), 'in_range_max_abs_diff': max(d_in) if d_in else 0,
                    'zero_reach_mean_abs_diff_vs_joint_avg': sum(d_zr_avg) / max(1, len(d_zr_avg)),
                    'zero_reach_mean_abs_diff_vs_joint_br': sum(d_zr_br) / max(1, len(d_zr_br)),
                    'joint_br_minus_avg_in_range_max': max((jb[h] - jv[h]) for h in inr) if inr else 0,
                    'joint_br_minus_avg_zero_reach_mean': sum(jb[h] - jv[h] for h in zr) / max(1, len(zr)),
                    'reach_weighted_mean_abs_diff_fp_vs_joint_avg': wdiff_avg,
                    'reach_weighted_mean_abs_diff_fp_vs_joint_br': wdiff_br,
                    'all_classes_mean_abs_diff_fp_vs_joint_br': sum(d_br_all) / 169, 'all_classes_max_abs_diff_fp_vs_joint_br': max(d_br_all),
                    'storage_quantisation_band': qband[pos],
                    'top': [{'class': L[h], 'fp': round(fv[h], 3), 'joint_avg': round(jv[h], 3), 'joint_br': round(jb[h], 3),
                             'joint_keep': round(keepj[h], 3)} for h in top]}
    res['continuation_values'] = val
    # (d)/(e) joint trajectory: aggregate + class-level movement between checkpoints
    traj = []
    prev = None
    for c in J['checkpoints']:
        row = {'iteration': c['iteration'], 'gap_total': c['gap_total'], 'unallocated_bb': c['invariant']['unallocated_bb'],
               'btn_open': c['frequencies']['rfi_BTN']['mix'].get('raise_2'), 'bb_fold': c['frequencies']['terminal_parent']['mix']['fold'],
               'postflop_exploitability_max_pct': max(x['pct_pot'] for x in c['postflop_exploitability_pct_pot']),
               'postflop_exploitability_mean_pct': sum(x['pct_pot'] for x in c['postflop_exploitability_pct_pot']) / len(c['postflop_exploitability_pct_pot']),
               'elapsed_s': c['elapsed_s'], 'vm_hwm_kb': c['vm_hwm_kb']}
        if prev is not None:
            for node in ('rfi_BTN', 'terminal_parent'):
                x = prev['frequencies'][node]['class_strategy']
                y = c['frequencies'][node]['class_strategy']
                row[f'max_class_delta_{node}'] = max(abs(x[i][h] - y[i][h]) for i in range(len(x)) for h in range(169))
        traj.append(row)
        prev = c
    res['joint_trajectory'] = traj
    res['fp'] = {'gap_total': FT['gap_total'], 'table_unallocated_bb': FV['invariant']['unallocated_bb'],
                 'postflop_exploitability_max_pct': FV['provenance']['exploitability_pct_pot_max']}
    res['joint'] = {'gap_total_joint_game': J['checkpoints'][-1]['gap_total'], 'unallocated_bb': J['checkpoints'][-1]['invariant']['unallocated_bb'],
                    'postflop_arena_gb': J['postflop_arena_bytes'] / 1e9, 'vm_hwm_gb': J['checkpoints'][-1]['vm_hwm_kb'] / 1e6,
                    'wall_s': J['checkpoints'][-1]['elapsed_s'], 'mean_iteration_s': sum(J['per_iteration_s']) / len(J['per_iteration_s'])}
    json.dump(res, open(a.out_json, 'w'), indent=1)

    # figure
    fig, ax = plt.subplots(2, 2, figsize=(14, 9.5), dpi=120)
    fig.patch.set_facecolor(SURF)
    x = [r['iteration'] for r in traj]
    g = ax[0][0]
    g.plot(x, [r['btn_open'] for r in traj], 'o-', color=C_J, lw=2, label='joint: BTN open')
    g.plot(x, [r['bb_fold'] for r in traj], 's--', color=C_J, lw=2, label='joint: BB fold vs BTN')
    g.axhline(FT['frequencies']['rfi_BTN']['mix'].get('raise_2'), color=C_FP, lw=2, label=f'damped FP k{K}: BTN open')
    g.axhline(FT['frequencies']['terminal_parent']['mix']['fold'], color=C_FP, lw=2, ls='--', label=f'damped FP k{K}: BB fold')
    g.set_title('(1) aggregates: joint CFR trajectory vs damped fixed point', loc='left', fontsize=11, color=INK)
    g.set_xlabel('joint iteration', fontsize=9, color=MUTED)
    g.legend(fontsize=8, frameon=False)
    g = ax[0][1]
    for node, mk in (('rfi_BTN', 'o-'), ('terminal_parent', 's--')):
        g.plot(x[1:], [r.get(f'max_class_delta_{node}') for r in traj[1:]], mk, color=C_J, lw=2, label=f'joint {node} max class Δ per 50 it')
    g.set_title('(2) joint: class-level movement between checkpoints', loc='left', fontsize=11, color=INK)
    g.set_xlabel('joint iteration', fontsize=9, color=MUTED)
    g.legend(fontsize=8, frameon=False)
    g = ax[1][0]
    for pos, col in (('BB', C_FP), ('BTN', C_J)):
        fv = seat(FV, pos, 'seats')['gross']
        jv = seat(J, pos)['gross_avg']
        keepj = seat(J, pos)['class_keep_fraction']
        jb = seat(J, pos)['gross_br']
        g.scatter(fv, jb, s=14, color=col, alpha=0.8, label=f'{pos}: joint best-response value (all classes)')
        g.scatter(fv, jv, s=14, facecolors='none', edgecolors=col, alpha=0.5, label=f'{pos}: joint average-strategy value (off-diagonal = low/zero reach, uniform fallback)')
    lo = min(min(seat(FV, p, 'seats')['gross']) for p in ('BB', 'BTN'))
    hi = max(max(seat(FV, p, 'seats')['gross']) for p in ('BB', 'BTN'))
    g.plot([lo, hi], [lo, hi], color=MUTED, lw=1)
    g.set_xlabel('damped FP measured table (bb, f32, eps-tremble)', fontsize=9, color=MUTED)
    g.set_ylabel('joint CFR value (bb, compressed)', fontsize=9, color=MUTED)
    g.set_title('(3) per-class continuation value', loc='left', fontsize=11, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[1][1]
    g.plot(x, [r['gap_total'] for r in traj], 'o-', color=C_J, lw=2, label='joint-game gap (preflop + postflop BR)')
    g.plot(x, [r['postflop_exploitability_max_pct'] / 100 * J['pot_bb'] for r in traj], 's--', color=C_J, lw=1.5, label='postflop exploitability max (bb)')
    g.plot(x, [abs(r['unallocated_bb']) for r in traj], '^:', color=MUTED, lw=1.5, label='|unallocated| (bb)')
    g.axhline(0.05, color=MUTED, lw=1, ls=':')
    g.set_yscale('log')
    g.set_title('(4) joint convergence metrics', loc='left', fontsize=11, color=INK)
    g.set_xlabel('joint iteration', fontsize=9, color=MUTED)
    g.legend(fontsize=8, frameon=False)
    for r in ax:
        for g in r:
            g.set_facecolor(SURF)
            g.grid(color=GRID, lw=0.8)
            for sp in ('top', 'right'):
                g.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(a.out_png, facecolor=SURF, bbox_inches='tight')
    print(json.dumps({k: res[k] for k in ('aggregates', 'arriving_range_distance', 'fp', 'joint')}, indent=1))
    for node, v in cls.items():
        print(node, 'max class diff', round(v['max_class_diff'], 3), '>0.1:', v['n_classes_diff_gt_0.1'], '>0.5:', v['n_classes_diff_gt_0.5'],
              [(t['class'], t['diff']) for t in v['top'][:8]])
    for pos, v in val.items():
        print(pos, {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if k != 'top'})


if __name__ == '__main__':
    main()
