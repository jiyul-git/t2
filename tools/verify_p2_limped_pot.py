#!/usr/bin/env python3
"""Targeted verifier for P2 limped-pot fixes.

No production state or baselines are modified.
"""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import preflop as PF
import reads as RD
import persona as PS
import session as SE


def _prof():
    return {
        'type': 'TAG',
        'concepts': {
            'pf_range': 6.0, 'positional': 6.0, 'spr': 6.0,
            'bluff': 5.0, 'icm': 5.0, 'range_read': 8.0,
            'sizing_tell': 8.0,
        },
        'temper': {
            'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0,
            'discipline': 5.0, 'attention': 8.0, 'adaptability': 8.0,
            'consistency': 5.0,
        },
    }


class HighRoll:
    def random(self):
        return 0.999999


def test_rfi_count_once_and_limp_raise_channel():
    b = RD.Book()
    obs = ['o', 't']
    b.observe_preflop(obs, 't', vpip=True, pfr=False,
                      limp=True, limp_chance=True, rfi_exp=0.25)
    r = b.rec('o', 't')
    assert r['rfi_opp'] == 1, r
    assert abs(r['rfi_exp'] - 0.25) < 1e-12, r
    assert r['rfi_did'] == 0, r

    b.observe_limp_raise(obs, 't', True, True)
    r = b.rec('o', 't')
    assert r['pf_faced_limp_raise'] == 1, r
    assert r['pf_fold_after_limp_raise'] == 1, r

    rd = PS.read_opponent(
        _prof(),
        {'confidence': 1.0, 'n': 20, 'pf_fold_after_limp_raise': 0.90}
    )
    assert 'f2iso_gap' in rd, rd
    assert rd['f2iso_gap'] > 0.0, rd
    return rd['f2iso_gap']


def test_iso_no_second_roll_premium():
    prof = _prof()
    old_open, old_feel = PF._open, PF.feel_of
    old_tp, old_hp = PF.table_pressure, PF.hotzone_pressure
    try:
        PF._open = lambda *a, **k: 0.25
        PF.feel_of = lambda *a, **k: 0.5
        PF.table_pressure = lambda x: 1.0
        PF.hotzone_pressure = lambda *a, **k: 1.0
        act, sz = PF.iso_decision(
            prof, 'HJ', ['As', 'Ah'], 1, 40.0, HighRoll(),
            seats=8, ante=True
        )
    finally:
        PF._open, PF.feel_of = old_open, old_feel
        PF.table_pressure, PF.hotzone_pressure = old_tp, old_hp
    assert act == 'raise', (act, sz)
    return act, sz


def test_actual_context_reaches_open_lookup():
    prof = _prof()
    seen = {}
    old_open, old_feel = PF._open, PF.feel_of
    old_tp, old_hp = PF.table_pressure, PF.hotzone_pressure
    try:
        def fake_open(_prof, pos, seats=8, bb=100.0, ante=True):
            seen.update(pos=pos, seats=seats, bb=bb, ante=ante)
            return 0.25
        PF._open = fake_open
        PF.feel_of = lambda *a, **k: 0.5
        PF.table_pressure = lambda x: 1.0
        PF.hotzone_pressure = lambda *a, **k: 1.0
        PF.iso_decision(
            prof, 'CO', ['As', 'Ah'], 2, 22.0, HighRoll(),
            seats=6, ante=False
        )
    finally:
        PF._open, PF.feel_of = old_open, old_feel
        PF.table_pressure, PF.hotzone_pressure = old_tp, old_hp
    assert seen == {'pos': 'CO', 'seats': 6, 'bb': 22.0, 'ante': False}, seen
    return seen


def test_bb_option_is_explicit_check():
    prof = _prof()
    old_open, old_feel = PF._open, PF.feel_of
    old_tp, old_hp = PF.table_pressure, PF.hotzone_pressure
    try:
        PF._open = lambda *a, **k: 0.0
        PF.feel_of = lambda *a, **k: 0.5
        PF.table_pressure = lambda x: 1.0
        PF.hotzone_pressure = lambda *a, **k: 1.0
        act, sz = PF.iso_decision(
            prof, 'BB', ['7c', '2d'], 2, 40.0, HighRoll(),
            seats=8, ante=True, can_check=True
        )
    finally:
        PF._open, PF.feel_of = old_open, old_feel
        PF.table_pressure, PF.hotzone_pressure = old_tp, old_hp
    assert (act, sz) == ('check', 0), (act, sz)
    return act, sz


def test_pf_action_drives_range_role():
    h = SimpleNamespace(
        pf_seed={
            1: {'pf_role': 'iso', 'pf_act': 'check'},
            2: {'pf_role': 'iso', 'pf_act': 'limp'},
            3: {'pf_role': 'defend', 'pf_act': 'raise'},
        },
        pos={1: 'BB', 2: 'CO', 3: 'BTN'}
    )
    hr = object.__new__(SE.HandRun)
    hr.h = h
    got = (
        SE.HandRun._pf_range_action(hr, 1, None),
        SE.HandRun._pf_range_action(hr, 2, None),
        SE.HandRun._pf_range_action(hr, 3, None),
    )
    assert got == ('check', 'limp', '3bet'), got
    return got


def main():
    fg = test_rfi_count_once_and_limp_raise_channel()
    premium = test_iso_no_second_roll_premium()
    ctx = test_actual_context_reaches_open_lookup()
    bb = test_bb_option_is_explicit_check()
    roles = test_pf_action_drives_range_role()

    print("PASS RFI counted once + dedicated limp-raise fold read", round(fg, 4))
    print("PASS premium iso cannot fail a second iso roll", premium)
    print("PASS actual seats/stack/ante reach iso base", ctx)
    print("PASS BB free option is explicit check", bb)
    print("PASS pf action drives postflop range role", roles)
    print("5/5 P2 structural checks passed")


if __name__ == '__main__':
    main()
