#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Targeted checks for effective-all-in v1 classifier."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU


def expect(cond, label):
    if not cond:
        raise AssertionError(label)


def case_actor_effective_true():
    x = RU.effective_allin_v1(
        target=950, actor_cap=1000, opp_cap_max=1200,
        contrib_before=0, pot_before=1000)
    expect(x['actor_effective'], 'actor should be limiting stack')
    expect(x['effective'], '95% commit with tiny post-SPR should classify')


def case_opponent_effective_false():
    x = RU.effective_allin_v1(
        target=950, actor_cap=1000, opp_cap_max=400,
        contrib_before=0, pot_before=1000)
    expect(not x['actor_effective'], 'opponent should be limiting stack')
    expect(not x['effective'], 'opponent-effective must not force actor shove')


def case_commit_floor_false():
    x = RU.effective_allin_v1(
        target=890, actor_cap=1000, opp_cap_max=1500,
        contrib_before=0, pot_before=5000)
    expect(x['post_spr'] <= .05, 'fixture should have low post-SPR')
    expect(x['commit_frac'] < .90, 'fixture should be below commit floor')
    expect(not x['effective'], 'sub-90% commit must not classify')


def case_post_spr_false():
    x = RU.effective_allin_v1(
        target=950, actor_cap=1000, opp_cap_max=1500,
        contrib_before=0, pot_before=0)
    expect(x['commit_frac'] >= .90, 'fixture should clear commit floor')
    expect(x['post_spr'] > .05, 'fixture should exceed post-SPR ceiling')
    expect(not x['effective'], 'post-SPR above .05 must not classify')


def case_contrib_coordinate():
    x = RU.effective_allin_v1(
        target=1000, actor_cap=1100, opp_cap_max=1500,
        contrib_before=200, pot_before=1200)
    # actor has already put 200 in this street; target 1000 means only 800 more.
    # pot_before=1200 makes the post-action SPR exactly 100/2000 = 0.05.
    expect(abs(x['increment'] - 800) < 1e-9, 'increment must use target coordinate')
    expect(abs(x['residual'] - 100) < 1e-9, 'residual must use actor cap coordinate')
    expect(x['effective'], 'target-coordinate fixture should classify')


def case_exact_allin_true():
    x = RU.effective_allin_v1(
        target=1000, actor_cap=1000, opp_cap_max=1000,
        contrib_before=0, pot_before=500)
    expect(x['effective'], 'exact actor-effective all-in should classify')
    expect(abs(x['residual']) < 1e-9, 'exact all-in residual should be zero')


def main():
    cases = [
        case_actor_effective_true,
        case_opponent_effective_false,
        case_commit_floor_false,
        case_post_spr_false,
        case_contrib_coordinate,
        case_exact_allin_true,
    ]
    for fn in cases:
        fn()
        print('PASS', fn.__name__)
    print('PASS effective-allin v1 targeted verification (%d cases)' % len(cases))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
