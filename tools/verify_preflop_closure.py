#!/usr/bin/env python3
"""Preflop closure verifier for P1 reopen fixes and P7 decision classes."""
import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import preflop as PF
import plan as PL
import persona as PS


def prof():
    """Production-shaped profile.

    persona.overall_skill() expects both EXEC and CALC concept families to be
    represented.  The previous verifier used a tiny partial dict, so it failed
    inside statistics.mean before reaching the behavior under test.
    """
    concepts = {k: 5.0 for k in PS.ALL_CONCEPTS}
    concepts.update({
        'pf_range': 6.0,
        'pf_defend': 6.0,
        'spr': 6.0,
        'open_size': 6.0,
        'icm': 5.0,
    })
    temper = {k: 5.0 for k in PS.TEMPER}
    return {
        'type': 'TAG',
        'concepts': concepts,
        'temper': temper,
    }


def test_variance_seek_reaches_open_form():
    p=prof()
    seen={}
    ov, oo, ol = PF.PS.variance_seek, PF.open_form, PF.limp_p
    try:
        PF.PS.variance_seek=lambda *a, **k: 0.37
        def fake_open_form(_p, _feel, _r, _bb, _rng, vs=0.0, traits=None):
            seen['vs']=vs
            return (None,0)
        PF.open_form=fake_open_form
        PF.limp_p=lambda *a, **k: 0.0
        out=PF.open_decision(
            p,'BTN',40.0,['As','Ah'],random.Random(1),
            seats=8,ante=True,field_avg_bb=40.0)
    finally:
        PF.PS.variance_seek, PF.open_form, PF.limp_p = ov, oo, ol
    assert abs(seen['vs']-0.37)<1e-12, seen
    assert out[0]=='raise', out
    return seen['vs'], out


def test_sb_complete_reachable():
    p=prof()
    oo, ol = PF.open_form, PF.limp_p
    try:
        PF.open_form=lambda *a, **k:(None,0)
        PF.limp_p=lambda *a, **k:1.0
        out=PF.open_decision(
            p,'SB',40.0,['7c','6c'],random.Random(2),
            seats=8,ante=True,field_avg_bb=40.0)
    finally:
        PF.open_form, PF.limp_p = oo, ol
    assert out == ('limp',1.0), out
    return out


def test_weak_habit_limp_outside_raise_range():
    p=prof()
    oo, ol, ob = PF.open_form, PF.limp_p, PF._open
    try:
        PF._open=lambda *a, **k:0.01
        PF.open_form=lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("outside raise range must not call open_form"))
        PF.limp_p=lambda *a, **k:1.0
        out=PF.open_decision(
            p,'HJ',100.0,['7c','2d'],random.Random(3),
            seats=8,ante=True,field_avg_bb=100.0)
    finally:
        PF.open_form, PF.limp_p, PF._open = oo, ol, ob
    assert out == ('limp',1.0), out
    return out


def _stub_plan_kind(prior, level):
    import preflop as _pf
    old=_pf.defend_decision
    try:
        _pf.defend_decision=lambda *a, **k: ('call', 8.0)
        _,_,seed=PL.preflop_plan(
            prof(),'BTN',['As','Kd'],40.0,random.Random(4),
            aggressor_pos='CO',open_bb=8.0,n_callers=0,
            raise_level=level,prior_pf=prior,
            can_raise=True,pot_bb=12.0,to_call_bb=8.0)
    finally:
        _pf.defend_decision=old
    return seed['pf_decision_kind']


def test_p7_decision_classes():
    got={
        'face_first_open': _stub_plan_kind(None,1),
        'cold_vs_reraise': _stub_plan_kind(None,2),
        'opener_backaction': _stub_plan_kind(
            {'pf_role':'open','pf_act':'raise'},2),
        'caller_backaction': _stub_plan_kind(
            {'pf_role':'defend','pf_act':'call'},2),
        'reraiser_backaction': _stub_plan_kind(
            {'pf_role':'defend','pf_act':'3bet'},3),
    }
    assert got == {
        'face_first_open':'face_first_open',
        'cold_vs_reraise':'cold_vs_reraise',
        'opener_backaction':'opener_backaction',
        'caller_backaction':'caller_backaction',
        'reraiser_backaction':'reraiser_backaction',
    }, got
    return got


def main():
    a=test_variance_seek_reaches_open_form()
    b=test_sb_complete_reachable()
    c=test_weak_habit_limp_outside_raise_range()
    d=test_p7_decision_classes()
    print("PASS live variance-seek reaches open planning", a)
    print("PASS SB complete is reachable", b)
    print("PASS weak habitual limp can exist outside raise range", c)
    print("PASS preflop decision classes are preserved", d)
    print("4/4 preflop closure checks passed")


if __name__=='__main__':
    main()
