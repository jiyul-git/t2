#!/usr/bin/env python3
"""Targeted structural verifier for P6 all-in/call-off fixes."""
import os
import sys
import random
import inspect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU
import preflop as PF
import plan as PL


def profile():
    return {
        'type': 'TAG',
        'concepts': {
            'pf_defend': 6.0, 'pf_range': 6.0, 'spr': 6.0,
            'icm': 6.0, 'bluff': 5.0,
        },
        'temper': {
            'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0,
            'discipline': 5.0, 'slowplay_taste': 5.0,
        },
    }


def test_stack_exhausting_call_is_allin_call():
    r = RU.Round(None, [1,2], {1:8,2:0}, 1,
                 current_bet=10, min_raise=2, contrib={1:2,2:10})
    r.allin.add(2)
    r.apply(1, 'call')
    m = r.action_meta[-1]
    assert m['action'] == 'call', m
    assert m['allin_call'] is True, m
    assert 1 in r.allin, r.allin
    return m


def test_short_shove_no_responder_routes_calloff_and_real_price():
    p = profile()
    seen = {}
    orig = PF.calloff_decision
    try:
        def fake(*args, **kwargs):
            # args: prof, pos, hand, bb, level, pot, tocall, ...
            seen['pot'] = args[5]
            seen['tocall'] = args[6]
            return (('call', args[6]), 0.25)
        PF.calloff_decision = fake
        out = PF.defend_decision(
            p, 'BB', 'BTN', ['As','Kd'],
            bb=100.0, open_bb=20.0, n_callers=0,
            rng=random.Random(1), raise_level=1, stack_bb=100.0,
            exploit=None, bf=1.0, seats=8, ante=True,
            opener_allin=True, can_raise=False,
            pot_bb=23.5, to_call_bb=19.0)
    finally:
        PF.calloff_decision = orig

    assert out == ('call', 19.0), out
    assert seen == {'pot': 23.5, 'tocall': 19.0}, seen
    return out, seen


def test_short_shove_live_responder_keeps_raise_branch_available():
    p = profile()
    called = {'n': 0}
    orig = PF.calloff_decision
    try:
        def fake(*args, **kwargs):
            called['n'] += 1
            return (('fold',0), 0.0)
        PF.calloff_decision = fake
        # With another live responder, opener_allin alone must not force pure calloff.
        PF.defend_decision(
            p, 'BTN', 'CO', ['As','Ah'],
            bb=100.0, open_bb=20.0, n_callers=0,
            rng=random.Random(3), raise_level=1, stack_bb=100.0,
            exploit=None, bf=1.0, seats=8, ante=True,
            opener_allin=True, can_raise=True,
            pot_bb=23.5, to_call_bb=20.0)
    finally:
        PF.calloff_decision = orig
    assert called['n'] == 0, called
    return True


def test_contestable_sidepot_cap():
    # Hero can reach only 20 total; opponents have 50 each.
    r = RU.Round(None, [1,2,3], {1:10,2:0,3:0}, 1,
                 current_bet=50, min_raise=10,
                 contrib={1:10,2:50,3:50})
    r.allin.update({2,3})
    # hero cap = 10 already in + 10 left = 20; each opponent contributes at most 20
    assert r.contestable_contrib(1) == 60, r.contestable_contrib(1)
    assert r.to_call(1) == 10, r.to_call(1)
    return r.contestable_contrib(1), r.to_call(1)


def test_p6_context_fields_in_seed():
    src = inspect.getsource(PL.preflop_plan)
    for key in ('pf_facing_allin','pf_pot_bb','pf_to_call_bb','pf_can_raise'):
        assert key in src, key
    return True


def main():
    a = test_stack_exhausting_call_is_allin_call()
    b = test_short_shove_no_responder_routes_calloff_and_real_price()
    c = test_short_shove_live_responder_keeps_raise_branch_available()
    d = test_contestable_sidepot_cap()
    e = test_p6_context_fields_in_seed()

    print("PASS stack-exhausting call is all-in call", a)
    print("PASS short shove/no responder routes calloff with exact price", b)
    print("PASS live responder preserves non-calloff-only branch", c)
    print("PASS contestable pot excludes unreachable side-pot chips", d)
    print("PASS P6 context survives in plan seed", e)
    print("5/5 P6 structural checks passed")


if __name__ == '__main__':
    main()
