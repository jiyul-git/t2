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


# ---------- 프리플랍: 인간모델이 실제로 쓴 선택 경계 ----------
# 행위자 결정 함수만 감싼다(관찰자의 레인지 추론도 defend_action_likelihoods 를
# 부르므로 그 함수 자체는 감싸지 않는다). 재계산은 전부 RNG 없는 함수다.
import preflop as PFM            # noqa: E402

_BOUND = []
PF_EXTRA = []                    # SIM.PF 와 같은 순서·길이
_LIK_KEYS = ('raise_level', 'stack_bb', 'exploit', 'bf', 'seats', 'ante',
             'opener_allin', 'can_raise', 'pot_bb', 'to_call_bb')

_amot = PFM.apply_money_open_threshold


def apply_money_open_threshold(thr, r, money_open):
    out = _amot(thr, r, money_open)
    _BOUND.append({'kind': 'open', 'thr': float(out), 'r': float(r)})
    return out


PFM.apply_money_open_threshold = apply_money_open_threshold
_iso = PFM.iso_decision


def iso_decision(prof, pos, hand, n_limpers, bb, rng, limper_reads=None,
                 behind_stacks=None, behind_reads=None, seats=8, ante=True, **kw):
    # iso_decision 안의 최종 thr(림퍼 읽기 보정 후)를 같은 식으로 재계산한다.
    thr = PFM.iso_entry_threshold(prof, pos, bb, seats, ante, PFM._tr(prof),
                                  behind_reads, behind_stacks)
    _lv = [x for x in (limper_reads or []) if x and x.get('w', 0) > 0]
    if _lv:
        _n = float(len(_lv))
        _w = sum(x['w'] for x in _lv) / _n
        _fg = sum(x.get('f2iso_gap', 0.0) for x in _lv) / _n
        _ps = sum(x.get('passive', 0.0) for x in _lv) / _n
        _lg = max((x.get('limp_gap', 0.0) for x in _lv), default=0.0)
        thr *= max(0.70, min(1.60, 1.0 + _w*(0.45*max(0.0, _fg) + 0.25*max(0.0, _ps))
                             + 0.30*max(0.0, _lg)))
    _BOUND.append({'kind': 'iso', 'thr': float(thr),
                   'r': float(PFM.legacy_preflop_order_percentile(hand))})
    return _iso(prof, pos, hand, n_limpers, bb, rng, limper_reads=limper_reads,
                behind_stacks=behind_stacks, behind_reads=behind_reads,
                seats=seats, ante=ante, **kw)


PFM.iso_decision = iso_decision


def _lik_record(kind, prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, kw):
    lk = {k: kw[k] for k in _LIK_KEYS if k in kw}
    lik = PFM.defend_action_likelihoods(prof, def_pos, opener_pos, hand, bb,
                                        open_bb, n_callers, **lk)
    rec = {'kind': kind, 'r': float(lik['hand_pct'])}
    if lik['calloff']:
        rec.update(kind=kind + '_calloff', cap=float(lik['calloff_cap']))
    else:
        rec.update(tot=float(lik['tot']), tp=float(lik['tp']))
    return rec


_defend = PFM.defend_decision


def defend_decision(prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, rng, **kw):
    _BOUND.append(_lik_record('defend', prof, def_pos, opener_pos, hand, bb,
                              open_bb, n_callers, kw))
    return _defend(prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, rng, **kw)


PFM.defend_decision = defend_decision
_mw = PFM.multiway_reraise_decision


def multiway_reraise_decision(prof, def_pos, reraiser_pos, hand, bb, open_bb,
                              n_callers, rng, **kw):
    rec = _lik_record('multiway', prof, def_pos, reraiser_pos, hand, bb,
                      open_bb, n_callers, kw)
    out = _mw(prof, def_pos, reraiser_pos, hand, bb, open_bb, n_callers, rng, **kw)
    au = out[2] if len(out) > 2 and isinstance(out[2], dict) else {}
    if au.get('complete'):
        rec.update(eq=float(au['equity_vs_multiway_ranges']), need=float(au['need_seen']),
                   reason_skill=float(au.get('reason_skill', 0.0)))
    _BOUND.append(rec)
    return out


PFM.multiway_reraise_decision = multiway_reraise_decision
_pfp = PL.preflop_plan


def preflop_plan(ax, pos, hand, bbs, rng, **kw):
    # r2 의 pf_wrap 은 호출자 프레임의 h/s 를 읽는다. 여기 지역변수로 넘겨준다.
    h = sys._getframe(1).f_locals.get('h')     # noqa: F841
    s = sys._getframe(1).f_locals.get('s')     # noqa: F841
    del _BOUND[:]
    r = _pfp(ax, pos, hand, bbs, rng, **kw)
    seed = r[2] or {}
    co = seed.get('pf_calloff_consumer')
    ext = {'bounds': list(_BOUND)}
    if isinstance(co, dict) and co.get('strategy_consumer'):
        ext['calloff_layer'] = {
            'eq': co.get('layer_effective_equity'),
            'need': co.get('perceived_required_equity'),
            'act': co.get('selected_action')}
    PF_EXTRA.append(ext)
    return r


PL.preflop_plan = preflop_plan


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
    assert len(PF_EXTRA) == len(BT.SIM.PF), (len(PF_EXTRA), len(BT.SIM.PF))
    for _p, _x in zip(BT.SIM.PF, PF_EXTRA):
        _p['pf_bound'] = _x
    json.dump({'seed': int(seed), 'field': field, 'cap': int(cap), 'pf': BT.SIM.PF,
               'hands': BT.HANDS, 'stage': STAGE}, open(out, 'w'), default=str)


if __name__ == '__main__':
    main()
