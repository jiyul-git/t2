#!/usr/bin/env python3
"""Beta A: judgment -> plan -> execution trace on the max-skill uniform field.

Field = tools/r2_baseline_sim.py conditions (every bot max skill, neutral
temperament, tilt 0, read book frozen).  With no persona noise, a decision that
looks wrong is a bug, a missing concept or a coefficient problem.

Collected per decision (no RNG consumed; the digest equals the plain sim):
  preflop   preflop_plan inputs/outputs (hand_pct, spot, act, size) + the action
            actually applied by the engine.
  postflop  session intent record (judgment facts, plan, intent, calculated act /
            target, execution provenance) + act_with_plan's response equity and
            required equity (not stored by the engine).

  python tools/beta_trace.py SEED [CAP] OUT.json
"""
import copy, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import plan as PL
import fieldsim as FS

RESP = {}          # (hash, street, seat) -> [ {eq, need, src, kind}, ... ]
_awp = PL.act_with_plan


def awp(hero, board, profile, plan_state, pot, tocall, stack, street, **kw):
    r = _awp(hero, board, profile, plan_state, pot, tocall, stack, street, **kw)
    h = sys._getframe(1).f_locals.get('h')
    s = sys._getframe(1).f_locals.get('s')
    key = (getattr(h, 'hash', None), street, s)
    (a, amt), eq, need = r
    RESP.setdefault(key, []).append({
        'resp_eq': (round(float(eq), 4) if eq is not None else None),
        'resp_need': (round(float(need), 4) if need is not None else None),
        'resp_src': plan_state.get('_last_response_source'),
        'response_kind': kw.get('response_kind'),
        'calc_act': a, 'calc_amt': amt})
    return r


PL.act_with_plan = awp

DROP = {'my_range', 'opp_range', 'opp_ranges', 'trace', 'why_by_street'}
HANDS = []
_grab = FS.Field._log_bot_hand


def grab(self, tb, h, run):
    _grab(self, tb, h, run)
    res = getattr(run, 'result', None) or {}
    ints = []
    cnt = {}
    for it in getattr(h, 'intents', []) or []:
        x = {k: v for k, v in it.items() if k not in DROP}
        key = (h.hash, it.get('street'), it.get('seat'))
        i = cnt.get(key, 0)
        lst = RESP.get(key) or []
        if i < len(lst):
            x.update(lst[i])
        cnt[key] = i + 1
        ints.append(x)
    HANDS.append({'hash': h.hash, 'bb': h.bb, 'pos': {str(k): v for k, v in h.pos.items()},
                  'hole': {str(k): v for k, v in h.hole.items()},
                  'board': res.get('board'), 'full_log': res.get('full_log'),
                  'how': res.get('how'), 'winners': res.get('winners'),
                  'stacks_before': {str(k): v for k, v in (getattr(h, '_start_stacks', {}) or {}).items()},
                  'intents': ints})


FS.Field._log_bot_hand = grab


def main():
    seed = sys.argv[1]
    cap = sys.argv[2] if len(sys.argv) > 2 else '60'
    out = sys.argv[3]
    sys.argv = ['x', seed, cap]
    SIM.main()
    blob = {'seed': int(seed), 'cap': int(cap), 'pf': SIM.PF, 'hands': HANDS}
    json.dump(blob, open(out, 'w'), default=str)


if __name__ == '__main__':
    main()
