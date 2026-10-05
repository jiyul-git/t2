#!/usr/bin/env python3
"""Decision trace for the bot-timing design, with tournament stage per hand.

Same per-decision provenance as tools/beta_trace.py (preflop_plan inputs and
act_with_plan response equity), plus a stage map hash -> {remaining, itm, bb}
so late-stage (20-30bb, bubble / ITM) decisions can be measured directly.

  python tools/timing_trace.py SEED FIELD OUT.json [CAP]
    FIELD = uniform  r2 baseline field (max skill, neutral, frozen reads)
            real     generated population (persona.make_player), emotion and
                     read book restored
    CAP   = round cap (default: play to the end)

Design tool only.  No production behaviour changes.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import persona as PS
import play as PLY
import reads as RD
_ORIG = (PS.make_player, PLY.Hand.emotion_level, RD.Book.rec)

import beta_trace as BT          # noqa: E402  (applies r2 baseline patches)
import fieldsim as FS            # noqa: E402

import plan as PL                # noqa: E402

STAGE = {}
_grab = FS.Field._log_bot_hand
_LAST_DR = []
_dr = PL.decide_response


def decide_response(profile, hero, board, street, plan, plan_state, eq, need,
                    made_now, opp_range, pot, tocall, stack, committed, rng, **kw):
    """최종 콜/폴드 경계: 실제로 비교된 eq/need(레이어 콜이면 call_eq/call_need)."""
    r = _dr(profile, hero, board, street, plan, plan_state, eq, need,
            made_now, opp_range, pot, tocall, stack, committed, rng, **kw)
    act, mult, need_out, why = r
    layer = kw.get('call_eq') is not None and kw.get('call_need') is not None
    _LAST_DR.append({
        'dr_act': act, 'dr_layer': layer, 'dr_committed': bool(committed),
        'dr_eq_used': round(float(kw['call_eq'] if layer else eq), 4),
        'dr_need_used': round(float(need_out), 4),
        'dr_why': str(why)[:120]})
    return r


PL.decide_response = decide_response
_awp = BT._awp


def awp(hero, board, profile, plan_state, pot, tocall, stack, street, **kw):
    """beta_trace.awp 와 같은 기록 + decide_response 의 최종 비교값."""
    del _LAST_DR[:]
    r = _awp(hero, board, profile, plan_state, pot, tocall, stack, street, **kw)
    h = sys._getframe(1).f_locals.get('h')
    s = sys._getframe(1).f_locals.get('s')
    key = (getattr(h, 'hash', None), street, s)
    (a, amt), eq, need = r
    rec = {
        'resp_eq': (round(float(eq), 4) if eq is not None else None),
        'resp_need': (round(float(need), 4) if need is not None else None),
        'resp_src': plan_state.get('_last_response_source'),
        'response_kind': kw.get('response_kind'),
        'calc_act': a, 'calc_amt': amt}
    if _LAST_DR:
        rec.update(_LAST_DR[-1])
    BT.RESP.setdefault(key, []).append(rec)
    return r


PL.act_with_plan = awp


def grab(self, tb, h, run):
    STAGE[h.hash] = {'remaining': self.remaining(), 'itm': self.itm, 'bb': h.bb,
                     'entries': self.entries}
    _grab(self, tb, h, run)


FS.Field._log_bot_hand = grab


def main():
    seed, field, out = sys.argv[1], sys.argv[2], sys.argv[3]
    cap = sys.argv[4] if len(sys.argv) > 4 else '100000'
    if field == 'real':
        PS.make_player, PLY.Hand.emotion_level, RD.Book.rec = _ORIG
    elif field != 'uniform':
        raise SystemExit('FIELD must be uniform or real')
    sys.argv = ['x', seed, cap]
    BT.SIM.main()
    json.dump({'seed': int(seed), 'field': field, 'cap': int(cap), 'pf': BT.SIM.PF,
               'hands': BT.HANDS, 'stage': STAGE}, open(out, 'w'), default=str)


if __name__ == '__main__':
    main()
