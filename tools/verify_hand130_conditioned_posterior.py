#!/usr/bin/env python3
"""P8 action-conditional range invariants, replay weights and sampled equity.

This compares an existing actor policy, not a solver. Original B37's Book and
288 per-combo weights are not archived and cannot be reconstructed by this test.
"""
import json
import math
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import bot
import preflop as PF
import ranges as R
import reads as RD
import range_posterior_v1 as RP
from tools.verify_hand130_b37_replay import original


def rows(stack=63442, shoved=True):
    return [
        {'seat': 3, 'action': 'raise', 'raised': True,
         'full_raise': True, 'actor_allin_after': False,
         'pre_current': 10000, 'post_current': 20000},
        {'seat': 9, 'action': 'allin' if shoved else 'raise',
         'raised': True, 'full_raise': True,
         'actor_allin_after': shoved, 'pre_stack': stack,
         'pre_current': 20000, 'post_current': (stack+10000 if shoved else 52000),
         'pre_contrib': 10000,
         'post_contrib': (stack+10000 if shoved else 52000)},
    ]


def event_tests():
    shove = RP.classify_public_action(rows(), 9, 10000, 'BB',
                                      seats=8, effective_stack_bb=6.3442)
    ordinary = RP.classify_public_action(rows(shoved=False), 9, 10000, 'BB')
    first = RP.classify_public_action([
        {'seat': 9, 'action': 'allin', 'raised': True, 'full_raise': True,
         'actor_allin_after': True, 'pre_stack': 90000,
         'pre_current': 10000, 'post_current': 90000,
         'pre_contrib': 0, 'post_contrib': 90000},
    ], 9, 10000, 'CO')
    assert shove['kind'] == 'threebet_shove'
    assert ordinary['kind'] == 'threebet_raise'
    assert first['kind'] == 'first_in_shove'
    assert shove['open_bb'] == 2.0
    assert shove['observed_total_bb'] == 7.3442
    assert shove['stack_bb'] == 6.3442
    assert shove['raise_level'] == 1 and shove['opener_seat'] == 3
    assert shove['action_history'][0]['seat'] == 3
    assert shove['effective_stack_bb'] == 6.3442
    # Public first-in context: a later actor's recorded pre_stack is the
    # exact stack at the earlier open if that actor has not acted since.
    behind, provenance = RP.public_behind_stacks(
        [
            {'seat': 3, 'action': 'allin', 'raised': True,
             'full_raise': True, 'actor_allin_after': True,
             'pre_stack': 60000},
            {'seat': 4, 'action': 'fold', 'pre_stack': 85000},
            {'seat': 5, 'action': 'fold', 'pre_stack': 45000},
        ], [3,4,5], 3, {3:0,4:85000,5:45000}, 10000)
    assert behind == [8.5, 4.5], (behind, provenance)
    assert provenance['seats']['4']['source'] == 'later_public_action_pre_stack'
    assert provenance['seats']['5']['source'] == 'later_public_action_pre_stack'
    absent, reason = RP.public_behind_stacks(
        [{'seat':3,'action':'allin'}], [3,4], 3, {}, 10000)
    assert absent is None and reason['reason'] == 'missing_behind_stack'
    iso = RP.classify_public_action([
        {'seat':1,'action':'call','raised':False,'full_raise':False},
        {'seat':9,'action':'raise','raised':True,'full_raise':True,
         'actor_allin_after':False,'pre_current':10000,'post_current':30000,
         'pre_stack':50000}], 9, 10000, 'BB')
    assert iso['kind'] == 'iso_after_limp'
    return shove, ordinary, first


def posterior_tests(shove, ordinary, first):
    profile = RD.range_profile(None)
    dead = {'Ac', 'Kh'}
    ctx = {'opener_pos': 'LJ'}
    vs_shove, ms = RP.conditioned_preflop_range(
        profile, shove, dead, observer_context=ctx)
    vs_raise, mr = RP.conditioned_preflop_range(
        profile, ordinary, dead, observer_context=ctx)
    assert ms['complete'] and isinstance(vs_shove, dict)
    # At 6.3442BB the legacy actor raise_form geometrically forces a
    # shove: observing a non-all-in 3bet is impossible under this model,
    # not an invitation to fall back to a guessed uniform range.
    assert vs_raise is None and not mr['complete']
    assert 'zero_posterior_evidence' in mr['missing']
    assert R.range_mass(vs_shove) > 0
    assert all(0 < w <= 1 for w in vs_shove.values())
    assert ms['posterior_support'] == len(vs_shove)
    assert ms['posterior_mass'] == R.range_mass(vs_shove)

    # At 20BB the existing raise_form policy has a meaningful
    # nonshove route, and the shove/ordinary posterior MUST differ.
    deep_s = dict(shove, stack_bb=20.0, observed_total_bb=21.0,
                  post_contrib_bb=21.0)
    deep_r = dict(ordinary, stack_bb=20.0, observed_total_bb=8.0)
    ds, dms = RP.conditioned_preflop_range(
        profile, deep_s, dead, observer_context=ctx)
    dr, dmr = RP.conditioned_preflop_range(
        profile, deep_r, dead, observer_context=ctx)
    assert ds and dr and dms['complete'] and dmr['complete']
    assert R.range_signature(ds) != R.range_signature(dr), (
        'Shove and nonshove posterior should have distinct policy likelihood')

    # Per-class identity: P(shove attack) + P(nonshove attack) equals
    # actor's attack probability; no new polar blend coefficient.
    sample = next(c for c in R.ALL if PF.cls(list(c)) == 'QQ' and not (set(c) & dead))
    lk = PF.defend_action_likelihoods(
        profile, 'BB', 'LJ', list(sample), 20, 2, 0,
        raise_level=1, stack_bb=20, seats=8, ante=True,
        opener_allin=False, can_raise=True)
    total_attack = lk['attack']
    c1 = ds.get(sample, 0.0)
    c2 = dr.get(sample, 0.0)
    assert abs(c1 + c2 - total_attack) <= 1e-12, (
        c1, c2, total_attack)

    # First-in shove: no use of generic RFI-only posterior.
    missing, mm = RP.conditioned_preflop_range(
        profile, first, dead, observer_context={'field_q': 0.6})
    assert missing is None and not mm['complete']
    assert 'behind_stacks_bb' in mm['missing']
    fctx = dict(field_q=0.6, bubble_factor=1.0, tilt=0.0,
                payout_flat=0.0, reentry=False, progress=0.0,
                behind_stacks_bb=[8.0, 19.0], erosion=0.0,
                field_avg_bb=None)
    f, mf = RP.conditioned_preflop_range(
        profile, first, dead, observer_context=fctx)
    assert mf['complete'] and f and isinstance(f, dict)
    generic = R.preflop_range(profile, 'CO', 'open', 9.0, dead,
                              seats=8, ante=True)
    assert R.range_signature(f) != R.range_signature(generic)
    # Unsupported previous-action roles must never be silently assigned
    # a normal open/3bet probability.
    unsupported, um = RP.conditioned_preflop_range(
        profile, dict(shove, kind='iso_over_shove'), dead, ctx)
    assert unsupported is None and not um['complete']

    old = R.preflop_range(profile, 'BB', '3bet', 6.3442, dead,
                          opener_pos='LJ', open_bb=2.0,
                          seats=8, ante=True, raise_level=1)
    assert old and vs_shove and R.range_mass(old) > 0
    trace = RP.replay_record(
        {9: vs_shove}, {9: ms}, event_tag='6e1ba98ab1a0|3|B37')
    obj = json.loads(json.dumps(trace, sort_keys=True))
    weights = {(a, b): w for a, b, w in obj['opponents']['9']['weights']}
    assert R.range_signature(weights) == R.range_signature(vs_shove)
    assert obj['opponents']['9']['support'] == len(vs_shove)
    assert obj['opponents']['9']['mass'] == R.range_mass(vs_shove)
    assert len(obj['opponents']['9']['sha256']) == 64

    # Accepted-sample accounting is opt-in and must NOT change estimator
    # randomness or the returned result. Also preserve weighted support.
    hero = ['Ac', 'Kh']
    a = {}
    eq1 = bot.equity_vs_combos(
        hero, [], [vs_shove], sims=160, seed=678901, audit=a)
    eq2 = bot.equity_vs_combos(
        hero, [], [vs_shove], sims=160, seed=678901)
    assert eq1 == eq2
    assert a['accepted'] + a['rejected'] == 160
    assert a['accepted'] > 0
    assert a['mean_share'] == eq1
    assert a['sample_variance'] >= 0
    assert a['seed'] == 678901

    saved = original()
    assert saved['actor_pf_seed']['pf_opp_ranges_n']['9'] == 288
    assert saved['actor_pf_seed']['pf_opp_ranges_mass']['9'] == 288.0
    return {
        'hand130_original_posterior_reconstructed': False,
        'hand130_original_mc_reconstructed': False,
        'original_n': 288,
        'new_6p3442_shove_support': len(vs_shove),
        'new_6p3442_shove_mass': R.range_mass(vs_shove),
        'new_6p3442_normal_support': 0,
        'new_6p3442_normal_mass': 0,
        'new_deep_shove_support': len(ds),
        'new_deep_normal_support': len(dr),
        'first_in_shove_support': len(f),
        'first_in_shove_mass': R.range_mass(f),
        'legacy_proxy_support': len(old),
        'legacy_proxy_mass': R.range_mass(old),
        'mc_accepted': a['accepted'],
        'mc_requested': a['requested'],
        'mc_variance': a['sample_variance'],
        'mc_equity': eq1,
    }


if __name__ == '__main__':
    shove, ordinary, first = event_tests()
    report = posterior_tests(shove, ordinary, first)
    print(json.dumps(report, sort_keys=True))
    print('PASS action-conditional posterior and lossless replay invariants')
