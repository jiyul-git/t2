#!/usr/bin/env python3
"""Targeted structural verifier for F4 direct facing-bet fixes."""
import os
import sys
import inspect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU
import session as SE
import plan as PL


def test_action_increment():
    r = RU.Round(None, [1,2,3], {1:1000,2:1000,3:1000}, 10)
    r.apply(1, 'bet', 50)
    r.apply(2, 'call')
    incs = [m['increment'] for m in r.action_meta]
    assert incs == [50,50], incs
    return incs


def test_bet_call_hero_facing_size():
    # Street begins with pot 100. A bets 50, B calls 50, hero acts.
    r = RU.Round(None, [1,2,3], {1:1000,2:1000,3:1000}, 10)
    r.apply(1, 'bet', 50)
    r.apply(2, 'call')
    ctx = SE._facing_wager_context(r, 1, 100)
    assert ctx is not None, ctx
    assert abs(ctx['size_frac'] - 0.50) < 1e-12, ctx

    pot_live = 100 + r.contestable_contrib(3)
    tc = r.to_call(3)
    old_proxy = tc / max(1.0, pot_live)
    assert abs(old_proxy - 0.25) < 1e-12, (tc,pot_live,old_proxy)
    return ctx, old_proxy


def test_calldown_receives_facing_fraction():
    captured = {}
    old_norm = PL.PS.opp_size_norm
    old_read = PL.PS.size_read
    old_noise = PL.PS.calc_noise
    old_bias = PL.PS.call_bias
    try:
        PL.PS.opp_size_norm = lambda rd, x, street=None: x
        def fake_size_read(profile, x):
            captured['x'] = x
            return x
        PL.PS.size_read = fake_size_read
        PL.PS.calc_noise = lambda *a, **k: 1.0
        PL.PS.call_bias = lambda *a, **k: 1.0

        prof = {'concepts': {'potodds':5.0}, 'aggr':5.0}
        PL.calldown_need(
            prof, ['As','Kd'], ['7c','4d','2s'], 'flop',
            pot=200, tocall=50, bf=1.0, read=None,
            to_act_behind=0, opp_est=None, n_opp=2,
            rng=None, facing_size_frac=0.50)
    finally:
        PL.PS.opp_size_norm = old_norm
        PL.PS.size_read = old_read
        PL.PS.calc_noise = old_noise
        PL.PS.call_bias = old_bias
    assert abs(captured['x'] - 0.50) < 1e-12, captured
    return captured['x']


def test_barrel_count_includes_current_street():
    full = [
        {'street':'flop','seat':1,'raised':True},
        {'street':'flop','seat':2,'raised':False},
    ]
    current = [
        {'seat':2,'raised':False},
        {'seat':1,'raised':True},
    ]
    n = SE._barrel_count(full, current, 1, 'turn')
    assert n == 2, n
    return n


def test_allin_observation_normalization():
    ar = SE._observed_postflop_action(
        {'action':'allin','raised':True,'allin_call':False})
    ac = SE._observed_postflop_action(
        {'action':'allin','raised':False,'allin_call':True})
    assert ar == 'raise', ar
    assert ac == 'call', ac
    return ar, ac


def test_session_aggressor_is_rule_event_based():
    src = inspect.getsource(SE.HandRun._run)
    assert "action_meta[-1].get('raised')" in src, src
    assert "if act[0] in ('bet', 'raise', 'allin'): aggressor = s" not in src, src
    return True


def main():
    a=test_action_increment()
    b=test_bet_call_hero_facing_size()
    c=test_calldown_receives_facing_fraction()
    d=test_barrel_count_includes_current_street()
    e=test_allin_observation_normalization()
    f=test_session_aggressor_is_rule_event_based()

    print("PASS exact per-action chip increment", a)
    print("PASS bet-call-hero preserves bettor size fraction", b)
    print("PASS calldown receives actual facing wager fraction", c)
    print("PASS barrel count includes current street", d)
    print("PASS all-in observation semantics normalized", e)
    print("PASS aggressor update is rule-event based", f)
    print("6/6 F4 structural checks passed")


if __name__ == '__main__':
    main()
