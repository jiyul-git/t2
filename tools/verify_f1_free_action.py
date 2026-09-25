#!/usr/bin/env python3
"""Targeted structural verifier for F1 no-wager fixes."""
import os
import sys
import inspect
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import plan as PL
import persona as PS


def profile(value_label):
    concepts = {k: 5.0 for k in PS.ALL_CONCEPTS}
    concepts.update({
        'range_merge': 6.5,
        'thin_value_turn': 1.0,
        'thin_value_river': 5.0,
        'stackoff': 5.0,
    })
    temper = {k: 5.0 for k in PS.TEMPER}
    p = {
        'type':'TAG',
        'concepts':concepts,
        'temper':temper,
        'aggr':5.0,
        'bluff':5.0,
        'gamble':5.0,
        'icm':5.0,
        'value':value_label,
    }
    return p


def test_permission_gate_once():
    refresh_src = inspect.getsource(PL.refresh)
    update_src = inspect.getsource(PL.update_plan)
    assert "_allowed(" not in refresh_src, refresh_src
    assert update_src.count("_allowed(") == 1, update_src.count("_allowed(")
    return True


def test_flop_thin_value_uses_range_merge():
    assert PS.street_concept('thin_value','flop') == 'range_merge'
    assert PS.street_concept('thin_value','turn') == 'thin_value_turn'
    assert PS.street_concept('thin_value','river') == 'thin_value_river'
    return (
        PS.street_concept('thin_value','flop'),
        PS.street_concept('thin_value','turn'),
        PS.street_concept('thin_value','river'),
    )


def test_derived_value_label_no_longer_changes_value_bet_probability():
    args = dict(
        board=['As','7d','2c'],
        street='flop',
        plan='value_3street',
        rel=0.82,
        n_opp=1,
        oop=False,
        initiative=True,
        to_act_behind=0,
        rng=random.Random(123),
        opp_est=None,
        outs=0,
        plan_state={'range_adv':0.0},
        oop_vs_aggr=False,
        oop_legacy_abs=False,
    )
    a = PL.decide_aggression(profile('xr'), **args)
    args['rng'] = random.Random(123)
    b = PL.decide_aggression(profile('lead'), **args)
    assert a == b, (a,b)
    return a,b


def test_blockbet_label_gate_is_legacy_only():
    src = inspect.getsource(PL.make_plan)
    # The F1 blockbet fish-label modifier must be guarded by absence of concepts.
    needle = "not profile.get('concepts')"
    assert needle in src, "vector profile still lacks legacy-only label guard"
    return True


def main():
    a=test_permission_gate_once()
    b=test_flop_thin_value_uses_range_merge()
    c=test_derived_value_label_no_longer_changes_value_bet_probability()
    d=test_blockbet_label_gate_is_legacy_only()

    print("PASS plan permission gate occurs once", a)
    print("PASS flop thin-value maps to range_merge", b)
    print("PASS compatibility value label no longer changes value betting", c)
    print("PASS display-label blockbet fallback is legacy-only", d)
    print("4/4 F1 structural checks passed")


if __name__=='__main__':
    main()
