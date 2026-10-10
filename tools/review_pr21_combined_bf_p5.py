#!/usr/bin/env python3
"""P5 independent PR21 BF/MC joint consumer contract.

Do not use archived B37 estimated equity as proof of optimal play. The
threshold-midpoint scenario below is an algebraically chosen *test input*,
not a poker range adjustment, solver prior, or empirical coefficient.
"""
import math
import os
import random
import sys
from unittest.mock import patch

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
import icm as I
import session as S
import play as P
import plan as PL
import preflop as PF
import gto as G
import bot
from tools.verify_p13_complete_field_bf import hand,LOCAL,FULL,ALL,PAYOUTS
from tools.verify_hand130_b37_replay import original

POT=108442.0
COST=53442.0

def decision(bf, equity, exact=None, complete=True, cause=None):
    sh={'pure_calloff':True,'complete':complete,
        'call_cost':COST,'contestable_after_call':POT+COST,
        'effective_equity':equity if complete else None,
        'breakeven_equity':COST/(POT+COST),
        'incomplete_reasons': ({0:cause} if cause else {}),
        'missing_equity_layers':([0] if not complete else []),
        'exact_hu_icm':exact}
    base=original()
    p=base['actor_pf_seed']
    rng=random.Random(66)
    prior=rng.getstate()
    a,sz,seed=PL.preflop_plan(
        {'type':'TAG'},'LJ',['Kh','Ac'],p['pf_stack_bb'],rng,
        aggressor_pos='BB',open_bb=p['pf_open_bb'],
        n_callers=0,n_limpers=0,raise_level=2,
        can_raise=False,opener_allin=True,
        pot_bb=POT/10000,to_call_bb=COST/10000,
        seats=8,ante=True,bb_chips=10000,bf=bf,
        prior_pf={'pf_act':'raise','pf_role':'open'},
        call_ev_shadow=sh,calloff_decision_seed=3365551903)
    assert rng.getstate()==prior,'calloff modified shared RNG'
    return a,sz,seed

def full_field_variants():
    exact=hand(LOCAL,ALL)
    missing=hand(LOCAL,())
    altered=hand(LOCAL,ALL)
    altered.stacks[3]-=1
    complete=exact.bf_details(3)
    unavailable=missing.bf_details(3)
    stale=altered.bf_details(3)
    whole=hand(FULL,()).bf_details(3)
    assert complete['is_exact'] and whole['is_exact']
    assert complete['method']=='exact_full_field_icm'
    assert complete['field_completeness']=='verified_player_id_field_snapshot'
    assert not unavailable['is_exact'] and not stale['is_exact']
    assert unavailable['reason']=='missing_full_field_stacks'
    assert stale['reason']=='table_stacks_changed_after_field_snapshot'
    for source,details in [('complete',complete),('missing',unavailable),
                           ('stale',stale),('same_table',whole)]:
        assert details['bf_kind']=='generic_default_risk_not_spot_call_prize_ev'
        assert details['price_specific'] is False
        assert details['value']>=1.0,(source,details)
        assert details['value']==(
            {'complete':exact,'missing':missing,
             'stale':altered,'same_table':hand(FULL,())}[source]).bf(3)
    assert math.isclose(complete['value'],3.465325154547401,rel_tol=1e-12)
    assert unavailable['value']!=complete['value']
    assert stale['value']!=complete['value']
    assert whole['value']==complete['value']
    assert I.required_equity(POT,COST,complete['value']) != I.required_equity(
        POT,COST,unavailable['value'])
    # Pure calloff consumer must receive EXACT same scalar that provenance
    # advertises; no alternative/hidden unscaled BF in the planner.
    eq0=I.required_equity(POT,COST,complete['value'])
    eq1=I.required_equity(POT,COST,unavailable['value'])
    derived_midpoint=(eq0+eq1)/2
    action0,size0,seed0=decision(complete['value'],derived_midpoint)
    action1,size1,seed1=decision(unavailable['value'],derived_midpoint)
    assert action0!=action1,(action0,action1,eq0,eq1)
    assert {action0,action1}=={'fold','call'}
    assert seed0['pf_calloff_consumer']['objective_spot_bf']==round(
        complete['value'],6)
    assert seed1['pf_calloff_consumer']['objective_spot_bf']==round(
        unavailable['value'],6)
    # There is NO price-specific payout EV for split-table nonterminal hands.
    for details,seed in [(complete,seed0),(unavailable,seed1)]:
        seed['pf_bf_provenance']=dict(details)
        meta={9:{'source':'test_pr21_range','complete':True,
                 'model_calibrated':False}}
        S._attach_p8_observer_evidence(seed,meta)
        saved=S._merge_pf_seed({},seed)
        assert saved['pf_bf_provenance']==details
        assert saved['pf_opp_range_meta']['9']==meta[9]
        consumer=saved['pf_calloff_consumer']
        assert consumer['objective_unconditional_bf']==details['value']
        assert consumer['icm_pricing_basis']=='generic_bf_approximation_not_spot_validated'
        assert consumer['icm_fallback_risk'] is not None
        assert not consumer['mathematically_justified']
    print('PASS combined full/missing/stale BF source and actual planner price threshold')
    print({'exact':complete['value'],'missing_empirical':unavailable['value'],
           'stale_empirical':stale['value'],
           'synthetic_midpoint_equity':derived_midpoint,
           'exact_action':action0,'missing_action':action1})
    return complete

def exact_spot_is_distinct(complete):
    h=original()
    shadow=h['actor_pf_seed']['pf_call_ev_shadow']
    stacks={int(k):float(v)-1250 for k,v in h['stacks_before'].items()}
    stacks[3]-=20000
    stacks[8]-=5000
    stacks[9]-=73442
    result=S._terminal_hu_call_icm(
        stacks,{3:20000,8:5000,9:73442},{1,2,4,5,7,8},
        list(stacks),3,9,shadow['call_cost'],10000,shadow['layers'],
        PAYOUTS,8,shadow['effective_equity'],
        unit=5000,odd_order=[8,9,1,2,3,4,5,7])
    assert result is not None
    assert math.isclose(result['no_tie_breakeven_equity'],
                        0.3715371093145927,rel_tol=1e-12)
    assert result['tie_stacks'][3]==231422
    assert result['tie_stacks'][9]==86884
    bf_price=result['equivalent_bubble_factor']
    bf_generic=complete['value']
    assert bf_price!=bf_generic
    a,sz,seed=decision(bf_generic,shadow['effective_equity'],exact=result)
    c=seed['pf_calloff_consumer']
    assert a=='call' and sz==COST/10000
    assert math.isclose(c['objective_spot_bf'],bf_price,abs_tol=1e-6)
    assert c['objective_unconditional_bf']==bf_generic
    assert c['icm_pricing_basis']=='terminal_hu_exact_outcome_prices'
    assert c['decision_quantity']=='perceived_layer_equity_vs_spot_icm_price'
    assert not c['mathematically_justified']
    print('PASS exact HAND130 price-specific payout ICM never confused with generic full-field BF')

def incomplete_against_complete_field(complete):
    # BF completeness MUST NOT falsely complete missing MC equity.
    causes=[
        {'reason':'no_valid_mc_samples','requested_samples':800,'valid_samples':0},
        {'reason':'insufficient_valid_samples','requested_samples':800,'valid_samples':7},
        {'reason':'missing_opponent_range','missing_ranges':[9],
         'missing_range_details':{'9':{'complete':False,'missing':['public_actor_stack_bb']}}},
        {'reason':'unsupported_opponent_model','missing_ranges':[9],
         'missing_range_details':{'9':{'complete':False,'missing':['action_class_not_supported']}}},
    ]
    for cause in causes:
        a,sz,seed=decision(complete['value'],None,complete=False,cause=cause)
        consumer=seed['pf_calloff_consumer']
        assert a=='fold' and sz==0
        assert consumer['equity_status']=='unavailable_not_negative_ev'
        assert consumer['mathematically_justified'] is False
        assert consumer['strategy_consumer'] is False
        assert consumer['incomplete_reasons'][0]==cause
        assert consumer['legacy_evaluated'] is False
        seed['pf_bf_provenance']=dict(complete)
        S._attach_p8_observer_evidence(
            seed,{9:{'complete':False,'missing':['no_model'],
                     'source':'test_pr21'}})
        saved=S._merge_pf_seed({},seed)
        assert saved['pf_bf_provenance']==complete
        assert saved['pf_calloff_consumer']['incomplete_reasons'][0]==cause
        assert saved['pf_calloff_consumer']['opponent_range_evidence']['9']['complete'] is False
    print('PASS complete generic field BF cannot promote failed MC equity to a proven -EV fold')

def main():
    field=full_field_variants()
    incomplete_against_complete_field(field)
    exact_spot_is_distinct(field)
    print('PASS PR21 independent combined BF/MC to P5 contract')

if __name__=='__main__':
    main()
