#!/usr/bin/env python3
"""Same-runtime-state replay: current (test) vs compact / residual candidates.

Shadow only. Production code is not modified; candidates are applied by wrapping
preflop.defend_action_likelihoods inside this process.

  --capture OUT   run the test runtime (8-max, ante, turbo), record every eligible
                  defend state (args + current output), then score every arm on the
                  identical args. Eligible = the gate the compact experiment used
                  (8 seats, ante, raise_level 1, no callers, open 2.5bb / SB 3.0bb,
                  can_raise, not call-off, def_pos in BB/SB/BTN/CO).
  --endpoint ARM  run the same tournaments with ARM wired in, report VPIP/PFR/flop and
                  per-seed fingerprints (current = ARM 'current').

Arms: current, compact, cand_def, cand_logit, cand_node_logit. Parameters come from
data/gto_public/defense_residual_candidate_20260928.json.

Persona handling for candidate arms is copied from the compact experiment
(tmp/preflop-policy-shape-20260928 preflop._mtt8_policy_shape): aggression moves
continue mass call<->attack, premium slowplay attack->call, hot-zone shove kept.
With the neutral profile (aggression 5) both transfers are the identity.

Reference: runtime stacks are not chart stacks, so each state also gets a
source-interpolated reference (linear in log stack between the bracketing chart
stacks, opener mapped EP=UTG/UTG+1/LJ, MP=HJ/CO). The reference is the neutral chart;
runtime tp/tot carry persona adjustments, so reference Brier is secondary.
"""
import argparse
import bisect
import collections
import hashlib
import inspect
import json
import math
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import preflop  # noqa: E402
import gto as _G  # noqa: E402

PARAMS = json.loads((ROOT / 'data' / 'gto_public' /
                     'defense_residual_candidate_20260928.json').read_text())['params']
EDGES = [float('inf') if e is None else e for e in PARAMS['edges']]
RV = {r: i + 2 for i, r in enumerate('23456789TJQKA')}
ARMS = ('current', 'compact', 'cand_def', 'cand_logit', 'cand_node_logit')
EP = {'UTG', 'UTG+1', 'LJ'}
MP = {'HJ', 'CO'}
CHART_STACKS = [10, 15, 20, 30, 50, 100]


def feats(h):
    pair = len(h) == 2
    suited = len(h) == 3 and h[2] == 's'
    off = len(h) == 3 and h[2] == 'o'
    r1, r2 = RV[h[0]], RV[h[1]]
    hi, lo = max(r1, r2), min(r1, r2)
    gap = abs(r1 - r2)
    ace, king, queen = hi == 14, hi == 13, hi == 12
    broad = hi >= 10 and lo >= 10
    return [1.0, float(pair), float(pair) * (hi - 2) / 12, float(suited), float(off),
            float(ace), float(ace and suited), float(ace and off),
            float(suited and ace and lo <= 5), float(king), float(king and suited),
            float(queen), float(broad), float(broad and suited),
            float(suited and gap == 1), float(suited and gap == 2),
            float(suited and gap == 1 and hi <= 9), float(pair and hi <= 6),
            float(pair and 7 <= hi <= 11), float(pair and hi >= 12),
            (hi - 2) / 12, (lo - 2) / 12, min(gap, 12) / 12]


FN = ['bias', 'pair', 'pair_rank', 'suited', 'offsuit', 'ace', 'ace_suited',
      'ace_offsuit', 'wheel_ace_suited', 'king', 'king_suited', 'queen_high',
      'broadway', 'broadway_suited', 'suited_connector', 'suited_onegap',
      'low_suited_connector', 'small_pair', 'mid_pair', 'premium_pair', 'hi_rank',
      'lo_rank', 'gap']
BETA = [PARAMS['beta'][n] for n in FN]


def _bin(z):
    nb = len(EDGES) - 1
    return max(0, min(nb - 1, bisect.bisect_right(EDGES, z) - 1))


def _lg(p, eps):
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))


def model(arm, def_pos, h, tp, tot, opener=None):
    r = preflop.PCT[h]
    cv = PARAMS['curves'][def_pos]
    cont = cv['continue'][_bin(r / max(tot, 1e-9))]
    a = min(cv['attack'][_bin(r / max(tp, 1e-9))], cont)
    a = max(0.0, min(cont, a + sum(q * v for q, v in zip(BETA, feats(h)))))
    key = '%s|%s' % (def_pos, h)
    if arm == 'cand_def':
        ra, rc = PARAMS['residual'].get(key, [0.0, 0.0])
        cont = max(0.0, min(1.0, cont + rc))
        a = max(0.0, min(cont, a + ra))
    elif arm == 'cand_logit':
        ra, rc = PARAMS['logit_residual'].get(key, [0.0, 0.0])
        cont = 1.0 / (1.0 + math.exp(-(_lg(cont, PARAMS['logit_eps']) + rc)))
        a = max(0.0, min(cont, a + ra))
    elif arm == 'cand_node_logit':
        # runtime (opener, defender) with no chart node (e.g. CO vs HJ) -> no residual
        node = node_of(opener, def_pos) if opener else None
        ra, rc = PARAMS['node_logit_residual'].get('%s|%s' % (node, h), [0.0, 0.0])
        cont = 1.0 / (1.0 + math.exp(-(_lg(cont, PARAMS['node_logit_eps']) + rc)))
        a = max(0.0, min(cont, a + ra))
    return a, cont


def persona_shape(prof, attack, cont, r, p_hot):
    """Copied from tmp/preflop-policy-shape-20260928 preflop._mtt8_policy_shape."""
    a = preflop.prof_aggr(prof)
    q = attack / max(1e-9, cont) if cont > 1e-9 else 0.0
    fac = max(0.20, (0.55 + 0.085 * a) / 0.975)
    if 0.0 < q < 1.0:
        q = (q * fac) / max(1e-9, (1.0 - q) + q * fac)
    attack = cont * max(0.0, min(1.0, q))
    pf_slow = 0.0
    if prof.get('concepts'):
        taste = preflop.PS.temper(prof, 'slowplay_taste', 5.0) / 10.0
        passive = max(0.0, min(1.0, (5.0 - a) / 5.0))
        premium = max(0.0, min(1.0, (0.10 - r) / 0.10))
        pf_slow = passive * (0.35 + 0.65 * taste) * premium
    elif preflop.A.ARCHETYPES.get(prof.get('type'), (0,) * 7 + ('reg',))[6] == 'fish':
        pf_slow = max(0.0, min(1.0, (0.10 - r) / 0.10)) * 0.55
    attack *= max(0.30, 1.0 - 0.70 * pf_slow)
    attack = max(0.0, min(cont, attack))
    hot = max(0.0, min(float(p_hot or 0.0), attack))
    if hot >= 1.0 - 1e-12:
        mr = mc = mf = 0.0
    else:
        mr = max(0.0, min(1.0, (attack - hot) / (1.0 - hot)))
        mcont = max(mr, min(1.0, (cont - hot) / (1.0 - hot)))
        mc = max(0.0, mcont - mr)
        mf = max(0.0, 1.0 - mcont)
    return attack, max(0.0, cont - attack), max(0.0, 1.0 - cont), hot, mr, mc, mf


def eligible(b, out):
    if out.get('calloff'):
        return False
    dp = b['def_pos']
    if dp not in PARAMS['curves']:
        return False
    if not (b['can_raise'] and int(b['seats']) == 8 and bool(b['ante'])
            and int(b['raise_level']) == 1 and int(b['n_callers'] or 0) == 0):
        return False
    if not _G._use_mtt8_ante_defense(dp, b['seats'], b['ante']):
        return False
    target = 3.0 if b['opener_pos'] == 'SB' else 2.5
    return abs(float(b['open_bb']) - target) <= 0.25


def arm_output(arm, b, out):
    h = preflop.cls(b['hand'])
    a, cont = model(arm, b['def_pos'], h, out['tp'], out['tot'], b['opener_pos'])
    return persona_shape(b['prof'], a, cont, out['hand_pct'], out['hot_attack'])


# ---------------- source reference ---------------------------------------------------

def load_ref(path):
    ref = collections.defaultdict(dict)
    for ln in open(path):
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get('scenario') != 'vs-open':
            continue
        a = float(r.get('raise', 0)) + float(r.get('allin', 0))
        ref[(r['node'], r['hand'])][int(r['stack_bb'])] = (a, float(r['call']), float(r['fold']))
    return ref


def node_of(opener, dp):
    g = 'EP' if opener in EP else 'MP' if opener in MP else opener
    if dp == 'CO':
        return 'EP-vs-MP' if g == 'EP' else None
    return '%s-vs-%s' % (g, dp)


def ref_at(ref, node, h, stack):
    tab = ref.get((node, h))
    if not tab or len(tab) < 6:
        return None
    s = max(CHART_STACKS[0], min(CHART_STACKS[-1], stack))
    i = max(1, bisect.bisect_left(CHART_STACKS, s))
    s0, s1 = CHART_STACKS[i - 1], CHART_STACKS[i]
    t = (math.log(s) - math.log(s0)) / (math.log(s1) - math.log(s0))
    return tuple(tab[s0][k] * (1 - t) + tab[s1][k] * t for k in range(3))


# ---------------- running ------------------------------------------------------------

def run_tour(seeds, hands):
    import tourney as T
    per_seed, stats = {}, collections.Counter()
    for sd in seeds:
        t = T.Tournament(entries=100, hero_seat=7, seats=8, seed=sd,
                         hands_per_level=200, fmt='turbo')
        rows = []
        for _ in range(hands):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1
            log = getattr(t.run, 'full_log', []) or []
            rows.append(';'.join('%s:%s:%s:%s' % x for x in log))
            sn = set()
            for (stt, x, a, _amt) in log:
                if stt != 'preflop' or x == t.hero or x in sn:
                    continue
                sn.add(x)
                stats['n'] += 1
                if a in ('bet', 'raise', 'allin'):
                    stats['vpip'] += 1
                    stats['pfr'] += 1
                elif a == 'call':
                    stats['vpip'] += 1
            stats['hands'] += 1
            if any(s == 'flop' for (s, _, _, _) in log):
                stats['flop'] += 1
            t.finish_hand()
        per_seed[str(sd)] = hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
    return per_seed, dict(stats)


def capture(seeds, hands, out_path, data):
    orig = preflop.defend_action_likelihoods
    sig = inspect.signature(orig)
    states = []

    def wrap(*a, **kw):
        out = orig(*a, **kw)
        b = sig.bind(*a, **kw)
        b.apply_defaults()
        b = dict(b.arguments)
        if eligible(b, out):
            states.append((b, dict(out)))
        return out
    preflop.defend_action_likelihoods = wrap
    per_seed, stats = run_tour(seeds, hands)
    preflop.defend_action_likelihoods = orig

    ref = load_ref(data)
    rows = []
    for b, out in states:
        h = preflop.cls(b['hand'])
        row = {'def_pos': b['def_pos'], 'opener_pos': b['opener_pos'], 'hand': h,
               'stack_bb': round(float(b['stack_bb'] if b['stack_bb'] is not None else b['bb']), 2),
               'aggr': preflop.prof_aggr(b['prof']), 'tp': out['tp'], 'tot': out['tot'],
               'hot': out['hot_attack'],
               'current': [out['attack'], out['call'], out['fold']]}
        for arm in ARMS[1:]:
            x = arm_output(arm, b, out)
            row[arm] = [x[0], x[1], x[2]]
        node = node_of(b['opener_pos'], b['def_pos'])
        rf = ref_at(ref, node, h, row['stack_bb']) if node else None
        row['node'] = node
        row['ref'] = list(rf) if rf else None
        tab = ref.get((node, h)) if node else None
        row['allstack_pure_fold'] = bool(tab and len(tab) == 6
                                         and all(v[2] >= 0.999 for v in tab.values()))
        rows.append(row)

    def am(v):
        return max(range(3), key=lambda i: v[i])
    summ = {'states': len(rows), 'per_seed': per_seed, 'stats': stats, 'arms': {}}
    for arm in ARMS[1:]:
        d = collections.defaultdict(float)
        byp = collections.defaultdict(lambda: collections.defaultdict(float))
        for r in rows:
            c, x = r['current'], r[arm]
            flip = am(c) != am(x)
            for tgt in (d, byp[r['def_pos']]):
                tgt['n'] += 1
                tgt['abs_attack'] += abs(x[0] - c[0])
                tgt['abs_call'] += abs(x[1] - c[1])
                tgt['abs_fold'] += abs(x[2] - c[2])
                tgt['d_attack'] += x[0] - c[0]
                tgt['d_call'] += x[1] - c[1]
                tgt['d_fold'] += x[2] - c[2]
                tgt['flips'] += flip
        def fin(t):
            n = max(1.0, t['n'])
            return {k: (t[k] if k in ('n', 'flips') else t[k] / n) for k in t}
        flips = collections.Counter()
        for r in rows:
            c, x = r['current'], r[arm]
            if am(c) != am(x):
                flips['%s>%s' % ('ACF'[am(c)], 'ACF'[am(x)])] += 1
        summ['arms'][arm] = {'all': fin(d), 'by_pos': {k: fin(v) for k, v in sorted(byp.items())},
                             'flip_types': dict(flips)}
    # reference-based scoring (secondary)
    refrows = [r for r in rows if r['ref']]
    sc = {}
    for arm in ARMS:
        s = collections.defaultdict(float)
        for r in refrows:
            x, t = r[arm], r['ref']
            s['A'] += (x[0] - t[0]) ** 2
            s['C'] += (x[1] - t[1]) ** 2
            s['F'] += (x[2] - t[2]) ** 2
            s['aMAE'] += abs(x[0] - t[0])
            s['cMAE'] += abs((x[0] + x[1]) - (t[0] + t[1]))
            s['argmax_vs_ref'] += am(x) != am(t)
        n = max(1, len(refrows))
        sc[arm] = {'n': len(refrows), 'attack_brier': s['A'] / n, 'call_brier': s['C'] / n,
                   'fold_brier': s['F'] / n, 'action_brier': (s['A'] + s['C'] + s['F']) / 3 / n,
                   'attack_mae': s['aMAE'] / n, 'continue_mae': s['cMAE'] / n,
                   'argmax_disagree': s['argmax_vs_ref']}
    summ['vs_reference'] = sc
    pure = [r for r in rows if r['allstack_pure_fold']]
    summ['allstack_pure_fold_states'] = {
        'n': len(pure),
        'continue_ge_0.5': {arm: sum(1 for r in pure if r[arm][0] + r[arm][1] >= 0.5)
                            for arm in ARMS},
        'mean_continue': {arm: sum(r[arm][0] + r[arm][1] for r in pure) / max(1, len(pure))
                          for arm in ARMS}}
    json.dump({'summary': summ, 'rows': rows}, open(out_path, 'w'), indent=1)
    return summ


def endpoint(arm, seeds, hands):
    if arm != 'current':
        orig = preflop.defend_action_likelihoods
        sig = inspect.signature(orig)
        hits = collections.Counter()

        def wrap(*a, **kw):
            out = orig(*a, **kw)
            b = sig.bind(*a, **kw)
            b.apply_defaults()
            b = dict(b.arguments)
            if not eligible(b, out):
                return out
            at, ca, fo, hot, mr, mc, mf = arm_output(arm, b, out)
            hits['n'] += 1
            out = dict(out)
            out.update({'attack': at, 'call': ca, 'fold': fo, 'hot_attack': hot,
                        'mixed_attack': mr, 'mixed_call': mc, 'mixed_fold': mf,
                        'w_raise': mr, 'w_call': mc, 'w_fold': mf,
                        'total_weight': mr + mc + mf})
            return out
        preflop.defend_action_likelihoods = wrap
    per_seed, stats = run_tour(seeds, hands)
    return per_seed, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--capture')
    ap.add_argument('--endpoint', choices=ARMS)
    ap.add_argument('--data')
    ap.add_argument('--seeds', default='3100-3105')
    ap.add_argument('--hands', type=int, default=30)
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    if a.capture:
        s = capture(seeds, a.hands, a.capture, a.data)
        print('@@RESULT@@' + json.dumps({k: v for k, v in s.items()}))
    elif a.endpoint:
        ps, st = endpoint(a.endpoint, seeds, a.hands)
        print('@@RESULT@@' + json.dumps({'arm': a.endpoint, 'per_seed': ps, 'stats': st}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
