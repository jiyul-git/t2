#!/usr/bin/env python3
"""30bb 9-max solver vs reference discrepancy audit (v1). Read-only: no solver code or DB value is changed.

    python3 tools/gto_validation/audit_30bb_solver_reference.py

Inputs (existing artifacts only, plus the small A/B results file if present):
  data/gto_9max_solver_pilot_30bb.json            GTOpen 9-max 30bb pilot (static realization, 20 iterations)
  data/gto_9max_solver_pilot_30bb_ensemble.json   2/8 runs of a 100-iteration static / balanced ensemble
  origin/chatgpt/gto-reference-20260928:data/gto_db/external_rfi_crosscheck_9max.json   PreflopRanges 9-max aggregate RFI (manual)
  origin/chatgpt/gto-reference-20260928:data/gto_public/8max_mtt_matthiola.jsonl         Matthiola 8-max MTT per-hand charts (MIT)
  data/gto_terminal_expansion/terminals/p0_node*.json, a4c/points/Gext/terminal_node*.json   4-handed 30bb static vs solved continuation
  data/gto_validation/ab_small_v1.json (optional)  same-engine small A/B solves
Output: data/gto_validation/30bb_solver_reference_audit_v1.json (+ .md written by the companion renderer in this file)
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF_BRANCH = 'origin/chatgpt/gto-reference-20260928'
OUT = os.path.join(ROOT, 'data/gto_validation/')
RANKS = '23456789TJQKA'
POS9 = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']
# Matthiola 8-max node for each 9-max opener, by distance from the button (9-max UTG has no 8-max twin: nearest = 8-max UTG)
M8 = {'UTG': 'UTG', 'UTG+1': 'UTG', 'UTG+2': 'UTG1', 'LJ': 'LJ', 'HJ': 'HJ', 'CO': 'CO', 'BTN': 'BTN', 'SB': 'SB'}
M8_EXACT_DISTANCE = {'UTG': False, 'UTG+1': True, 'UTG+2': True, 'LJ': True, 'HJ': True, 'CO': True, 'BTN': True, 'SB': True}
FOCUS_POS = ['UTG', 'HJ', 'CO', 'BTN']
FOCUS_HANDS = ['A5s', 'K9s', 'KQo', '22', '55', '98s', 'AKo']


def git_show(path):
    return subprocess.run(['git', '-C', ROOT, 'show', f'{REF_BRANCH}:{path}'], check=True, capture_output=True, text=True).stdout


def combos(h):
    return 6 if len(h) == 2 else (4 if h[2] == 's' else 12)


def family(h):
    a, b = RANKS.index(h[0]), RANKS.index(h[1])
    hi, lo = max(a, b), min(a, b)
    if len(h) == 2:
        return 'pocket pair'
    s = h[2] == 's'
    H, L = RANKS[hi], RANKS[lo]
    if s:
        if H == 'A':
            return 'suited Ax'
        if H in 'KQ':
            return 'suited Kx/Qx'
        if hi - lo <= 3:
            return 'suited connectors/gappers'
        return 'other suited'
    if lo >= RANKS.index('T'):
        return 'offsuit broadway'
    if H in 'AK':
        return 'offsuit Ax/Kx'
    return 'other offsuit'


FAMILIES = ['pocket pair', 'suited Ax', 'suited Kx/Qx', 'suited connectors/gappers', 'offsuit broadway', 'offsuit Ax/Kx', 'other suited', 'other offsuit']


def load():
    pilot = json.load(open(os.path.join(ROOT, 'data/gto_9max_solver_pilot_30bb.json')))
    ens = json.load(open(os.path.join(ROOT, 'data/gto_9max_solver_pilot_30bb_ensemble.json')))
    ext = json.loads(git_show('data/gto_db/external_rfi_crosscheck_9max.json'))
    mrows = [json.loads(l) for l in git_show('data/gto_public/8max_mtt_matthiola.jsonl').splitlines() if l.strip()]
    m30 = {}
    for r in mrows:
        if r['stack_bb'] == 30:
            m30.setdefault((r['scenario'], r['node']), {})[r['hand']] = r
    return pilot, ens, ext, m30


def solver_rfi(pilot):
    out = {}
    for s in pilot['spots']:
        if s.get('spot_type') == 'rfi':
            out[s['position']] = {h: {'fold': v.get('fold', 0.0), 'raise': sum(x for k, x in v.items() if k.startswith('raise')),
                                      'jam': sum(x for k, x in v.items() if k.startswith('jam')), 'call': sum(x for k, x in v.items() if k.startswith('call'))}
                                  for h, v in s['hands'].items()}
    return out


def solver_face(pilot, opener, defender):
    for s in pilot['spots']:
        if s.get('spot_type') == 'face_open' and s.get('opener') == opener and s.get('defender') == defender:
            return {h: {'fold': v.get('fold', 0.0), 'call': sum(x for k, x in v.items() if k.startswith('call')),
                        'raise': sum(x for k, x in v.items() if k.startswith('raise')), 'jam': sum(x for k, x in v.items() if k.startswith('jam'))}
                    for h, v in s['hands'].items()}
    return None


def ref_open(r):
    return r['raise'] + r['allin']


def comparability(pilot, ens, ext):
    cfg = pilot['config']
    solver = {'source': 'GTOpen 9-max 30bb pilot (data/gto_9max_solver_pilot_30bb.json)', 'table_size': 9,
              'stack': f"cfg.stack {cfg['stack']} bb after the ante -> hand-start {cfg['stack'] + cfg['ante']:.4f} bb",
              'ante': f"uniform {cfg['ante']:.4f} bb x 9 (total 1 bb), paid outside cfg.stack", 'open_size': '2.0 bb (SB 2.5)',
              'raise_tree': f"3bet = 3x (blinds 4x), fourbet_mults {cfg['fourbet_mults']} unreachable at max_raises {cfg['max_raises']}",
              'limp': cfg['limp'], 'jam': f"add_allin {cfg['add_allin']}, allin_threshold {cfg['allin_threshold']}",
              'max_raise_depth': f"{cfg['max_raises']} (open + one re-raise; no 4bet)", 'icm_rake': 'chip EV, rake 0',
              'postflop': f"no postflop tree: pot-share terminal payoff, realization '{cfg['realization']}' (class-independent), multiway coupled_deck_v1",
              'convergence': f"{pilot['solver']['status']['iteration']} iterations, gap_total {pilot['solver']['status']['gap_total']:.3f} bb (target 0.5)"}
    refs = [
        {'source': 'PreflopRanges public MTT 9-max 30bb chart (manual aggregate, external_rfi_crosscheck_9max.json)', 'table_size': 9, 'stack': '30 bb',
         'ante': 'chart-specific MTT ante, not recorded', 'open_size': '2.0 bb (SB 3.5)', 'raise_tree': 'not recorded', 'limp': 'unknown (SB RFI 89.4% suggests limps included)',
         'jam': 'unknown', 'max_raise_depth': 'unknown', 'icm_rake': 'chip EV presumed, not recorded', 'granularity': 'aggregate RFI per position only',
         'class': 'near-reference', 'why_not_exact': ['ante model unknown', 'raise tree / 4bet depth unknown', 'SB open size and limp differ', 'no per-hand data']},
        {'source': 'Matthiola 8-max MTT 30bb charts (MIT, commit 9ef33a4)', 'table_size': 8, 'stack': '30 bb', 'ante': 'MTT ante, unspecified',
         'open_size': 'unspecified', 'raise_tree': 'unspecified', 'limp': 'call column present (SB limps)', 'jam': 'allin column present',
         'max_raise_depth': '3bet / 4bet nodes exist (EPopen-vs-IP3bet etc.)', 'icm_rake': 'unspecified', 'granularity': 'per hand, 7 RFI nodes + vs-open nodes',
         'class': 'near-reference', 'why_not_exact': ['8-max, not 9-max (positions mapped by distance from the button; 9-max UTG has no twin)', 'ante / sizes unspecified', 'origin of the charts (solver vs hand-built) not documented']},
        {'source': 'GTOpen 4-handed 30bb (CO/BTN/SB/BB), same engine, P0 static payoff vs A4c solved flop continuation at nodes 6 / 28', 'table_size': 4,
         'stack': '30 bb after a 0.25 ante (30.25 hand-start)', 'ante': '0.25 x 4', 'open_size': '2.0 (SB 2.5)', 'raise_tree': '3x / 3.5x, 4bet 2.2x', 'limp': False,
         'jam': 'add_allin, 0.85', 'max_raise_depth': 4, 'icm_rake': 'chip EV, rake 0', 'granularity': 'per class, converged (400 iterations, gap 3e-4)',
         'class': 'internal same-engine comparator (not a reference)', 'why_not_exact': ['4-handed', 'different ante split and max_raises']},
    ]
    return {'solver': solver, 'references': refs, 'exact_comparable': [],
            'verdict': 'no exact-comparable reference exists locally; all comparisons below are near-reference and are labelled so'}


def main():
    pilot, ens, ext, m30 = load()
    srfi = solver_rfi(pilot)
    res = {'schema': 'solver_reference_audit_v1', 'stack_bb': 30, 'comparability': comparability(pilot, ens, ext)}
    # aggregate RFI
    agg = {}
    for p in POS9:
        s = sum(combos(h) * (v['raise'] + v['jam']) for h, v in srfi[p].items()) / 1326
        mn = M8[p]
        m = m30.get(('rfi', mn))
        mref = sum(combos(h) * ref_open(r) for h, r in m.items()) / 1326 if m else None
        agg[p] = {'solver': s, 'preflopranges_9max': ext['stacks']['30']['rfi'].get(p), 'matthiola_8max_mapped': mref, 'matthiola_node': mn,
                  'mapping_exact_distance': M8_EXACT_DISTANCE[p],
                  'ensemble_static_100it': ens['arms']['static']['rfi_all'].get(p, {}).get('mean'),
                  'ensemble_balanced_100it': ens['arms']['balanced']['rfi_all'].get(p, {}).get('mean')}
    res['aggregate_rfi'] = agg
    # family decomposition vs Matthiola (per hand) and jam share
    fam = {}
    for p in POS9:
        m = m30.get(('rfi', M8[p]))
        d = {f: {'combos': 0, 'solver_open': 0.0, 'ref_open': 0.0, 'solver_jam': 0.0, 'ref_jam': 0.0} for f in FAMILIES}
        for h, v in srfi[p].items():
            f = family(h)
            c = combos(h)
            d[f]['combos'] += c
            d[f]['solver_open'] += c * (v['raise'] + v['jam']) / 1326
            d[f]['solver_jam'] += c * v['jam'] / 1326
            if m and h in m:
                d[f]['ref_open'] += c * ref_open(m[h]) / 1326
                d[f]['ref_jam'] += c * m[h]['allin'] / 1326
        tot = sum(x['ref_open'] - x['solver_open'] for x in d.values())
        for f in d:
            d[f]['shortfall'] = d[f]['ref_open'] - d[f]['solver_open']
            d[f]['share_of_shortfall'] = d[f]['shortfall'] / tot if tot else None
        fam[p] = {'families': d, 'total_shortfall_vs_matthiola': tot}
    res['family_decomposition_vs_matthiola'] = fam
    # hand-level tables
    hl = {}
    for p in FOCUS_POS:
        m = m30.get(('rfi', M8[p]), {})
        allh = list(srfi[p])
        by_ref = sorted(allh, key=lambda h: (ref_open(m[h]) if h in m else -1))
        # picks from the near-reference: clear-open = ref >= 0.95 with the LOWEST solver open; boundary = ref in [0.25, 0.75]; clear-fold = ref <= 0.05 with the HIGHEST solver open
        so = lambda h: srfi[p][h]['raise'] + srfi[p][h]['jam']
        clear_open = sorted([h for h in allh if h in m and ref_open(m[h]) >= 0.95], key=so)[:3]
        boundary = sorted([h for h in allh if h in m and 0.25 <= ref_open(m[h]) <= 0.75], key=lambda h: abs(ref_open(m[h]) - 0.5))[:3]
        clear_fold = sorted([h for h in allh if h in m and ref_open(m[h]) <= 0.05], key=lambda h: -so(h))[:3]
        rows = []
        for tag, hs in (('focus', FOCUS_HANDS), ('clear_open_by_ref', clear_open), ('boundary_by_ref', boundary), ('clear_fold_by_ref', clear_fold)):
            for h in hs:
                v = srfi[p][h]
                r = m.get(h)
                modal = max(('fold', 'raise', 'jam'), key=lambda k: v[k])
                rows.append({'group': tag, 'hand': h, 'family': family(h), 'solver': {k: round(v[k], 4) for k in ('fold', 'call', 'raise', 'jam')},
                             'solver_modal': modal, 'action_ev': (res.get('_ev', {}).get(p, {}).get(h)),
                             'ref_matthiola_8max': ({k: r[k] for k in ('fold', 'call', 'raise', 'allin')} if r else None),
                             'diff_open_solver_minus_ref': (round(v['raise'] + v['jam'] - ref_open(r), 4) if r else None)})
        hl[p] = {'matthiola_node': M8[p], 'rows': rows}
    res['hand_level'] = hl
    # BB defence
    bbd = {}
    for op in ('CO', 'BTN', 'SB'):
        f = solver_face(pilot, op, 'BB')
        if not f:
            continue
        # range-weighted by the opener's solver range
        ow = {h: combos(h) * (srfi[op][h]['raise']) for h in srfi[op]}
        tw = sum(ow.values())
        unweighted_fold = sum(combos(h) * f[h]['fold'] for h in f) / 1326
        fams = {}
        for h in f:
            fams.setdefault(family(h), []).append((combos(h), f[h]['fold']))
        bbd[op] = {'bb_fold_unweighted': unweighted_fold, 'bb_fold_by_family': {k: sum(c * x for c, x in v) / sum(c for c, _ in v) for k, v in fams.items()},
                   'worst_hands_continue': sorted(((h, round(1 - f[h]['fold'], 3)) for h in ('72o', '82o', '92o', '32o', '42o', 'T2o', 'J3o')), key=lambda x: x[0])}
    mb = m30.get(('vs-open', 'BTN-vs-BB'))
    if mb:
        bbd['matthiola_8max_BB_vs_BTN_fold_unweighted'] = sum(combos(h) * r['fold'] for h, r in mb.items()) / 1326
        bbd['matthiola_8max_BB_vs_BTN_worst_hands_continue'] = sorted(((h, round(1 - mb[h]['fold'], 3)) for h in ('72o', '82o', '92o', '32o', '42o', 'T2o', 'J3o') if h in mb))
    # 4-handed same-engine evidence
    def mixes(f6, f28):
        out = {}
        for f in (f28, f6):
            for pn in json.load(open(os.path.join(ROOT, f)))['path_nodes']:
                out[f"{pn['actor']}@{pn['node']}"] = pn['mix']
        return out
    bbd['four_handed_same_engine'] = {
        'P0_static_payoff': mixes('data/gto_terminal_expansion/terminals/p0_node6.json', 'data/gto_terminal_expansion/terminals/p0_node28.json'),
        'A4c_solved_continuation_nodes_6_28': mixes('data/gto_terminal_expansion/a4c/points/Gext/terminal_node6.json', 'data/gto_terminal_expansion/a4c/points/Gext/terminal_node28.json'),
        'note': 'converged (400 iterations). BB@26 = BB vs BTN open, BB@4 = BB vs SB open; CO@0 terminals vs BB stay static in both'}
    res['bb_defence'] = bbd
    ab = os.path.join(ROOT, 'data/gto_validation/ab_small_v1.json')
    res['ab_small'] = json.load(open(ab)) if os.path.exists(ab) else None
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(OUT + '30bb_solver_reference_audit_v1.raw.json', 'w'), indent=1)
    print(json.dumps({'aggregate_rfi': agg}, indent=1)[:3000])
    for p in ('UTG', 'CO', 'BTN'):
        print(p, {f: (round(x['solver_open'] * 100, 2), round(x['ref_open'] * 100, 2), round(x['solver_jam'] * 100, 2), round(x['ref_jam'] * 100, 2)) for f, x in fam[p]['families'].items()})
    print(json.dumps({k: v for k, v in bbd.items() if k != 'four_handed_same_engine'}, indent=1)[:2500])


if __name__ == '__main__':
    main()
