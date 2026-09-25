#!/usr/bin/env python3
"""Targeted structural verifier for F5 postflop aggressor back-action fixes."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import plan as PL
import reads as RD
import session as SE


def _prof():
    return {
        'type': 'TAG',
        'aggr': 5.0,
        'bluff': 5.0,
        'gamble': 5.0,
    }


def _run_response(mult, stack, contrib, pot=300, tocall=100):
    orig_norm = PL._normalize_opp_pools
    orig_eq = PL.bot.equity_vs_betting
    orig_need = PL.calldown_need
    orig_resp = PL.decide_response
    try:
        PL._normalize_opp_pools = lambda *a, **k: []
        PL.bot.equity_vs_betting = lambda *a, **k: 0.80
        PL.calldown_need = lambda *a, **k: 0.30
        PL.decide_response = (
            lambda profile, hero, board, street, plan, plan_state,
                   eq, need, made_now, opp_range, pot, tocall, stack,
                   committed, rng, allow_raise=True:
            ('raise', mult, need, 'test raise')
        )
        out, _, _ = PL.act_with_plan(
            ['As','Ah'], ['Ks','7d','2c'], _prof(),
            {'plan':'value_3street','rel':0.95,'outs':0},
            pot=pot, tocall=tocall, stack=stack, street='flop',
            initiative=True, opp_range=None, bf=1.0, seed=1,
            n_opp=1, to_act_behind=0, read=None, opp_est=None,
            can_raise=True, hero_contrib=contrib,
            response_kind='aggressor_backaction')
        return out
    finally:
        PL._normalize_opp_pools = orig_norm
        PL.bot.equity_vs_betting = orig_eq
        PL.calldown_need = orig_need
        PL.decide_response = orig_resp


def test_reraise_target_includes_prior_contrib():
    out = _run_response(mult=1.0, stack=950, contrib=50)
    assert out == ('raise', 550), out
    return out


def test_reraise_cap_uses_total_target():
    out = _run_response(mult=1.0, stack=300, contrib=50)
    assert out == ('raise', 350), out
    return out


def test_call_comparison_uses_total_coordinate():
    # base = (300 + 2*100) * 0.20 = 100; + hero 50 = 150.
    # Current call target is also 50 + 100 = 150, so this is a call, not a raise.
    out = _run_response(mult=0.20, stack=950, contrib=50)
    assert out == ('call', 100), out
    return out


def test_fold_to_bet_and_raise_are_separate():
    b = RD.Book()
    obs = ['o','x']

    # Ordinary bet-facing fold.
    b.observe_postflop(obs, 'x', 'fold', False, False,
                       facing_bet=True, facing_raise=False, street='flop')
    r = b.rec('o','x')
    assert r['facing_bet'] == 1 and r['fold_to_bet'] == 1, r
    assert r['facing_raise'] == 0 and r['fold_to_raise'] == 0, r

    # Raise-facing fold must not touch fold_to_bet.
    b.observe_postflop(obs, 'x', 'fold', False, False,
                       facing_bet=False, facing_raise=True, street='flop')
    r = b.rec('o','x')
    assert r['facing_bet'] == 1 and r['fold_to_bet'] == 1, r
    assert r['facing_raise'] == 1 and r['fold_to_raise'] == 1, r
    assert r['fb_flop'] == 1 and r['f2b_flop'] == 1, r
    assert r['fr_flop'] == 1 and r['f2r_flop'] == 1, r
    return {
        'ftb': (r['fold_to_bet'], r['facing_bet']),
        'ftr': (r['fold_to_raise'], r['facing_raise']),
    }


def _m(seat, action, pre_current, raised=False, allin_call=False):
    return {
        'seat': seat,
        'action': action,
        'pre_current': pre_current,
        'raised': raised,
        'full_raise': raised,
        'incomplete_raise': False,
        'allin_call': allin_call,
        'increment': 50,
    }


def test_facing_sequence():
    seq = [
        _m(1,'bet',0,True),       # creates first wager
        _m(2,'call',50,False),    # faces bet
        _m(3,'raise',50,True),    # faces bet, then creates raise
        _m(1,'fold',150,False),   # faces raise
    ]
    got = SE._postflop_facing_contexts(seq)
    assert got == [None, 'bet', 'bet', 'raise'], got
    return got


class _RoundLike:
    def __init__(self, action_meta, contrib):
        self.action_meta = action_meta
        self.contrib = contrib


def test_aggressor_backaction_kind():
    seq = [
        _m(1,'bet',0,True),
        _m(2,'raise',50,True),
    ]
    ctx = SE._postflop_response_context(_RoundLike(seq, {1:50,2:150}), 1)
    assert ctx['kind'] == 'aggressor_backaction', ctx
    assert ctx['prior_action'] == 'bet', ctx
    assert ctx['facing_kind'] == 'raise', ctx
    assert ctx['hero_contrib'] == 50.0, ctx
    return ctx


def main():
    a=test_reraise_target_includes_prior_contrib()
    b=test_reraise_cap_uses_total_target()
    c=test_call_comparison_uses_total_coordinate()
    d=test_fold_to_bet_and_raise_are_separate()
    e=test_facing_sequence()
    f=test_aggressor_backaction_kind()

    print("PASS re-raise target includes prior contribution", a)
    print("PASS re-raise cap uses total reachable target", b)
    print("PASS call comparison uses total contribution coordinate", c)
    print("PASS fold-to-bet and fold-to-raise reads are separate", d)
    print("PASS current-street facing sequence is classified", e)
    print("PASS aggressor back-action kind is preserved", f)
    print("6/6 F5 structural checks passed")


if __name__ == '__main__':
    main()
