#!/usr/bin/env python3
"""Targeted verifier for P3 first-open audit fixes."""

import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import preflop as PF


def profile(thin_turn):
    return {
        'type': 'TAG',
        'concepts': {
            'pf_defend': 6.0,
            'pf_range': 6.0,
            'spr': 6.0,
            'bluff': 5.0,
            'thin_value_turn': thin_turn,
            'thin_value_river': 5.0,
            'range_read': 6.0,
            'sizing_tell': 6.0,
            'icm': 5.0,
        },
        'temper': {
            'aggression': 3.5,
            'looseness': 5.0,
            'gamble': 5.0,
            'discipline': 5.0,
            'attention': 6.0,
            'adaptability': 6.0,
            'consistency': 6.0,
            'slowplay_taste': 7.0,
        },
    }


def test_thin_value_no_longer_changes_preflop_response():
    # Same seed/state, only postflop thin-value skill differs.
    # Outputs must be identical now that the domain leak is removed.
    outs = []
    for tv in (0.0, 10.0):
        p = profile(tv)
        r = random.Random(918273)
        out = PF.defend_decision(
            p, 'BTN', 'CO', ['As','Kd'],
            bb=40.0, open_bb=2.5, n_callers=0, rng=r,
            raise_level=1, stack_bb=40.0,
            exploit=None, bf=1.0, seats=8, ante=True,
            opener_allin=False,
        )
        outs.append(out)
    assert outs[0] == outs[1], outs
    return outs


def test_callers_change_squeeze_context():
    p = profile(5.0)
    a = PF.defend_thresholds(p, 'BTN', 'CO', 40.0, 2.5, 0, 1, 8, True)
    b = PF.defend_thresholds(p, 'BTN', 'CO', 40.0, 2.5, 2, 1, 8, True)
    assert a != b, (a, b)
    return a, b


def test_raise_level_one_is_first_open():
    # reraise_mult documents level=1 as a 3bet over the first open.
    ip = PF.reraise_mult(1, 'BTN')
    oop = PF.reraise_mult(1, 'BB')
    assert ip > 1.0 and oop > ip, (ip, oop)
    return ip, oop


def main():
    x = test_thin_value_no_longer_changes_preflop_response()
    y = test_callers_change_squeeze_context()
    z = test_raise_level_one_is_first_open()

    print("PASS postflop thin_value no longer changes P3 response", x)
    print("PASS caller count changes squeeze/defense context", y)
    print("PASS first-open raise level maps to 3bet sizing", z)
    print("3/3 P3 structural checks passed")


if __name__ == '__main__':
    main()
