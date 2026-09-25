#!/usr/bin/env python3
"""Targeted structural verifier for F3 check-then-face-bet fixes."""
import os
import sys
import inspect
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import plan as PL
import persona as PS
import session as SE


def profile():
    concepts = {k: 5.0 for k in PS.ALL_CONCEPTS}
    concepts['bluffcatch_early'] = 1.0
    concepts['bluffcatch_river'] = 9.0
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


def _patched_response_case(gate_value, can_raise=True):
    p = profile()
    st = {'plan':'trap', 'rel':0.92, 'outs':0, 'made':4}
    old_eq = PL.bot.equity_vs_betting
    old_need = PL.calldown_need
    old_made = PL.bot.made_strength
    old_gate = PL.checkraise_decision
    old_size = PL.checkraise_size
    old_resp = PL.decide_response
    seen = {'resp_calls':0, 'allow_raise':None, 'gate_calls':0}
    try:
        PL.bot.equity_vs_betting = lambda *a, **k: 0.80
        PL.calldown_need = lambda *a, **k: 0.30
        PL.bot.made_strength = lambda *a, **k: 4
        def gate(*a, **k):
            seen['gate_calls'] += 1
            return gate_value
        PL.checkraise_decision = gate
        PL.checkraise_size = lambda *a, **k: 777
        def response(*a, **k):
            seen['resp_calls'] += 1
            seen['allow_raise'] = k.get('allow_raise')
            return ('call', 0.0, a[6], 'stub call')
        PL.decide_response = response
        out = PL.act_with_plan(
            ['As','Ad'], ['Ah','7c','2d'], p, st,
            pot=300, tocall=100, stack=1000, street='flop',
            opp_range=None, bf=1.0, seed=11, n_opp=1,
            checked_before=True, can_raise=can_raise,
            checkraise_seed=12, checkraise_size_seed=13)
    finally:
        PL.bot.equity_vs_betting = old_eq
        PL.calldown_need = old_need
        PL.bot.made_strength = old_made
        PL.checkraise_decision = old_gate
        PL.checkraise_size = old_size
        PL.decide_response = old_resp
    return out, seen, st


def test_checkraise_is_single_producer():
    out, seen, st = _patched_response_case(True, True)
    assert out[0] == ('raise', 777), (out, seen)
    assert seen['gate_calls'] == 1, seen
    assert seen['resp_calls'] == 0, seen
    assert st.get('_last_response_source') == 'checkraise_gate', st
    return out[0], seen


def test_declined_checkraise_disables_generic_raise():
    out, seen, st = _patched_response_case(False, True)
    assert out[0][0] == 'call', (out, seen)
    assert seen['gate_calls'] == 1, seen
    assert seen['resp_calls'] == 1, seen
    assert seen['allow_raise'] is False, seen
    assert st.get('_last_response_source') == 'checkraise_declined', st
    return out[0], seen


def test_closed_raise_right_skips_checkraise_and_generic_raise():
    out, seen, st = _patched_response_case(True, False)
    assert out[0][0] == 'call', (out, seen)
    assert seen['gate_calls'] == 0, seen
    assert seen['resp_calls'] == 1, seen
    assert seen['allow_raise'] is False, seen
    return out[0], seen


def test_session_no_posthoc_checkraise_override():
    src = inspect.getsource(SE.HandRun._run)
    assert "PL.checkraise_decision(" not in src, "session still makes strategic checkraise decision"
    assert "PL.checkraise_size(" not in src, "session still sizes checkraise after response"
    assert "checked_before=_already_checked" in src, "check history not passed to planner"
    assert "can_raise=r2.can_raise(s)" in src, "legal raise right not passed to planner"
    return True


def test_bluffcatch_bias_is_street_aware():
    p = profile()
    f = PS.bias(p, 'bluff_fear', 'flop')
    r = PS.bias(p, 'bluff_fear', 'river')
    hf = PS.bias(p, 'hero_call', 'flop')
    hr = PS.bias(p, 'hero_call', 'river')
    assert f != r, (f,r)
    assert hf != hr, (hf,hr)
    # weak early bluffcatch => more fear and less hero-call than strong river skill
    assert f > r, (f,r)
    assert hf < hr, (hf,hr)
    return round(f,3), round(r,3), round(hf,3), round(hr,3)


def test_checkraise_no_longer_uses_fold_to_bet_read():
    src = inspect.getsource(PL.checkraise_decision)
    assert "street_gap" not in src, src
    assert "read_opponent" not in src, src
    return True


def main():
    a=test_checkraise_is_single_producer()
    b=test_declined_checkraise_disables_generic_raise()
    c=test_closed_raise_right_skips_checkraise_and_generic_raise()
    d=test_session_no_posthoc_checkraise_override()
    e=test_bluffcatch_bias_is_street_aware()
    f=test_checkraise_no_longer_uses_fold_to_bet_read()

    print("PASS checkraise has one strategic producer", a)
    print("PASS declined checkraise cannot fall through to generic raise", b)
    print("PASS closed raise right removes all raise plans", c)
    print("PASS session no longer overrides response with checkraise", d)
    print("PASS bluffcatch behavioral bias is street-aware", e)
    print("PASS checkraise no longer borrows fold-to-bet read", f)
    print("6/6 F3 structural checks passed")


if __name__=='__main__':
    main()
