#!/usr/bin/env python3
"""Assemble data/gto_validation/30bb_solver_reference_audit_v1.{json,md} from
  - 30bb_solver_reference_audit_v1.raw.json (audit_30bb_solver_reference.py: comparability, aggregates, families, hand rows, BB defence)
  - the 9-max reproduction runs (pilot config, 20 and 100 iterations; action EVs from path_nodes)
  - the 4-handed same-engine small A/B (realization raw, max_raises 2, no jam option)
Read-only with respect to solver code and DB values."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = os.path.join(ROOT, 'data/gto_validation/')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_30bb_solver_reference import family, combos, FOCUS_HANDS  # noqa: E402

LAB = json.load(open(os.path.join(ROOT, 'data/gto_terminal_expansion/terminals/p9_node6.json')))['class_labels']


def nodes(f):
    t = json.load(open(f))
    return t, {p['actor']: p for p in t['path_nodes']}


def ev_rows(pn, pos, hands):
    p = pn[pos]
    out = {}
    for h in hands:
        i = LAB.index(h)
        out[h] = {'actions': p['actions'], 'freq': [round(p['class_strategy'][k][i], 4) for k in range(len(p['actions']))],
                  'ev_bb': [round(p['ev_bb'][k][i], 4) for k in range(len(p['actions']))]}
    return out


def consistency(pn, pos):
    """share of combos whose most-frequent action is not the highest-EV action, and the combo-weighted regret (bb)."""
    p = pn[pos]
    na = len(p['actions'])
    mis = reg = tot = 0.0
    big = []
    for i, h in enumerate(LAB):
        c = combos(h)
        f = [p['class_strategy'][k][i] for k in range(na)]
        e = [p['ev_bb'][k][i] for k in range(na)]
        best = max(range(na), key=lambda k: e[k])
        modal = max(range(na), key=lambda k: f[k])
        r = max(e) - sum(f[k] * e[k] for k in range(na))
        tot += c
        reg += c * r
        if modal != best:
            mis += c
            big.append((h, round(r, 3), p['actions'][modal], p['actions'][best], round(e[best] - e[modal], 3)))
    big.sort(key=lambda x: -x[1])
    return {'modal_not_best_ev_combo_share': mis / tot, 'mean_class_regret_bb': reg / tot, 'top': big[:8]}


def rfi_of(pn, pos):
    p = pn[pos]
    a = p['actions']
    return sum(combos(h) * sum(p['class_strategy'][k][i] for k in range(len(a)) if a[k] != 'Fold') for i, h in enumerate(LAB)) / 1326


def vs_open_table():
    import subprocess
    rows = [json.loads(l) for l in subprocess.run(['git', '-C', ROOT, 'show', 'origin/chatgpt/gto-reference-20260928:data/gto_public/8max_mtt_matthiola.jsonl'],
                                                  capture_output=True, text=True, check=True).stdout.splitlines() if l.strip()]
    m = {}
    for r in rows:
        if r['stack_bb'] == 30 and r['scenario'] == 'vs-open':
            m.setdefault(r['node'], {})[r['hand']] = r
    ref = {n: {k: sum(combos(h) * r[k] for h, r in d.items()) / 1326 for k in ('allin', 'raise', 'call', 'fold')} for n, d in m.items()}
    p = json.load(open(os.path.join(ROOT, 'data/gto_9max_solver_pilot_30bb.json')))
    sol = {}
    for sp in p['spots']:
        if sp['spot_type'] == 'face_open':
            H = sp['hands']
            t = lambda pre: sum(combos(h) * sum(x for k, x in v.items() if k.startswith(pre)) for h, v in H.items()) / 1326
            sol[f"{sp['opener']}->{sp['defender']}"] = {'jam': t('jam'), 'raise': t('raise'), 'call': t('call'), 'fold': t('fold')}
    pairs = [('EP-vs-MP', ['UTG->UTG+2', 'UTG->LJ']), ('EP-vs-BTN', ['UTG->BTN', 'UTG+1->BTN']), ('EP-vs-SB', ['UTG->SB', 'UTG+1->SB']), ('EP-vs-BB', ['UTG->BB', 'UTG+1->BB']),
             ('MP-vs-BTN', ['LJ->BTN', 'HJ->BTN']), ('MP-vs-SB', ['LJ->SB', 'HJ->SB']), ('MP-vs-BB', ['LJ->BB', 'HJ->BB']), ('BTN-vs-SB', ['BTN->SB']), ('BTN-vs-BB', ['BTN->BB']),
             ('SB-vs-BB', ['SB->BB'])]
    out = []
    for rn, sl in pairs:
        for x in sl:
            if x in sol and rn in ref:
                out.append({'ref_node_8max': rn, 'solver_spot_9max': x, 'ref': ref[rn], 'solver': sol[x]})
    return {'mapping': 'Matthiola 8-max EP = 9-max UTG / UTG+1, MP = LJ / HJ; combo-weighted shares of all 1326 combos; near-reference only', 'rows': out}


def attribution(res):
    ab = res['ab_small_4handed']['arms']
    g = lambda arm, k: ab.get(arm, {}).get(k)
    rep = res['reproduction_9max']['runs']
    r20 = rep.get(20) or rep.get('20') or {}
    r100 = rep.get(100) or rep.get('100') or {}
    bb = res['bb_defence']
    ev72 = (r20.get('ev_focus', {}).get('BB', {}).get('72o') or {}).get('ev_bb')
    def d(a, b):
        return None if a is None or b is None else a - b
    out = [
        {'candidate': 'realization model (static: pot x equity x r, r = 1 +- 0.08 by seat order, identical for every hand class)',
         'evidence': (f"BB vs BTN: 72o call EV {ev72[1]:+.3f} vs fold {ev72[0]:+.3f} bb (raw equity realized in full OOP); solver BB folds {pct(bb['BTN']['bb_fold_unweighted'])} vs Matthiola {pct(bb.get('matthiola_8max_BB_vs_BTN_fold_unweighted'))}; "
                      if ev72 else '') + f"removing only the positional skew (raw) moves CO / BTN RFI by {100 * d(g('raw_realization', 'CO_rfi'), g('base_static_mr4', 'CO_rfi')):+.1f} / {100 * d(g('raw_realization', 'BTN_rfi'), g('base_static_mr4', 'BTN_rfi')):+.1f} pp (skew is not the driver; the class-independence is); "
                      "shortfall concentrates in playability families (suited Kx/Qx, suited connectors) whose value a raw-equity payoff cannot express",
         'verdict': 'solver/model mismatch (strong)'},
        {'candidate': 'preflop terminal value (pot-share payoff at every flop-reaching terminal)',
         'evidence': f"4-handed same engine: replacing the payoff at only the two HU terminals 6 / 28 with solved flop values raises BTN RFI {pct(g('base_static_mr4', 'BTN_rfi'))} -> {pct(g('A4c_solved_continuation_nodes_6_28', 'BTN_rfi'))} and BB vs BTN fold 0% -> {pct(g('A4c_solved_continuation_nodes_6_28', 'BB_vs_BTN_fold'))}; CO RFI unchanged ({pct(g('A4c_solved_continuation_nodes_6_28', 'CO_rfi'))}) because CO's terminals stayed static",
         'verdict': 'solver/model mismatch (strong; same mechanism as the realization model)'},
        {'candidate': 'opponent defence saturation (BB continues ~99%)',
         'evidence': f"present in the current 30bb 9-max artifact: BB vs CO fold {pct(bb['CO']['bb_fold_unweighted'])}, vs BTN {pct(bb['BTN']['bb_fold_unweighted'])}; 72o/82o/92o continue >= 95% (Matthiola folds them 100%); when BB starts folding (solved continuation) the BTN opens more; this is the channel through which the payoff model makes openers tight -> the old 'BB never folds' finding and today's low RFI are the same problem",
         'verdict': 'solver/model mismatch (strong, mechanism)'},
        {'candidate': 'multiway continuation / payoff approximation (coupled_deck_v1 raw equity)',
         'evidence': 'not isolated by an A/B here; it shares the class-independent raw-equity payoff, so speculative hands get no multiway playability premium; no near-reference covers multiway pots',
         'verdict': 'both/uncertain (leaning solver)'},
        {'candidate': 'action abstraction / sizing',
         'evidence': 'non-SB opens are 2.0 bb in solver and both references; the SB tree differs (2.5 bb, no limp vs 3.5 bb / limps) so SB is excluded; 3-bet sizes of the references are not recorded',
         'verdict': 'uncertain (minor for UTG-BTN; decisive only for SB comparability)'},
        {'candidate': 'max_raises (pilot uses 2: open + one re-raise, no 4-bet)',
         'evidence': f"4-handed A/B max_raises 4 -> 2: CO / BTN RFI {100 * d(g('max_raises_2', 'CO_rfi'), g('base_static_mr4', 'CO_rfi')):+.1f} / {100 * d(g('max_raises_2', 'BTN_rfi'), g('base_static_mr4', 'BTN_rfi')):+.1f} pp; 9-max has more players behind, so the 9-max effect may be somewhat larger but is not of the 10 pp order",
         'verdict': 'solver abstraction, small contributor'},
        {'candidate': 'all-in threshold / jam availability',
         'evidence': (f"4-handed A/B without any jam option: CO / BTN RFI {pct(g('no_jam_option', 'CO_rfi'))} / {pct(g('no_jam_option', 'BTN_rfi'))} (base {pct(g('base_static_mr4', 'CO_rfi'))} / {pct(g('base_static_mr4', 'BTN_rfi'))}) -> the reshove structure is a large lever on RFI; "
                      if g('no_jam_option', 'CO_rfi') is not None else '')
                     + "but the solver's 3-bet-jam frequencies are close to the near-reference (BB vs BTN jam 8.1% vs Matthiola 8.6%; SB vs BTN 8.9% vs 11.8%), early-position cold jams are somewhat higher (2-6% vs 0-4%); removing jams is not T2 play. Open-jams by the opener (BTN 22 / 98s / 55) are a symptom of the 2 bb raise getting no folds",
         'verdict': 'structural lever, not the miscalibration (reshove rates near reference); opener jam overuse = symptom of the payoff model'},
        {'candidate': 'over-calling by SB / BB / BTN (passive continuation value)',
         'evidence': 'vs-open table: SB flats 32-37% of combos vs EP/MP opens (Matthiola 13-14%); BB folds 1-3% vs MP opens (Matthiola 17%) and 10% / 2% vs UTG / UTG+1 (Matthiola EP 24%); BTN cold-calls only 2-6% (Matthiola 14%) but 3-bets more; flat calls are valued by raw-equity realization, so blinds over-call and pots go multiway against the opener',
         'verdict': 'solver/model mismatch (strong; this is how the payoff model reaches the opener)'},
        {'candidate': 'convergence (pilot: 20 iterations, gap_total 0.31 bb)',
         'evidence': (f"20 it: modal action != best-EV action for {100 * r20['consistency']['UTG']['modal_not_best_ev_combo_share']:.1f}% (UTG) - {100 * max(c['modal_not_best_ev_combo_share'] for c in r20['consistency'].values()):.1f}% of combos (e.g. UTG KQo raise EV beats fold by 0.11 bb but folds 66%); " if r20 else '')
                     + (f"100 it: RFI UTG {pct(r100['rfi']['UTG'])}, BTN {pct(r100['rfi']['BTN'])} (20 it: {pct(r20['rfi']['UTG'])}, {pct(r20['rfi']['BTN'])}); " if r100 else '')
                     + 'ensemble static 100 it gives the same aggregate RFI -> convergence adds hand-level noise but does not explain the aggregate gap',
         'verdict': 'solver issue at hand level; not the aggregate cause'},
        {'candidate': 'reference side (conditions / provenance)',
         'evidence': 'two independent near-references agree on aggregate RFI (UTG+1 18.6 vs 18.5, CO 37.5 vs 36.3, BTN 48.7 vs 48.7); neither records the ante model or raise tree; Matthiola is 8-max; no exact-comparable reference exists locally; a larger chart ante (e.g. 12.5% = 1.125 bb) would widen the reference somewhat',
         'verdict': 'reference mismatch possible for part of the gap; not the main cause'},
    ]
    return out


STACK_SEMANTICS = {
    'GTOpen semantics': 'cfg.stack is the stack AFTER the ante (behind = stack - invested + ante); hand-start stack S needs cfg.stack = S - ante',
    '30bb (44 spots in the Termux branch)': 'imported from the 9-max pilot: cfg.stack 30, ante 1/9 -> actual hand-start stack 30.1111 bb (each seat paid 1/9 from outside the 30); state metadata says prehand_bb 30 and target "T2 1BB BBA"; realization static, 20 iterations, gap_total 0.309 bb',
    '25bb (added in 9730a5f, removed in 355f033)': 'worker cfg_for(25): cfg.stack 25, ante 1/9, realization balanced, 40 iterations, gap_total 0.085 -> hand-start 25.1111 bb; no longer on the branch',
    '20 / 40bb': 'not present on origin/chatgpt/gto-db-worker-v1-20261003 (head 355f033); if produced by cfg_for they are 20.1111 / 40.1111 bb hand-start',
    'ante model actually solved': 'uniform 1/9 bb per seat (9 x 1/9 = 1 bb) = the new T2 uniform_total rule in structure, but at a stack 1/9 bb deeper than labelled; it is NOT the 1 bb big-blind ante the metadata names',
    'migration proposal': 'do not delete or overwrite; import with canonical_state = what was solved (hand_start_players 9, stacks 30.1111, ante uniform_total 1 bb) as its own sk1 spot, tier 3, with a provenance note and a link to the nominal 30 bb target spot; the 30 bb sk1 spot stays empty until an exact solve exists (lookup may offer the 30.1111 solution only as a declared near match)',
    're-solve needed?': 'yes eventually for exact 20/25/30/40 bb (cfg.stack = S - 1/9), but only after the payoff-model issue is addressed; re-solving with the current static model would reproduce the same bias at a 0.11 bb different stack, which matters far less than the model',
}

PROPOSALS = [
    'Do not promote the 30bb pilot or the Termux spots beyond tier 3 / unassessed; record the stack-semantics correction in their provenance before migration.',
    'Primary fix to evaluate: replace the class-independent pot-share payoff at the dominant flop-reaching terminals (BB vs CO / BTN / SB SRPs) with solved continuation values (A4c-style panels) or a class-dependent realization fit; A4c already shows the direction (BTN +3.8 pp, BB starts folding).',
    'Check the calibrated ("balanced") realization before relying on it: the existing ensemble balanced arm was tighter, not looser (MAE 10.3% vs 8.9%), and its fit file (cache/realization_fit.json) is not present in this checkout.',
    'Convergence gate for any stored frequency: >= 100 iterations and a per-seat gap target well below the marginal EV gaps (e.g. gap_total <= 0.02 bb), plus the hand_records_v1 status fields.',
    'Use max_raises >= 3 for stored 9-max trees (small effect, but the no-4bet tree is not T2 play).',
    'Acquire one exact-comparable reference (known 9-max, 30 bb, ante model, open / 3-bet sizes, raise depth) before any re-calibration; until then all reference comparisons stay near-reference.',
    'Only after the payoff model is fixed: exact 20/25/30/40 bb re-solves with cfg.stack = S - 1/9 and hand_start_players in the key.',
]


def main():
    raw = json.load(open(V + '30bb_solver_reference_audit_v1.raw.json'))
    S = '/tmp/claude-0/-home-user-t2/0f5a154b-8ae8-5a6f-a261-583af56cff70/scratchpad/'
    res = {k: v for k, v in raw.items() if k != 'ab_small'}
    # 9-max reproduction (20 and 100 iterations, identical config)
    rep = {}
    for it, f in ((20, S + 'audit9/t_btn20.json'), (100, S + 'audit9/t_btn100.json')):
        if not os.path.exists(f):
            continue
        t, pn = nodes(f)
        rep[it] = {'gap_total': t['gap_total'], 'rfi': {p: rfi_of(pn, p) for p in ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN')},
                   'bb_vs_btn': pn['BB']['mix'], 'consistency': {p: consistency(pn, p) for p in ('UTG', 'HJ', 'CO', 'BTN', 'BB')},
                   'ev_focus': {p: ev_rows(pn, p, FOCUS_HANDS + ['72o', 'T7s', 'Q9o']) for p in ('UTG', 'HJ', 'CO', 'BTN', 'BB')}}
    res['reproduction_9max'] = {'config': 'data/gto_9max_solver_pilot_30bb.json config, t2_cont_terminal path BTN open / BB call, seeds 202', 'runs': rep}
    # attach action EVs (20-iteration reproduction) to the hand rows
    if 20 in rep:
        for pos, blk in res['hand_level'].items():
            t, pn = nodes(S + 'audit9/t_btn20.json')
            for r in blk['rows']:
                r['action_ev_reproduction20'] = ev_rows(pn, pos, [r['hand']])[r['hand']]
    # 4-handed A/B
    ab = {}
    for v in ('base_static_mr4', 'raw_realization', 'max_raises_2', 'no_jam_option', 'mr2_no_jam'):
        f28, f6 = S + f'ab4/{v}_n28.json', S + f'ab4/{v}_n6.json'
        if not (os.path.exists(f28) and os.path.exists(f6)):
            continue
        _, p28 = nodes(f28)
        _, p6 = nodes(f6)
        ab[v] = {'CO_rfi': rfi_of(p28, 'CO'), 'BTN_rfi': rfi_of(p28, 'BTN'), 'CO_jam': p28['CO']['mix'].get('All-in 30', 0.0), 'BTN_jam': p28['BTN']['mix'].get('All-in 30', 0.0),
                 'SB_rfi': rfi_of(p6, 'SB'), 'BB_vs_BTN_fold': p28['BB']['mix'].get('Fold'), 'BB_vs_SB_fold': p6['BB']['mix'].get('Fold'),
                 'BB_vs_BTN': p28['BB']['mix']}
    ab['A4c_solved_continuation_nodes_6_28'] = {
        'CO_rfi': 1 - raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['CO@0']['Fold'],
        'BTN_rfi': 1 - raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['BTN@1']['Fold'],
        'BB_vs_BTN_fold': raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['BB@26']['Fold'],
        'BB_vs_SB_fold': raw['bb_defence']['four_handed_same_engine']['A4c_solved_continuation_nodes_6_28']['BB@4']['Fold']}
    res['ab_small_4handed'] = {'engine': 'same GTOpen preflop engine, 4-handed CO/BTN/SB/BB 30bb (cfg_4h_mr4_30bb), 400 iterations, one factor changed per arm', 'arms': ab}
    res['vs_open_comparison'] = vs_open_table()
    res['attribution'] = attribution(res)
    res['stack_semantics'] = STACK_SEMANTICS
    res['proposals'] = PROPOSALS
    json.dump(res, open(V + '30bb_solver_reference_audit_v1.json', 'w'), indent=1)
    open(V + '30bb_solver_reference_audit_v1.md', 'w').write(render_md(res))
    print(json.dumps({'reproduction': {it: {'gap': r['gap_total'], 'rfi': {k: round(x, 3) for k, x in r['rfi'].items()}, 'bb_vs_btn': {k: round(x, 3) for k, x in r['bb_vs_btn'].items()},
                                             'consistency': {p: (round(c['modal_not_best_ev_combo_share'], 3), round(c['mean_class_regret_bb'], 4)) for p, c in r['consistency'].items()}} for it, r in rep.items()},
                      'ab': {k: {x: (round(y, 3) if isinstance(y, float) else y) for x, y in v.items() if x != 'BB_vs_BTN'} for k, v in ab.items()}}, indent=1))



def pct(x):
    return '—' if x is None else f'{100 * x:.1f}%'


def render_md(res):
    L = []
    w = L.append
    w('# 30bb 9-max solver vs reference audit v1')
    w('')
    w('Read-only audit. No solver code or DB value was changed. Machine-readable: `30bb_solver_reference_audit_v1.json`.')
    w('')
    w('## 1. Comparability')
    c = res['comparability']
    w(f"**Verdict:** {c['verdict']}.")
    w('')
    w('| | table | stack | ante | open | raise tree | limp | jam | max raises | ICM/rake | granularity | class |')
    w('|---|---|---|---|---|---|---|---|---|---|---|---|')
    s = c['solver']
    w(f"| solver pilot | 9 | {s['stack']} | {s['ante']} | {s['open_size']} | {s['raise_tree']} | {s['limp']} | {s['jam']} | {s['max_raise_depth']} | {s['icm_rake']} | per hand (no EV stored) | solver |")
    for r in c['references']:
        w(f"| {r['source']} | {r['table_size']} | {r['stack']} | {r['ante']} | {r['open_size']} | {r['raise_tree']} | {r['limp']} | {r['jam']} | {r['max_raise_depth']} | {r['icm_rake']} | {r['granularity']} | {r['class']} |")
    w('')
    w(f"Solver postflop model: {s['postflop']}. Convergence: {s['convergence']}.")
    w('')
    w('## 2. Aggregate RFI')
    w('| position | solver pilot | reproduction 20 it | reproduction 100 it | ensemble static 100 it | PreflopRanges 9-max | Matthiola 8-max (mapped) |')
    w('|---|---|---|---|---|---|---|')
    rep = res['reproduction_9max']['runs']
    for p, a in res['aggregate_rfi'].items():
        r20 = rep.get('20', rep.get(20, {})).get('rfi', {}).get(p) if rep else None
        r100 = (rep.get('100') or rep.get(100) or {}).get('rfi', {}).get(p)
        w(f"| {p} | {pct(a['solver'])} | {pct(r20)} | {pct(r100)} | {pct(a['ensemble_static_100it'])} | {pct(a['preflopranges_9max'])} | {pct(a['matthiola_8max_mapped'])}{'' if a['mapping_exact_distance'] else ' (nearest node)'} |")
    w('')
    w('SB is not comparable (references include limps / 3.5bb opens; the solver has no limp and opens 2.5bb).')
    w('')
    w('## 3. RFI shortfall by hand family (vs Matthiola 8-max, combo-weighted, % of 1326)')
    fam = res['family_decomposition_vs_matthiola']
    fams = list(next(iter(fam.values()))['families'])
    w('| position | ' + ' | '.join(fams) + ' | total |')
    w('|---|' + '---|' * (len(fams) + 1))
    for p in ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN'):
        d = fam[p]['families']
        w(f'| {p} | ' + ' | '.join(f"{100 * d[f]['shortfall']:+.2f}" for f in fams) + f" | {100 * fam[p]['total_shortfall_vs_matthiola']:+.2f} |")
    w('')
    w('Solver jam share of all combos (reference jam share is 0 in every family at 30bb):')
    w('| position | ' + ' | '.join(fams) + ' |')
    w('|---|' + '---|' * len(fams))
    for p in ('UTG', 'HJ', 'CO', 'BTN'):
        d = fam[p]['families']
        w(f'| {p} | ' + ' | '.join(f"{100 * d[f]['solver_jam']:.2f}" for f in fams) + ' |')
    w('')
    w('## 4. Hand level (UTG / HJ / CO / BTN)')
    w('Solver = pilot artifact; EV = 20-iteration reproduction of the same config (bb, net, per action in the order shown); ref = Matthiola 8-max mapped node.')
    for p, blk in res['hand_level'].items():
        w('')
        w(f"### {p} (Matthiola node {blk['matthiola_node']})")
        w('| group | hand | family | fold | raise | jam | modal | EV fold / raise / jam | ref fold / raise / allin / call | open diff |')
        w('|---|---|---|---|---|---|---|---|---|---|')
        for r in blk['rows']:
            ev = r.get('action_ev_reproduction20', {}).get('ev_bb')
            rf = r['ref_matthiola_8max']
            ev_s = ' / '.join(f'{x:+.3f}' for x in ev) if ev else '—'
            rf_s = f"{rf['fold']:.2f} / {rf['raise']:.2f} / {rf['allin']:.2f} / {rf['call']:.2f}" if rf else '—'
            d = r['diff_open_solver_minus_ref']
            d_s = '—' if d is None else f'{d:+.2f}'
            so = r['solver']
            w(f"| {r['group']} | {r['hand']} | {r['family']} | {so['fold']:.2f} | {so['raise']:.2f} | {so['jam']:.2f} | {r['solver_modal']} | {ev_s} | {rf_s} | {d_s} |")
    w('')
    w('## 5. BB defence (the link to RFI)')
    b = res['bb_defence']
    for op in ('CO', 'BTN', 'SB'):
        if op in b:
            w(f"- solver BB vs {op} open: fold {pct(b[op]['bb_fold_unweighted'])} of all combos; trash continue rates {b[op]['worst_hands_continue']}")
    w(f"- Matthiola 8-max BB vs BTN: fold {pct(b.get('matthiola_8max_BB_vs_BTN_fold_unweighted'))}; same trash {b.get('matthiola_8max_BB_vs_BTN_worst_hands_continue')}")
    w('')
    w('## 5b. Facing an open: solver 9-max vs Matthiola 8-max (combo share jam / 3-bet / call / fold)')
    w('| ref node | solver spot | ref allin / raise / call / fold | solver jam / 3-bet / call / fold |')
    w('|---|---|---|---|')
    for r in res['vs_open_comparison']['rows']:
        a, b = r['ref'], r['solver']
        w(f"| {r['ref_node_8max']} | {r['solver_spot_9max']} | {100 * a['allin']:.1f} / {100 * a['raise']:.1f} / {100 * a['call']:.1f} / {100 * a['fold']:.1f} | {100 * b['jam']:.1f} / {100 * b['raise']:.1f} / {100 * b['call']:.1f} / {100 * b['fold']:.1f} |")
    w('')
    w('## 6. Small same-engine A/B (4-handed 30bb, 400 iterations, one factor per arm)')
    w('| arm | CO RFI | BTN RFI | BTN jam | SB RFI | BB vs BTN fold | BB vs SB fold |')
    w('|---|---|---|---|---|---|---|')
    for k, a in res['ab_small_4handed']['arms'].items():
        w(f"| {k} | {pct(a.get('CO_rfi'))} | {pct(a.get('BTN_rfi'))} | {pct(a.get('BTN_jam'))} | {pct(a.get('SB_rfi'))} | {pct(a.get('BB_vs_BTN_fold'))} | {pct(a.get('BB_vs_SB_fold'))} |")
    w('')
    w('## 7. Convergence')
    for it, r in sorted(rep.items(), key=lambda x: int(x[0])):
        w(f"- {it} iterations: gap_total {r['gap_total']:.3f} bb; share of combos whose most-frequent action is not the best-EV action / mean class regret (bb): "
          + ', '.join(f"{p} {100 * c['modal_not_best_ev_combo_share']:.1f}% / {c['mean_class_regret_bb']:.4f}" for p, c in r['consistency'].items()))
    w('')
    w('## 8. Attribution (where the evidence points)')
    w('| candidate | evidence | leaning |')
    w('|---|---|---|')
    for a in res['attribution']:
        w(f"| {a['candidate']} | {a['evidence']} | **{a['verdict']}** |")
    w('')
    w('## 9. Termux / GTOpen stack semantics')
    for k, v in res['stack_semantics'].items():
        w(f'- **{k}:** {v}')
    w('')
    w('## 10. Fix proposals (not applied)')
    for x in res['proposals']:
        w(f'- {x}')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    main()
