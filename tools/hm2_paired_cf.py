#!/usr/bin/env python3
"""Human Model v2 — same-state paired attribution of the GTO_MEMORY_V2 flag.

Runs a fixture with the flag OFF (the executed trajectory = current behaviour) and at
every preflop decision (session.py:1357 PL.preflop_plan) re-evaluates the SAME state
with the flag ON. h.rng is snapshot/restored and dict/list args are deep-copied, so
the game does not diverge. Records action flips by situation / position / stack /
hand class, plus the rfi / defend condition-match at that state.

  python3 tools/hm2_paired_cf.py --fixture regress9|turbo8 --out out.json
"""
import argparse
import collections
import copy
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    import verify_human_model_v2 as V
    import persona as PS
    import plan as PL
    import preflop as PF
    import tourney as T
    PS.GTO_MEMORY_V2 = False
    orig = PL.preflop_plan
    rows = []
    ctx = {'seed': None, 'h': -1}

    def cp(x):
        return copy.deepcopy(x) if isinstance(x, (dict, list)) else x

    def wrap(profile, pos, hand, bb, rng, **kw):
        fr = sys._getframe(1)
        rnd, s = fr.f_locals.get('rnd'), fr.f_locals.get('s')
        first = not any(x[0] == s for x in (getattr(rnd, 'log', []) or []))
        st0 = rng.getstate()
        new = orig(profile, pos, hand, bb, rng, **kw)
        st1 = rng.getstate()
        rng.setstate(st0)
        PS.GTO_MEMORY_V2 = True
        try:
            alt = orig(cp(profile), pos, hand, bb, rng, **{k: cp(v) for k, v in kw.items()})
            st_alt = rng.getstate()
        finally:
            PS.GTO_MEMORY_V2 = False
            rng.setstate(st1)
        ag = kw.get('aggressor_pos')
        sit = ('unopened' if ag is None and not kw.get('n_limpers') else
               'vs_limp' if ag is None else
               'vs_open' if int(kw.get('raise_level') or 1) <= 1 else 'vs_3bet+')
        seats, ante = kw.get('seats', 8), kw.get('ante', True)
        m_rfi = PS.gto_condition_match('rfi', pos, seats, bb, ante)
        m_def = (PS.gto_condition_match('defend', pos, seats, bb, ante, opener_pos=ag,
                                        open_bb=kw.get('open_bb') or 2.5)
                 if ag and pos in ('BB', 'SB', 'BTN', 'CO') else None)
        rows.append({'seed': ctx['seed'], 'h': ctx['h'], 'sit': sit, 'pos': pos,
                     'bb': round(float(bb), 1), 'hand': PF.cls(hand),
                     'pct': round(PF.pct(hand), 4), 'first': first,
                     'off': new[0], 'on': alt[0], 'rng_diff': st1 != st_alt,
                     'match_rfi': round(m_rfi, 3),
                     'match_def': None if m_def is None else round(m_def, 3),
                     'looseness': PS.temper(profile, 'looseness', 5.0),
                     'pf_range': PS.sk(profile, 'pf_range'),
                     'pf_defend': PS.sk(profile, 'pf_defend')})
        return new

    PL.preflop_plan = wrap
    fx = V.FIXTURES[a.fixture]
    o_init, o_next = T.Tournament.__init__, T.Tournament.next_hand

    def init(self, *x, **kw):
        ctx['seed'], ctx['h'] = kw.get('seed'), -1
        return o_init(self, *x, **kw)

    def nxt(self, *x, **kw):
        ctx['h'] += 1
        return o_next(self, *x, **kw)
    T.Tournament.__init__, T.Tournament.next_hand = init, nxt
    for sd in fx['seeds']:
        t = T.Tournament(seed=sd, **fx['kw'])
        for _ in range(30):
            if sum(1 for q in t.seats if t.stacks[q] > 0) < 3:
                break
            s0 = t.next_hand()
            g = 0
            while s0 and not s0.get('done') and g < 200:
                s0 = t.submit('fold')
                g += 1
            t.finish_hand()
    flips = [r for r in rows if r['off'] != r['on']]
    C = collections.Counter
    summ = {'decisions': len(rows), 'flips': len(flips),
            'flip_types': dict(C('%s:%s>%s' % (r['sit'], r['off'], r['on']) for r in flips)),
            'by_pos': dict(C(r['pos'] for r in flips)),
            'by_stack': dict(C('<=100' if r['bb'] <= 100 else '>100' for r in flips)),
            'rng_only': sum(1 for r in rows if r['off'] == r['on'] and r['rng_diff']),
            'decisions_by_sit': dict(C(r['sit'] for r in rows)),
            'match_rfi_hist': dict(C(str(round(r['match_rfi'], 1)) for r in rows
                                     if r['sit'] in ('unopened', 'vs_limp')))}
    json.dump({'summary': summ, 'flips': flips}, open(a.out, 'w'), indent=1)
    print(json.dumps(summ))


if __name__ == '__main__':
    raise SystemExit(main())
