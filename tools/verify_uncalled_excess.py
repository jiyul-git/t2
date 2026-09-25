#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Targeted verification for contestable-pot / uncalled-excess semantics."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU


def eq(got, want, label):
    if got != want:
        raise AssertionError('%s: got %r want %r' % (label, got, want))


def truth(x, label):
    if not x:
        raise AssertionError(label)


def chips(r):
    seats = set(r.stacks) | set(r.contrib)
    return sum(r.stacks.get(s, 0) + r.contrib.get(s, 0) for s in seats)


def case_hu_overbet_short_call():
    r = RU.Round(None, [1, 2], {1: 1000, 2: 300}, 100)
    eq(chips(r), 1300, 'HU initial chips')

    r.apply(1, 'bet', 1000)
    eq(r.to_call(2), 300, 'short stack callable amount')
    eq(r.contestable_contrib(2), 300, 'short stack contestable pot before call')

    r.apply(2, 'call')
    ret = r.settle_uncalled()
    truth(ret is not None, 'HU uncalled return missing')
    eq(ret['seat'], 1, 'HU refund seat')
    eq(ret['amount'], 700, 'HU refund amount')
    eq(r.contrib[1], 300, 'HU bettor matched contribution')
    eq(r.contrib[2], 300, 'HU caller contribution')
    eq(r.stacks[1], 700, 'HU bettor returned stack')
    eq(r.stacks[2], 0, 'HU caller all-in')
    truth(1 not in r.allin, 'covering bettor must not remain physical all-in')
    truth(2 in r.allin, 'short caller should remain all-in')
    eq(r.current, 300, 'HU settled current')
    eq(chips(r), 1300, 'HU chip conservation')


def case_legit_sidepot_no_return():
    r = RU.Round(None, [1, 2, 3], {1: 1000, 2: 500, 3: 300}, 100)
    r.apply(1, 'bet', 500)
    r.apply(2, 'call')
    r.apply(3, 'call')

    # A/B are tied at 500; C is all-in at 300.  The A/B-only 200-each side
    # pot is legitimate, so nothing is uncalled.
    eq(r.settle_uncalled(), None, 'legitimate side pot must not refund')
    eq(r.contrib[1], 500, 'sidepot A contrib')
    eq(r.contrib[2], 500, 'sidepot B contrib')
    eq(r.contrib[3], 300, 'sidepot C contrib')
    eq(chips(r), 1800, 'sidepot chip conservation')


def case_raise_then_fold_return():
    r = RU.Round(None, [1, 2], {1: 500, 2: 500}, 100)
    r.apply(1, 'bet', 100)
    r.apply(2, 'raise', 300)
    eq(r.to_call(1), 200, 'facing raise amount')
    r.apply(1, 'fold')

    ret = r.settle_uncalled()
    truth(ret is not None, 'folded-opponent uncalled return missing')
    eq(ret['seat'], 2, 'fold refund seat')
    eq(ret['amount'], 200, 'fold refund amount')
    eq(r.contrib[1], 100, 'folded money stays in pot')
    eq(r.contrib[2], 100, 'only matched raiser amount stays')
    eq(r.stacks[2], 400, 'raiser receives uncalled chips')
    eq(chips(r), 1000, 'fold case chip conservation')


def case_contestable_multiway_view():
    r = RU.Round(
        None, [1, 2, 3],
        {1: 0, 2: 200, 3: 0},
        100,
        current_bet=500,
        min_raise=100,
        contrib={1: 500, 2: 100, 3: 500},
    )
    # Seat 2 can reach only 300 total on this street.  It can win at most
    # 300 from each deep opponent plus its own 100.
    eq(r.to_call(2), 200, 'multiway short call cap')
    eq(r.contestable_contrib(2), 700, 'multiway contestable contribution')


def case_tied_high_no_return():
    r = RU.Round(
        None, [1, 2, 3],
        {1: 500, 2: 500, 3: 700},
        100,
        current_bet=500,
        contrib={1: 500, 2: 500, 3: 300},
    )
    eq(r.settle_uncalled(), None, 'tied top contributions are fully matched')


def main():
    cases = [
        case_hu_overbet_short_call,
        case_legit_sidepot_no_return,
        case_raise_then_fold_return,
        case_contestable_multiway_view,
        case_tied_high_no_return,
    ]
    for fn in cases:
        fn()
        print('PASS', fn.__name__)
    print('PASS uncalled-excess targeted verification (%d cases)' % len(cases))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
