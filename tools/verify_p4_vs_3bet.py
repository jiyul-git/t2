#!/usr/bin/env python3
"""Targeted structural verifier for P4 opener-facing-3bet fixes."""
import os
import sys
import inspect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import reads as RD
import ranges as R
import session as SE


def prof():
    return {
        'type': 'TAG',
        'concepts': {
            'pf_range': 6.0, 'pf_defend': 6.0, 'positional': 6.0,
            'bluff': 5.0, 'spr': 6.0,
        },
        'temper': {
            'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0,
            'discipline': 5.0, 'adaptability': 5.0,
            'consistency': 5.0, 'attention': 5.0,
            'slowplay_taste': 5.0,
        },
    }


def test_story_merge():
    first = {
        'pf_role': 'open', 'pf_act': 'raise', 'pf_vs': None,
        'pf_level': 1, 'pf_open_bb': 0.0,
        'pf_n_callers': 0, 'pf_n_limpers': 0,
    }
    a = SE._merge_pf_seed(None, first)
    second = {
        'pf_role': 'defend', 'pf_act': 'call', 'pf_vs': 'BTN',
        'pf_level': 2, 'pf_open_bb': 8.5,
        'pf_n_callers': 0, 'pf_n_limpers': 0,
    }
    b = SE._merge_pf_seed(a, second)
    assert b['pf_origin_role'] == 'open', b
    assert b['pf_origin_act'] == 'raise', b
    assert len(b['pf_line']) == 2, b
    assert b['pf_line'][0]['act'] == 'raise', b
    assert b['pf_line'][1]['act'] == 'call', b
    assert b['pf_line'][1]['level'] == 2, b
    return b['pf_line']


def test_level_aware_range():
    p = prof()
    r1 = R.preflop_range(
        p, 'CO', 'call', 40.0, set(),
        opener_pos='BTN', open_bb=8.5, seats=8, ante=True, raise_level=1)
    r2 = R.preflop_range(
        p, 'CO', 'call', 40.0, set(),
        opener_pos='BTN', open_bb=8.5, seats=8, ante=True, raise_level=2)
    assert len(r1) != len(r2), (len(r1), len(r2))
    return len(r1), len(r2)


def test_public_range_profile():
    perceived = {
        'aggr': 7.5, 'tight': 6.0,
        'est_concepts': {
            'pf_range': 6.2, 'pf_defend': 5.7, 'positional': 6.1,
            'bluff': 5.4, 'spr': 5.9,
        }
    }
    rp = RD.range_profile(perceived)
    assert abs(rp['temper']['aggression'] - 7.5) < 1e-12, rp
    assert abs(rp['temper']['looseness'] - 4.0) < 1e-12, rp
    assert rp['concepts']['pf_range'] == 6.2, rp
    return rp['temper']['aggression'], rp['temper']['looseness']


def test_no_true_opponent_axes_in_range_loop():
    src = inspect.getsource(SE.HandRun._run)
    assert "h.axes(o)" not in src, "opponent true axes still used in HandRun._run"
    assert "RD.range_profile(_oe)" in src, "perceived range profile not wired"
    return True


def test_context_fields_exist():
    # Structural source check: fields must be written by preflop_plan and consumed postflop.
    import plan as PL
    psrc = inspect.getsource(PL.preflop_plan)
    ssrc = inspect.getsource(SE.HandRun._run)
    for key in ("pf_open_bb", "pf_n_callers", "pf_level"):
        assert key in psrc, key
        assert key in ssrc, key
    return True


def main():
    line = test_story_merge()
    lens = test_level_aware_range()
    temper = test_public_range_profile()
    hidden = test_no_true_opponent_axes_in_range_loop()
    ctx = test_context_fields_exist()

    print("PASS preflop line preserved", line)
    print("PASS raise level changes reconstructed continuation range", lens)
    print("PASS perceived-only opponent range profile", temper)
    print("PASS no true opponent axes in range loop", hidden)
    print("PASS response context fields survive into range reconstruction", ctx)
    print("5/5 P4 structural checks passed")


if __name__ == '__main__':
    main()
