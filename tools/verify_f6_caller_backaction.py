#!/usr/bin/env python3
"""Targeted structural verifier for F6 caller back-action."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import plan as PL
import session as SE


def _m(seat, action, pre_current, raised=False, full=None, incomplete=False,
       allin_call=False, increment=50):
    if full is None:
        full = raised and not incomplete
    return {
        'seat': seat,
        'action': action,
        'pre_current': pre_current,
        'raised': bool(raised),
        'full_raise': bool(full),
        'incomplete_raise': bool(incomplete),
        'allin_call': bool(allin_call),
        'increment': increment,
    }


class _RoundLike:
    def __init__(self, action_meta, contrib):
        self.action_meta = action_meta
        self.contrib = contrib


def test_call_bet_then_raise_context():
    seq = [
        _m(1,'bet',0,True, increment=50),
        _m(2,'call',50,False, increment=50),
        _m(3,'raise',50,True, increment=150),
    ]
    ctx = SE._postflop_response_context(_RoundLike(seq,{1:50,2:50,3:150}),2)
    assert ctx['kind'] == 'caller_backaction', ctx
    assert ctx['prior_action'] == 'call', ctx
    assert ctx['prior_facing_kind'] == 'bet', ctx
    assert ctx['facing_kind'] == 'raise', ctx
    assert ctx['raise_depth_full'] == 2, ctx
    return ctx


def test_call_raise_then_reraise_context():
    seq = [
        _m(1,'bet',0,True, increment=50),
        _m(3,'raise',50,True, increment=150),
        _m(2,'call',150,False, increment=150),
        _m(4,'raise',150,True, increment=300),
    ]
    ctx = SE._postflop_response_context(_RoundLike(seq,{1:50,2:150,3:150,4:300}),2)
    assert ctx['kind'] == 'caller_backaction', ctx
    assert ctx['prior_facing_kind'] == 'raise', ctx
    assert ctx['facing_kind'] == 'raise', ctx
    assert ctx['raise_depth_full'] == 3, ctx
    return ctx


def test_incomplete_raise_context():
    seq = [
        _m(1,'bet',0,True, increment=50),
        _m(2,'call',50,False, increment=50),
        _m(3,'allin',50,True,full=False,incomplete=True,increment=30),
    ]
    ctx = SE._postflop_response_context(_RoundLike(seq,{1:50,2:50,3:80}),2)
    assert ctx['kind'] == 'caller_backaction', ctx
    assert ctx['facing_incomplete_raise'] is True, ctx
    assert ctx['facing_full_raise'] is False, ctx
    assert ctx['raise_depth_full'] == 1, ctx
    assert ctx['raise_depth_any'] == 2, ctx
    return ctx


def _prof():
    return {'type':'TAG','aggr':5.0,'bluff':5.0,'gamble':5.0}


def test_response_plan_persisted():
    state={'plan':'value_3street','rel':0.95,'outs':0}
    ctx={
        'kind':'caller_backaction',
        'facing_kind':'raise',
        'prior_action':'call',
        'prior_facing_kind':'bet',
        'raise_depth_full':2,
        'raise_depth_any':2,
        'facing_full_raise':True,
        'facing_incomplete_raise':False,
        'hero_contrib':50.0,
    }

    orig_norm=PL._normalize_opp_pools
    orig_eq=PL.bot.equity_vs_betting
    orig_need=PL.calldown_need
    orig_resp=PL.decide_response
    try:
        PL._normalize_opp_pools=lambda *a,**k:[]
        PL.bot.equity_vs_betting=lambda *a,**k:0.80
        PL.calldown_need=lambda *a,**k:0.30
        PL.decide_response=lambda *a,**k:('call',0.0,0.30,'test caller continue')
        out,eq,need=PL.act_with_plan(
            ['As','Ah'],['Ks','7d','2c'],_prof(),state,
            pot=300,tocall=100,stack=900,street='flop',
            opp_range=None,bf=1.0,seed=1,n_opp=2,to_act_behind=1,
            can_raise=True,hero_contrib=50,
            response_kind='caller_backaction',response_context=ctx)
    finally:
        PL._normalize_opp_pools=orig_norm
        PL.bot.equity_vs_betting=orig_eq
        PL.calldown_need=orig_need
        PL.decide_response=orig_resp

    assert out == ('call',100), out
    rows=state.get('response_plans',{}).get('flop',[])
    assert len(rows)==1, rows
    rp=rows[0]
    assert rp['response_kind']=='caller_backaction', rp
    assert rp['act']=='call', rp
    assert rp['target']==150.0, rp
    assert rp['context']['prior_facing_kind']=='bet', rp
    assert state['_last_response_plan']==rp, state
    return out,rp


def main():
    a=test_call_bet_then_raise_context()
    b=test_call_raise_then_reraise_context()
    c=test_incomplete_raise_context()
    d=test_response_plan_persisted()

    print("PASS caller back-action remembers prior call-vs-bet", a)
    print("PASS caller back-action remembers prior call-vs-raise", b)
    print("PASS incomplete raise semantics survive response context", c)
    print("PASS explicit response plan is persisted", d)
    print("4/4 F6 structural checks passed")


if __name__=='__main__':
    main()
