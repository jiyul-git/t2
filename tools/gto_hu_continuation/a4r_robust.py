#!/usr/bin/env python3
"""A4R per amendment 2 (data/gto_terminal_expansion/a4b_panel144/prereg_amendment_2.json).

    python3 tools/gto_hu_continuation/a4r_robust.py run
    python3 tools/gto_hu_continuation/a4r_robust.py analyze [--png docs/GTO_TERMINAL_A4R_ROBUST_V2.png]

Primary: dEV_p(A -> G) = EV_p(sigma_G; G) - EV_p(A_p (+) sigma_G,-p; G) per seat / sub-seat group, by splicing A's
strategy blocks into G's own solve (t2_splice_eval). Validations: BR value identical, dEV = gap difference,
dEV >= -gap_p(sigma_G). Also raw NashConv of A and sigma_G in G (t2_cross_eval) and class-level L1 distances.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a4_audit import BIN, ENV  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
B = E + 'a4b_panel144/'
OUT = E + 'a4r_robust/'
GROUPS = {'CO': (0, 'all'), 'BTN': (1, 'all'), 'SB': (2, 'all'), 'BB': (3, 'all'), 'BB|SB-open': (3, '4'), 'BB|BTN-open': (3, '26')}
TERMINAL_OF = {'SB': 'node 6', 'BB|SB-open': 'node 6', 'BTN': 'node 28', 'BB|BTN-open': 'node 28', 'CO': '-', 'BB': 'both'}
NODE_OF = {'SB': ['SB first-in'], 'BB|SB-open': ['BB vs SB'], 'BTN': ['BTN first-in'], 'BB|BTN-open': ['BB vs BTN'], 'BB': ['BB vs SB', 'BB vs BTN'],
           'CO': [], }


def env(man):
    return {**os.environ, **ENV, 'T2_CONT_FILE': man}


def splice(game, donor, seat, root, out):
    if not os.path.exists(out):
        subprocess.run([BIN + '/t2_splice_eval', game['profile'], donor['profile'], str(seat), root, out], check=True, env=env(game['manifest']),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return json.load(open(out))


def xeval(game, donor, out):
    if not os.path.exists(out):
        subprocess.run([BIN + '/t2_cross_eval', donor['profile'], out], check=True, env=env(game['manifest']), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return json.load(open(out))


def l1(a, g, node):
    """reach-weighted class-level L1 distance of the action distributions at one node (sigma_G's arriving reach)."""
    ra, rg = a['key_nodes'][node], g['key_nodes'][node]
    w = rg['class_reach_before']
    tot = sum(w)
    if tot <= 0:
        return None
    return sum(w[h] * sum(abs(x[h] - y[h]) for x, y in zip(ra['class_strategy'], rg['class_strategy'])) for h in range(169)) / tot


def evaluate(tag, game, donor, d):
    os.makedirs(d, exist_ok=True)
    own_g, own_e = game['gaps'], game['evs']
    rec = {'tag': tag, 'groups': {}}
    for name, (seat, root) in GROUPS.items():
        s = splice(game, donor, seat, root, os.path.join(d, f"swap_{name.replace('|', '_')}.json"))
        dEV = own_e[seat] - s['evs'][seat]
        dgap = s['gaps'][seat] - own_g[seat]
        br_own = own_g[seat] + own_e[seat]
        rec['groups'][name] = {'dEV': dEV, 'positive_loss': max(dEV, 0.0), 'own_gap': own_g[seat], 'gap_diff': dgap,
                               'check_dEV_minus_gapdiff': abs(dEV - dgap), 'check_BR_value': abs(s['br_values'][seat] - br_own),
                               'check_lower_bound': dEV >= -own_g[seat] - 1e-12, 'nodes_swapped': s['nodes_swapped'],
                               'L1': {nd: l1(donor, game, nd) for nd in NODE_OF[name]}}
    x = xeval(game, donor, os.path.join(d, 'full_profile_xeval.json'))
    rec['nashconv_A_in_G'] = x['gap_total']
    rec['nashconv_own'] = game['gap_total']
    rec['gaps_A_in_G'] = x['gaps']
    return rec


def run(a):
    R = json.load(open(B + 'paired_results.json'))
    P = R['points']
    os.makedirs(OUT + 'evals', exist_ok=True)
    out = {'points': {}, 'boot': {}}
    # validation: self-splice of a game's own profile is exact
    v = evaluate('self_G144', P['V144'], P['V144'], OUT + 'evals/self_G144')
    out['self_validation'] = {g: x['dEV'] for g, x in v['groups'].items()}
    for tag, G, A in (('sigma72->G144', 'V144', 'V72'), ('sigma144->G72', 'V72', 'V144'), ('P15->G72', 'V72', 'P15'), ('P15->G144', 'V144', 'P15')):
        out['points'][tag] = evaluate(tag, P[G], P[A], OUT + f"evals/points/{tag.replace('->', '_to_')}")
        print(tag, {g: round(x['dEV'], 6) for g, x in out['points'][tag]['groups'].items()}, flush=True)
    for k, rep in sorted(R['boot'].items(), key=lambda kv: int(kv[0])):
        if 'V72' not in rep or 'V144' not in rep:
            continue
        out['boot'][k] = {
            'sigma72->G144': evaluate('sigma72->G144', rep['V144'], rep['V72'], OUT + f'evals/boot/r{int(k):02d}/s72_to_G144'),
            'sigma144->G72': evaluate('sigma144->G72', rep['V72'], rep['V144'], OUT + f'evals/boot/r{int(k):02d}/s144_to_G72')}
        print('boot', k, flush=True)
        json.dump(out, open(OUT + 'evals.json.tmp', 'w'), indent=1)
        os.replace(OUT + 'evals.json.tmp', OUT + 'evals.json')
    json.dump(out, open(OUT + 'evals.json', 'w'), indent=1)


def analyze(a):
    D = json.load(open(OUT + 'evals.json'))
    q95 = lambda xs: sorted(xs)[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]
    recs = [D['points'][t] for t in D['points']] + [b[t] for b in D['boot'].values() for t in b]
    checks = {'self_splice_dEV_max_abs': max(abs(x) for x in D['self_validation'].values()),
              'dEV_vs_gapdiff_max': max(g['check_dEV_minus_gapdiff'] for r in recs for g in r['groups'].values()),
              'BR_value_max': max(g['check_BR_value'] for r in recs for g in r['groups'].values()),
              'lower_bound_all': all(g['check_lower_bound'] for r in recs for g in r['groups'].values())}
    valid = checks['self_splice_dEV_max_abs'] == 0 and checks['dEV_vs_gapdiff_max'] <= 1e-12 and checks['BR_value_max'] <= 1e-12 and checks['lower_bound_all']
    nb = len(D['boot'])
    table = {}
    for gname in GROUPS:
        row = {'terminal': TERMINAL_OF[gname]}
        for tag in ('sigma72->G144', 'sigma144->G72'):
            pt = D['points'][tag]['groups'][gname]
            bs = [b[tag]['groups'][gname] for b in D['boot'].values()]
            row[tag] = {'point_dEV': pt['dEV'], 'point_positive_loss': pt['positive_loss'], 'point_own_gap': pt['own_gap'],
                        'point_L1': pt['L1'],
                        'boot_dEV_mean': sum(x['dEV'] for x in bs) / len(bs), 'boot_positive_loss_q95': q95([x['positive_loss'] for x in bs]),
                        'boot_excess_over_own_gap_q95': q95([x['positive_loss'] - x['own_gap'] for x in bs]),
                        'boot_own_gap_median': sorted(x['own_gap'] for x in bs)[len(bs) // 2],
                        'boot_L1_median': {nd: sorted(x['L1'][nd] for x in bs)[len(bs) // 2] for nd in pt['L1']},
                        'ratio_point_loss_to_B_post': pt['positive_loss'] / 0.0076}
        for tag in ('P15->G72', 'P15->G144'):
            pt = D['points'][tag]['groups'][gname]
            row[tag] = {'point_dEV': pt['dEV'], 'point_own_gap': pt['own_gap'], 'point_L1': pt['L1']}
        table[gname] = row
    # amendment 3: E_r = positive_loss_r - floor_r; whole-seat groups only (sub-seats diagnostic)
    q05 = lambda xs: sorted(xs)[min(len(xs) - 1, int(round(0.05 * (len(xs) - 1))))]
    seat_groups = ('CO', 'BTN', 'SB', 'BB')
    stab, sens = {}, {}
    for g in seat_groups:
        for t in ('sigma72->G144', 'sigma144->G72'):
            pt = D['points'][t]['groups'][g]
            E0 = pt['positive_loss'] - pt['own_gap']
            Er = [b[t]['groups'][g]['positive_loss'] - b[t]['groups'][g]['own_gap'] for b in D['boot'].values()]
            table[g][t].update({'E0': E0, 'E_q05': q05(Er), 'E_q95': q95(Er)})
            stab[(g, t)] = E0 <= 0 and q95(Er) <= 0
            sens[(g, t)] = E0 > 0 and q05(Er) > 0
    ev_stable = all(stab.values())
    ev_sensitive = any(sens.values())
    A4b = json.load(open(B + 'a4b_paired_analysis.json'))
    freq_unstable = bool(A4b['panel_detectable_shift']) or A4b['max_h144'] > 0.005
    usable = A4b['replicates_usable'] / max(1, A4b['replicates_planned'])
    if not valid or usable < 0.9 or nb < 0.9 * A4b['replicates_planned']:
        label = 'inconclusive'
    elif ev_sensitive:
        label = 'EV-sensitive to panel refinement'
    elif ev_stable:
        label = 'frequency-unstable but EV-stable' if freq_unstable else 'stable at 144 in frequency and EV'
    else:
        label = 'still precision-limited'
    nash = {t: {'A_in_G': D['points'][t]['nashconv_A_in_G'], 'own': D['points'][t]['nashconv_own']} for t in D['points']}
    res = {'rule': 'amendment 3 (E_r = positive_loss_r - own gap; stable: E0 <= 0 and q95 <= 0 for all whole seats and directions; sensitive: E0 > 0 and q05 > 0 for some)',
           'sensitive_seat_directions': [f'{g} {t}' for (g, t), v in sens.items() if v],
           'stable_seat_directions': [f'{g} {t}' for (g, t), v in stab.items() if v],
           'sub_seat_groups_diagnostic_only': ['BB|SB-open', 'BB|BTN-open'],
           'validations': checks, 'validations_pass': valid, 'boot_pairs': nb, 'EV_stable': ev_stable, 'EV_sensitive': ev_sensitive,
           'frequency_unstable': freq_unstable, 'frequency_basis': {'panel_detectable_shift': A4b['panel_detectable_shift'], 'max_h144': A4b['max_h144']},
           'label': label, 'nashconv_points': nash, 'B_post_reference_bb_per_hand': 0.0076,
           'wording': "losses are compared with the residual suboptimality of the baseline preflop solve (own gap); B_post is a different error source and a scale only",
           'limitation': 'frozen-table game at the P14 ranges; range-dependence of continuation values under a changed policy is not measured',
           'groups': table}
    json.dump(res, open(OUT + 'a4r_analysis.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'groups'}, indent=1))
    for g, row in table.items():
        for t in ('sigma72->G144', 'sigma144->G72'):
            r = row[t]
            print(f"{g:12s} {t:14s} dEV={r['point_dEV']:+.6f} own_gap={r['point_own_gap']:.6f} boot_q95_loss={r['boot_positive_loss_q95']:.6f} "
                  f"E0={r.get('E0', float('nan')):+.6f} E_q05={r.get('E_q05', float('nan')):+.6f} E_q95={r.get('E_q95', float('nan')):+.6f} L1={ {k: round(v, 3) for k, v in r['point_L1'].items()} }")
        print(f"{'':12s} P15->G72 dEV={row['P15->G72']['point_dEV']:+.6f}  P15->G144 dEV={row['P15->G144']['point_dEV']:+.6f}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'analyze'])
    ap.add_argument('--png', default=os.path.join(ROOT, 'docs/GTO_TERMINAL_A4R_ROBUST_V2.png'))
    a = ap.parse_args()
    run(a) if a.cmd == 'run' else analyze(a)
