#!/usr/bin/env python3
"""HAND130 B37 / Department 8: range-reconstruction routing and shared-producer audit.

This verifier deliberately does NOT claim to reconstruct the archived 288
opponent combos or the 800 equity draws: the opponent Book and combo weights
are absent from the archived appendix. It tests *real production functions*
for category separation, loss of all-in conditioning, representation, and
the shared defend_thresholds dependency. No strategy source is modified.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import preflop as PF
import ranges as R
import reads as RD
import session as S
from tools.verify_hand130_b37_replay import original


def context_tests():
    # Public events: the same string 'allin' is FIRST-IN for one history,
    # but a 3bet after a prior full LJ raise in a different history.
    first_in = [
        {'seat': 9, 'action': 'allin', 'raised': True,
         'full_raise': True, 'pre_current': 10000,
         'actor_allin_after': True},
    ]
    threebet = [
        {'seat': 3, 'action': 'raise', 'raised': True,
         'full_raise': True, 'pre_current': 10000,
         'actor_allin_after': False},
        {'seat': 9, 'action': 'allin', 'raised': True,
         'full_raise': True, 'pre_current': 20000,
         'actor_allin_after': True},
    ]
    a = S._preflop_public_action_context(first_in, 9, 10000)
    b = S._preflop_public_action_context(threebet, 9, 10000)
    assert a['action'] == 'open' and a['raise_level'] == 1, a
    assert b['action'] == '3bet' and b['opener_seat'] == 3, b
    assert b['raise_level'] == 1 and b['open_bb'] == 2.0, b

    # The bot-role route also maps first-in shove -> ordinary RFI action.
    dummy = SimpleNamespace(h=SimpleNamespace(
        pos={9: 'CO'},
        pf_seed={9: {'pf_act': 'shove', 'pf_role': 'open'}}))
    assert S.HandRun._pf_range_action(dummy, 9) == 'open'
    dummy.h.pf_seed[9] = {
        'pf_act': 'shove', 'pf_role': 'defend',
        'pf_facing_allin': False, 'pf_level': 1}
    assert S.HandRun._pf_range_action(dummy, 9) == '3bet'
    return a, b


def range_tests():
    prof = RD.range_profile(None)  # *perceived* population default, not hidden actor
    dead = {'Ac', 'Kh'}
    kwargs = dict(range_profile=prof, pos='BB', stack_bb=6.3442,
                  dead=dead, seats=8, ante=True, action='3bet',
                  polar=0.0)

    # Same prior contexts with different publicly observed all-in form.
    base = dict(pf_vs='LJ', pf_open_bb=2.0, pf_level=1,
                pf_n_callers=0)
    regular = dict(base, pf_act='3bet', pf_role='defend')
    shoved = dict(base, pf_act='shove', pf_role='defend')

    orig_defend = PF.defend_thresholds
    calls = {'count': 0}

    def spy(*args, **kw):
        calls['count'] += 1
        return orig_defend(*args, **kw)

    # The class-likelihood cache must be cleared when instrumenting the
    # producer; cache entries do not key on the producer implementation.
    PF.defend_thresholds = spy
    R._LIK_CACHE.clear()
    try:
        regular_range, rm = S._preflop_story_range(
            pfo=regular, **kwargs)
        regular_calls = calls['count']
        shoved_range, sm = S._preflop_story_range(
            pfo=shoved, **kwargs)
        assert regular_calls > 0
        assert R.range_signature(regular_range) == R.range_signature(shoved_range)
        assert rm['source'] == sm['source'] == 'standard_preflop_range'
        assert rm['action'] == sm['action'] == '3bet'
        # When no polar override is active, likelihood posterior is weighted.
        assert isinstance(regular_range, dict), (
            'Expected weighted action likelihood; fallback may have fired',
            type(regular_range).__name__)

        calls['count'] = 0
        polar_range, _ = S._preflop_story_range(
            pfo=shoved, **dict(kwargs, polar=0.25))
        polar_calls = calls['count']
        assert polar_calls > 0
        assert isinstance(polar_range, list), type(polar_range).__name__
        assert R.range_mass(polar_range) == len(polar_range)

        # First-in shoved and ordinary opened ranges are indistinguishable
        # to _preflop_story_range when both are labeled action='open'.
        fkwargs = dict(kwargs, pos='CO', stack_bb=10.0,
                       action='open', polar=0.0)
        first_shove, _ = S._preflop_story_range(
            pfo={'pf_role': 'open', 'pf_act': 'shove'},
            **fkwargs)
        normal_open, _ = S._preflop_story_range(
            pfo={'pf_role': 'open', 'pf_act': 'raise'},
            **fkwargs)
        assert R.range_signature(first_shove) == R.range_signature(normal_open)
    finally:
        PF.defend_thresholds = orig_defend
        R._LIK_CACHE.clear()

    return {
        '3bet_normal_n': len(regular_range),
        '3bet_normal_mass': R.range_mass(regular_range),
        '3bet_normal_representation': type(regular_range).__name__,
        '3bet_shove_identical_to_normal': True,
        'polarized_n': len(polar_range),
        'polarized_mass': R.range_mass(polar_range),
        'polarized_representation': type(polar_range).__name__,
        'producer_calls_nonpolar_first': regular_calls,
        'producer_calls_polar': polar_calls,
        'first_in_shove_equals_rfi_model': True,
    }


def main():
    archive = original()
    assert archive['hand_no'] == 130
    pf = archive['actor_pf_seed']
    assert pf['pf_opp_ranges_n']['9'] == 288
    assert pf['pf_opp_ranges_mass']['9'] == 288.0
    meta = pf['pf_opp_range_meta']['9']
    assert meta['source'] == 'standard_preflop_range'
    assert meta['action'] == '3bet' and meta['raise_level'] == 1
    assert meta['opener_pos'] == 'LJ' and meta['open_bb'] == 2.0
    assert meta['stack_bb'] == 6.3442
    assert meta['first_in_allin_read_as_open'] is False
    a, b = context_tests()
    result = range_tests()
    print(json.dumps({
        'pass': True,
        'base_sha': '874aa76eacec319cd0d6c52b694f841c85dd42ef',
        'archive': {
            'hash': archive['hash'],
            'opponent_count': pf['pf_opp_ranges_n']['9'],
            'opponent_mass': pf['pf_opp_ranges_mass']['9'],
            'action_meta': meta,
        },
        'public_first_in': a,
        'public_threebet': b,
        'range_tests': result,
        'archived_posterior_recomputed': False,
        'archived_mc_recomputed': False,
    }, sort_keys=True, ensure_ascii=False))
    print('PASS HAND130 range posterior routing / producer dependency audit')


if __name__ == '__main__':
    main()
