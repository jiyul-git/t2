#!/usr/bin/env python3
"""P13 exact-vs-empirical field BF: 5 of 8 / 8 of 8 / P5 actor tests.

Fixtures are HAND130's stored public stack geometry. Synthetic .61 equity
below is derived *only* as the midpoint between the two computed price
thresholds, not a new fitted poker coefficient or real opponent estimate.
"""
import json
import math
import os
import random
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import icm as I
import play as P
import plan as PL

ORIGINAL = {1:90441,2:44988,3:231114,4:112013,5:83636,
            7:50573,8:212543,9:74692}
PAYOUTS = [32.573,20.195,14.332,11.075,8.795,7.166,5.863]
FULL = sorted(ORIGINAL)
LOCAL = [1,3,5,8,9]
ST = [ORIGINAL[s] for s in LOCAL]
ALL = [ORIGINAL[s] for s in FULL]
HERO_LOCAL = LOCAL.index(3)
HERO_FULL = FULL.index(3)


def equal(got, want, label, tol=1e-10):
    assert math.isclose(got, want, rel_tol=tol, abs_tol=tol), (
        label, got, want)


def hand(seats, snapshot):
    h = object.__new__(P.Hand)
    h.seats = list(seats)
    h.stacks = {s: ORIGINAL[s] for s in seats}
    h.field_remaining = 8
    h.field_itm = 7
    h.field_avg_stack = 112500.0
    h.payouts = list(PAYOUTS)
    h.payout_flat = 0.0
    h.field_stacks = tuple(snapshot)
    return h


def planned(bf, eq):
    cost, pot = 53442.0, 108442.0
    sh = {
        'pure_calloff': True, 'complete': True,
        'call_cost': cost, 'contestable_after_call': pot + cost,
        'effective_equity': eq,
        'breakeven_equity': cost / (pot + cost),
    }
    action, size, info = PL.preflop_plan(
        {'type':'TAG'}, 'LJ', ['Kh','Ac'], 20.9864,
        random.Random(919), aggressor_pos='BB', open_bb=7.3442,
        n_callers=0, n_limpers=0, raise_level=2,
        bf=bf, seats=8, ante=True, bb_chips=10000,
        opener_allin=True, can_raise=False,
        pot_bb=pot/10000, to_call_bb=cost/10000,
        prior_pf={'pf_act':'raise','pf_role':'open'},
        call_ev_shadow=sh, calloff_decision_seed=3365551903)
    assert info['pf_calloff_consumer']['objective_spot_bf'] == round(bf,6)
    return action, size


def main():
    former = I.bubble_factor(ST, PAYOUTS, HERO_LOCAL)
    whole = I.bubble_factor(ALL, PAYOUTS, HERO_FULL)
    equal(former,3.0391747926446717,'former partial-table BF')
    equal(whole,3.465325154547401,'full eight-player BF')

    full_info = I.table_bf(
        ST, HERO_LOCAL, 8, 7, PAYOUTS, field_avg=112500,
        field_stacks=ALL, return_details=True)
    assert full_info['is_exact']
    assert full_info['method']=='exact_full_field_icm'
    assert full_info['field_completeness']=='verified_full_field_snapshot'
    equal(full_info['value'],whole,'exact complete 5-table/8-field BF')

    local_h = hand(LOCAL, ALL)
    equal(local_h.bf(3),whole,'Hand.bf full-field integration')
    assert local_h.bf_details(3)['is_exact']
    single = hand(FULL, ())
    exact_single = single.bf_details(3)
    assert exact_single['is_exact']
    assert exact_single['field_completeness']=='complete_table'
    equal(exact_single['value'],whole,'HAND130 all eight seats unchanged')

    no_snapshot = hand(LOCAL, ())
    missing = no_snapshot.bf_details(3)
    assert not missing['is_exact']
    assert missing['method']=='field_bf_empirical_approximation'
    assert missing['reason']=='missing_full_field_stacks'
    equal(missing['value'],I.field_bf(ORIGINAL[3],112500.,8,7,0.0),
          'existing heuristic preserved')
    assert missing['value'] > 1.0  # never arbitrary BF=1 for this bubble

    short_snapshot=hand(LOCAL,ALL[:7]).bf_details(3)
    assert not short_snapshot['is_exact']
    assert short_snapshot['reason']=='snapshot_size_differs_from_remaining'
    wrong=[1., 2., 3., 4., 5., 6., 7., 8.]
    invalid=hand(LOCAL,wrong).bf_details(3)
    assert not invalid['is_exact']
    assert invalid['field_completeness']=='invalid_field_snapshot'
    assert invalid['value']==missing['value']
    duplicated = dict(ORIGINAL)
    duplicated[2] = duplicated[9]
    dupl_local=[1,3,5,8,9]
    dupl_full=list(duplicated.values())
    dupl_table=[duplicated[s] for s in dupl_local]
    dupl = I.table_bf(
        dupl_table,dupl_local.index(3),8,7,PAYOUTS,
        field_avg=112500,field_stacks=dupl_full,return_details=True)
    assert dupl['is_exact']
    equal(dupl['value'],I.bubble_factor(dupl_full,PAYOUTS,FULL.index(3)),
          'duplicate stack multiset proof')

    many=I.table_bf(ST,HERO_LOCAL,10,7,PAYOUTS,
                    field_avg=112500,field_stacks=ALL,return_details=True)
    assert not many['is_exact']
    assert many['reason']=='more_than_exact_max_survivors'
    # A field of 8 cannot be declared exact using 5 players, even if
    # a wrong full-field list was supplied.

    old_need=I.required_equity(108442.,53442.,former)
    new_need=I.required_equity(108442.,53442.,whole)
    assert new_need > old_need
    eq=(old_need+new_need)/2.0
    prior_action=planned(former,eq)
    complete_action=planned(whole,eq)
    assert prior_action[0]=='call' and complete_action[0]=='fold', (
        prior_action,complete_action,old_need,new_need)
    # This is a synthetic fixed-equity sensitivity case, not an AKo override.

    print('PASS p13 5-of-8 full-snapshot exact BF and provenance')
    print('PASS incomplete/invalid field snapshot empirical fallback (not exact)')
    print('PASS full HAND130 8-of-8 original BF preserved')
    print('PASS duplicate stack multiset and >9-field approximation')
    print('PASS P5 decision consumer comparison on matched synthetic price')
    print(json.dumps({
        'before_five_table_exact_wrong':former,
        'after_complete_field_exact':full_info,
        'after_missing_field_heuristic':missing,
        'hand130_eight_table_bf':exact_single,
        'controlled_decision':{
            'type':'synthetic_equity_midpoint_not_hand130_actual',
            'old_required_equity':old_need,
            'new_required_equity':new_need,
            'equity':eq,
            'old_action':prior_action[0],
            'new_action':complete_action[0],
        },
        'invalid_snapshot':invalid,
        'short_snapshot':short_snapshot,
        'large_field':many,
    },sort_keys=True,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
