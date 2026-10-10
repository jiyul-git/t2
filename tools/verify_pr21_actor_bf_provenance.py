#!/usr/bin/env python3
"""P8 PR21 observed-actor BF provenance, isolated from P13 field-epoch work.

Checks the value used in actor-policy likelihood matches the exact bf_details
source of *target* (not observer/hero), with an unchanged posterior for
provenance-only changes, and lossless propagation to MC layers, replay and P5.
No calibrated prior, coefficient, forced range floor or GTO claim.
"""
import json
import math
import os
import random
import sys
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import icm as I
import ranges as R
import reads as RD
import range_posterior_v1 as RP
import session as S
from tools.verify_pr16_p5_provenance import fixture
from tools.verify_p13_complete_field_bf import hand, ORIGINAL, LOCAL, FULL, ALL, PAYOUTS


def bf_samples():
    exact=hand(LOCAL, ALL).bf_details(3)
    approximate=hand(LOCAL, ()).bf_details(3)
    assert exact['method']=='exact_full_field_icm' and exact['is_exact']
    assert approximate['method']=='field_bf_empirical_approximation'
    assert not approximate['is_exact']
    assert approximate['reason']=='missing_full_field_stacks'
    assert exact['bf_kind']=='generic_default_risk_not_spot_call_prize_ev'
    assert exact['price_specific'] is False
    # A new P13 field-time field must pass through intact; P8 doesn't
    # interpret or self-certify a snapshot epoch.
    next_epoch=dict(exact, field_snapshot_epoch='test-only-epoch-token')
    return exact,approximate,next_epoch


def first_in_event(stack):
    b=int(stack*10000)
    return RP.classify_public_action([{
        'seat':9,'action':'allin','raised':True,'full_raise':True,
        'actor_allin_after':True,'pre_stack':b,
        'pre_contrib':0,'post_contrib':b,
        'pre_current':10000,'post_current':b
    }],9,10000,'CO',seats=8,effective_stack_bb=stack)


def context(bf):
    return {'field_q':0.6, 'bubble_factor':bf, 'tilt':0.0,
            'payout_flat':0.0,'reentry':False,'progress':0.0,
            'erosion':0.0,'field_avg_bb':11.25,
            'behind_stacks_bb':[8.0,19.0]}


def get_first_in(run,rnd,details,stack):
    run.h.pos[9]='CO'
    run.h.bf_details=lambda s:dict(details) if s==9 else {
        'value':99.0,'method':'observer_not_actor'}
    event=first_in_event(stack)
    with patch.object(RD,'perceived_profile',return_value=None), \
         patch.object(RP,'classify_public_action',return_value=event), \
         patch.object(RP,'public_behind_stacks',return_value=(
             [8.0,19.0],{'source':'public_action_history_stack_snapshots'})):
        return run._preflop_perceived_range(
            3,9,{'concepts':{}},rnd,9,8,True)


def check_forward_contract():
    orig=os.environ.get('T2_RANGE_CONDITIONAL_V1')
    global_rng=random.getstate()
    try:
        os.environ['T2_RANGE_CONDITIONAL_V1']='1'
        exact,approx,forward=bf_samples()
        wrong=I.bubble_factor([ORIGINAL[s] for s in LOCAL],
                              PAYOUTS,LOCAL.index(3))
        corrected=exact['value']
        assert math.isclose(corrected,3.465325154547401,abs_tol=1e-10)
        run,rnd=fixture()
        # Match the full-field average from the earlier independent P8
        # first-in BF sensitivity witness (otherwise this is a different
        # policy context and the BF derivative can legitimately be zero).
        run.h.field_avg_stack=112500.0

        # One single production bf_details(target) invocation per observer
        # reconstruction, and no hidden call to h.bf(target).
        def forbidden_bf(_):
            raise AssertionError('scalar h.bf(target) must not be called')
        run.h.bf=forbidden_bf
        first,first_meta=get_first_in(run,rnd,forward,18.)
        assert first and first_meta['complete']
        assert first_meta['source']==RP.MODEL
        assert first_meta['actor_bf_provenance']['field_snapshot_epoch']==forward['field_snapshot_epoch']
        assert first_meta['actor_bf_provenance']['value']==corrected
        assert first_meta['observer_model_inputs']['bubble_factor']==corrected
        assert first_meta['observer_model_inputs']['actor_bf_provenance']==forward
        assert first_meta['actor_bf_evidence_source']=='Hand.bf_details(target)'
        assert first_meta['actor_bf_likelihood_direct_input'] is True
        assert first_meta['actor_bf_evaluation_phase']=='observer_reconstruction'
        assert first_meta['actor_action_epoch_bf_verified'] is False
        assert first_meta['actor_bf_provenance']['method']=='exact_full_field_icm'
        assert first_meta['actor_bf_provenance']['field_completeness']=='verified_player_id_field_snapshot'
        assert first_meta['actor_bf_provenance']['price_specific'] is False

        # Only the explanation changes: weighted combo dict stays exactly
        # unchanged, including float masses / signatures / support.
        alternate=dict(approx,value=corrected,
                       field_snapshot_epoch='new-P13-epoch-token')
        again,alternate_meta=get_first_in(run,rnd,alternate,18.)
        assert first==again
        assert R.range_signature(first)==R.range_signature(again)
        assert first_meta['posterior_mass']==alternate_meta['posterior_mass']
        assert first_meta['posterior_support']==alternate_meta['posterior_support']
        assert alternate_meta['actor_bf_provenance']['method']=='field_bf_empirical_approximation'
        assert alternate_meta['actor_bf_provenance']['reason']=='missing_full_field_stacks'
        assert not alternate_meta['actor_bf_provenance']['is_exact']
        assert alternate_meta['observer_model_inputs']['actor_bf_provenance']['snapshot_current'] is True

        # Real P13 method remains honest; that previous same-value synthetic
        # check only isolates the metadata transport, not actual BF valuation.
        missing,missing_meta=get_first_in(run,rnd,approx,18.)
        assert missing_meta['actor_bf_provenance']['value']==approx['value']
        assert missing_meta['actor_bf_provenance']['method']=='field_bf_empirical_approximation'
        assert missing_meta['actor_bf_provenance']['is_exact'] is False

        # Numeric BF change drives first-in likelihood for supported depths.
        old_meta=dict(forward,value=wrong)
        old,_=get_first_in(run,rnd,old_meta,18.)
        assert old!=first
        old21,_=get_first_in(run,rnd,old_meta,21.)
        new21,_=get_first_in(run,rnd,forward,21.)
        assert old21!=new21

        neutral=RD.range_profile(None)
        e3=RP.classify_public_action(rnd.action_meta,9,10000,'BB',
                                     seats=8,effective_stack_bb=6.3442)
        def combo3(p):
            run.h.pos[9]='BB'
            run.h.bf_details=lambda s:dict(p)
            with patch.object(RD,'perceived_profile',return_value=None):
                return run._preflop_perceived_range(
                    3,9,{'concepts':{}},rnd,9,8,True)
        old3,mold3=combo3(old_meta)
        new3,mnew3=combo3(forward)
        assert old3==new3 and len(new3)==845
        assert mold3['actor_bf_provenance']['value']==wrong
        assert mnew3['actor_bf_provenance']['value']==corrected
        assert mold3['actor_bf_likelihood_direct_input'] is False
        assert mnew3['actor_bf_likelihood_direct_input'] is False

        # Valid weighted MC layer carries provenance even though it is
        # complete and missing_range_details must stay empty.
        layer=[{'idx':0,'level':73442,'amount':161884,
                'hero_eligible':True,'eligible_seats':[3,9]}]
        out=S.layer_equities_by_pot_layer(
            3,['Ac','Kh'],[],layer,{}, {9:new3},sims=120,seed=271828,
            capture_sampling=True,range_metadata={9:mnew3})
        item=out[0]
        assert item['complete'] and item['equity'] is not None
        assert item['valid_samples']==item['requested_samples']==120
        assert item['range_provenance']['9']['actor_bf_provenance']==forward
        assert item['range_provenance']['9']['source']==RP.MODEL
        assert item['missing_range_details']=={}
        assert item['sampling']['seed']==item['seed']
        assert item['sampling']['sample_variance']==item['sample_variance']
        assert random.getstate()==global_rng

        rec=RP.replay_record({9:new3},{9:mnew3},layers=out,
                             event_tag='P8-PR21-observed-actor-provenance')
        decoded=json.loads(json.dumps(rec,allow_nan=False))
        recovered={(a,b):w for a,b,w in
                   decoded['opponents']['9']['weights']}
        assert recovered==new3
        assert decoded['opponents']['9']['source_metadata']['actor_bf_provenance']==forward
        assert decoded['range_metadata']['9']['actor_bf_provenance']==forward
        assert decoded['layer_sampling'][0]['range_provenance']['9']['actor_bf_provenance']==forward

        # P5 consumer owns *hero* BF, not actor BF. Both remain separately
        # identifiable, including an arbitrary future P13 snapshot field.
        pfseed={'pf_bf_provenance':{'value':1.987,'method':'hero_bf_only'},
                'pf_calloff_consumer':{'selected_action':'call',
                     'mathematically_justified':False}}
        S._attach_p8_observer_evidence(pfseed,{9:mnew3})
        assert pfseed['pf_bf_provenance']=={'value':1.987,'method':'hero_bf_only'}
        assert pfseed['pf_calloff_consumer']['opponent_range_evidence']['9']['actor_bf_provenance']==forward

        # Missing evidence has no combo pool but carries P13 method through
        # pot layer -> summary -> P5 missing log -> replay *metadata*.
        run.h.pos[9]='CO'
        run.h.bf_details=lambda s:dict(approx)
        with patch.object(RD,'perceived_profile',return_value=None), \
             patch.object(RP,'classify_public_action',return_value=first_in_event(18.)), \
             patch.object(RP,'public_behind_stacks',return_value=(
                 [8.,19.],{'source':'public_action_history_stack_snapshots'})), \
             patch.object(RP,'conditioned_preflop_range',return_value=(
                 None,{'source':RP.MODEL,'kind':'first_in_shove',
                       'complete':False,'missing':['public_actor_stack_bb']})):
            empty,failed=run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert not empty and not failed['complete']
        assert failed['actor_bf_provenance']['method']=='field_bf_empirical_approximation'
        pools,provenance={},{}
        S._record_preflop_observer_range(pools,provenance,9,empty,failed)
        assert not pools
        miss_layer=S.layer_equities_by_pot_layer(
            3,['Ac','Kh'],[],layer,{},pools,
            sims=120,seed=271828,range_metadata=provenance)
        row=miss_layer[0]
        assert not row['complete'] and row['equity'] is None
        assert row['missing_range_details']['9']['actor_bf_provenance']==failed['actor_bf_provenance']
        assert row['range_provenance']['9']['actor_bf_provenance']==failed['actor_bf_provenance']
        summary=S._layer_call_summary(53442,layer,miss_layer)
        assert not summary['complete'] and summary['call_chip_ev'] is None
        assert summary['incomplete_reasons'][0]['range_provenance']['9']['actor_bf_provenance']==failed['actor_bf_provenance']
        seed={'pf_bf_provenance':{'value':1.234,'method':'decider'},'pf_calloff_consumer':{
            'incomplete_reasons':summary['incomplete_reasons'],
            'mathematically_justified':False,'equity_status':'unavailable_not_negative_ev'}}
        S._attach_p8_observer_evidence(seed,provenance)
        assert seed['pf_calloff_consumer']['opponent_range_evidence']['9']['actor_bf_provenance']==failed['actor_bf_provenance']
        assert seed['pf_bf_provenance']['method']=='decider'
        no_combo=RP.replay_record(pools,provenance,layers=miss_layer)
        assert not no_combo['opponents']
        assert no_combo['range_metadata']['9']['actor_bf_provenance']==failed['actor_bf_provenance']

        # Unsupported call_allin still labels legacy_fallback explicitly;
        # it is not upgraded to a successful weighted inference.
        run.h.bf_details=lambda s:dict(approx)
        with patch.object(RD,'perceived_profile',return_value=None), \
             patch.object(RP,'classify_public_action',
                          return_value={'kind':'call_allin'}):
            legacy,unsupported=run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert legacy and unsupported['source']=='legacy_fallback'
        assert unsupported['complete'] is False
        assert unsupported['actor_bf_provenance']==dict(approx)
        assert unsupported['actor_bf_likelihood_direct_input'] is False

        # Legacy OFF never accesses bf_details merely to construct a range.
        os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        run.h.bf_details=lambda s: (_ for _ in ()).throw(
            AssertionError('OFF must not call actor bf_details'))
        with patch.object(RD,'perceived_profile',return_value=None):
            off,off_meta=run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert off and 'actor_bf_provenance' not in off_meta
        assert random.getstate()==global_rng

        print(json.dumps({
            'source':'P8_source_actor_bf_details',
            'first_in_18bb_mass_old':R.range_mass(old),
            'first_in_18bb_mass_new':R.range_mass(first),
            'first_in_21bb_mass_old':R.range_mass(old21),
            'first_in_21bb_mass_new':R.range_mass(new21),
            'threebet_support':len(new3),
            'threebet_mass':R.range_mass(new3),
            'same_bf_provenance_only_combo_identity':True,
            'old_vs_new_numeric_bf_first_in_changes':True,
            'threebet_bf_independent':True,
            'mc_accepted':item['valid_samples'],
            'mc_seed':item['seed'],
            'replay_contains_missing_range_evidence':True,
            'default_off_untouched':True,
            'global_rng_preserved':True,
            'archived_HAND130_288_recreated':False
        },sort_keys=True))
        print('PASS actor BF provenance vs hero BF, future P13 epoch, replay, successful/incomplete layer, P5')
    finally:
        if orig is None:
            os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:
            os.environ['T2_RANGE_CONDITIONAL_V1']=orig


if __name__=='__main__':
    check_forward_contract()
