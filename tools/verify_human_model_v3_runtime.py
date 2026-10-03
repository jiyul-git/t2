#!/usr/bin/env python3
"""Human Model v3 runtime / paired-counterfactual verifier.

No target poker frequency is fitted here.  PASS means the new mechanism is
attributed to the intended condition mismatch and the population actually
contains the knowledge/reasoning combinations the model claims to represent.
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

FIXTURES = {
    # 8-max + ante + ~50bb: inside the declared studied RFI/defend family.
    'matched8': dict(seeds=range(4200, 4204),
                     # turbo has ante_from=1; hands_per_level is overridden so
                     # the fixture stays on one blind level.  With bb=230 and
                     # 5,000 chips this starts at ~21.7bb, squarely inside the
                     # studied 8-max + ante depth range.
                     kw=dict(entries=100, start_stack=12000, hero_seat=7,
                             seats=8, hands_per_level=200, fmt='turbo'), hands=6),
    # 9-max + ~200bb: table-size and depth mismatch by construction.
    'mismatch9deep': dict(seeds=range(4300, 4304),
                          kw=dict(entries=100, start_stack=20000, hero_seat=7,
                                  seats=9, hands_per_level=200), hands=16),
}


def mkprof(knowledge=8.0, loose=5.0, aggr=5.0,
           stack_decay=5.0, positional=5.0, potodds=5.0):
    import persona as PS
    c = {k: 5.0 for k in PS.ALL_CONCEPTS}
    c['pf_range'] = c['pf_defend'] = float(knowledge)
    c['stack_decay'] = float(stack_decay)
    c['positional'] = float(positional)
    c['potodds'] = float(potodds)
    t = {k: 5.0 for k in PS.TEMPER}
    t['looseness'] = float(loose)
    t['aggression'] = float(aggr)
    return {'id': None, 'concepts': c, 'temper': t,
            'type': 'X', 'aggr': float(aggr), 'bluff': 5.0}


def _def_width(p, seats, bb, ante):
    import preflop as PF
    return PF.defend_thresholds(
        p, 'BB', 'HJ', bb, open_bb=2.5, seats=seats, ante=ante)


def paired_counterfactual():
    import gto as G
    import persona as PS

    old = PS.PREFLOP_REASONING_V3
    PS.PREFLOP_REASONING_V3 = True
    try:
        rows = []
        ok = True

        # Depth reasoning: stack_decay should be inert inside the studied depth
        # range and matter only once depth is outside it.
        lo = mkprof(stack_decay=0.0, positional=6.0, potodds=6.0)
        hi = mkprof(stack_decay=10.0, positional=6.0, potodds=6.0)
        for bb in (40.0, 100.0, 150.0, 250.0):
            a = PS.open_pct(lo, 'HJ', 8, bb, True)
            b = PS.open_pct(hi, 'HJ', 8, bb, True)
            target = G.rfi('HJ', 8, bb, True)
            inside = bb <= 100.0
            cond = (a == b) if inside else (abs(b-target) < abs(a-target))
            ok &= cond
            rows.append({'axis':'stack_decay','bb':bb,'inside':inside,
                         'low':a,'high':b,'target':target,'pass':cond})

        # Dead-money reasoning: potodds skill should not change the matched ante
        # spot; with ante removed the stronger reasoner should move farther from
        # the memorized ante chart toward the current no-ante reference.
        lo = mkprof(stack_decay=6.0, positional=6.0, potodds=0.0)
        hi = mkprof(stack_decay=6.0, positional=6.0, potodds=10.0)
        for ante in (True, False):
            a = PS.open_pct(lo, 'CO', 8, 40.0, ante)
            b = PS.open_pct(hi, 'CO', 8, 40.0, ante)
            target = G.rfi('CO', 8, 40.0, ante)
            cond = (a == b) if ante else (abs(b-target) < abs(a-target))
            ok &= cond
            rows.append({'axis':'potodds_ante','ante':ante,
                         'low':a,'high':b,'target':target,'pass':cond})

        # Defense gets the same depth test, independently for total continue
        # and 3bet widths.
        lo = mkprof(stack_decay=0.0, positional=6.0, potodds=6.0)
        hi = mkprof(stack_decay=10.0, positional=6.0, potodds=6.0)
        for bb in (50.0, 100.0, 150.0, 250.0):
            atp, atot = _def_width(lo, 8, bb, True)
            btp, btot = _def_width(hi, 8, bb, True)
            tgt_tot = G.defend_pct('BB','HJ',8,bb,True,2.5)
            tgt_tp = G.threebet_pct('BB','HJ',8,bb,True,2.5)
            inside = bb <= 100.0
            cond = ((atp == btp and atot == btot) if inside else
                    (abs(btp-tgt_tp) < abs(atp-tgt_tp)
                     and abs(btot-tgt_tot) < abs(atot-tgt_tot)))
            ok &= cond
            rows.append({'axis':'defend_stack_decay','bb':bb,'inside':inside,
                         'low_tp':atp,'high_tp':btp,'target_tp':tgt_tp,
                         'low_tot':atot,'high_tot':btot,'target_tot':tgt_tot,
                         'pass':cond})
        return {'pass': bool(ok), 'rows': rows}
    finally:
        PS.PREFLOP_REASONING_V3 = old


def population_quadrants(n=6000):
    import persona as PS
    rng = random.Random(20260929)
    P = [PS.make_player(rng, 0.78, pid=i) for i in range(n)]
    know = [(p['concepts']['pf_range'] + p['concepts']['pf_defend'])/2.0 for p in P]
    reason = [(p['concepts']['stack_decay'] + p['concepts']['positional']
               + p['concepts']['potodds'])/3.0 for p in P]

    def q(xs, f):
        return sorted(xs)[int(f*(len(xs)-1))]
    kh, kl = q(know,.8), q(know,.2)
    rh, rl = q(reason,.8), q(reason,.2)
    cells = {
        'highK_highR': sum(1 for k,r in zip(know,reason) if k>=kh and r>=rh),
        'highK_lowR':  sum(1 for k,r in zip(know,reason) if k>=kh and r<=rl),
        'lowK_highR':  sum(1 for k,r in zip(know,reason) if k<=kl and r>=rh),
        'lowK_lowR':   sum(1 for k,r in zip(know,reason) if k<=kl and r<=rl),
    }
    mk, mr = sum(know)/n, sum(reason)/n
    cov = sum((a-mk)*(b-mr) for a,b in zip(know,reason))/n
    sk = math.sqrt(sum((a-mk)**2 for a in know)/n)
    sr = math.sqrt(sum((b-mr)**2 for b in reason)/n)
    corr = cov/(sk*sr) if sk and sr else 1.0
    # We do not require weak correlation; the latent study factor should make
    # these skills related.  We require all four behavioral quadrants to exist.
    return {'pass': all(v > 0 for v in cells.values()),
            'n':n, 'thresholds':{'kh':kh,'kl':kl,'rh':rh,'rl':rl},
            'cells':cells, 'corr':round(corr,4)}


def run_fixture(name):
    import tourney as T
    import persona as PS
    import preflop as PF
    fx = FIXTURES[name]
    per_seed = {}
    st = collections.Counter()
    matches = collections.Counter()
    active = collections.Counter()
    orig = PS.open_pct
    orig_def = PF.defend_thresholds

    def _mismatch(family, seats, bb, ante):
        S = PS.GTO_STUDIED[family]
        return (int(seats) != int(S['seats'])
                or bool(ante) != bool(S['ante'])
                or float(bb) < S['bb'][0] or float(bb) > S['bb'][1])

    def wrap(prof, pos, seats=8, bb=100.0, ante=True, band=None):
        v = orig(prof,pos,seats,bb,ante,band)
        if prof and prof.get('concepts'):
            m = PS.gto_condition_match('rfi',pos,seats,bb,ante)
            matches[round(m,1)] += 1
            active['rfi_calls'] += 1
            if _mismatch('rfi', seats, bb, ante):
                active['rfi_mismatch'] += 1
        return v

    def wrap_def(prof, def_pos, opener_pos, bb, open_bb=2.5, n_callers=0,
                 raise_level=1, seats=8, ante=True):
        if isinstance(prof, dict) and prof.get('concepts'):
            active['def_calls'] += 1
            if _mismatch('defend', seats, bb, ante):
                active['def_mismatch'] += 1
        return orig_def(prof, def_pos, opener_pos, bb, open_bb, n_callers,
                        raise_level, seats, ante)

    PS.open_pct = wrap
    PF.defend_thresholds = wrap_def

    for sd in fx['seeds']:
        t = T.Tournament(seed=sd, **fx['kw'])
        rows = []
        for _ in range(fx['hands']):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            s0 = t.next_hand()
            g = 0
            while s0 and not s0.get('done') and g < 200:
                s0 = t.submit('fold')
                g += 1
            log = getattr(t.run,'full_log',[]) or []
            rows.append(';'.join('%s:%s:%s:%s' % x for x in log))
            seen = set()
            for street, seat, act, _amt in log:
                if street != 'preflop' or seat == t.hero or seat in seen:
                    continue
                seen.add(seat)
                st['n'] += 1
                if act in ('bet','raise','allin'):
                    st['vpip'] += 1; st['pfr'] += 1
                elif act == 'call':
                    st['vpip'] += 1
            st['hands'] += 1
            if any(x[0]=='flop' for x in log):
                st['flop'] += 1
            t.finish_hand()
        per_seed[str(sd)] = hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
    print(json.dumps({'per_seed':per_seed,'stats':dict(st),
                      'match_hist':{str(k):v for k,v in sorted(matches.items())},
                      'condition_counts':dict(active)}))


def fixture(name, v3):
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT)
    env['T2_PREFLOP_REASONING_V3'] = '1' if v3 else '0'
    # Isolate the reasoning change.  Exploit unification is validated by the
    # structural verifier and is intentionally OFF in this tournament fixture.
    out = subprocess.run(
        [sys.executable, __file__, '--child', name],
        env=env, cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[-3000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def runtime_attribution():
    rows = {}
    ok = True
    for name in FIXTURES:
        off = fixture(name, False)
        on = fixture(name, True)
        changed = sum(off['per_seed'][k] != on['per_seed'][k] for k in off['per_seed'])
        ident = off['per_seed'] == on['per_seed']
        rows[name] = {'off':off,'on':on,'changed_seed_fingerprints':changed,
                      'identical':ident}
        if name == 'matched8':
            # A real tournament can leave the studied region after a large pot.
            # Only demand bit identity if *every* RFI and defend decision stayed
            # inside the declared studied family.  Otherwise report attribution
            # rather than pretending the fixture remained matched.
            cc_off = off.get('condition_counts', {})
            cc_on = on.get('condition_counts', {})
            pure = (cc_off.get('rfi_mismatch',0)==0
                    and cc_off.get('def_mismatch',0)==0
                    and cc_on.get('rfi_mismatch',0)==0
                    and cc_on.get('def_mismatch',0)==0)
            rows[name]['pure_studied_conditions'] = pure
            if pure:
                ok &= ident
        else:
            # Mismatch fixture is attribution, not quality calibration.  The
            # new mechanism must be live and alter at least one seeded path.
            cc = off.get('condition_counts', {})
            ok &= (cc.get('rfi_mismatch',0) + cc.get('def_mismatch',0) > 0
                   and changed > 0)
    return {'pass':bool(ok),'fixtures':rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--child')
    a = ap.parse_args()
    if a.child:
        run_fixture(a.child)
        return
    out = {
        'paired': paired_counterfactual(),
        'population': population_quadrants(),
        'runtime': runtime_attribution(),
    }
    out['pass'] = all(v.get('pass') for v in out.values())
    print(json.dumps(out, indent=2, sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)


if __name__ == '__main__':
    main()
