#!/usr/bin/env python3
"""Targeted verifier for P5 preflop back-action fixes."""
import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU
import session as SE
import reads as RD
import preflop as PF


def profile():
    return {
        'type': 'TAG',
        'concepts': {
            'pf_defend': 6.0, 'pf_range': 6.0, 'spr': 6.0,
            'bluff': 5.0, 'icm': 5.0,
        },
        'temper': {
            'aggression': 7.0, 'looseness': 5.0, 'gamble': 5.0,
            'discipline': 5.0, 'slowplay_taste': 4.0,
        },
    }


def test_allin_call_not_raise():
    r = RU.Round(None, [1,2], {1:100,2:5}, 1, current_bet=10, min_raise=10)
    r.apply(2, 'allin')
    m = r.action_meta[-1]
    assert m['allin_call'] is True, m
    assert m['raised'] is False, m
    assert r.full_raise_count == 0, r.full_raise_count
    aggr, callers, limpers = SE._update_pf_state_after_apply(r, 2, 1, 0, [])
    assert aggr == 1 and callers == 1, (aggr, callers, limpers)
    return m


def test_incomplete_raise_not_full_level():
    r = RU.Round(None, [1,2,3], {1:100,2:15,3:100}, 1,
                 current_bet=10, min_raise=10)
    r.apply(2, 'allin')
    m = r.action_meta[-1]
    assert m['raised'] is True, m
    assert m['incomplete_raise'] is True, m
    assert m['full_raise'] is False, m
    assert r.full_raise_count == 0, r.full_raise_count
    return m


def _m(seat, action, full=False):
    return {
        'seat': seat, 'action': action,
        'full_raise': bool(full),
        'raised': bool(full),
        'allin_call': False,
    }


def test_role_clean_observation():
    # seat1 open, seat2 call, seat3 squeeze, seat1 call, seat2 fold
    seq = [
        _m(1,'raise',True),
        _m(2,'call',False),
        _m(3,'raise',True),
        _m(1,'call',False),
        _m(2,'fold',False),
    ]
    o1 = SE._pf_observation_flags(seq, 1)
    o2 = SE._pf_observation_flags(seq, 2)
    assert o1['faced_threebet_as_opener'] is True, o1
    assert o1['folded_to_threebet_as_opener'] is False, o1
    assert o2['faced_threebet_as_opener'] is False, o2
    assert o2['backraise_chance_as_caller'] is True, o2
    assert o2['folded_to_squeeze_after_call'] is True, o2
    return o1, o2


def test_backraise_separate():
    seq = [
        _m(1,'raise',True),
        _m(2,'call',False),
        _m(3,'raise',True),
        _m(1,'fold',False),
        _m(2,'raise',True),
    ]
    o2 = SE._pf_observation_flags(seq, 2)
    assert o2['did_backraise'] is True, o2
    assert o2['fourbet_chance_as_opener'] is False, o2
    return o2


def test_old_book_hydrates():
    b = RD.Book()
    key = b._k('o','t')
    b.d[key] = {'hands': 3}
    r = b.rec('o','t')
    assert r['hands'] == 3
    for k in ('pf_backraise_opp','pf_call_faced_squeeze',
              'pf_faced_limp_raise','rfi_opp'):
        assert k in r, (k, r)
    return True


def test_closed_raise_right_removes_raise_plan():
    p = profile()
    outs = []
    for seed in range(30):
        out = PF.defend_decision(
            p, 'BTN', 'CO', ['As','Ah'],
            bb=40.0, open_bb=8.0, n_callers=0,
            rng=random.Random(seed), raise_level=2, stack_bb=40.0,
            exploit=None, bf=1.0, seats=8, ante=True,
            opener_allin=False, can_raise=False)
        outs.append(out[0])
    assert not any(a in ('3bet','raise','shove') for a in outs), outs
    return sorted(set(outs))


def main():
    a = test_allin_call_not_raise()
    b = test_incomplete_raise_not_full_level()
    c = test_role_clean_observation()
    d = test_backraise_separate()
    e = test_old_book_hydrates()
    f = test_closed_raise_right_removes_raise_plan()

    print("PASS all-in call is not a raise", a)
    print("PASS incomplete raise does not increment full-raise level", b)
    print("PASS opener fold-to-3bet separated from caller squeeze response", c)
    print("PASS caller backraise is separate observation", d)
    print("PASS old read records hydrate new schema", e)
    print("PASS closed raise rights remove raise plans", f)
    print("6/6 P5 structural checks passed")


if __name__ == '__main__':
    main()
