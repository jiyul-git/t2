#!/usr/bin/env python3
import inspect
import random

import persona as PS
import ranges as R
import session as S


def check_seedless_bb_call():
    # Public preflop rule events: HJ opens to 3bb, BB calls.
    meta = [
        {'seat': 6, 'action': 'raise', 'raised': True, 'full_raise': True,
         'pre_current': 200, 'post_current': 600},
        {'seat': 1, 'action': 'call', 'raised': False, 'full_raise': False,
         'allin_call': False, 'pre_current': 600, 'post_current': 600},
    ]
    ctx = S._preflop_public_action_context(meta, 1, 200)
    assert ctx['action'] == 'call', ctx
    assert ctx['opener_seat'] == 6, ctx
    assert abs(ctx['open_bb'] - 3.0) < 1e-9, ctx

    prof = PS.make_player(random.Random(7), 0.6, 16)
    rr = R.preflop_range(
        prof, 'BB', ctx['action'], 160.5, {'Qd', 'Kh'},
        opener_pos='HJ', open_bb=ctx['open_bb'],
        n_callers=ctx['n_callers'], raise_level=ctx['raise_level'],
        seats=9, ante=False)
    assert len(rr) > 0, 'BB call range unexpectedly empty'

    src = inspect.getsource(S.HandRun._run)
    assert 'self.preflop_action_meta' in src
    assert "_public_pf = _preflop_public_action_context" in src
    print('PASS seedless BB call -> public call range, combos=%d' % len(rr))


def check_adaptability_continuous():
    prof = PS.make_player(random.Random(11), 0.6, 16)
    prof['temper']['adaptability'] = 1.5
    prof['temper']['attention'] = 5.0
    prof['concepts']['range_read'] = 7.6
    prof['concepts']['sizing_tell'] = 5.0

    est = {
        'confidence': 0.12, 'n': 7,
        'ftb': 0.52, 'bluff': 4.1, 'aggr': 4.0,
        'barrel': 0.42, 'pf_3bet': 0.07, 'pf_4bet': 0.04,
        'pf_limp': 0.06, 'rfi_rel': 1.0,
        'pf_fold_to_3bet': 0.55, 'pf_fold_to_4bet': 0.60,
        'sz_mean': 0.62, 'sz_sd': 0.22, 'sz_n': 0,
    }
    rd = PS.read_opponent(prof, est)
    assert rd['w'] > 0.0, rd
    assert rd['w'] < 0.05, rd
    assert rd['see_line'] > 0.0, rd
    print('PASS low adaptability stays weak-but-nonzero, w=%.3f' % rd['w'])


def main():
    check_seedless_bb_call()
    check_adaptability_continuous()


if __name__ == '__main__':
    main()
