#!/usr/bin/env python3
"""Regression checks for public preflop range reconstruction and read semantics."""
import copy
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS
import plan as PL
import ranges as R
import reads as RD
import session as SE


def check_public_bb_call_range():
    # round_000007 shape: HJ opens to 3bb, BB (human/seedless seat) calls.
    meta = [
        {
            'seat': 6, 'action': 'raise', 'raised': True, 'full_raise': True,
            'allin_call': False, 'pre_current': 200, 'post_current': 600,
        },
        {
            'seat': 1, 'action': 'call', 'raised': False, 'full_raise': False,
            'allin_call': False, 'pre_current': 600, 'post_current': 600,
        },
    ]
    ctx = SE._preflop_public_action_context(meta, 1, 200)
    assert ctx['action'] == 'call', ctx
    assert ctx['opener_seat'] == 6, ctx
    assert abs(ctx['open_bb'] - 3.0) < 1e-12, ctx

    observer = PS.make_player(random.Random(16), 0.6, pid=16)
    book = RD.Book()
    oe = RD.perceived_profile(book, 16, 0, observer, random.Random(991))
    opp_view = RD.range_profile(oe)
    rd = PS.read_opponent(observer, oe)
    polar = (float(rd.get('tb_polar', 0.0) or 0.0)
             * float(rd.get('w', 0.0) or 0.0))

    rr = R.preflop_range(
        opp_view, 'BB', ctx['action'], 157.5, {'Qd', 'Kh'},
        n_callers=ctx['n_callers'], opener_pos='HJ',
        open_bb=ctx['open_bb'], seats=9, ante=False,
        polar=polar, raise_level=ctx['raise_level'])
    assert len(rr) > 0, 'seedless BB call reconstructed to empty range'
    return len(rr)


def check_low_adaptability_is_continuous():
    p = PS.make_player(random.Random(1600), 0.6, pid=16)
    p = copy.deepcopy(p)
    p['temper']['adaptability'] = 1.5
    p['temper']['attention'] = 6.0
    p['concepts']['range_read'] = 7.0
    p['concepts']['sizing_tell'] = 6.0
    oe = {
        'confidence': 0.60, 'n': 12,
        'ftb': 0.52, 'ftb_flop': 0.52, 'ftb_turn': 0.52, 'ftb_river': 0.52,
        'bluff': 7.0, 'aggr': 6.0, 'tight': 5.0,
        'rfi_rel': 1.0, 'pf_limp': 0.06,
        'pf_fold_after_limp_raise': 0.48,
        'barrel': 0.60, 'pf_3bet': 0.07, 'pf_fold_to_3bet': 0.55,
        'pf_4bet': 0.04, 'pf_fold_to_4bet': 0.60,
        'sz_mean': 0.62, 'sz_sd': 0.22, 'sz_n': 12, 'sz_big': 0.15,
        'sz_river': 0.62,
    }
    rd = PS.read_opponent(p, oe)
    assert rd['w'] > 0.0, rd
    assert rd['w'] < 0.20, rd
    return rd


def check_line_prior_no_raw_bluff_bypass():
    board = ['6d', 'Ac', '2d', 'Qd', '3d']
    raw_lo = {'bluff': 1.0}
    raw_hi = {'bluff': 10.0}

    # With zero read weight, raw historical bluff estimate must not leak through.
    neutral = {'w': 0.0, 'bluff_gap': 1.0}
    a = PL.line_bluff_prior(
        raw_lo, 'river', 1, 0.20, board, False, opp_read=neutral)
    b = PL.line_bluff_prior(
        raw_hi, 'river', 1, 0.20, board, False, opp_read=neutral)
    assert abs(a - b) < 1e-12, (a, b)

    # Authorized opponent-specific read may shift the same public line.
    use_lo = {'w': 0.50, 'bluff_gap': -0.50}
    use_hi = {'w': 0.50, 'bluff_gap': 0.50}
    lo = PL.line_bluff_prior(
        raw_hi, 'river', 1, 0.20, board, False, opp_read=use_lo)
    hi = PL.line_bluff_prior(
        raw_lo, 'river', 1, 0.20, board, False, opp_read=use_hi)
    assert hi > lo, (lo, hi)
    return a, lo, hi


def check_no_self_range_fallback():
    text = (ROOT / 'session.py').read_text(encoding='utf-8')
    for needle in (
        'opp_r = R.range_unique_sorted(my_r)',
        'opp_r = my_r',
    ):
        assert needle not in text, 'self-range fallback reintroduced: ' + needle


def main():
    n = check_public_bb_call_range()
    rd = check_low_adaptability_is_continuous()
    line = check_line_prior_no_raw_bluff_bypass()
    check_no_self_range_fallback()
    print('PASS read/range semantics')
    print('  seedless_BB_call_range_n=%d' % n)
    print('  adaptability_1.5_read_weight=%.3f' % rd['w'])
    print('  line_prior neutral=%.4f low=%.4f high=%.4f' % line)
    print('  self_range_fallback=ABSENT')


if __name__ == '__main__':
    main()
