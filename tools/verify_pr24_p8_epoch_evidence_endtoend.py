#!/usr/bin/env python3
"""P8 / P13 exact epoch-data transport on PR24 + selective PR23 integration.

Read real P13 Field/Hand.bf_details sources. Never manufacture epoch status
or infer BF at actor original action time from later observer reconstruction.
"""
import json
import os
import random
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import ranges as R
import session as S
import range_posterior_v1 as RP
from tools.verify_p13_field_epoch_freshness import field, stamped
from tools.verify_pr16_p5_provenance import fixture
from tools.verify_pr21_actor_bf_provenance import get_first_in

KEYS=('field_snapshot_id','field_epoch_status',
      'snapshot_epoch_exact','snapshot_current')


def real_p13_variants():
    f=field()
    h=stamped(f)
    initial=h.bf_details(3)
    assert initial['field_epoch_status']=='current_verified'
    assert initial['snapshot_current'] is True
    assert initial['snapshot_epoch_exact'] is True
    assert initial['is_exact'] is True
    f.players['2']['stack']+=5000
    f.players['4']['stack']-=5000
    stale=h.bf_details(3)
    assert stale['field_epoch_status']=='stale_remote'
    assert stale['snapshot_current'] is False
    assert stale['snapshot_epoch_exact'] is False
    assert stale['is_exact'] is False
    assert stale['reason']=='remote_field_changed_after_snapshot'
    assert stale['field_snapshot_id']==initial['field_snapshot_id']
    assert stale['observed_field_epoch_id']!=initial['observed_field_epoch_id']

    f2=field()
    f2._frozen_field=f2.field_snapshot()
    hh=stamped(f2)
    frozen=hh.bf_details(3)
    assert frozen['field_epoch_status']=='frozen_epoch_reference'
    assert frozen['snapshot_current'] is False
    assert frozen['snapshot_epoch_exact'] is True
    assert frozen['is_exact'] is False
    assert frozen['field_snapshot_id']==hh.field_snapshot_id
    assert frozen['method']=='frozen_epoch_reference_icm'
    return [('current_verified',initial),
            ('stale_remote',stale),
            ('frozen_epoch_reference',frozen)]


def verify():
    rng_before=random.getstate()
    old=os.environ.get('T2_RANGE_CONDITIONAL_V1')
    try:
        os.environ['T2_RANGE_CONDITIONAL_V1']='1'
        run,rnd=fixture()
        run.h.field_avg_stack=112500
        layer=[{'idx':0,'level':73442,'amount':161884,
                'hero_eligible':True,'eligible_seats':[3,9]}]
        done=[]
        for tag,original in real_p13_variants():
            weighted,meta=get_first_in(run,rnd,original,18.0)
            assert weighted and meta['complete'], (tag,meta)
            assert meta['actor_bf_provenance']==original
            assert meta['observer_model_inputs']['actor_bf_provenance']==original
            assert meta['observer_model_inputs']['bubble_factor']==original['value']
            assert meta['actor_bf_evaluation_phase']=='observer_reconstruction'
            assert meta['actor_action_epoch_bf_verified'] is False
            assert meta['actor_bf_evidence_source']=='Hand.bf_details(target)'
            assert meta['actor_bf_likelihood_direct_input'] is True
            for key in KEYS:
                assert key in original
                assert meta['actor_bf_provenance'][key]==original[key]
            assert meta['actor_bf_provenance']['price_specific'] is False
            assert meta['actor_bf_provenance']['bf_kind']=='generic_default_risk_not_spot_call_prize_ev'

            # Valid weighted MC path: metadata is a diagnostic layer, not
            # a new condition on sampler weights or ICM precision.
            complete=S.layer_equities_by_pot_layer(
                3,['Ac','Kh'],[],layer,{}, {9:weighted},
                range_metadata={9:meta}, sims=32,seed=4337,
                capture_sampling=True)[0]
            assert complete['complete'] and complete['valid_samples']==32
            assert complete['range_provenance']['9']['actor_bf_provenance']==original
            assert complete['sampling']['accepted']==32
            assert complete['sampling']['seed']==complete['seed']

            # Fail-closed path with nonempty candidate still cannot
            # turn a declared incomplete posterior into usable equity.
            fail=dict(meta,complete=False,status='missing_evidence',
                      missing=['synthetic_unverified_actor_model'],
                      failure_kind='missing_evidence')
            rejected=S.layer_equities_by_pot_layer(
                3,['Ac','Kh'],[],layer,{}, {9:weighted},
                range_metadata={9:fail}, sims=32,seed=4337)[0]
            assert rejected['equity'] is None and rejected['complete'] is False
            assert rejected['range_provenance']['9']['actor_bf_provenance']==original
            assert rejected['missing_range_details']['9']['actor_bf_provenance']==original
            summary=S._layer_call_summary(53442,layer,[rejected])
            assert not summary['complete'] and summary['effective_equity'] is None
            assert summary['incomplete_reasons'][0]['range_provenance']['9']['actor_bf_provenance']==original

            seed={'pf_bf_provenance':{'value':999.0,'method':'deciding_seat_only'},
                  'pf_calloff_consumer':{'selected_action':'fold',
                    'mathematically_justified':False,
                    'equity_status':'unavailable_not_negative_ev',
                    'incomplete_reasons':summary['incomplete_reasons']}}
            S._attach_p8_observer_evidence(seed,{9:fail})
            assert seed['pf_bf_provenance']['method']=='deciding_seat_only'
            evidence=seed['pf_calloff_consumer']['opponent_range_evidence']['9']
            assert evidence['actor_bf_provenance']==original
            assert evidence['actor_action_epoch_bf_verified'] is False
            assert seed['pf_calloff_consumer']['incomplete_reasons'][0]['range_provenance']['9']['actor_bf_provenance']==original

            replay=RP.replay_record({},{9:fail},layers=[rejected],
                                    event_tag=tag)
            record=json.loads(json.dumps(replay,allow_nan=False))
            assert record['opponents']=={}
            assert record['range_metadata']['9']['actor_bf_provenance']==original
            assert record['range_metadata']['9']['actor_bf_evaluation_phase']=='observer_reconstruction'
            assert record['layer_sampling'][0]['range_provenance']['9']['actor_bf_provenance']==original
            done.append({'status':tag,'snapshot_current':original['snapshot_current'],
                         'snapshot_epoch_exact':original['snapshot_epoch_exact'],
                         'is_exact':original['is_exact'],
                         'method':original['method'],
                         'support':len(weighted),
                         'mass':R.range_mass(weighted),
                         'field_snapshot_id':original['field_snapshot_id']})

        assert random.getstate()==rng_before
        print(json.dumps({'P13_epoch_cases':done,
                         'actor_action_epoch_inferred':False,
                         'normal_and_missing_layer_provenance':True,
                         'no_pool_replay_metadata':True,
                         'final_P5_hero_and_actor_separate':True,
                         'global_RNG_unchanged':True},
                         sort_keys=True))
        print('PASS PR24 current/stale/frozen P13 epoch 4-tuple losslessly reaches normal/missing layer, replay and P5 consumer')
    finally:
        if old is None:
            os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:
            os.environ['T2_RANGE_CONDITIONAL_V1']=old


if __name__=='__main__':
    verify()
