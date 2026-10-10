#!/usr/bin/env python3
"""Department 13's independent partial-call regression, no fitted inputs.

At decision time: hero has 20 behind/10 in, shover has 0 behind/40 in,
a folded third player has 60 behind. Cost 20, all posted contributions 50.
The last 10 of shover contribution is NOT hero-contestable after the call.
Exact resulting stacks:
  fold (20,50,60), call-win (60,10,60), call-lose (0,70,60).
Payouts [50,30], three remaining players, no other table.
"""
import math
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
import session as S
import icm as I

def near(got, expected, field, tol=1e-11):
    assert math.isclose(got, expected, abs_tol=tol, rel_tol=tol), (field,got,expected)

def main():
    before={1:20,2:0,3:60}
    contrib={1:10,2:40,3:0}
    folded={3}
    post_contrib={1:30,2:40,3:0}
    after={1:0,2:0,3:60}
    layers=S._decision_pot_layers(
        {},post_contrib,folded,after,hero=1,dead=0)
    assert [int(x['amount']) for x in layers] == [60,10],layers
    assert [x['eligible_seats'] for x in layers] == [[1,2],[2]]
    result=S._terminal_hu_call_icm(
        before,contrib,folded,[1,2,3],1,2,20,0,layers,
        [50,30],3,0.6,unit=1,odd_order=[2,3,1])
    assert result is not None
    assert result['fold_stacks']=={1:20.0,2:50.0,3:60.0}
    assert result['win_stacks']=={1:60.0,2:10.0,3:60.0}
    assert result['lose_stacks']=={1:0.0,2:70.0,3:60.0}
    assert result['full_pre_call_pot']==50
    assert result['contestable_before_call']==40
    assert result['contestable_after_call']==60
    assert result['uncalled_opponent_excess_after_call']==10
    # No contestable chip vanishes or appears; the opponent-only upper layer
    # belongs to the shover even when the hero wins.
    for outcome in ('fold_stacks','win_stacks','lose_stacks','tie_stacks'):
        assert sum(result[outcome].values())==130,(outcome,result[outcome])

    near(result['no_tie_breakeven_equity'],
         0.40258751902587525,'prize ICM break even')
    near(I.required_equity(40,20,result['equivalent_bubble_factor']),
         0.40258751902587525,'converted BF same contestable pot')
    # Regression signature of the previous error: full 50 counted as pot
    # in the BF numerator, but price consumer saw only contestable 40.
    loss=result['fold_prize']-result['lose_prize']
    gain=result['win_prize']-result['fold_prize']
    wrong_bf=(loss/gain)*50/20
    near(I.required_equity(40,20,wrong_bf),
         0.4572169403630078,'old mismatched-pot conversion')
    print('PASS department13 partial-call regression: 40.2587519026% (not 45.7216940363%)')
    print('PASS opponent-only unmatched 10 and fold/win/lose/tie chip conservation')

if __name__=='__main__':
    main()
