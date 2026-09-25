#!/usr/bin/env python3
"""Targeted structural verifier for F2 check-through fixes."""
import os
import sys
import inspect
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import plan as PL
import persona as PS
import reads as RD
import runner as RU
import session as SE


def profile(delayed):
    concepts = {k: 5.0 for k in PS.ALL_CONCEPTS}
    concepts['delayed_cbet'] = delayed
    temper = {k: 5.0 for k in PS.TEMPER}
    return {
        'type':'TAG',
        'concepts':concepts,
        'temper':temper,
        'aggr':5.0,
        'bluff':5.0,
        'gamble':5.0,
        'icm':5.0,
    }


def test_probe_context_precedes_intent():
    src = inspect.getsource(PL.update_plan)
    pos_ctx = src.index("st['opp_checked_prev']")
    pos_intent = src.index("attach_intent(")
    assert pos_ctx < pos_intent, (pos_ctx, pos_intent)

    ssrc = inspect.getsource(SE.HandRun._run)
    assert "opp_checked_prev=_opp_checked_prev" in ssrc
    return True


def _aggr(p, plan):
    return PL.decide_aggression(
        p,
        board=['As','7d','2c','4h'],
        street='turn',
        plan=plan,
        rel=0.82 if plan == 'value_3street' else 0.20,
        n_opp=1,
        oop=False,
        initiative=True,
        to_act_behind=0,
        rng=random.Random(77),
        opp_est=None,
        outs=0,
        plan_state={'flop_checked':True, 'range_adv':0.0},
        oop_vs_aggr=False,
        oop_legacy_abs=False,
    )[0]


def test_delayed_skill_reaches_giveup_and_value():
    low_g = _aggr(profile(0.0), 'giveup')
    high_g = _aggr(profile(10.0), 'giveup')
    low_v = _aggr(profile(0.0), 'value_3street')
    high_v = _aggr(profile(10.0), 'value_3street')
    assert high_g > low_g, (low_g, high_g)
    assert high_v > low_v, (low_v, high_v)
    return (low_g, high_g), (low_v, high_v)


def test_delayed_read_is_not_barrel():
    b = RD.Book()
    b.observe_postflop(
        ['obs','villain'], 'villain', 'bet',
        is_cbet_spot=False,
        is_barrel_spot=False,
        facing_bet=False,
        street='turn',
        is_delayed_cbet_spot=True)
    r = b.rec('obs','villain')
    assert r['delayed_cbet_opp'] == 1, r
    assert r['delayed_cbet'] == 1, r
    assert r['barrel_opp'] == 0, r
    assert r['barrel'] == 0, r
    return {
        'delayed_opp':r['delayed_cbet_opp'],
        'delayed':r['delayed_cbet'],
        'barrel_opp':r['barrel_opp'],
        'barrel':r['barrel'],
    }


def test_execution_provenance_wired_and_preserved():
    rsrc = inspect.getsource(PL.refresh)
    assert "executed_actions" in rsrc
    assert "all(a == 'check' for a in _fx)" in rsrc

    usrc = inspect.getsource(PL.update_plan)
    revsrc = inspect.getsource(RU.revise_plan)
    ssrc = inspect.getsource(SE.HandRun._run)
    assert "executed_actions" in usrc
    assert "executed_actions" in revsrc
    assert "setdefault('executed_actions', {})" in ssrc
    return True


def main():
    a = test_probe_context_precedes_intent()
    b = test_delayed_skill_reaches_giveup_and_value()
    c = test_delayed_read_is_not_barrel()
    d = test_execution_provenance_wired_and_preserved()

    print("PASS probe/check-through context reaches plan before intent", a)
    print("PASS delayed-cbet skill affects giveup and value turn ranges", b)
    print("PASS delayed-cbet read is separate from barrel", c)
    print("PASS actual execution provenance is wired and preserved", d)
    print("4/4 F2 structural checks passed")


if __name__ == '__main__':
    main()
