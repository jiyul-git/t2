#!/usr/bin/env python3
"""Structural verification for canonical postflop action events."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import action_events as AE
import ranges as R
import runner as RU


def _round(stacks=None):
    return RU.Round(None, [1,2,3], stacks or {1:10000,2:10000,3:10000},
                    100, current_bet=0, min_raise=100)


def test_arbitrary_raise_depth():
    r = _round()
    r.apply(1, 'bet', 200)    # depth 1
    r.apply(2, 'raise', 500)  # depth 2
    r.apply(1, 'raise', 900)  # depth 3
    r.apply(2, 'raise', 1400) # depth 4
    ev = AE.postflop_events(r.action_meta, street='flop', pot_start=300)
    assert [e['raise_depth_full_after'] for e in ev] == [1,2,3,4], ev
    assert [e['facing_kind'] for e in ev] == [None,'bet','raise','raise'], ev
    assert ev[2]['response_kind'] == 'aggressor_backaction', ev[2]
    assert ev[3]['response_kind'] == 'aggressor_backaction', ev[3]
    assert abs(ev[1]['facing_price_frac'] - 0.4) < 1e-12, ev[1]
    assert abs(ev[2]['facing_price_frac'] - 0.3) < 1e-12, ev[2]
    ctx = AE.pending_response_context(r.action_meta, 1)
    assert ctx['raise_depth_full'] == 4, ctx
    assert ctx['kind'] == 'aggressor_backaction', ctx
    return ev, ctx


def test_allin_raise_vs_call_and_incomplete():
    # Full all-in raise.
    r = RU.Round(None, [1,2,3], {1:10000,2:1000,3:10000},
                 100, current_bet=0, min_raise=100)
    r.apply(1, 'bet', 300)
    r.apply(2, 'allin')
    ev = AE.postflop_events(r.action_meta, street='flop', pot_start=300)
    assert ev[-1]['allin_raise'] is True, ev[-1]
    assert ev[-1]['allin_call'] is False, ev[-1]
    assert ev[-1]['full_raise'] is True, ev[-1]

    # All-in call: target cannot exceed current.
    r2 = RU.Round(None, [1,2,3], {1:10000,2:250,3:10000},
                  100, current_bet=0, min_raise=100)
    r2.apply(1, 'bet', 300)
    r2.apply(2, 'call')
    ev2 = AE.postflop_events(r2.action_meta, street='flop', pot_start=300)
    assert ev2[-1]['allin_call'] is True, ev2[-1]
    assert ev2[-1]['allin_raise'] is False, ev2[-1]
    assert ev2[-1]['action_kind'] == 'call', ev2[-1]

    # Incomplete all-in raise: raises price but does not add full-raise depth.
    r3 = RU.Round(None, [1,2,3], {1:10000,2:450,3:10000},
                  100, current_bet=0, min_raise=100)
    r3.apply(1, 'bet', 300)       # min raise now 300
    r3.apply(2, 'allin')          # to 450, only +150 => incomplete
    ev3 = AE.postflop_events(r3.action_meta, street='flop', pot_start=300)
    assert ev3[-1]['incomplete_raise'] is True, ev3[-1]
    assert ev3[-1]['allin_raise'] is True, ev3[-1]
    assert ev3[-1]['raise_depth_full_after'] == 1, ev3[-1]
    assert ev3[-1]['raise_depth_any_after'] == 2, ev3[-1]
    ctx3 = AE.pending_response_context(r3.action_meta, 1)
    assert ctx3['facing_incomplete_raise'] is True, ctx3
    assert ctx3['facing_allin_raise'] is True, ctx3
    return ev[-1], ev2[-1], ev3[-1]


def test_raise_is_conditional_not_another_barrel():
    # Build rich events for actor 1: bet, then re-raise on same flop.
    r = _round()
    r.apply(1, 'bet', 200)
    r.apply(2, 'raise', 500)
    r.apply(1, 'raise', 900)
    acts = [e for e in AE.postflop_events(
        r.action_meta, street='flop', pot_start=300) if e['seat'] == 1]

    orig_bet = R._bet_range
    orig_cont = R._continue_range
    seen = {'barrels': [], 'continue': 0, 'continue_sizes': []}
    try:
        def fake_bet(rr, board, street, bluff, size, damp=1.0,
                     barrel=0.0, n_barrels=1):
            seen['barrels'].append(n_barrels)
            return rr
        def fake_cont(rr, board, street, size, damp=1.0):
            seen['continue'] += 1
            seen['continue_sizes'].append(size)
            return rr
        R._bet_range = fake_bet
        R._continue_range = fake_cont
        base = [('As','Kd'),('Ah','Kh'),('Qs','Qd'),('Jh','Th'),
                ('9s','8s'),('7h','6h'),('5c','4c'),('Ac','Jc'),
                ('Kc','Qc'),('Ts','9s'),('8c','7c'),('6s','5s'),
                ('Ad','Td'),('Kh','Jh'),('Qh','Th'),('9c','7c')]
        R.narrow_by_actions(base, ['Qh','9h','3s'], acts)
    finally:
        R._bet_range = orig_bet
        R._continue_range = orig_cont

    # Same-street re-raise remains barrel #1 and conditions on facing wager.
    assert seen['barrels'] == [1,1], seen
    assert seen['continue'] == 1, seen
    # Actor 1's re-raise faced 300 more into a 1000 pot: 30%, not the
    # opponent's 500-chip raise increment / prior pot.
    assert len(seen['continue_sizes']) == 1, seen
    assert abs(seen['continue_sizes'][0] - 0.3) < 1e-12, seen
    return seen


def test_allin_call_keeps_continue_semantics():
    base = [('As','Ad'),('Ks','Kd'),('Qs','Qd'),('Jh','Th'),
            ('9s','8s'),('7h','6h'),('5c','4c'),('Ac','Jc'),
            ('Kc','Qc'),('Ts','9s'),('8c','7c'),('6s','5s'),
            ('Ad','Td'),('Kh','Jh'),('Qh','Th'),('9c','7c')]
    event = {
        'street':'turn','action_kind':'call','size_frac':0.4,
        'facing_kind':'bet','facing_size_frac':0.8,
        'allin_call':True,'can_raise_before':False,
    }
    orig_call = R._call_range
    orig_cont = R._continue_range
    seen = {'call':0,'continue':0}
    try:
        R._call_range = lambda rr,*a,**k: (
            seen.__setitem__('call', seen['call']+1) or rr)
        R._continue_range = lambda rr,*a,**k: (
            seen.__setitem__('continue', seen['continue']+1) or rr)
        R.narrow_by_actions(base, ['Qh','9h','3s','2c'], [event])
    finally:
        R._call_range = orig_call
        R._continue_range = orig_cont
    assert seen == {'call':0,'continue':1}, seen
    return seen


def main():
    a, ctx = test_arbitrary_raise_depth()
    b1, b2, b3 = test_allin_raise_vs_call_and_incomplete()
    c = test_raise_is_conditional_not_another_barrel()
    d = test_allin_call_keeps_continue_semantics()
    print("PASS arbitrary full raise depth", [x['raise_depth_full_after'] for x in a])
    print("PASS pending response context", ctx)
    print("PASS full all-in raise", b1)
    print("PASS all-in call", b2)
    print("PASS incomplete all-in raise", b3)
    print("PASS same-street re-raise is not another barrel", c)
    print("PASS all-in call uses continue range", d)
    print("7/7 canonical postflop event checks passed")


if __name__ == '__main__':
    main()
