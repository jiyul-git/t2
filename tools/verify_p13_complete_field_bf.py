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
    h._start_stacks = dict(h.stacks)
    h.seat_pid = {s: 'P%s' % s for s in seats}
    h.field_pid_stacks = {'P%s' % s: ORIGINAL[s] for s in FULL}
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
    equal(info['pf_calloff_consumer']['objective_spot_bf'], bf, 'P5 objective BF pass-through')
    return action, size


def main():
    former = I.bubble_factor(ST, PAYOUTS, HERO_LOCAL)
    whole = I.bubble_factor(ALL, PAYOUTS, HERO_FULL)
    equal(former,3.0391747926446717,'former partial-table BF')
    equal(whole,3.465325154547401,'full eight-player BF')

    pid_full = {'P%s' % s: ORIGINAL[s] for s in FULL}
    local_pids = ['P%s' % s for s in LOCAL]
    # Actual fieldsim snapshot producer must capture counts, chips and
    # PID mapping from one synchronous read, not disjoint samplings.
    import fieldsim as FS
    fs = object.__new__(FS.Field)
    fs.players = {str(k): {'pid':'P%s'%k,'stack':ORIGINAL[k]}
                  for k in FULL}
    fs.entries = 8
    fs.start_stack = 112500
    captured = fs.field_snapshot()
    assert captured['remaining'] == 8
    assert captured['pid_stacks'] == pid_full
    assert list(captured['stacks']) == ALL

    full_info = I.table_bf(
        ST, HERO_LOCAL, 8, 7, PAYOUTS, field_avg=112500,
        field_stacks=ALL, field_pid_stacks=pid_full,
        table_pids=local_pids, return_details=True)
    assert full_info['is_exact']
    assert full_info['price_specific'] is False
    assert full_info['bf_kind'] == 'generic_default_risk_not_spot_call_prize_ev'
    assert full_info['method']=='exact_full_field_icm'
    assert full_info['field_completeness']=='verified_player_id_field_snapshot'
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
        field_avg=112500,field_stacks=dupl_full,
        field_pid_stacks={'P%s'%s:duplicated[s] for s in FULL},
        table_pids=['P%s'%s for s in dupl_local],
        return_details=True)
    assert dupl['is_exact']
    equal(dupl['value'],I.bubble_factor(dupl_full,PAYOUTS,FULL.index(3)),
          'duplicate stack multiset proof')

    # Same chip multiset with wrong participant identities must never prove
    # a complete field (even if the totals look plausible).
    bogus = dict(pid_full)
    bogus['P9'] = bogus.pop('P2')
    unknown = I.table_bf(
        ST, HERO_LOCAL, 8, 7, PAYOUTS, field_avg=112500,
        field_stacks=ALL, field_pid_stacks=bogus,
        table_pids=local_pids, return_details=True)
    assert not unknown['is_exact']
    assert unknown['reason'] == 'missing_or_mismatched_player_id_snapshot'
    # Snapshot was captured before this hand changed the local hero's chips.
    stale = hand(LOCAL, ALL)
    stale.stacks[3] -= 1
    current = stale.bf_details(3)
    assert not current['is_exact']
    assert current['reason'] == 'table_stacks_changed_after_field_snapshot'
    # Counts-only snapshot with no pid association also fails exactness.
    unverified = I.table_bf(
        ST, HERO_LOCAL, 8, 7, PAYOUTS, field_avg=112500,
        field_stacks=ALL, return_details=True)
    assert not unverified['is_exact']
    assert unverified['reason'] == 'missing_or_mismatched_player_id_snapshot'

    many=I.table_bf(ST,HERO_LOCAL,10,7,PAYOUTS,
                    field_avg=112500,field_stacks=ALL,return_details=True)
    assert not many['is_exact']
    assert many['reason']=='more_than_exact_max_survivors'
    # A contradictory "remaining=5" with an 8-survivor field snapshot
    # must never make five local seats masquerade as a complete final table.
    contradictory = I.table_bf(
        ST, HERO_LOCAL, 5, 5, PAYOUTS, field_avg=112500,
        field_stacks=ALL, field_pid_stacks=pid_full,
        table_pids=local_pids, return_details=True)
    assert not contradictory['is_exact']
    assert contradictory['reason'] == 'field_snapshot_conflicts_with_table_field_count'
    # Busted seats cannot be counted as extra payout ranks.
    with_dead = [0] + ALL
    exact_dead = I.table_bf(
        with_dead, HERO_FULL + 1, 8, 7, PAYOUTS,
        field_avg=112500, return_details=True)
    assert exact_dead['is_exact']
    equal(exact_dead['value'],whole,'busted seat omitted from exact prize rank')

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
        'stale_snapshot':current,
        'wrong_pid_snapshot':unknown,
        'multiset_only_snapshot':unverified,
        'large_field':many,
        'contradictory_remaining_snapshot':contradictory,
        'complete_with_busted_table_seat':exact_dead,
    },sort_keys=True,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
