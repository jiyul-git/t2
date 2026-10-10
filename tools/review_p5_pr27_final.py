#!/usr/bin/env python3
"""P5 independent PR27 acceptance: frozen/current/partial BF into actual caller.

Immutable production base 3c434b28046643ba54c04447951ad148ae6f9c1c.
Tests are audit-only; no game rules, coefficients, or action policy changes.
"""
import json
import math
import os
import random
import sys
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fieldsim as FS
import icm as I
import play as P
import plan as PL
import session as S
import reads as RD
import range_posterior_v1 as RP
import ranges as R
from tools.verify_p13_field_epoch_freshness import field,stamped
from tools.verify_pr21_actor_bf_provenance import get_first_in
from tools.verify_pr16_p5_provenance import fixture
from tools.verify_hand130_b37_replay import original

PRICE=53442.0
BEFORE=108442.0

def p5_action(source,eq,missing=None,exact_hu=None):
    sh={'pure_calloff':True,'complete':missing is None,
        'effective_equity':eq if missing is None else None,
        'call_cost':PRICE,'contestable_after_call':BEFORE+PRICE,
        'exact_hu_icm':exact_hu,
        'missing_equity_layers':[0] if missing else [],
        'incomplete_reasons':{0:missing} if missing else {}}
    base=original()
    a=base['actor_pf_seed']
    rng=random.Random(55126)
    rng_state=rng.getstate()
    action,size,seed=PL.preflop_plan(
        {'type':'TAG'},'LJ',['Kh','Ac'],a['pf_stack_bb'],rng,
        aggressor_pos='BB',open_bb=a['pf_open_bb'],
        n_callers=0,n_limpers=0,raise_level=2,
        can_raise=False,opener_allin=True,
        pot_bb=BEFORE/10000,to_call_bb=PRICE/10000,
        seats=8,ante=True,bb_chips=10000,bf=source['value'],
        prior_pf={'pf_act':'raise','pf_role':'open'},
        call_ev_shadow=sh,calloff_decision_seed=3365551903)
    assert rng.getstate()==rng_state,'shared RNG moved'
    seed['pf_bf_provenance']=dict(source)
    return action,size,seed

def source_variants():
    full=field()
    h=stamped(full)
    exact=h.bf_details(3)
    assert exact['field_epoch_status']=='current_verified'
    assert exact['snapshot_current'] and exact['is_exact']
    assert exact['observed_epoch_diverged'] is False
    assert exact['observed_field_epoch_id']==exact['field_snapshot_id']

    freeze=field()
    freeze._frozen_field=freeze.field_snapshot()
    hf=stamped(freeze)
    before=hf.bf_details(3)
    assert before['method']=='frozen_epoch_reference_icm'
    assert before['snapshot_epoch_exact'] is True
    assert before['is_exact'] is False
    assert before['observed_field_epoch_id'] is None
    assert before['observed_epoch_diverged'] is None
    assert math.isclose(before['value'],exact['value'],abs_tol=1e-12)
    # Remote drift is purposely unobservable *within* frozen round.
    freeze.players['2']['stack']+=1000
    freeze.players['4']['stack']-=1000
    still=hf.bf_details(3)
    assert still==before,'active frozen BF changed after unobserved remote work'

    partial_full=field()
    hp=stamped(partial_full)
    mini=SimpleNamespace(
        players={str(s):{'pid':'P%s'%s,'stack':hp.field_pid_stacks['P%s'%s]}
                 for s in (1,3,5,8,9)},
        hand_no=partial_full.hand_no,level=partial_full.level,_frozen_field=None)
    hp._field_epoch_owner=mini
    unknown=hp.bf_details(3)
    assert unknown['method']=='field_bf_empirical_approximation'
    assert unknown['field_epoch_status']=='unobservable_partial_field'
    assert unknown['observed_field_epoch_id'] is None
    assert unknown['observed_epoch_diverged'] is None
    assert unknown['snapshot_current'] is False
    assert unknown['snapshot_epoch_exact'] is False
    assert not unknown['is_exact']

    mini._frozen_field=freeze._frozen_field
    hp_f=stamped(freeze)
    hp_f._field_epoch_owner=mini
    hp_f._field_frozen_epoch_ref=freeze._frozen_field
    mini_frozen=hp_f.bf_details(3)
    assert mini_frozen==before,('partial/full frozen provenance differs',
                                mini_frozen,before)
    # A real clock progression invalidates even still-referenced frozen object.
    mini.hand_no+=1
    expired=hp_f.bf_details(3)
    assert expired['field_epoch_status']=='expired_frozen_epoch'
    assert expired['method']=='field_bf_empirical_approximation'
    assert expired['observed_field_epoch_id'] is None
    assert expired['observed_epoch_diverged'] is None
    mini.hand_no-=1

    # Outside frozen scope actual remote change remains observable and stale.
    full.players['2']['stack']+=1000
    full.players['4']['stack']-=1000
    stale=h.bf_details(3)
    assert stale['field_epoch_status']=='stale_remote'
    assert stale['observed_epoch_diverged'] is True
    assert stale['field_snapshot_id']!=stale['observed_field_epoch_id']
    assert not stale['is_exact']

    out={'current':exact,'frozen':before,'mini_frozen':mini_frozen,
         'partial':unknown,'expired':expired,'stale':stale}
    for label,source in out.items():
        assert source['price_specific'] is False,label
        assert source['bf_kind']=='generic_default_risk_not_spot_call_prize_ev',label
        assert source['value']>=1,label
        assert source['is_exact'] is (label=='current'),label
    print('PASS live P13 full/current/frozen/mini partial/expired/remote BF cases with honest epoch statuses')
    return out

def p5_consumers(sources):
    for name,src in sources.items():
        # On a fully conditioned draw, P5 consumer must consume the SAME
        # full-precision numerical field BF as the matching final seed.
        action,size,seed=p5_action(src,0.53)
        c=seed['pf_calloff_consumer']
        assert c['strategy_consumer'] is True
        assert math.isclose(c['objective_unconditional_bf'],src['value'],rel_tol=1e-14)
        assert math.isclose(c['objective_spot_bf'],src['value'],rel_tol=1e-14)
        assert c['icm_pricing_basis']=='generic_bf_approximation_not_spot_validated'
        assert c['exact_hu_icm'] is None and c['icm_fallback_risk'] is not None
        assert c['mathematically_justified'] is False
        assert seed['pf_bf_provenance']==src
        assert action in ('fold','call')
        print(json.dumps({'case':name,'BF':src['value'],
          'method':src['method'],'decision':action,
          'observed_epoch_diverged':src['observed_epoch_diverged']},
          sort_keys=True))

    # Synthetic midpoint is algebraic sensitivity, not an AK exception
    # and not an assertion about original hand outcome.
    exact=sources['current'];approx=sources['partial']
    high=I.required_equity(BEFORE,PRICE,exact['value'])
    low=I.required_equity(BEFORE,PRICE,approx['value'])
    assert high>low
    e=(high+low)/2
    a,_,_=p5_action(exact,e)
    b,_,_=p5_action(approx,e)
    assert (a,b)==('fold','call'),(a,b,high,low)
    f,_,_=p5_action(sources['frozen'],e)
    assert f==a,('frozen/reference BF changed its numeric value',a,f)
    print(json.dumps({'case':'BF price sensitivity fixed synthetic equity',
       'equity_not_real_HAND130':e,'current':a,'frozen':f,
       'partial_empirical':b,'current_bf':exact['value'],
       'partial_bf':approx['value']},sort_keys=True))
    print('PASS P5 BF number/provenance and selected action agree in all epoch modes')

def missing_mc_with_actor_source(sources):
    old=os.environ.get('T2_RANGE_CONDITIONAL_V1')
    state=random.getstate()
    try:
        os.environ['T2_RANGE_CONDITIONAL_V1']='1'
        run,rnd=fixture()
        for name in ('current','frozen','partial'):
            actor=sources[name]
            # Use REAL P8 conditional model adapter + target actor BF source.
            weighted,meta=get_first_in(run,rnd,actor,18.)
            assert weighted and meta['complete'],(name,meta)
            assert meta['actor_bf_provenance']==actor
            assert meta['actor_bf_evaluation_phase']=='observer_reconstruction'
            assert meta['actor_action_epoch_bf_verified'] is False
            assert meta['observer_model_inputs']['bubble_factor']==actor['value']
            layer=[{'idx':0,'hero_eligible':True,
                    'eligible_seats':[3,9],'amount':161884,'level':73442}]
            row=S.layer_equities_by_pot_layer(
                3,['Ac','Kh'],[],layer,{}, {9:weighted},sims=32,
                seed=399,range_metadata={9:meta},
                capture_sampling=True)[0]
            assert row['complete'] and row['equity'] is not None
            assert row['valid_samples']==row['requested_samples']==32
            assert row['range_provenance']['9']['actor_bf_provenance']==actor
            assert row['sampling']['seed']==row['seed']
            assert row['sampling']['sample_variance']==row['sample_variance']
            summ=S._layer_call_summary(PRICE,layer,[row])
            assert summ['complete']
            hero=sources['partial'] if name=='current' else sources['current']
            a,sz,seed=p5_action(hero,summ['effective_equity'])
            S._attach_p8_observer_evidence(seed,{9:meta})
            assert seed['pf_bf_provenance']==hero
            assert seed['pf_calloff_consumer']['opponent_range_evidence']['9']['actor_bf_provenance']==actor
            replay=RP.replay_record({9:weighted},{9:meta},
                                    layers=[row],event_tag=name)
            assert replay['opponents']['9']['source_metadata']['actor_bf_provenance']==actor
            assert replay['layer_sampling'][0]['range_provenance']['9']['actor_bf_provenance']==actor

            # Force an INCOMPLETE producer despite nonempty candidate:
            # actor BF evidence, missing cause and failed status all survive
            # P5 final consumer and empty-range replay, with no fabricated EV.
            failed=dict(meta,complete=False,status='missing_evidence',
                        missing=['simulated_missing_actor_likelihood'],
                        failure_kind='missing_evidence')
            absent=S.layer_equities_by_pot_layer(
                3,['Ac','Kh'],[],layer,{}, {9:weighted},
                sims=32,seed=399,range_metadata={9:failed})[0]
            assert absent['equity'] is None and absent['complete'] is False
            assert absent['range_provenance']['9']['actor_bf_provenance']==actor
            absent_sum=S._layer_call_summary(PRICE,layer,[absent])
            assert absent_sum['complete'] is False
            assert absent_sum['effective_equity'] is None
            fallback,sz,unverified=p5_action(
                hero,None,missing=absent_sum['incomplete_reasons'][0])
            assert fallback=='fold'
            S._attach_p8_observer_evidence(unverified,{9:failed})
            decision=unverified['pf_calloff_consumer']
            assert decision['strategy_consumer'] is False
            assert decision['mathematically_justified'] is False
            assert decision['equity_status']=='unavailable_not_negative_ev'
            assert decision['incomplete_reasons'][0]['range_provenance']['9']['actor_bf_provenance']==actor
            assert decision['opponent_range_evidence']['9']['actor_bf_provenance']==actor
            empty=RP.replay_record({},{9:failed},layers=[absent])
            assert empty['opponents']=={}
            assert empty['range_metadata']['9']['actor_bf_provenance']==actor
            assert random.getstate()==state
        print('PASS P8 actor BF current/frozen/partial through valid + incomplete MC, P5 final log and empty replay')
    finally:
        if old is None:os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:os.environ['T2_RANGE_CONDITIONAL_V1']=old

def main():
    sources=source_variants()
    p5_consumers(sources)
    missing_mc_with_actor_source(sources)
    print('PASS P5 independent PR27 final judgement and epoch/RNG provenance')

if __name__=='__main__':
    main()
