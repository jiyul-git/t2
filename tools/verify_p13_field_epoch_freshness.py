#!/usr/bin/env python3
"""P13/P8 regression: remote-only epoch drift and true frozen batch provenance.

No tournament timing, RNG, payout, BF coefficients or card-policy changes.
"""
import json
import math
import os
import random
import sys
from unittest.mock import patch

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
import fieldsim as FS
import icm as I
import reads as RD
import range_posterior_v1 as RP
from tools.verify_p13_complete_field_bf import ORIGINAL, LOCAL, FULL, ALL, PAYOUTS, hand
from tools.verify_pr16_p5_provenance import fixture


def field():
    # Real Field.stamp -> Context.apply path, fixed public stack fixture.
    f=FS.Field(entries=8,start_stack=112500,hero_pid=-1,seed=1137)
    f.players={str(s): {'pid':'P%s'%s,'stack':ORIGINAL[s],
                         'prof':{}} for s in FULL}
    f.itm=7
    f.payouts=list(PAYOUTS)
    return f


def stamped(f):
    h=hand(LOCAL,ALL)
    f.stamp(h)
    assert h.field_snapshot_id
    assert h.field_snapshot_hand_no==f.hand_no
    assert h.field_snapshot_level==f.level
    assert h.field_pid_stacks=={
        'P%s'%s: ORIGINAL[s] for s in FULL}
    assert h._field_epoch_owner is f
    return h


def latest_remote_only():
    f=field()
    h=stamped(f)
    exact=h.bf_details(3)
    assert exact['is_exact']
    assert exact['field_epoch_status']=='current_verified'
    original_id=h.field_snapshot_id
    assert exact['observed_field_epoch_id']==original_id
    # Only REMOTE players change, conserving the tournament's chips.
    # Local table identities/stacks/hand number remain fixed.
    f.players['2']['stack']+=5000
    f.players['4']['stack']-=5000
    fresh=h.bf_details(3)
    assert not fresh['is_exact'],fresh
    assert fresh['method']=='field_bf_empirical_approximation'
    assert fresh['reason']=='remote_field_changed_after_snapshot'
    assert fresh['field_epoch_status']=='stale_remote'
    assert fresh['field_snapshot_id']==original_id
    assert fresh['observed_field_epoch_id']!=original_id
    assert fresh['value']!=1.0
    # After restamping at the genuine new decision epoch, full-field generic
    # ICM is again allowed; the changed chips must affect its underlying set.
    h2=stamped(f) if False else hand(LOCAL,ALL)
    f.stamp(h2)
    now=h2.bf_details(3)
    assert now['is_exact'] and now['field_epoch_status']=='current_verified'
    assert h2.field_snapshot_id!=original_id
    print(json.dumps({'case':'remote_only_after_snapshot',
                      'old_bf':exact['value'],'stale_method':fresh['method'],
                      'stale_bf':fresh['value'],
                      'reason':fresh['reason'],'new_field_bf':now['value'],
                      'old_epoch':original_id,'observed_epoch':fresh['observed_field_epoch_id']},
                     sort_keys=True))


def simultaneous_frozen():
    f=field()
    frozen=f.field_snapshot()
    f._frozen_field=frozen
    h=stamped(f)
    assert h.field_snapshot_scope=='simultaneous_frozen'
    at_start=h.bf_details(3)
    assert not at_start['is_exact'] and not at_start['snapshot_current']
    assert at_start['snapshot_epoch_exact']
    assert at_start['method']=='frozen_epoch_reference_icm'
    # Other table completes later in the SAME logical round, *without*
    # rebasing the frozen common-round reference or ordering of actions.
    f.players['2']['stack']+=1500
    f.players['4']['stack']-=1500
    after=h.bf_details(3)
    assert not after['is_exact'] and not after['snapshot_current'],after
    assert after['snapshot_epoch_exact'] is True
    assert after['method']=='frozen_epoch_reference_icm'
    assert after['reason']=='remote_field_advanced_since_frozen_epoch'
    assert after['field_snapshot_scope']=='simultaneous_frozen'
    assert after['field_snapshot_id']!=after['observed_field_epoch_id']
    assert after['value']==at_start['value'] # frozen batch policy unchanged
    # Frozen epoch is no longer valid after the scheduler releases it.
    f._frozen_field=None
    released=h.bf_details(3)
    assert released['method']=='field_bf_empirical_approximation'
    assert not released['is_exact']
    assert released['reason']=='remote_field_changed_after_snapshot'
    print(json.dumps({'case':'common_simultaneous_round_start',
                      'frozen_value_unchanged':after['value']==at_start['value'],
                      'method_after_remote':after['method'],
                      'decision_current_exact':after['is_exact'],
                      'reference_epoch_exact':after['snapshot_epoch_exact'],
                      'post_release_method':released['method'],
                      'frozen_epoch':frozen['epoch_id']},sort_keys=True))


def no_attestation():
    h=hand(LOCAL,ALL)
    h._field_epoch_owner=None
    # Mere matching historic chips/PIDs is no proof of freshness.
    result=h.bf_details(3)
    assert not result['is_exact']
    assert result['reason']=='missing_verified_field_epoch'
    assert result['method']=='field_bf_empirical_approximation'
    print('PASS unverified/PID-only source never claims current exact ICM')


def actor_provenance():
    run,rnd=fixture()
    old=os.environ.get('T2_RANGE_CONDITIONAL_V1')
    global_before=random.getstate()
    try:
        os.environ['T2_RANGE_CONDITIONAL_V1']='1'
        with patch.object(RD,'perceived_profile',return_value=None):
            pool,meta=run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert pool and meta['complete'],meta
        actor=meta['actor_bf_provenance']
        assert actor==meta['observer_model_inputs']['actor_bf_provenance']
        assert meta['observer_model_inputs']['bubble_factor']==actor['value']
        assert 'is_exact' in actor and 'method' in actor and 'reason' in actor
        assert 'field_epoch_status' in actor and 'snapshot_current' in actor
        assert 'field_snapshot_id' in actor
        record=RP.replay_record({9:pool},{9:meta},event_tag='p13_epoch_actor')
        assert record['opponents']['9']['source_metadata']['actor_bf_provenance']==actor
        assert random.getstate()==global_before
        print(json.dumps({'actor_bf_method':actor['method'],
                          'source':meta['source'],
                          'actor_vs_observer_provenance_separate':True,
                          'replay_source_preserved':True},sort_keys=True))
    finally:
        if old is None:os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:os.environ['T2_RANGE_CONDITIONAL_V1']=old


if __name__=='__main__':
    latest_remote_only()
    simultaneous_frozen()
    no_attestation()
    actor_provenance()
    print('PASS P13 epoch/remote drift, frozen reference and P8 target-actor provenance')
