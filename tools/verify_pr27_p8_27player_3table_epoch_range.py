#!/usr/bin/env python3
"""P8 independent immutable PR27 review: actual 27 players / 3 tables.

Do not fabricate a remote observed epoch from a partial worker, convert
None to False, or infer original actor action-time BF from reconstruction.
Only uses production P13 BF, P8 range, P9 sampler, P5 metadata consumers.
No strategy constants or producer changes.
"""
import json
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import fieldsim as FS
import play as P
import ranges as R
import range_posterior_v1 as RP
import session as S
import reads as RD
from tools.verify_pr16_p5_provenance import fixture
from tools.verify_pr21_actor_bf_provenance import get_first_in

BFS=('value','method','is_exact','reason','field_completeness',
     'field_snapshot_id','field_epoch_status','snapshot_epoch_exact',
     'snapshot_current','observed_field_epoch_id',
     'observed_epoch_diverged','field_observation_status',
     'field_snapshot_scope','price_specific')
def hand_for(f,tb):
    alive=tb.ordered_alive()
    seats=[tb.seat_of(p['pid']) for p in alive]
    h=object.__new__(P.Hand)
    h.seats=list(seats)
    h.stacks={tb.seat_of(p['pid']):p['stack'] for p in alive}
    h._start_stacks=dict(h.stacks)
    h.seat_pid={tb.seat_of(p['pid']):p['pid'] for p in alive}
    f.stamp(h)
    return h, seats[0]

def partial_owner(f,tb):
    return SimpleNamespace(
        players={p['pid']:{'pid':p['pid'],'stack':p['stack']}
                 for p in tb.ordered_alive()},
        hand_no=f.hand_no,level=f.level,_frozen_field=None)

def assert_unknown(d, label):
    assert d['field_epoch_status']==label,d
    assert d['observed_field_epoch_id'] is None,d
    assert d['observed_epoch_diverged'] is None,d
    assert d['is_exact'] is False,d
    assert d['snapshot_current'] is False,d
    for key in BFS:assert key in d,(key,d)

def verify_field():
    f=FS.Field(entries=27,start_stack=30000,hero_pid=0,seed=8227)
    assert len(f.tables)==3 and f.remaining()==27
    assert sorted(tb.n() for tb in f.tables.values())==[9,9,9]
    tb=next(iter(f.tables.values()))
    h,seat=hand_for(f,tb)
    current=h.bf_details(seat)
    assert current['field_epoch_status']=='current_verified',current
    assert current['observed_field_epoch_id']==current['field_snapshot_id']
    assert current['observed_epoch_diverged'] is False
    assert current['field_observation_status']=='verified_full_current_roster'
    # 27 survivors exceeds exact ICМ capacity: full roster current DOES
    # NOT imply an exact generic BF, and no BF=1 synthetic shortcut.
    assert current['is_exact'] is False
    assert current['method']=='field_bf_empirical_approximation'
    assert current['price_specific'] is False

    # Partial worker has local table only; cannot form whole-field epoch.
    mini=partial_owner(f,tb)
    h._field_epoch_owner=mini
    unknown=h.bf_details(seat)
    assert_unknown(unknown,'unobservable_partial_field')
    assert unknown['field_observation_status']=='incomplete_current_field_roster'
    assert unknown['reason']=='more_than_exact_max_survivors'
    assert unknown['field_snapshot_id']==current['field_snapshot_id']

    # Current reference is FULL owner, so remote-only drift is measurable
    # without changing this table's chip state or adding lost chips.
    h._field_epoch_owner=f
    remote=[p for p in f.players.values() if p['table']!=tb.id]
    assert len(remote)==18
    remote[0]['stack']+=2000
    remote[1]['stack']-=2000
    changed=h.bf_details(seat)
    assert changed['field_epoch_status']=='stale_remote',changed
    assert changed['observed_epoch_diverged'] is True
    assert changed['observed_field_epoch_id']!=changed['field_snapshot_id']
    assert changed['field_observation_status']=='verified_full_current_roster'
    assert changed['is_exact'] is False

    # Frozen common logical round: coordinator and partial worker MUST
    # share evidence without sampling a live (possibly advanced) roster.
    frozen=f.field_snapshot()
    f._frozen_field=frozen
    fh,s=hand_for(f,tb)
    full_frozen=fh.bf_details(s)
    assert_unknown(full_frozen,'frozen_epoch_reference') if False else None
    assert full_frozen['field_epoch_status']=='frozen_epoch_reference'
    assert full_frozen['observed_field_epoch_id'] is None
    assert full_frozen['observed_epoch_diverged'] is None
    assert full_frozen['snapshot_current'] is False
    assert full_frozen['is_exact'] is False
    # >9 does not promote mathematical epoch exactness.
    assert full_frozen['snapshot_epoch_exact'] is False
    mini._frozen_field=frozen
    fh._field_epoch_owner=mini
    worker_frozen=fh.bf_details(s)
    assert worker_frozen==full_frozen
    assert worker_frozen['observed_field_epoch_id'] is None
    assert worker_frozen['observed_epoch_diverged'] is None

    mini.hand_no+=1
    expired=fh.bf_details(s)
    assert_unknown(expired,'expired_frozen_epoch')
    assert expired['field_observation_status']=='frozen_clock_mismatch'
    mini.hand_no-=1
    mini.level+=1
    expired_level=fh.bf_details(s)
    assert_unknown(expired_level,'expired_frozen_epoch')
    mini.level-=1
    mini._frozen_field=None
    release=fh.bf_details(s)
    assert_unknown(release,'expired_frozen_epoch')

    return f,tb,{'current_verified':current,
                 'unobservable_partial_field':unknown,
                 'stale_remote':changed,
                 'frozen_epoch_reference':worker_frozen,
                 'expired_frozen_epoch':expired}

def verify_pipeline(states):
    start_rng=random.getstate()
    old=os.environ.get('T2_RANGE_CONDITIONAL_V1')
    os.environ['T2_RANGE_CONDITIONAL_V1']='1'
    try:
        run,rnd=fixture()
        run.h.field_avg_stack=112500
        layer=[{'idx':0,'level':73442,'amount':161884,
                'hero_eligible':True,'eligible_seats':[3,9]}]
        actual=[]
        for status,src in states.items():
            # Full source dictionary comes from actual P13 Hand.bf_details,
            # NOT a hand-written unobserved epoch or a substituted status.
            pool,meta=get_first_in(run,rnd,src,18.)
            assert pool and meta['complete'],(status,meta)
            assert meta['actor_bf_provenance']==src,(status,meta)
            assert meta['observer_model_inputs']['actor_bf_provenance']==src
            assert meta['observer_model_inputs']['bubble_factor']==src['value']
            assert meta['actor_bf_evaluation_phase']=='observer_reconstruction'
            assert meta['actor_action_epoch_bf_verified'] is False
            assert meta['actor_bf_likelihood_direct_input'] is True
            for k in BFS:
                assert meta['actor_bf_provenance'][k]==src[k],(status,k)

            # P9 full accepted weighted MC; preserve seed and variance
            # and all 27-field epoch evidence in this normal pot layer.
            valid=S.layer_equities_by_pot_layer(
                3,['Ac','Kh'],[],layer,{}, {9:pool},
                sims=32,seed=4227,range_metadata={9:meta},
                capture_sampling=True)[0]
            assert valid['complete'] and valid['equity'] is not None
            assert valid['requested_samples']==valid['valid_samples']==32
            assert valid['rejected_samples']==0
            assert valid['sampling']['seed']==valid['seed']
            assert valid['sample_variance']==valid['sampling']['sample_variance']
            assert valid['range_provenance']['9']['actor_bf_provenance']==src

            # Deliberately incomplete posterior with *non-empty* weighted
            # candidate must fail closed without replacing source metadata.
            missing=dict(meta,complete=False,status='missing_evidence',
                         missing=['public_actor_stack_bb'],
                         failure_kind='missing_evidence')
            incomplete=S.layer_equities_by_pot_layer(
                3,['Ac','Kh'],[],layer,{}, {9:pool},
                sims=32,seed=4227,range_metadata={9:missing})[0]
            assert not incomplete['complete'] and incomplete['equity'] is None
            assert incomplete['range_provenance']['9']['actor_bf_provenance']==src
            assert incomplete['missing_range_details']['9']['actor_bf_provenance']==src
            summ=S._layer_call_summary(53442,layer,[incomplete])
            assert not summ['complete'] and summ['effective_equity'] is None
            assert summ['incomplete_reasons'][0]['range_provenance']['9']['actor_bf_provenance']==src
            seed={'pf_bf_provenance':{'value':77.0,'method':'deciding_player_only'},
                  'pf_calloff_consumer':{'selected_action':'fold',
                   'mathematically_justified':False,
                   'equity_status':'unavailable_not_negative_ev',
                   'incomplete_reasons':summ['incomplete_reasons']}}
            S._attach_p8_observer_evidence(seed,{9:missing})
            assert seed['pf_bf_provenance']['method']=='deciding_player_only'
            assert seed['pf_calloff_consumer']['opponent_range_evidence']['9']['actor_bf_provenance']==src
            assert seed['pf_calloff_consumer']['incomplete_reasons'][0]['range_provenance']['9']['actor_bf_provenance']==src

            # No combos means no opponents record but MUST leave full
            # original BF provenance including None, False and True.
            rec=RP.replay_record({},{9:missing},layers=[incomplete],
                                 event_tag='P8-PR27-'+status)
            out=json.loads(json.dumps(rec,allow_nan=False))
            assert out['opponents']=={}
            assert out['range_metadata']['9']['actor_bf_provenance']==src
            assert out['layer_sampling'][0]['range_provenance']['9']['actor_bf_provenance']==src
            assert out['range_metadata']['9']['actor_action_epoch_bf_verified'] is False
            for k in ('observed_field_epoch_id','observed_epoch_diverged'):
                assert out['range_metadata']['9']['actor_bf_provenance'][k] is src[k],(status,k)
            actual.append({'state':status,'method':src['method'],
                           'field_observation_status':src['field_observation_status'],
                           'snapshot_current':src['snapshot_current'],
                           'snapshot_epoch_exact':src['snapshot_epoch_exact'],
                           'observed_epoch_diverged':src['observed_epoch_diverged'],
                           'mass':R.range_mass(pool),'support':len(pool),
                           'mc_accepted':valid['valid_samples']})
        assert random.getstate()==start_rng
        print(json.dumps({'actual_entries':27,'tables':3,
             'production_epoch_states_in_actor_range_and_p5':actual,
             'empty_replay_retains_null_distinction':True,
             'complete_and_incomplete_layers_provenance':True,
             'shared_rng_preserved':True,
             'actor_action_epoch_bf_verified':False,
             'original_HAND130_288_combos_rebuilt':False},
             sort_keys=True,allow_nan=False))
        print('PASS independent PR27 real 27/3 partial/frozen/expired/full/stale provenance to weighted MC, empty replay, P5 and RNG')
    finally:
        if old is None:os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:os.environ['T2_RANGE_CONDITIONAL_V1']=old

if __name__=='__main__':
    _,_,states=verify_field()
    verify_pipeline(states)
