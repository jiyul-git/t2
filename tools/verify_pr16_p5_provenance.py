#!/usr/bin/env python3
"""P5's independent PR16 blocker contract: verification AFTER P8 corrections.

Original witness: P5 review commit 3f17b663; original reviewer script
tools/review_pr16_p5_contract.py. This test deliberately does NOT bless the
unresolved zero-accepted-MC issue, which is owned by Department 9.
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import session as S
import ranges as R
import range_posterior_v1 as RP
import reads as RD
from tools.verify_hand130_conditioned_posterior import rows


def fixture():
    h = SimpleNamespace(
        bb=10000, pos={3: 'LJ', 9: 'BB'},
        hole={3: ['Ac','Kh']}, hash='6e1ba98ab1a0',
        pf_seed={9: {'pf_stack_bb': 6.3442, 'pf_act':'shove',
                     'pf_role':'defend', 'pf_level':2}},
        _start_stacks={3:231114,9:74692}, book=None,
        bf=lambda s:1.2,
        bf_details=lambda s: {
            'value':1.2, 'method':'field_bf_empirical_approximation',
            'is_exact':False, 'reason':'missing_full_field_stacks',
            'field_completeness':'incomplete_field_snapshot',
            'snapshot_alive':0, 'snapshot_current':False,
            'snapshot_epoch_exact': False,
            'field_epoch_status':'unverified',
            'field_snapshot_id':None, 'observed_field_epoch_id':None,
            'observed_epoch_diverged':False,
            'field_snapshot_scope':'unknown',
            'bf_kind':'generic_default_risk_not_spot_call_prize_ev',
            'price_specific':False},
        field_q=0.6, payout_flat=0.0,
        reentry=False,progress=0.0,erosion_per_hand=0.0,field_avg_stack=0)
    rnd = SimpleNamespace(action_meta=rows(), order=[3,9],
                          stacks={3:209864,9:0})
    run = S.HandRun.__new__(S.HandRun)
    run.h=h
    run._pid=lambda s:s
    run._dseed=lambda *args:111
    return run,rnd


def test_contract():
    run,rnd = fixture()
    old = os.environ.get('T2_RANGE_CONDITIONAL_V1')
    try:
        os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        with patch.object(RD,'perceived_profile',return_value=None):
            legacy_pool, legacy_meta = run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert legacy_pool and legacy_meta['source'] != RP.MODEL

        os.environ['T2_RANGE_CONDITIONAL_V1']='1'
        with patch.object(RD,'perceived_profile',return_value=None):
            weighted, good = run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert isinstance(weighted,dict) and good['complete']
        assert good['source'] == RP.MODEL
        assert good['status'] == 'conditioned'
        assert good['model_calibrated'] is False
        assert R.range_signature(weighted) != R.range_signature(legacy_pool)

        with patch.object(RD,'perceived_profile',return_value=None), patch.object(
            RP,'conditioned_preflop_range',return_value=(
                None,{'source': RP.MODEL, 'kind':'threebet_shove',
                      'complete':False,'missing':['public_actor_stack_bb']})):
            absent, failed = run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert not absent
        assert failed['complete'] is False
        assert failed['status'] == failed['failure_kind'] == 'missing_evidence'
        assert failed['source'] == RP.MODEL
        assert failed['missing'] == ['public_actor_stack_bb']
        assert failed['failure_reason'] == 'public_actor_stack_bb'

        # A producer MUST NOT smuggle a nonempty candidate to equity when
        # the same response explicitly says complete=False.
        with patch.object(RD,'perceived_profile',return_value=None), patch.object(
            RP,'conditioned_preflop_range',return_value=(
                {('As','Ad'):1.0}, {'source': RP.MODEL,
                    'kind':'threebet_shove', 'complete':False,
                    'missing':['unverified_action_likelihood']})):
            candidate, bad = run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert not candidate and bad['complete'] is False
        assert bad['failure_reason'] == 'unverified_action_likelihood'
        print('PASS incomplete producer cannot leak a nonempty candidate into P5 equity')

        pools, meta = {},{}
        S._record_preflop_observer_range(pools,meta,9,absent,failed)
        assert pools=={}
        assert meta[9] == failed
        seed = {'pf_calloff_consumer': {
            'selected_action':'fold', 'mathematically_justified':False,
            'fallback_reason':'missing_pot_or_range_evidence'}}
        S._attach_p8_observer_evidence(seed,meta)
        assert seed['pf_opp_range_meta']['9'] == failed
        assert seed['pf_calloff_consumer']['opponent_range_evidence']['9'] == failed
        assert seed['pf_calloff_consumer']['mathematically_justified'] is False
        print('PASS missing_evidence + original source + missing fields survive final calloff seed')

        with patch.object(RD,'perceived_profile',return_value=None), patch.object(
            RP,'classify_public_action',return_value={'kind':'call_allin'}):
            fallback_pool, fallback = run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert fallback_pool
        assert R.range_signature(fallback_pool)==R.range_signature(legacy_pool)
        assert fallback['source'] == 'legacy_fallback'
        assert fallback['legacy_source'] == legacy_meta['source']
        assert fallback['conditional_source'] == RP.MODEL
        assert fallback['conditional_complete'] is False
        assert fallback['complete'] is False
        assert fallback['status'] == 'legacy_fallback'
        assert fallback['failure_kind'] == 'model_unavailable'
        assert fallback['missing'] == ['action_class_not_supported']
        assert fallback['model_calibrated'] is False
        assert fallback['equity_model_status'] == 'unvalidated_legacy_proxy'
        pools, meta = {},{}
        S._record_preflop_observer_range(
            pools, meta, 9, fallback_pool, fallback)
        assert 9 in pools and meta[9]['status'] == 'legacy_fallback'
        seed = {'pf_calloff_consumer': {
            'selected_action': 'call', 'mathematically_justified':False}}
        S._attach_p8_observer_evidence(seed,meta)
        assert seed['pf_calloff_consumer']['opponent_range_evidence']['9']['failure_kind'] == 'model_unavailable'
        assert seed['pf_calloff_consumer']['mathematically_justified'] is False
        print('PASS model_unavailable + explicit legacy_fallback, no false conditional success')

        # When no calloff consumer exists, seed provenance must still survive.
        seed = {'pf_calloff_consumer':None}
        S._attach_p8_observer_evidence(seed,meta)
        assert seed['pf_calloff_consumer'] is None
        assert seed['pf_opp_range_meta']['9']['complete'] is False
        print('PASS ON/OFF weighted posterior, call_allin legacy behavior and independent missing-evidence path')
    finally:
        if old is None:
            os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:
            os.environ['T2_RANGE_CONDITIONAL_V1']=old


if __name__=='__main__':
    test_contract()
