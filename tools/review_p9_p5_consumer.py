#!/usr/bin/env python3
"""Independent P5 and P8 consumer-level review, pinned to PR18 69e55fc.

No strategy changes and no assumed solver equity. Simulated missing/partial
samples are intentionally diagnostic, not claimed as HAND130 events.
"""
import copy
import os
import random
import sys
from unittest.mock import patch
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
import bot
import plan as PL
import preflop as PF
import gto as G
import session as S
import ranges as R
from tools.verify_hand130_b37_replay import original

H=original()
P=H['actor_pf_seed']
PROFILE=H['actor_profile']
L={'idx':0,'hero_eligible':True,'eligible_seats':[3,9],
   'amount':161884,'level':73442}
WEIGHTED={('As','Ad'):0.25,('Qs','Qd'):0.75}
SEED=3365551903

def plan(sh):
    rng=random.Random(591)
    state=rng.getstate()
    def forbidden(*a,**kw):
        raise AssertionError('legacy defend path consumed incomplete MC')
    with patch.object(PF,'calloff_cap',forbidden),\
         patch.object(PF,'defend_decision',forbidden),\
         patch.object(G,'defend_pct',forbidden):
        act,sz,out=PL.preflop_plan(
            PROFILE,'LJ',['Kh','Ac'],P['pf_stack_bb'],rng,
            aggressor_pos='BB',open_bb=P['pf_open_bb'],raise_level=2,
            can_raise=False,opener_allin=True,to_call_bb=P['pf_to_call_bb'],
            pot_bb=P['pf_pot_bb'],seats=8,ante=True,bb_chips=10000,
            bf=P['pf_calloff_consumer']['objective_bubble_factor'],
            prior_pf={'pf_act':'raise','pf_role':'open'},
            call_ev_shadow=sh,calloff_decision_seed=SEED,
            cold_context=P['pf_cold_context'])
    assert rng.getstate()==state,'shared RNG modified'
    return act,sz,out

def to_shadow(rows,metadata=None):
    summary=S._layer_call_summary(53442,[L],rows)
    return dict(summary,pure_calloff=True,complete=summary['complete'],
                range_model_evidence=metadata or {})

def assert_unavailable(rows,reason,expected_details=None):
    assert not rows[0]['complete'] and rows[0]['equity'] is None,rows
    assert rows[0]['reason']==reason,(rows[0]['reason'],reason)
    sh=to_shadow(rows)
    assert not sh['complete'] and sh['effective_equity'] is None
    assert sh['call_chip_ev'] is None
    act,sz,out=plan(sh)
    assert (act,sz)==('fold',0.0),('legal execution fallback',act,sz)
    c=out['pf_calloff_consumer']
    assert c['strategy_consumer'] is False
    assert c['mathematically_justified'] is False
    assert c['equity_status']=='unavailable_not_negative_ev'
    assert c['decision_quantity']=='unverified_missing_calloff_equity'
    assert c['legacy_evaluated'] is False
    assert c['incomplete_reasons'][0]['reason']==reason
    if expected_details:
        assert c['incomplete_reasons'][0]['missing_range_details']['9']==expected_details
    return out

def status_tests():
    # Validly computed 0 is not None, even when the 5th street is deterministic.
    board=['Ah','Kd','7s','9c','Jd']
    h=['2c','3d']
    pool={('Ac','Ad'):1.0}
    zero=S.layer_equities_by_pot_layer(
        3,h,board,[L],{}, {9:pool},sims=8,seed=77,capture_sampling=True)
    assert zero[0]['complete'] and zero[0]['equity']==0.0
    assert zero[0]['valid_samples']==zero[0]['requested_samples']==8
    sh=to_shadow(zero)
    assert sh['complete'] and sh['effective_equity']==0.0
    act,sz,out=plan(sh)
    assert act=='fold' and sz==0
    c=out['pf_calloff_consumer']
    assert c['strategy_consumer'] is True
    assert c['conditional_point_estimate_action'] is True
    assert c['mathematically_justified'] is False
    print('PASS true sampled equity 0 vs unavailable None, planner distinguishes')

    # Impossible compatible combo draw => 0 valid, not a false 0% equity.
    bad=S.layer_equities_by_pot_layer(
        3,['Ah','Ad'],['Ks','Qs','Js','Ts','9s'],[L],
        {},{9:[('2c','3c')]},sims=0,seed=17,capture_sampling=True)
    assert_unavailable(bad,'no_requested_samples')

    impossible=S.layer_equities_by_pot_layer(
        3,['Ah','Ad'],['Ks','Qs','Js','Ts','9s'],
        [{'idx':0,'hero_eligible':True,'eligible_seats':[3,9,11],
          'amount':161884,'level':73442}],{},
        {9:[('2c','3c')],11:[('2c','4c')]},
        sims=4,seed=17,capture_sampling=True)
    # Separate multiway layers: reason and absence are preserved through summary,
    # while no invalid result is used by planner.
    assert impossible[0]['reason']=='no_valid_mc_samples'
    assert impossible[0]['equity'] is None and not impossible[0]['complete']
    assert impossible[0]['valid_samples']==0
    print('PASS 0-requested and 0-accepted MC unavailable, not -EV')

    # Partial acceptance: positive sample mean cannot become decision EV.
    def partial(*args,**kw):
        d=kw['audit'];d.update(requested=8,accepted=3,rejected=5,
            sample_variance=0.04,split_pot_draws=1,
            mean_share=0.75,complete=False,reason='insufficient_valid_samples')
        return None
    with patch.object(bot,'equity_vs_combos',side_effect=partial):
        some=S.layer_equities_by_pot_layer(3,['Kh','Ac'],[],[L],
            {},{9:WEIGHTED},sims=8,seed=21,capture_sampling=True)
    assert some[0]['observed_sample_mean']==0.75
    assert some[0]['valid_samples']==3
    assert_unavailable(some,'insufficient_valid_samples')
    print('PASS partial accepted draws diagnostic only, no hidden -EV fallback')

    unsupported={'complete':False,'source':'observer_actor_policy_conditional_v1',
        'status':'legacy_fallback','failure_kind':'model_unavailable',
        'missing':['action_class_not_supported']}
    u=S.layer_equities_by_pot_layer(
        3,['Kh','Ac'],[],[L],{}, {9:WEIGHTED},
        sims=8,seed=91,range_metadata={9:unsupported})
    out=assert_unavailable(u,'unsupported_opponent_model',unsupported)
    S._attach_p8_observer_evidence(out,{9:unsupported})
    c=out['pf_calloff_consumer']
    assert c['opponent_range_evidence']['9']==unsupported
    assert c['mathematically_justified'] is False
    print('PASS unvalidated legacy fallback disabled for EV; model provenance intact')

    missing={'complete':False,'status':'missing_evidence',
        'source':'observer_actor_policy_conditional_v1',
        'missing':['public_actor_stack_bb']}
    no=S.layer_equities_by_pot_layer(
        3,['Kh','Ac'],[],[L],{},{},sims=8,seed=15,
        range_metadata={9:missing})
    out=assert_unavailable(no,'missing_opponent_range',missing)
    S._attach_p8_observer_evidence(out,{9:missing})
    assert out['pf_calloff_consumer']['opponent_range_evidence']['9']==missing
    print('PASS missing range distinct from unsupported model through final seed')

def provenance():
    row=S.layer_equities_by_pot_layer(
        3,['Kh','Ac'],[],[L],{}, {9:WEIGHTED},sims=20,
        seed=42,capture_sampling=True,
        range_metadata={9:{'source':'observer_actor_policy_conditional_v1',
           'complete':True,'range_signature':'fixture'}})[0]
    assert row['complete'] and row['valid_samples']==20
    assert row['requested_samples']==20 and row['rejected_samples']==0
    assert row['seed']==row['sampling']['seed']
    assert row['sample_variance'] is not None
    assert 0<=row['split_pot_draws']<=20
    assert row['sampling']['share_sum_sq']>=0
    assert row['sampling']['mean_share']==row['equity'] or abs(
        row['sampling']['mean_share']-row['equity'])<0.0000006
    state=random.getstate()
    row2=S.layer_equities_by_pot_layer(
        3,['Kh','Ac'],[],[L],{}, {9:WEIGHTED},sims=20,
        seed=42,capture_sampling=False)[0]
    assert row2['equity']==row['equity']
    assert row2['seed']==row['seed']
    assert random.getstate()==state
    assert R.range_mass(WEIGHTED)==1.0
    print('PASS weighted pool, samples, seed, variance, split-pot trace, RNG parity')

def main():
    status_tests()
    provenance()
    print('PASS P5 independent PR18 end-to-end consumer status tests')

if __name__=='__main__':
    main()
