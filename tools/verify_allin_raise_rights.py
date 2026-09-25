#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Targeted checks for raise rights once all remaining opponents are all-in."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU


def expect(cond, label):
    if not cond:
        raise AssertionError(label)


def expect_raises(fn, label):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(label)


def case_hu_covering_stack_cannot_dead_raise():
    r = RU.Round(None, [1, 2], {1: 1000, 2: 1500}, 100)
    r.apply(1, 'allin')
    expect(1 in r.allin, 'seat1 should be all-in')
    expect(not r.can_raise(2), 'covering HU opponent must not have raise right')
    expect_raises(lambda: r.apply(2, 'raise', 1500),
                  'dead raise over lone all-in opponent must be rejected')


def case_hu_covering_allin_overcall_rejected():
    r = RU.Round(None, [1, 2], {1: 1000, 2: 1500}, 100)
    r.apply(1, 'allin')
    expect_raises(lambda: r.apply(2, 'allin'),
                  'covering all-in above call is still a dead raise')


def case_hu_short_allin_call_allowed():
    r = RU.Round(None, [1, 2], {1: 1000, 2: 600}, 100)
    r.apply(1, 'bet', 1000)
    # seat2 cannot raise, but may still make an all-in call for less.
    r.apply(2, 'allin')
    expect(r.contrib[2] == 600, 'short all-in call contribution')
    expect(2 in r.allin, 'short caller should be all-in')


def case_multiway_third_stack_keeps_raise_open():
    r = RU.Round(None, [1, 2, 3], {1: 1000, 2: 1500, 3: 2000}, 100)
    r.apply(1, 'allin')
    expect(r.can_raise(2), 'third live stack means seat2 may still raise')
    r.apply(2, 'raise', 1500)
    expect(r.current == 1500, 'multiway raise should be accepted')


def case_incomplete_allin_still_does_not_reopen():
    r = RU.Round(None, [1, 2, 3], {1: 2000, 2: 1300, 3: 2000}, 100)
    r.apply(1, 'bet', 1000)
    r.apply(2, 'allin')  # +300, incomplete raise
    expect(not r.can_raise(1), 'incomplete all-in must not reopen seat1')
    expect_raises(lambda: r.apply(1, 'allin'),
                  'all-in reraise must obey closed raise right')


def main():
    cases = [
        case_hu_covering_stack_cannot_dead_raise,
        case_hu_covering_allin_overcall_rejected,
        case_hu_short_allin_call_allowed,
        case_multiway_third_stack_keeps_raise_open,
        case_incomplete_allin_still_does_not_reopen,
    ]
    for fn in cases:
        fn()
        print('PASS', fn.__name__)
    print('PASS all-in raise-right verification (%d cases)' % len(cases))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
