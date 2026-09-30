#!/usr/bin/env python3
"""A3 analysis: per-step records, convergence case (convergence_rule.json), figure.

    python3 tools/gto_hu_continuation/analyze_a3.py [--png docs/GTO_TERMINAL_A3_V2.png]

Reads data/gto_terminal_expansion/outer_m28_6/ (loop_log.json, k*/terminal_node*.json, k*/census.json,
k*/node*/flops, k*/used_node*.json) and the P9 reference (terminals/p9_node*.json, census_p9.json).
"""
import argparse
import glob
import json
import math
import os

E = 'data/gto_terminal_expansion/'
OUT = E + 'outer_m28_6/'
INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
MAIN = {'CO first-in': ('rfi_CO', ['fold', 'raise_2', 'jam_30']), 'BTN first-in': ('rfi_BTN', ['fold', 'raise_2', 'jam_30']),
        'SB first-in': ('rfi_SB', ['fold', 'raise_2.5', 'jam_30']),
        'BB vs BTN (node 28 parent)': ('28:BB@26', ['Fold', 'Call 2', '3-bet 7', 'All-in 30']),
        'BB vs SB (node 6 parent)': ('6:BB@4', ['Fold', 'Call 2.5', '3-bet 8.8', 'All-in 30'])}


def finite(x):
    if isinstance(x, dict):
        return all(finite(v) for v in x.values())
    if isinstance(x, list):
        return all(finite(v) for v in x)
    if isinstance(x, float):
        return math.isfinite(x)
    return True


def state(tag, t28, t6, census):
    fr = t28['frequencies']
    st = {'tag': tag, 'gap_total': t28['gap_total'], 'ev_sum': sum(t28['evs'].values()) if isinstance(t28['evs'], dict) else sum(t28['evs']),
          'ranges_hash': {'28': t28['ranges_hash_fnv1a64'], '6': t6['ranges_hash_fnv1a64']}, 'freq': {}, 'class': {}}
    for name, (key, acts) in MAIN.items():
        if key.startswith('rfi'):
            mix = fr[key]['mix']
            cs = fr[key]['class_strategy']
            names = [a.lower().replace(' ', '_').replace('all-in_30', 'jam_30') for a in fr[key]['actions']]
        else:
            n, pos = key.split(':')
            tt = t28 if n == '28' else t6
            pn = next(p for p in tt['path_nodes'] if f"{p['actor']}@{p['node']}" == pos)
            mix, cs, names = pn['mix'], pn['class_strategy'], pn['actions']
        st['freq'][name] = {a: mix.get(a, 0.0) for a in acts}
        st['class'][name] = {'actions': names, 'strategy': cs}
    reach = {r['terminal_node']: r for r in census['terminals']}
    st['reach'] = {str(n): reach[n]['reach_probability'] for n in (28, 6, 46, 246)}
    st['flop_by_live'] = {f'{lc}-way': sum(r['reach_probability'] for r in census['terminals'] if r['live_count'] == lc) for lc in (2, 3, 4)}
    st['flop_total'] = sum(st['flop_by_live'].values())
    st['players'] = {n: {p['position']: p['class_reach_normalized'] for p in tt['players']} for n, tt in (('28', t28), ('6', t6))}
    st['finite'] = finite(t28['evs']) and finite(t6['evs']) and finite(st['freq'])
    return st


def argmax_class_changes(a, b):
    out = {}
    for name in MAIN:
        ca, cb = a['class'][name], b['class'][name]
        acts = ca['actions']
        sa, sb = ca['strategy'], cb['strategy']
        ch = []
        for h in range(169):
            ia = max(range(len(sa)), key=lambda i: sa[i][h])
            ib = max(range(len(sb)), key=lambda i: sb[i][h])
            if ia != ib:
                ch.append({'class': h, 'from': acts[ia], 'to': acts[ib]})
        out[name] = ch
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--png', default='docs/GTO_TERMINAL_A3_V2.png')
    a = ap.parse_args()
    labels = json.load(open(E + 'terminals/p9_node6.json'))['class_labels']
    log = json.load(open(OUT + 'loop_log.json'))
    states = [state('P9', json.load(open(E + 'terminals/p9_node28.json')), json.load(open(E + 'terminals/p9_node6.json')), json.load(open(E + 'census_p9.json')))]
    for s in sorted(log['steps'], key=lambda s: s['k']):
        d = OUT + f"k{s['k']}/"
        states.append(state(f"P{s['k']}", json.load(open(d + 'terminal_node28.json')), json.load(open(d + 'terminal_node6.json')), json.load(open(d + 'census.json'))))
    steps = []
    for s in sorted(log['steps'], key=lambda s: s['k']):
        row = {'k': s['k'], 'terminals': s.get('terminals', {}), 'combined_residual': s.get('combined_reach_weighted_used_unallocated_bb')}
        for n in ('28', '6'):
            fl = [json.load(open(f)) for f in sorted(glob.glob(OUT + f"k{s['k']}/node{n}/flops/*.json"))]
            if fl:
                ex = sorted(f['exploitability_pct_pot'] for f in fl)
                row.setdefault('postflop', {})[n] = {'flops': len(fl), 'converged': sum(1 for f in fl if f['exploitability_pct_pot'] <= f['provenance_key']['target_exploitability_pct_pot']),
                                                     'expl_min': ex[0], 'expl_median': ex[len(ex) // 2], 'expl_max': ex[-1],
                                                     'nonconverged': [f['board'] for f in fl if f['exploitability_pct_pot'] > f['provenance_key']['target_exploitability_pct_pot']]}
        steps.append(row)
    trans = []
    for x, y in zip(states, states[1:]):
        tr = {'from': x['tag'], 'to': y['tag'],
              'agg_change': {nm: {ac: y['freq'][nm][ac] - x['freq'][nm][ac] for ac in x['freq'][nm]} for nm in MAIN},
              'range_L1': {n: {pos: sum(abs(u - v) for u, v in zip(x['players'][n][pos], y['players'][n][pos])) for pos in x['players'][n]} for n in ('28', '6')},
              'boundary_changes': {nm: [dict(c, **{'label': labels[c['class']]}) for c in ch] for nm, ch in argmax_class_changes(x, y).items()}}
        tr['max_agg_change'] = max(abs(v) for d in tr['agg_change'].values() for v in d.values())
        tr['range_L1_max'] = max(v for d in tr['range_L1'].values() for v in d.values())
        trans.append(tr)
    # measured mean |dV| per terminal from the loop log (vs the previous measured table)
    dv = {}
    for s in steps:
        for n, t in s['terminals'].items():
            if 'measured_change' in t:
                dv.setdefault(n, {})[s['k']] = max(v['mean_abs'] for v in t['measured_change'].values())
    res = {'states': [{k: v for k, v in st.items() if k not in ('class', 'players')} for st in states], 'steps': steps, 'transitions': trans,
           'measured_mean_abs_dV_max_seat': dv, 'hard_stop_flags': {'non_finite': [st['tag'] for st in states if not st['finite']]}}
    # case (convergence_rule.json), evaluated on P10..P_last (P9 -> P10 is the frozen-table A2.5 step)
    tr = [t for t in trans if t['from'] != 'P9']
    case = 'insufficient'
    if len(tr) >= 3:
        last = tr[-1]
        mac = [t['max_agg_change'] for t in tr]
        l1 = [t['range_L1_max'] for t in tr]
        dvs = [max(dv[n].get(int(t['to'][1:]) - 1, 0) for n in dv) for t in tr]
        ev = [abs(s['ev_sum']) for s in states[1:]]
        period2 = False
        for nm in MAIN:
            for ac in states[0]['freq'][nm]:
                seq = [s['freq'][nm][ac] for s in states[1:]]
                for i in range(len(seq) - 2):
                    d1, d2, d02 = seq[i + 1] - seq[i], seq[i + 2] - seq[i + 1], abs(seq[i + 2] - seq[i])
                    if d1 * d2 < 0 and d02 < 0.5 * min(abs(d1), abs(d2)) and min(abs(d1), abs(d2)) > 0.005:
                        period2 = True
        inc2 = lambda xs: len(xs) >= 3 and xs[-1] > xs[-2] > xs[-3]
        dec = lambda xs: all(y < x for x, y in zip(xs, xs[1:]))
        if last['max_agg_change'] <= 0.005:
            case = 'A_converged'
        elif period2:
            case = 'C_period2'
        elif (inc2(l1) and inc2(dvs) and inc2(mac)) or inc2(ev):
            case = 'D_divergence'
        elif dec(l1) and dec(mac) and dec([x for x in dvs if x]):
            case = 'B_decreasing'
        else:
            case = 'not_converged_mixed'
        res['case_inputs'] = {'max_agg_change': mac, 'range_L1_max': l1, 'measured_dV': dvs, 'abs_ev_sum': ev, 'period2_detected': period2}
    res['case'] = case
    json.dump(res, open(OUT + 'analysis.json', 'w'), indent=1)
    for st in states:
        print(st['tag'], 'SB', {k: round(v, 3) for k, v in st['freq']['SB first-in'].items()}, 'BBvsSB', {k: round(v, 3) for k, v in st['freq']['BB vs SB (node 6 parent)'].items()},
              'reach', {k: round(v, 4) for k, v in st['reach'].items()}, 'EVsum', round(st['ev_sum'], 4))
    for t in trans:
        print(t['from'], '->', t['to'], 'max agg', round(t['max_agg_change'], 4), 'L1 max', round(t['range_L1_max'], 3),
              'boundary', {k[:6]: len(v) for k, v in t['boundary_changes'].items()})
    print('dV', dv, 'case', case)
    figure(res, states, steps, trans, a.png)


def figure(res, states, steps, trans, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tags = [s['tag'] for s in states]
    xs = list(range(len(states)))
    fig, ax = plt.subplots(2, 3, figsize=(22, 11), dpi=110)
    fig.patch.set_facecolor(SURF)
    ax = ax.ravel()
    g = ax[0]
    for ac, col, lab in (('raise_2.5', '#1baf7a', 'SB open raise 2.5'), ('jam_30', '#0b5d42', 'SB jam'), ('fold', '#9fd9c4', 'SB fold')):
        g.plot(xs, [s['freq']['SB first-in'][ac] for s in states], color=col, marker='o', lw=2, label=lab)
    for ac, col, lab in (('Call 2.5', '#2a78d6', 'BB vs SB: call'), ('All-in 30', '#123f73', 'BB vs SB: jam'), ('Fold', '#9cc3ef', 'BB vs SB: fold')):
        g.plot(xs, [s['freq']['BB vs SB (node 6 parent)'][ac] for s in states], color=col, marker='s', ls='--', lw=1.8, label=lab)
    g.axvspan(0.5, 1.5, color='#f3d9d3', alpha=0.6, lw=0)
    g.text(1, 0.97, 'P10 = frozen-table\n(A2.5) state', ha='center', va='top', fontsize=8, color='#c0392b')
    g.set_title('(1) SB first-in and BB response to the SB open, per outer step', loc='left', fontsize=10, color=INK)
    g.set_ylabel('aggregate frequency', fontsize=9, color=MUTED)
    g.legend(fontsize=7.5, frameon=False, ncol=2, loc='center right')
    g = ax[1]
    for n, col, lab in (('6', '#1baf7a', 'node 6 SB open / BB call (HU, solved)'), ('28', '#2a78d6', 'node 28 BTN open / BB call (HU, solved)'),
                        ('46', '#eb6834', 'node 46 BTN open, SB+BB call (3-way, legacy)'), ('246', '#8a5cd1', 'node 246 CO open, SB+BB call (3-way, legacy)')):
        g.plot(xs, [s['reach'][n] for s in states], color=col, marker='o', lw=2, label=lab)
    g.set_title('(2) terminal reach', loc='left', fontsize=10, color=INK)
    g.set_ylabel('reach probability', fontsize=9, color=MUTED)
    g.legend(fontsize=7.5, frameon=False)
    g = ax[2]
    tx = [i + 0.5 for i in range(len(trans))]
    for n, col in (('28', '#2a78d6'), ('6', '#1baf7a')):
        for pos, ls in (('BB', '-'), ('SB', '--'), ('BTN', '--')):
            v = [t['range_L1'][n].get(pos) for t in trans]
            if all(x is not None for x in v):
                g.plot(tx, v, color=col, ls=ls, marker='o', ms=4, label=f'range L1 node {n} {pos}')
    g2 = g.twinx()
    for n, col in (('28', '#2a78d6'), ('6', '#1baf7a')):
        d = res['measured_mean_abs_dV_max_seat'].get(n, {})
        if d:
            ks = sorted(d)
            g2.plot([tags.index(f'P{k}') for k in ks], [d[k] for k in ks], color=col, ls=':', marker='D', ms=6, label=f'measured mean |ΔV| node {n} (right)')
    g2.set_ylabel('measured table change, mean |ΔV| (bb, max seat)', fontsize=9, color=MUTED)
    g.set_ylabel('range L1 vs previous P', fontsize=9, color=MUTED)
    g.set_title('(3) range L1 between consecutive P (left) and measured |ΔV| (right)', loc='left', fontsize=10, color=INK)
    h1, l1 = g.get_legend_handles_labels()
    h2, l2 = g2.get_legend_handles_labels()
    g.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False)
    g = ax[3]
    for i, s in enumerate(steps):
        for j, (n, col) in enumerate((('28', '#2a78d6'), ('6', '#1baf7a'))):
            t = s['terminals'].get(n)
            if not t:
                continue
            x = i + (j - 0.5) * 0.3
            g.scatter(x, t['candidate_blend_unallocated_bb'], color=col, marker='o' if t['blend_candidate_accepted'] else 'X', s=90,
                      label=f'node {n} candidate α=0.5 ' + ('accepted' if t['blend_candidate_accepted'] else 'REJECTED'))
            g.scatter(x, t['measured_unallocated_bb'], color=col, marker='_', s=200, label=f'node {n} measured (own range)')
            g.scatter(x, t['previous_used_unallocated_at_these_ranges_bb'], color=col, marker='v', s=40, alpha=0.6, label=f'node {n} previous table at new ranges')
    g.axhspan(-0.05, 0.05, color='#e6f4ea', lw=0)
    g.axhline(0, color=INK, lw=0.8)
    g.set_xticks(range(len(steps)))
    g.set_xticklabels([f"V{s['k']} (at P{s['k']})" for s in steps])
    g.set_ylabel('unallocated bb at the step ranges (guard ±0.05 shaded)', fontsize=9, color=MUTED)
    g.set_title('(4) conservation and blend accept / reject', loc='left', fontsize=10, color=INK)
    hh, ll = g.get_legend_handles_labels()
    uniq = dict(zip(ll, hh))
    g.legend(uniq.values(), uniq.keys(), fontsize=7, frameon=False)
    g = ax[4]
    w = 0.25
    for j, (k, col) in enumerate((('2-way', '#1f1f1e'), ('3-way', '#eb6834'), ('4-way', '#8a5cd1'))):
        g.bar([x + (j - 1) * w for x in xs], [s['flop_by_live'][k] for s in states], w, color=col, label=f'{k} flop reach')
    g.plot(xs, [s['flop_total'] for s in states], color=MUTED, marker='o', label='total flop reach')
    g.set_xticks(xs)
    g.set_xticklabels(tags)
    g.set_title('(5) flop reach by number of players', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False)
    g = ax[5]
    g.plot(xs, [s['ev_sum'] for s in states], color='#c0392b', marker='o', lw=2, label='preflop EV sum (0 = conserving)')
    g.plot(xs, [s['gap_total'] * 100 for s in states], color=MUTED, marker='s', lw=1.5, label='preflop gap × 100')
    g.axhline(0, color=INK, lw=0.8)
    g.set_title(f"(6) preflop EV sum and gap; case: {res['case']}", loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False)
    for g in ax[:3].tolist() + [ax[5]]:
        g.set_xticks(xs)
        g.set_xticklabels(tags)
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.suptitle('A3 — synchronous node 28 + node 6 damped outer fixed point (72 flops each per step; P9 = start, P10 = A2.5 frozen-table state)',
                 fontsize=11.5, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(path, facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
