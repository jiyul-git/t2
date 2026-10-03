#!/usr/bin/env python3
"""Human Model v2 targeted verifier — GTO memory confidence + invariants A..G.

  python3 tools/verify_human_model_v2.py [--data 8max_mtt_matthiola.jsonl] [--out result.json]

What it checks (every threshold below is either structural — equality, ordering,
monotonicity, existence — or a comparison against the current code; no new tuned
number decides PASS/FAIL):

  IDENT  flag OFF: fixture fingerprints equal test@1a23123 (bit-identical default)
  A      neutral/high-GTO player stays near the source prior
           A1 open width: neutral temper, pf_range 10 -> equals reference except the
              existing positional-flattening term (reported)
           A2 defense: neutral pf_defend 10 vs public source charts (needs --data):
              continue probability on all-stack pure-fold hands (reported; a FAIL here is
              a prior-layer finding, not a persona finding)
  B      persona moves boundary hands more than far hands (same knowledge)
  C      persona does not invert clear dominance: for every persona the continue
         probability of source pure-fold hands stays below that of source
         pure-continue hands (ordering), plus absolute levels reported
  D      read evidence 0 -> exploit adjustment exactly 0
  E      evidence up -> exploit weight monotone non-decreasing, no step larger than
         the formula's own n/12 ramp step
  F      same GTO knowledge, different reasoning/persona: population quadrants exist
  G      same reasoning, different GTO knowledge: population quadrants exist
  MATCH  gto_condition_match: 1.0 inside studied conditions, <1 outside, in [0,1]
  ATTR   flag ON vs OFF runtime fixtures (separate processes): VPIP/PFR/flop,
         fingerprints, open-width change by position/stack, match distribution
"""
import argparse
import collections
import hashlib
import json
import math
import os
import pathlib
import random
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# test@1a23123 (== a148d95, docs-only diff) fingerprints of the two fixtures,
# measured in isolated processes before this change.
EXPECT_OFF = {
    'regress9': {'3000': '2d832d7055da3b84', '3001': 'ffa45668e102598c',
                 '3002': 'dcb481636e97a99b', '3003': '93ae14a828303a51',
                 '3004': '2edc7c6feeaa2a5c', '3005': '2f83a30af8ac3c97'},
    # turbo8: measured with THIS recipe (q/aggr header line included) on pristine
    # a148d95 via `git stash`; stats n 1223 / VPIP 368 / PFR 190 / flop 107.
    'turbo8': {'3100': '81aea8aa32443fdb', '3101': '61bbaf8c0719c317',
               '3102': 'd1b9c04aa0c17cc2', '3103': 'c034b8707389c9e2',
               '3104': '87de40c49e6b770a', '3105': '6296f93d78693cf6'},
}
FIXTURES = {
    'regress9': dict(seeds=range(3000, 3006),
                     kw=dict(entries=100, start_stack=30000, hero_seat=7,
                             hands_per_level=200)),
    'turbo8': dict(seeds=range(3100, 3106),
                   kw=dict(entries=100, hero_seat=7, seats=8, hands_per_level=200,
                           fmt='turbo')),
}


# ---------------------------------------------------------------- fixtures

def run_fixture(name):
    """Runs inside a child process. Prints one JSON line."""
    import tourney as T
    import persona as PS
    fx = FIXTURES[name]
    opens = collections.defaultdict(lambda: [0, 0.0, 0.0])   # pos|band -> n, sum acc
    matches = collections.Counter()
    orig = PS.open_pct

    def wrap(prof, pos, seats=8, bb=100.0, ante=True, band=None):
        v = orig(prof, pos, seats, bb, ante, band)
        if prof and prof.get('concepts'):
            _gm = getattr(PS, 'gto_condition_match', None)   # absent on pristine code
            m = _gm('rfi', pos, seats, bb, ante) if _gm else float('nan')
            k = '%s|%s' % (pos, '<=100' if bb <= 100 else '>100')
            o = opens[k]
            o[0] += 1
            o[1] += v
            o[2] += m
            matches[round(m, 1)] += 1
        return v
    PS.open_pct = wrap
    per_seed, st = {}, collections.Counter()
    for sd in fx['seeds']:
        t = T.Tournament(seed=sd, **fx['kw'])
        rows = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
        for _ in range(30):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            s0 = t.next_hand()
            g = 0
            while s0 and not s0.get('done') and g < 200:
                s0 = t.submit('fold')
                g += 1
            log = getattr(t.run, 'full_log', []) or []
            rows.append(';'.join('%s:%s:%s:%s' % x for x in log))
            seen = set()
            for (stt, x, a, _m) in log:
                if stt != 'preflop' or x == t.hero or x in seen:
                    continue
                seen.add(x)
                st['n'] += 1
                if a in ('bet', 'raise', 'allin'):
                    st['vpip'] += 1
                    st['pfr'] += 1
                elif a == 'call':
                    st['vpip'] += 1
            st['hands'] += 1
            if any(s == 'flop' for (s, _a, _b, _c) in log):
                st['flop'] += 1
            t.finish_hand()
        per_seed[str(sd)] = hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
    print(json.dumps({'per_seed': per_seed, 'stats': dict(st),
                      'opens': {k: [v[0], v[1] / v[0], v[2] / v[0]] for k, v in opens.items()},
                      'match_hist': {str(k): v for k, v in sorted(matches.items())}}))


def fixture(name, flag):
    env = dict(os.environ)
    env['T2_GTO_MEMORY_V2'] = '1' if flag else '0'
    env['PYTHONPATH'] = str(ROOT)
    out = subprocess.run([sys.executable, __file__, '--child', name], env=env,
                         capture_output=True, text=True, timeout=1500, cwd=str(ROOT))
    if out.returncode != 0:
        raise SystemExit(out.stderr[-2000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- helpers

def mkprof(knowledge=5.0, loose=5.0, aggr=5.0, reasoning=5.0, positional=5.0):
    import persona as PS
    c = {k: float(reasoning) for k in PS.ALL_CONCEPTS}
    c['pf_range'] = c['pf_defend'] = float(knowledge)
    c['positional'] = float(positional)
    t = {k: 5.0 for k in PS.TEMPER}
    t['looseness'] = float(loose)
    t['aggression'] = float(aggr)
    return {'id': None, 'concepts': c, 'temper': t, 'type': 'X', 'aggr': aggr, 'bluff': 5.0}


def cards(h):
    if len(h) == 2:
        return [h[0] + 's', h[1] + 'h']
    return [h[0] + 's', h[1] + ('s' if h[2] == 's' else 'h')]


def cont_prob(prof, h, stack, opener='UTG+1', seats=8, ante=True):
    import preflop as PF
    o = PF.defend_action_likelihoods(prof, 'BB', opener, cards(h), stack, 2.5, 0,
                                     raise_level=1, stack_bb=stack, exploit=None, bf=1.0,
                                     seats=seats, ante=ante, opener_allin=False,
                                     can_raise=True)
    return o['attack'] + o['call'], o['tot']


def source_sets(path, node='EP-vs-BB'):
    rows = [json.loads(x) for x in open(path) if x.strip()]
    tab = collections.defaultdict(dict)
    for r in rows:
        if r.get('scenario') == 'vs-open' and r.get('node') == node:
            tab[r['hand']][int(r['stack_bb'])] = (float(r['raise']) + float(r['allin'])
                                                 + float(r['call']))
    pure_fold = sorted(h for h, v in tab.items() if len(v) == 6 and max(v.values()) <= 0.001)
    pure_cont = sorted(h for h, v in tab.items() if len(v) == 6 and min(v.values()) >= 0.999)
    return tab, pure_fold, pure_cont


# ---------------------------------------------------------------- checks

def check_match():
    import persona as PS
    rows = []
    ok = True
    for (pos, seats, bb, ante) in [('UTG', 8, 40, True), ('BTN', 8, 100, True),
                                   ('CO', 8, 3, True), ('UTG', 9, 40, True),
                                   ('BTN', 8, 150, True), ('BTN', 8, 250, True),
                                   ('BTN', 8, 40, False), ('UTG', 9, 250, False),
                                   ('HJ', 9, 150, False), ('SB', 9, 300, False)]:
        m = PS.gto_condition_match('rfi', pos, seats, bb, ante)
        inside = seats == 8 and ante and 3 <= bb <= 100
        ok &= (0.0 <= m <= 1.0) and ((m == 1.0) if inside else True)
        rows.append({'family': 'rfi', 'pos': pos, 'seats': seats, 'bb': bb, 'ante': ante,
                     'match': round(m, 4), 'inside': inside})
    for (dp, op, seats, bb, ante) in [('BB', 'UTG+1', 8, 50, True), ('BB', 'UTG+1', 8, 150, True),
                                      ('BB', 'HJ', 9, 100, False), ('BTN', 'CO', 9, 250, False),
                                      ('SB', 'BTN', 8, 5, True)]:
        m = PS.gto_condition_match('defend', dp, seats, bb, ante, opener_pos=op)
        inside = seats == 8 and ante and 10 <= bb <= 100
        ok &= (0.0 <= m <= 1.0) and ((m == 1.0) if inside else True)
        rows.append({'family': 'defend', 'pos': dp, 'opener': op, 'seats': seats, 'bb': bb,
                     'ante': ante, 'match': round(m, 4), 'inside': inside})
    return {'pass': bool(ok), 'rows': rows}


def check_A(data):
    import persona as PS
    import gto as G
    out = {}
    # A1: open width, neutral temper, knowledge 10, positional 10 (max awareness)
    rows = []
    for flag in (False, True):
        PS.GTO_MEMORY_V2 = flag
        for pos, seats, bb, ante in [('UTG', 8, 40, True), ('BTN', 8, 40, True),
                                     ('CO', 9, 150, False), ('BTN', 9, 250, False)]:
            p = mkprof(10, 5, 5, 5, positional=10)
            ref = G.rfi(pos, seats, bb, ante)
            # neutral temper -> direction 0 -> the only remaining term is the
            # existing positional flattening at positional 10: flat = (1-0.90)*0.60
            expect = ref * (1 - 0.06) + G.avg_rfi(seats, bb, ante) * 0.06
            got = PS.open_pct(p, pos, seats, bb, ante)
            rows.append({'flag': flag, 'pos': pos, 'seats': seats, 'bb': bb, 'ante': ante,
                         'open': round(got, 4), 'ref': round(ref, 4),
                         'expect_no_persona_term': round(expect, 4),
                         'rel_dev_from_ref': round(abs(got - ref) / ref, 4)})
    PS.GTO_MEMORY_V2 = False
    out['A1_open'] = {'rows': rows,
                      'pass': all(abs(r['open'] - r['expect_no_persona_term']) < 1e-4
                                  for r in rows),
                      'note': 'PASS = no persona/memory term moves a neutral-temper player '
                              '(open == reference with only the existing positional term), '
                              'with the flag off AND on'}
    if data:
        tab, pf, pc = source_sets(data)
        p = mkprof(10, 5, 5, 5)
        vals = {h: {s: round(cont_prob(p, h, s)[0], 3) for s in (30, 50, 100)} for h in pf}
        viol = sorted([(max(v.values()), h) for h, v in vals.items() if max(v.values()) >= 0.5],
                      reverse=True)
        mean_pf = sum(sum(v.values()) / 3 for v in vals.values()) / max(1, len(vals))
        out['A2_defense'] = {
            'node': 'EP-vs-BB (BB vs UTG+1), 8-max ante, 2.5bb open',
            'n_allstack_pure_fold_hands': len(pf),
            'neutral_mean_continue_on_pure_fold': round(mean_pf, 4),
            'neutral_pure_fold_hands_continue_ge_0.5': [h for _, h in viol],
            '82o': vals.get('82o'), 'J4o': vals.get('J4o'),
            'pass': len(viol) == 0,
            'classification': 'prior-layer (GTO reference/defense width) finding — '
                              'neutral temper, pf_defend 10: no persona term is active'}
    return out


def check_B():
    import persona as PS
    import preflop as PF
    import gto as G
    # BTN open, 8-max ante 40bb, knowledge 4 (so persona can act), loose 9 vs tight 1
    base = G.rfi('BTN', 8, 40, True)
    lo, hi = mkprof(4, 1, 3), mkprof(4, 9, 7)
    w_lo, w_hi = PS.open_pct(lo, 'BTN', 8, 40, True), PS.open_pct(hi, 'BTN', 8, 40, True)
    # hands ranked by pct: boundary = between the two widths, far = well outside both
    hands = sorted(PF.PCT.items(), key=lambda kv: kv[1])
    boundary = [h for h, r in hands if w_lo < r <= w_hi]
    far_in = [h for h, r in hands if r <= min(w_lo, w_hi) * 0.5]
    far_out = [h for h, r in hands if r > max(w_lo, w_hi) * 1.5]
    frac = lambda hs, w: sum(1 for h in hs if PF.PCT[h] <= w) / max(1, len(hs))
    d_b = frac(boundary, w_hi) - frac(boundary, w_lo)
    d_fi = frac(far_in, w_hi) - frac(far_in, w_lo)
    d_fo = frac(far_out, w_hi) - frac(far_out, w_lo)
    # defense (logistic): boundary vs far hands
    p_lo, p_hi = mkprof(4, 1, 3), mkprof(4, 9, 7)
    def dcont(h):
        return cont_prob(p_hi, h, 50)[0] - cont_prob(p_lo, h, 50)[0]
    dd = {h: round(dcont(h), 3) for h in ('AA', 'AKs', 'KJo', 'Q9o', 'J8o', 'T7o', '72o')}
    return {'ref_BTN': round(base, 4), 'w_tight': round(w_lo, 4), 'w_loose': round(w_hi, 4),
            'open_delta_boundary': round(d_b, 3), 'open_delta_far_in': round(d_fi, 3),
            'open_delta_far_out': round(d_fo, 3), 'defense_delta_by_hand': dd,
            'pass': d_b > 0 and d_b > abs(d_fi) and d_b > abs(d_fo)}


def check_C(data):
    import persona as PS
    if not data:
        return {'skipped': 'needs --data'}
    tab, pf, pc = source_sets(data)
    res = []
    for flag in (False, True):
        PS.GTO_MEMORY_V2 = flag
        for label, p in [('neutral k10', mkprof(10, 5)), ('neutral k5', mkprof(5, 5)),
                         ('loose9 k5', mkprof(5, 9, 7)), ('loose9 k2', mkprof(2, 9, 7)),
                         ('loose10 k0', mkprof(0, 10, 9)), ('tight1 k2', mkprof(2, 1, 3))]:
            for stack, seats, ante in ((50, 8, True), (100, 8, True), (150, 9, False)):
                cf = [cont_prob(p, h, stack, seats=seats, ante=ante)[0] for h in pf]
                cc = [cont_prob(p, h, stack, seats=seats, ante=ante)[0] for h in pc]
                res.append({'flag': flag, 'persona': label, 'stack': stack, 'seats': seats,
                            'ante': ante,
                            'max_cont_pure_fold': round(max(cf), 3),
                            'mean_cont_pure_fold': round(sum(cf) / len(cf), 3),
                            'min_cont_pure_cont': round(min(cc), 3),
                            'mean_cont_pure_cont': round(sum(cc) / len(cc), 3),
                            'mean_ordering_ok': sum(cf) / len(cf) < sum(cc) / len(cc),
                            'share_pure_fold_ge_0.5': round(sum(1 for x in cf if x >= 0.5) / len(cf), 3),
                            'ordering_ok': max(cf) < min(cc)})
    PS.GTO_MEMORY_V2 = False
    studied = [r for r in res if r['seats'] == 8 and r['ante']]
    neutral = [r for r in studied if r['persona'].startswith('neutral')]
    return {'n_pure_fold': len(pf), 'n_pure_cont': len(pc), 'rows': res,
            'note': 'only 8-max ante rows are judged: the charts are 8-max ante; the '
                    '9-max no-ante rows are condition-mismatched and reported only',
            'pass_ordering': all(r['ordering_ok'] for r in studied),
            'pass_mean_ordering': all(r['mean_ordering_ok'] for r in studied),
            'neutral_prior_ordering_ok': all(r['ordering_ok'] for r in neutral)}


def check_DE():
    import persona as PS
    import reads as RD
    p = mkprof(6, 5, 5, 6)
    p['temper']['adaptability'] = 8.0
    p['temper']['attention'] = 8.0
    rd0 = PS.read_opponent(p, RD.estimate(RD.Book(), 1, 2, 'reg', rng=random.Random(1)))
    D = {'w': rd0['w'], 'fold_gap': rd0['fold_gap'],
         'exploit_weight_n0': PS._exploit_base_weight(p, 0.0, 0),
         'pass': rd0['w'] == 0.0 and rd0['fold_gap'] == 0.0
         and PS._exploit_base_weight(p, 0.0, 0) == 0.0}
    # E: opponent folds to bets 80% — feed observations hand by hand
    bk = RD.Book()
    ws, ews, gaps = [], [], []
    rng = random.Random(7)
    for n in range(0, 61):
        e = RD.estimate(bk, 1, 2, 'reg', rng=random.Random(1))
        r = PS.read_opponent(p, e)
        ws.append(r['w'])
        gaps.append(r.get('fold_gap', 0.0))
        ews.append(PS._exploit_base_weight(p, e.get('confidence', 0.0), e.get('n', 0)))  # stage9 B5: single weight
        bk.observe_preflop([1], 2, vpip=True, pfr=False)
        bk.observe_postflop([1], 2, 'fold' if rng.random() < 0.8 else 'call',
                            False, False, facing_bet=True, street='flop')
    mono = all(b >= a - 1e-12 for a, b in zip(ws, ws[1:]))
    mono_e = all(b >= a - 1e-12 for a, b in zip(ews, ews[1:]))
    step = max(b - a for a, b in zip(ws, ws[1:]))
    ramp = max(ws) / 12.0 if max(ws) > 0 else 0.0
    E = {'w_curve': [round(x, 3) for x in ws[::5]],
         'exploit_weight_curve': [round(x, 3) for x in ews[::5]],
         'fold_gap_curve': [round(x, 3) for x in gaps[::5]],
         'monotone_w': mono, 'monotone_exploit_weight': mono_e,
         'max_step': round(step, 4), 'ramp_step_bound': round(ramp, 4),
         'pass': mono and mono_e and step <= ramp + 1e-9}
    return D, E


def check_FG(n=5000):
    import persona as PS
    rng = random.Random(12345)
    P = [PS.make_player(rng, 0.78, pid=i) for i in range(n)]
    reason = [(p['concepts']['potodds'] + p['concepts']['spr'] + p['concepts']['range_read']
               + p['concepts']['blocker']) / 4 for p in P]
    know = [p['concepts']['pf_range'] for p in P]
    loose = [p['temper']['looseness'] for p in P]
    q = lambda xs, f: sorted(xs)[int(f * (len(xs) - 1))]
    kh, kl, rh, rl = q(know, .8), q(know, .2), q(reason, .8), q(reason, .2)
    lh, ll = q(loose, .8), q(loose, .2)
    F = {  # same knowledge band (middle 40-60%), reasoning / looseness spread
        'knowledge_band': [round(q(know, .4), 1), round(q(know, .6), 1)]}
    band = [i for i in range(n) if q(know, .4) <= know[i] <= q(know, .6)]
    F['reasoning_top20_in_band'] = sum(1 for i in band if reason[i] >= rh)
    F['reasoning_bottom20_in_band'] = sum(1 for i in band if reason[i] <= rl)
    F['loose_top20_in_band'] = sum(1 for i in band if loose[i] >= lh)
    F['loose_bottom20_in_band'] = sum(1 for i in band if loose[i] <= ll)
    F['band_n'] = len(band)
    F['pass'] = all(F[k] > 0 for k in ('reasoning_top20_in_band', 'reasoning_bottom20_in_band',
                                        'loose_top20_in_band', 'loose_bottom20_in_band'))
    bandr = [i for i in range(n) if q(reason, .4) <= reason[i] <= q(reason, .6)]
    G = {'reasoning_band_n': len(bandr),
         'knowledge_top20_in_band': sum(1 for i in bandr if know[i] >= kh),
         'knowledge_bottom20_in_band': sum(1 for i in bandr if know[i] <= kl)}
    G['pass'] = G['knowledge_top20_in_band'] > 0 and G['knowledge_bottom20_in_band'] > 0
    m = lambda xs: sum(xs) / len(xs)
    mk, mr = m(know), m(reason)
    cov = sum((a - mk) * (b - mr) for a, b in zip(know, reason)) / n
    sd = lambda xs, mu: math.sqrt(sum((x - mu) ** 2 for x in xs) / n)
    extremes = {
        'knowledge_top20_reasoning_bottom20': sum(1 for a, b in zip(know, reason) if a >= kh and b <= rl) / n,
        'knowledge_bottom20_reasoning_top20': sum(1 for a, b in zip(know, reason) if a <= kl and b >= rh) / n}
    return F, G, {'corr_knowledge_reasoning': round(cov / (sd(know, mk) * sd(reason, mr)), 3),
                  'extreme_offdiagonal_share': {k: round(v, 4) for k, v in extremes.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--child')
    ap.add_argument('--data')
    ap.add_argument('--out')
    ap.add_argument('--skip-runtime', action='store_true')
    a = ap.parse_args()
    if a.child:
        run_fixture(a.child)
        return 0
    import persona as PS
    PS.GTO_MEMORY_V2 = False
    R = {'MATCH': check_match(), 'A': check_A(a.data), 'B': check_B(), 'C': check_C(a.data)}
    R['D'], R['E'] = check_DE()
    R['F'], R['G'], R['FG_population'] = check_FG()
    if not a.skip_runtime:
        att = {}
        for name in FIXTURES:
            off, on = fixture(name, False), fixture(name, True)
            att[name] = {
                'off': off['stats'], 'on': on['stats'],
                'ident_off': off['per_seed'] == EXPECT_OFF[name],
                'fp_changed_on': sum(1 for k in off['per_seed']
                                     if off['per_seed'][k] != on['per_seed'][k]),
                'open_width_off_on': {k: [off['opens'][k][0], round(off['opens'][k][1], 4),
                                          round(on['opens'].get(k, [0, float('nan')])[1], 4),
                                          round(off['opens'][k][2], 3)]
                                      for k in sorted(off['opens'])},
                'match_hist_off_run': off['match_hist']}
        R['IDENT'] = {'pass': all(v['ident_off'] for v in att.values())}
        R['ATTR'] = att
    summary = {k: (v.get('pass') if isinstance(v, dict) else None) for k, v in R.items()}
    if 'A' in R:
        summary['A1'] = R['A']['A1_open']['pass']
        if 'A2_defense' in R['A']:
            summary['A2'] = R['A']['A2_defense']['pass']
    if 'C' in R and 'pass_ordering' in R['C']:
        summary['C_worst_hand_ordering'] = R['C']['pass_ordering']
        summary['C_mean_ordering'] = R['C']['pass_mean_ordering']
        summary['C_neutral_prior_ordering'] = R['C']['neutral_prior_ordering_ok']
        summary.pop('C', None)
    R['summary'] = summary
    txt = json.dumps(R, indent=1, sort_keys=True, default=str)
    if a.out:
        open(a.out, 'w').write(txt)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
