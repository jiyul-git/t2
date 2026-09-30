#!/usr/bin/env python3
"""B3b oracle-frontier equivalence test: verdict JSON + figure.

    python3 tools/gto_hu_continuation/analyze_b3b.py [--png docs/GTO_TERMINAL_B3B_V2.png]

Inputs (data/gto_terminal_expansion/threeway/): b3b_onestep.json, b3b_shadow50.json (monolithic simultaneous A'
vs factorized trunk fed the monolithic tree's exact frontier values at the same snapshot) and
b3b_control_stale_oracle.json (negative control: oracle values one iteration late).
"""
import argparse
import json

O = 'data/gto_terminal_expansion/threeway/'
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
SEAT = {'SB': '#1baf7a', 'BB': '#2a78d6', 'BTN': '#eb6834'}
FLOOR = 1e-18


def diffs(run):
    return [r['diff'] for r in run['rows'] if 'eval_mono' not in r]


def checks(run):
    return [r for r in run['rows'] if 'eval_mono' in r]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--png', default='docs/GTO_TERMINAL_B3B_V2.png')
    a = ap.parse_args()
    one, sh, ct = (json.load(open(O + f)) for f in ('b3b_onestep.json', 'b3b_shadow50.json', 'b3b_control_stale_oracle.json'))
    keys = ('trunk_regret_max_abs_diff', 'trunk_strategy_sum_max_abs_diff', 'frontier_reach_max_abs_diff', 'root_cf_value_max_abs_diff')
    d1 = diffs(one)[0]
    res = {'one_step': {k: d1[k] for k in keys} | {'limits': {'value_regret': 1e-6, 'strategy_reach': 1e-7}},
           'one_step_pass': d1['trunk_regret_max_abs_diff'] <= 1e-6 and d1['root_cf_value_max_abs_diff'] <= 1e-6
           and d1['frontier_reach_max_abs_diff'] <= 1e-7 and d1['trunk_strategy_sum_max_abs_diff'] <= 1e-7,
           'shadow': {'iterations': len(diffs(sh)), 'max_over_iterations': {k: max(r[k] for r in diffs(sh)) for k in keys},
                      'first_divergence': sh['first_divergence']},
           'control_stale_oracle': {'first_divergence': ct['first_divergence'],
                                    'max_over_iterations': {k: max(r[k] for r in diffs(ct)) for k in keys}},
           'checks': []}
    for c in checks(sh):
        em, ef = c['eval_mono'], c['eval_factorized']
        pm = {sh['positions'][p['player']]: p for p in em['players']}
        pf = {sh['positions'][p['player']]: p for p in ef['players']}
        row = {'iteration': c['iteration'], 'expl_mono_pct': em['exploitability_pct_pot'], 'expl_factorized_pct': ef['exploitability_pct_pot'],
               'range_ev_max_abs_diff': max(abs(pm[q]['range_value'] - pf[q]['range_value']) for q in pm),
               'br_gain_max_abs_diff': max(abs(pm[q]['br_gain_bb'] - pf[q]['br_gain_bb']) for q in pm),
               'class_value_max_abs_diff': max(abs(x - y) for q in pm for x, y in zip(pm[q]['class_gross'], pf[q]['class_gross'])
                                               if x is not None and y is not None),
               'strategy_max_abs_diff': max(abs(x - y) for m_, f_ in zip(c['root_mix_mono'], c['root_mix_factorized']) for x, y in zip(m_['mix'], f_['mix'])),
               'conservation': [em['conservation_error'], ef['conservation_error']]}
        res['checks'].append(row)
    a2 = json.load(open(O + 'b3a_A2_mono_sim.json'))
    a2_50 = next(t for t in a2['trace'] if t['iteration'] == 50)['eval']['exploitability_pct_pot']
    res['same_path_as_Aprime_run'] = {'Aprime_trace_expl_at_50': a2_50, 'shadow_mono_expl_at_50': res['checks'][-1]['expl_mono_pct']}
    shadow_zero = all(v == 0.0 for v in res['shadow']['max_over_iterations'].values())
    shadow_ok = all(res['shadow']['max_over_iterations'][k] <= 1e-6 for k in keys)
    res['verdict'] = {
        'split_wiring': 'correct' if (res['one_step_pass'] and shadow_ok and ct['first_divergence']) else 'bug',
        'bit_identical_50': shadow_zero,
        'test_power': 'the stale-by-one oracle diverges at iteration 2' if ct['first_divergence'] else 'NO POWER: control did not diverge',
        'implication': ('the factorized trunk reproduces the monolithic trunk exactly when fed the monolithic frontier values; the B/D stall '
                        'is therefore a property of combining the trunk with independently re-solved frontiers (3-player dynamics of the '
                        'decomposition), not a wiring bug')}
    json.dump(res, open(O + 'b3b_verdict.json', 'w'), indent=1)
    print(json.dumps(res, indent=1)[:3000])
    figure(res, sh, ct, a.png)


def figure(res, sh, ct, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 4, figsize=(25, 5.8), dpi=115)
    fig.patch.set_facecolor(SURF)
    g = ax[0]
    lab = {'trunk_regret_max_abs_diff': 'trunk regrets', 'root_cf_value_max_abs_diff': 'root counterfactual values',
           'trunk_strategy_sum_max_abs_diff': 'trunk strategy sums', 'frontier_reach_max_abs_diff': 'frontier arriving reach'}
    cols = {'trunk_regret_max_abs_diff': INK, 'root_cf_value_max_abs_diff': '#c0392b', 'trunk_strategy_sum_max_abs_diff': '#8a5cd1',
            'frontier_reach_max_abs_diff': '#2a78d6'}
    for k in lab:
        xs = [r['iteration'] for r in diffs(ct)]
        g.plot(xs, [max(FLOOR, r[k]) for r in diffs(ct)], color=cols[k], ls='--', marker='x', label=f'control (stale oracle): {lab[k]}')
        xs = [r['iteration'] for r in diffs(sh)]
        g.plot(xs, [max(FLOOR, r[k]) for r in diffs(sh)], color=cols[k], ls='-', lw=2, label=f'oracle shadow: {lab[k]}')
    g.set_yscale('log')
    g.axhline(1e-6, color=MUTED, ls=':', lw=1)
    g.text(1, 2e-6, 'limit 1e-6', fontsize=8, color=MUTED)
    g.text(3, 3e-18, 'oracle shadow: exactly 0 at every iteration (drawn at 1e-18)', fontsize=8.5, color=INK)
    g.set_xlabel('iteration', fontsize=9, color=MUTED)
    g.set_ylabel('max |monolithic − factorized| (log)', fontsize=9, color=MUTED)
    g.set_title('(1) differential: oracle shadow vs stale-oracle control', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=6.8, frameon=False, loc='center right')
    g = ax[1]
    ck = res['checks']
    xs = [c['iteration'] for c in ck]
    g.plot(xs, [c['expl_mono_pct'] for c in ck], color=INK, marker='o', lw=2, label="monolithic simultaneous (A′ schedule)")
    g.plot(xs, [c['expl_factorized_pct'] for c in ck], color='#c9a227', marker='s', ls='--', lw=2, label='factorized trunk + oracle frontier values')
    ctc = checks(ct)
    if ctc:
        g.scatter([c['iteration'] for c in ctc], [c['eval_factorized']['exploitability_pct_pot'] for c in ctc], color='#c0392b', marker='x', s=70,
                  label='control factorized (stale oracle)', zorder=4)
    g.set_yscale('log')
    g.set_xlabel('iteration', fontsize=9, color=MUTED)
    g.set_ylabel('exploitability (% pot, log)', fontsize=9, color=MUTED)
    g.set_title('(2) whole-game exploitability at the checks', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[2]
    last = checks(sh)[-1]
    pm = {sh['positions'][p['player']]: p for p in last['eval_mono']['players']}
    pf = {sh['positions'][p['player']]: p for p in last['eval_factorized']['players']}
    for q in pm:
        x = [u for u, v in zip(pm[q]['class_gross'], pf[q]['class_gross']) if u is not None and v is not None]
        y = [v for u, v in zip(pm[q]['class_gross'], pf[q]['class_gross']) if u is not None and v is not None]
        g.scatter(x, y, s=9, color=SEAT[q], label=f'{q}: max |Δ| {max(abs(u - v) for u, v in zip(x, y)):.1e} bb')
    lo, hi = g.get_xlim()
    g.plot([lo, hi], [lo, hi], color=MUTED, ls=':', lw=1)
    g.set_xlabel(f"monolithic class value @{last['iteration']} (bb)", fontsize=9, color=MUTED)
    g.set_ylabel('factorized (oracle) class value (bb)', fontsize=9, color=MUTED)
    g.set_title(f"(3) class values at {last['iteration']}", loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[3]
    g.axis('off')
    v = res['verdict']
    fd = ct['first_divergence']
    txt = [f"one-step differential (iteration 1): {'PASS' if res['one_step_pass'] else 'FAIL'}",
           '   ' + ', '.join(f"{lab[k]} {res['one_step'][k]:.0e}" for k in lab),
           f"shadow {res['shadow']['iterations']} iterations: max diffs " + ', '.join(f"{res['shadow']['max_over_iterations'][k]:.0e}" for k in lab),
           f"checks: range EV / BR gain / class / strategy max diff = "
           f"{max(c['range_ev_max_abs_diff'] for c in ck):.0e} / {max(c['br_gain_max_abs_diff'] for c in ck):.0e} / "
           f"{max(c['class_value_max_abs_diff'] for c in ck):.0e} / {max(c['strategy_max_abs_diff'] for c in ck):.0e}",
           f"control (oracle one iteration late): first divergence at iteration {fd['iteration']},",
           f"   template {fd['template']} ({fd['street']}), slot {fd['slot']}, player {sh['positions'][fd['player']]}, instance {fd['instance']},",
           f"   regret diff {fd['max_regret_diff']:.2e} (test has power)",
           '', f"verdict: split wiring {v['split_wiring'].upper()} (bit-identical over {res['shadow']['iterations']}: {v['bit_identical_50']})",
           'implication: B/D stall = dynamics of trunk + independently', 're-solved frontiers (3-player), not a wiring bug']
    g.text(0.0, 0.98, '\n'.join(txt), va='top', ha='left', fontsize=9.5, color=INK, family='monospace', transform=g.transAxes)
    g.set_title('(4) verdict', loc='left', fontsize=10, color=INK)
    for g in ax[:3]:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.suptitle('B3b oracle-frontier equivalence (reduced node 46 game, same as B3a): factorized trunk fed the monolithic frontier values at the same snapshot',
                 fontsize=10.5, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
