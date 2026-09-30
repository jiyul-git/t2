#!/usr/bin/env python3
"""T2-B item 9: a PROXY for the structural error of the legacy 3-way payoff (not a measurement).

    python3 tools/gto_hu_continuation/mw_transfer_proxy.py --out-json data/gto_terminal_expansion/mw_legacy/transfer_proxy.json

Assumption (stated, untested): the per-class realization of solved HU play relative to raw
equity transfers to the 3-way pot by role. For each class, R = V_solved / (pot * eq), with the
HU raw equity eq = V_legacy_HU / (pot * static_r) (the static legacy formula without its cap).
Roles: the aggressor (IP) takes the HU aggressor's R; both callers (SB and BB, OOP) take the HU
caller's R (the BB in the matching HU terminal: node 28 for the BTN open, node 228 for the CO open).
Node 28 uses the 72-flop k9 table (P9 ranges), node 228 the six-flop pilot.
Proxy 3-way value = coupled-deck gross * R, then one common factor restores sum r V = pot.
Reported: mean |proxy - legacy| per player, signed range-EV shift, and the preflop decisions on
the path with the other strategies fixed (EV of the on-path action moves by q * delta,
q = product of the later players' on-path reach factors).
"""
import argparse
import json

D = 'data/gto_terminal_expansion/'


def pl(t, pos):
    return next(p for p in t['players'] if p['position'] == pos)


def realization(term, solved, pos):
    p = pl(term, pos)
    out = []
    for h in range(169):
        leg = p['legacy_gross'][h]
        eq_pot = leg / p['static_r']
        out.append(solved[h] / eq_pot if eq_pot > 1e-9 else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-json', required=True)
    a = ap.parse_args()
    k9 = json.load(open('data/gto_hu_continuation/panel72/outer_v2_damped_a05/k9/table_measured.json'))
    t28 = json.load(open(D + 'terminals/p9_node28.json'))
    t228 = json.load(open(D + 'terminals/p9_node228.json'))
    p6 = json.load(open(D + 'pilot6/analysis.json'))['terminals']
    R = {
        46: {'agg': realization(t28, next(s for s in k9['seats'] if s['position'] == 'BTN')['gross'], 'BTN'),
             'call': realization(t28, next(s for s in k9['seats'] if s['position'] == 'BB')['gross'], 'BB'), 'aggressor': 'BTN',
             'source': 'node 28, 72-flop k9 table'},
        246: {'agg': realization(t228, p6['228']['seats']['CO']['solved'], 'CO'),
              'call': realization(t228, p6['228']['seats']['BB']['solved'], 'BB'), 'aggressor': 'CO',
              'source': 'node 228, six-flop pilot'},
    }
    res = {'assumption': __doc__.split('Assumption')[1].split('Reported')[0].strip(), 'nodes': {}}
    for node in (46, 246):
        t = json.load(open(f'{D}terminals/p9_node{node}.json'))
        L = t['class_labels']
        prox = {}
        for p in t['players']:
            role = 'agg' if p['position'] == R[node]['aggressor'] else 'call'
            rr = R[node][role]
            prox[p['position']] = [p['legacy_gross'][h] * (rr[h] if rr[h] is not None else 1.0) for h in range(169)]
        tot = sum(sum(r * v for r, v in zip(pl(t, pos)['class_reach_normalized'], prox[pos])) for pos in prox)
        k = t['pot_bb'] / tot
        for pos in prox:
            prox[pos] = [v * k for v in prox[pos]]
        row = {'renormalisation_factor': k, 'realization_source': R[node]['source'], 'players': {}, 'decisions': []}
        for p in t['players']:
            pos = p['position']
            r = p['class_reach_normalized']
            d = [x - y for x, y in zip(prox[pos], p['legacy_gross'])]
            row['players'][pos] = {'role': 'aggressor' if pos == R[node]['aggressor'] else 'caller',
                                   'mean_abs_delta': sum(abs(x) for x in d) / 169,
                                   'reach_weighted_abs_delta': sum(r[h] * abs(d[h]) for h in range(169)),
                                   'range_ev_shift': sum(r[h] * d[h] for h in range(169)),
                                   'legacy_range_ev': sum(r[h] * p['legacy_gross'][h] for h in range(169))}
        pn_all = t['path_nodes']
        for i, pn in enumerate(pn_all):
            pos = pn['actor']
            if pos not in prox or not pn['ev_bb']:
                continue
            q = 1.0
            for later in pn_all[i + 1:]:
                q *= later['reach_factor']
            a_on = pn['chosen']
            d = [x - y for x, y in zip(prox[pos], pl(t, pos)['legacy_gross'])]
            flips, took_before, took_after = [], 0.0, 0.0
            rb = pn['class_reach_before']
            for h in range(169):
                if rb[h] <= 0:
                    continue
                e0 = [e[h] for e in pn['ev_bb']]
                e1 = list(e0)
                e1[a_on] += q * d[h]
                b0 = max(range(len(e0)), key=lambda i_: e0[i_])
                b1 = max(range(len(e1)), key=lambda i_: e1[i_])
                took_before += rb[h] * (b0 == a_on)
                took_after += rb[h] * (b1 == a_on)
                if b0 != b1:
                    flips.append({'class': L[h], 'from': pn['actions'][b0], 'to': pn['actions'][b1], 'shift_bb': q * d[h]})
            m = sum(rb)
            row['decisions'].append({'actor': pos, 'on_path_action': pn['actions'][a_on], 'q': q, 'mix_P9': pn['mix'],
                                     'best_response_share_of_on_path_action_legacy': took_before / m,
                                     'best_response_share_of_on_path_action_proxy': took_after / m,
                                     'flips': flips})
        res['nodes'][node] = row
    json.dump(res, open(a.out_json, 'w'), indent=1)
    for node, row in res['nodes'].items():
        print(f'node {node}: renorm {row["renormalisation_factor"]:.3f} ({row["realization_source"]})')
        for pos, x in row['players'].items():
            print(f'   {pos} ({x["role"]}): mean|d| {x["mean_abs_delta"]:.3f} rw|d| {x["reach_weighted_abs_delta"]:.3f} range-EV shift {x["range_ev_shift"]:+.3f} (legacy range EV {x["legacy_range_ev"]:.3f})')
        for dd in row['decisions']:
            print(f'   {dd["actor"]} {dd["on_path_action"]} q {dd["q"]:.3f}: BR share of on-path action {dd["best_response_share_of_on_path_action_legacy"]:.3f} -> {dd["best_response_share_of_on_path_action_proxy"]:.3f};'
                  f' flips {len(dd["flips"])}', [(f['class'], f['from'][:4], f['to'][:4]) for f in dd['flips'][:12]])


if __name__ == '__main__':
    main()
