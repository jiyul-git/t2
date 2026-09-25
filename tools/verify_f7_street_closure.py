#!/usr/bin/env python3
"""Targeted verifier for F7 postflop street-closure carry fixes."""
import os
import sys
import inspect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import session as SE


def _hr():
    h = object.__new__(SE.HandRun)
    h._pot_at = {'flop': 100, 'turn': 300}
    h.full_log = []
    h.full_action_meta = []
    return h


def _m(seat, action, increment, raised=False, full=False,
       incomplete=False, allin_call=False, street=None):
    return {
        'seat': seat,
        'action': action,
        'increment': float(increment),
        'raised': bool(raised),
        'full_raise': bool(full),
        'incomplete_raise': bool(incomplete),
        'allin_call': bool(allin_call),
        'street': street,
    }


def test_completed_raise_uses_action_time_pot():
    h = _hr()
    h.full_action_meta = [
        _m(1, 'bet', 50, raised=True, full=True, street='flop'),
        _m(2, 'raise', 150, raised=True, full=True, street='flop'),
    ]
    got = SE.HandRun._acts_of(h, 2)
    assert len(got) == 1, got
    st, act, frac = got[0]
    assert st == 'flop' and act == 'raise', got
    assert abs(frac - 1.0) < 1e-12, got
    return got


def test_completed_allin_call_is_call():
    h = _hr()
    h.full_action_meta = [
        _m(1, 'bet', 50, raised=True, full=True, street='flop'),
        _m(2, 'allin', 50, allin_call=True, street='flop'),
    ]
    got = SE.HandRun._acts_of(h, 2)
    assert got[0][1] == 'call', got
    assert abs(got[0][2] - (50.0/150.0)) < 1e-12, got
    return got


def test_current_allin_call_is_call():
    h = _hr()
    meta = [
        _m(1, 'bet', 100, raised=True, full=True),
        _m(2, 'allin', 100, allin_call=True),
    ]
    got = SE.HandRun._acts_of(
        h, 2, current_street='turn', current_meta=meta)
    assert got[0][1] == 'call', got
    # turn starts 300, bettor adds 100 -> caller acts into 400
    assert abs(got[0][2] - 0.25) < 1e-12, got
    return got


def test_street_outcome_classes():
    bet = _m(1, 'bet', 50, raised=True, full=True)
    normal = _m(2, 'call', 50)
    ai = _m(3, 'allin', 50, allin_call=True)

    one = SE._postflop_street_outcome([bet, normal])
    one_ai = SE._postflop_street_outcome([bet, ai])
    multi_ai = SE._postflop_street_outcome([bet, normal, ai])
    folds = SE._postflop_street_outcome([
        bet, _m(2, 'fold', 0), _m(3, 'fold', 0)])
    checks = SE._postflop_street_outcome([
        _m(1, 'check', 0), _m(2, 'check', 0)])

    assert one['kind'] == 'one_call', one
    assert one_ai['kind'] == 'one_allin_call', one_ai
    assert multi_ai['kind'] == 'multi_call_with_allin', multi_ai
    assert folds['kind'] == 'all_fold', folds
    assert checks['kind'] == 'checkthrough', checks
    return [one['kind'], one_ai['kind'], multi_ai['kind'],
            folds['kind'], checks['kind']]


def test_showdown_uses_rule_event_aggression():
    src = inspect.getsource(SE.HandRun._finish)
    assert "full_action_meta" in src, src
    assert "m.get('raised')" in src, src
    return True


def main():
    a = test_completed_raise_uses_action_time_pot()
    b = test_completed_allin_call_is_call()
    c = test_current_allin_call_is_call()
    d = test_street_outcome_classes()
    e = test_showdown_uses_rule_event_aggression()

    print("PASS completed raise uses action-time pot", a)
    print("PASS completed all-in call carries as call", b)
    print("PASS current all-in call narrows as call", c)
    print("PASS POST-F street outcomes are explicit", d)
    print("PASS showdown aggression uses rule-event metadata", e)
    print("5/5 F7 structural checks passed")


if __name__ == '__main__':
    main()
