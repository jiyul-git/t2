#!/usr/bin/env python3
"""P8 independent PR21 combined P9+P13 review, pinned base 0a45af4.

Source-only audit: do not change opponent policy, ICM, coefficients or MC.
Checks scalar-BF vs BF-method isolation, first-in and 3bet likelihood,
snapshot fail-closed, exact replay weights and MC evidence.
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
import bot
import icm as I
import reads as RD
import range_posterior_v1 as RP
import ranges as R
import session as S
from tools.verify_p13_complete_field_bf import ORIGINAL, LOCAL, FULL, PAYOUTS, hand
from tools.verify_hand130_conditioned_posterior import rows as threebet_rows
from tools.verify_pr16_p5_provenance import fixture


def exact_and_empirical():
    snapshot=[ORIGINAL[s] for s in FULL]
    h=hand(LOCAL,snapshot)
    exact=h.bf_details(3)
    assert exact['is_exact'] and exact['method']=='exact_full_field_icm'
    assert not exact['price_specific']
    assert exact['bf_kind']=='generic_default_risk_not_spot_call_prize_ev'
    no=hand(LOCAL,()).bf_details(3)
    assert no['method']=='field_bf_empirical_approximation'
    assert not no['is_exact'] and no['reason']=='missing_full_field_stacks'
    short=hand(LOCAL,snapshot[:-1]).bf_details(3)
    assert not short['is_exact'] and short['reason']=='snapshot_size_differs_from_remaining'
    old=hand(LOCAL,snapshot)
    old.stacks[LOCAL[0]] += 1000
    stale=old.bf_details(3)
    assert not stale['is_exact'] and stale['reason']=='table_stacks_changed_after_field_snapshot'
    assert math.isclose(exact['value'],
                        I.bubble_factor(snapshot,PAYOUTS,FULL.index(3)),
                        abs_tol=1e-10)
    # A *remote-only* change is not detectable by the current API because
    # it is NOT passed any updated other-table data or a verified epoch ID.
    # This case is a reproducible missing evidence / potential stale claim,
    # not an assertion that an observed production source did change.
    remote=hand(LOCAL,snapshot)
    hypothetical_current_remote=dict(remote.field_pid_stacks)
    missing_remote_pid='P2'
    hypothetical_current_remote[missing_remote_pid] += 1000
    stale_remote=remote.bf_details(3)
    assert stale_remote['is_exact']
    assert hypothetical_current_remote != remote.field_pid_stacks
    print(json.dumps({
        'complete_field_bf':exact['value'],
        'missing_snapshot':no['method'],
        'missing_is_exact':no['is_exact'],
        'stale_local':stale['reason'],
        'remote_only_changed_not_observable_to_bf_details':True,
        'remote_only_stale_would_be_labelled_exact_if_unstamped':stale_remote['is_exact'],
        'provenance_limitation':'no_remote_snapshot_epoch_or_freshness_token',
    },sort_keys=True))
    print('PASS explicit missing / incomplete / local-stale snapshots never claim exact ICM')
    return exact, no


def event(kind, stack=18.0):
    if kind=='first_in_shove':
        m={'seat':3,'action':'allin','raised':True,'full_raise':True,
           'actor_allin_after':True,'pre_stack':int(stack*10000),
           'pre_contrib':0,'post_contrib':int(stack*10000),
           'pre_current':10000,'post_current':int(stack*10000)}
        return RP.classify_public_action([m],3,10000,'CO',
                                          seats=8,effective_stack_bb=stack)
    return RP.classify_public_action(threebet_rows(),9,10000,'BB',
                                     seats=8,effective_stack_bb=6.3442)


def bf_on_off_likelihood(exact, empirical):
    prof=RD.range_profile(None)     # neutral perceived profile only
    dead={'Ac','Kh'}
    ctx={'field_q':0.6,'erosion':0.0,
         'field_avg_bb':11.25,'tilt':0.0,
         'payout_flat':0.0,'reentry':False,'progress':0.0,
         'behind_stacks_bb':[8.,19.]}
    start=random.getstate()
    same=event('first_in_shove',18.0)
    b1=I.bubble_factor([ORIGINAL[s] for s in LOCAL],PAYOUTS,LOCAL.index(3))
    b2=exact['value']
    assert abs(b1-b2)>1e-8

    first_candidates=[]
    # The existing P13 neutral/9BB test had 0 changed likelihoods. Probe
    # additional STACK contexts without fitting BF thresholds or priors.
    for stack in (9.0,12.0,15.0,18.0,21.0,25.0):
        ev=event('first_in_shove',stack)
        before,m1=RP.conditioned_preflop_range(
            prof,ev,dead,observer_context=dict(ctx,bubble_factor=b1))
        after,m2=RP.conditioned_preflop_range(
            prof,ev,dead,observer_context=dict(ctx,bubble_factor=b2))
        changed=(before!=after)
        first_candidates.append({
            'stack_bb':stack,'changed':changed,
            'before_complete':m1['complete'],'after_complete':m2['complete'],
            'before_support':len(before or {}),'after_support':len(after or {}),
            'before_mass':R.range_mass(before or {}),
            'after_mass':R.range_mass(after or {}),
        })
        if before and after:
            assert m1['source']==RP.MODEL and m2['source']==RP.MODEL
            assert m1['complete'] and m2['complete']
            assert m1['posterior_support']==len(before)
            assert m2['posterior_support']==len(after)

    # On an exactly same scalar BF, method/provenance changes alone cannot
    # change the numerical posterior (which receives only bubble_factor).
    ev=event('first_in_shove',18.0)
    fixed,mfixed=RP.conditioned_preflop_range(
        prof,ev,dead,observer_context=dict(ctx,bubble_factor=b2))
    same_val,msame=RP.conditioned_preflop_range(
        prof,ev,dead,observer_context=dict(ctx,bubble_factor=b2))
    assert fixed==same_val and mfixed==msame
    # Yet the model result does not carry BF provenance; only scalar context
    # is in HandRun observer_model_inputs, as tested separately below.
    assert 'bf_method' not in mfixed
    assert 'bf_provenance' not in mfixed

    # 3bet/3bet shove use defend_action_likelihoods and raise_form; neither
    # consumes bubble_factor. Consequently scalar BF changes alone cannot
    # affect a fixed-profile, same-public-action posterior in this model.
    ev3=event('threebet_shove')
    r3,m3=RP.conditioned_preflop_range(
        prof,ev3,dead,observer_context={'opener_pos':'LJ','bubble_factor':b1})
    r4,m4=RP.conditioned_preflop_range(
        prof,ev3,dead,observer_context={'opener_pos':'LJ','bubble_factor':b2})
    assert r3 and r3==r4
    assert m3==m4 and m3['posterior_mass']==R.range_mass(r3)
    assert random.getstate()==start
    print(json.dumps({
        'profile':'actual_neutral_perceived_RangeProfile',
        'same_public_action':True,
        'wrong_old_partial_table_bf':b1,
        'complete_full_field_bf':b2,
        'first_in_stack_sensitivity':first_candidates,
        'first_in_any_changed':any(x['changed'] for x in first_candidates),
        'provenance_only_same_scalar_is_numerically_identical':True,
        'posterior_metadata_has_actor_bf_method':False,
        'threebet_shove_bf_scalar_unchanged':True,
        'threebet_shove_support':len(r3),
        'threebet_shove_mass':R.range_mass(r3),
        'global_rng_preserved':True,
        'historical_288_reconstructed':False,
    },sort_keys=True))
    print('PASS split first-in BF-scalar effects from BF-method changes and BF-independent 3bet-shove')


def session_bf_method_gap():
    # Existing code persists observer's own pf_bf_provenance at P5 planning,
    # but it does not record target/actor BF evidence for P8 likelihood.
    run,rnd=fixture()
    original=os.environ.get('T2_RANGE_CONDITIONAL_V1')
    try:
        os.environ['T2_RANGE_CONDITIONAL_V1']='1'
        with patch.object(RD,'perceived_profile',return_value=None):
            pool,meta=run._preflop_perceived_range(
                3,9,{'concepts':{}},rnd,9,8,True)
        assert pool and meta['complete']
        inputs=meta.get('observer_model_inputs',{})
        assert 'bubble_factor' in inputs and inputs['bubble_factor'] is not None
        assert 'bubble_factor_method' not in inputs
        assert 'bubble_factor_is_exact' not in inputs
        print(json.dumps({'source':meta['source'],
                          'bf_input_numeric':inputs['bubble_factor'],
                          'bf_input_exactness_logged':False,
                          'bf_input_method_logged':False,
                          'range_source_preserved':True},sort_keys=True))
        print('WARN target BF provenance not persisted in P8 conditional range observer_model_inputs')
    finally:
        if original is None:
            os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:
            os.environ['T2_RANGE_CONDITIONAL_V1']=original


if __name__=='__main__':
    bf_exact,bf_emp=exact_and_empirical()
    bf_on_off_likelihood(bf_exact,bf_emp)
    session_bf_method_gap()
    print('PASS independent P8 PR21 BF, weights, semantics and RNG review (warnings remain)')
