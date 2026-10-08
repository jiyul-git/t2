#!/usr/bin/env python3
"""Read-only verifier for familiar decisions using current 37 skills.

The 294 registry records are not generated player skills. Timings must use
only persona.sk concepts consulted by the actual decision and existing context.
No strategy RNG may be consumed.
"""
import math
import os
import random
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import timing as TM
import session as SE


def profile(skill):
    return {'concepts': {
        'pf_defend': skill,
        'potodds': skill,
        'range_read': skill,
        'board_texture': skill,
    }}


def test_existing_skill_combination():
    relevant = {'pf_defend', 'potodds', 'range_read'}
    high, low = profile(8.0), profile(2.0)
    familiar = TM.contextual_familiarity(high, relevant, 0.10, 0.10, 0.0)
    unfamiliar = TM.contextual_familiarity(low, relevant, 0.10, 0.10, 0.0)
    marginal = TM.contextual_familiarity(high, relevant, 0.90, 0.10, 0.0)
    assert familiar > 0.55, familiar
    assert unfamiliar < familiar, (unfamiliar, familiar)
    assert marginal < unfamiliar, (marginal, unfamiliar)
    assert TM.contextual_familiarity(high, set(), 0, 0, 0) is None
    # Free bet/check has no EV boundary; knowledge is a proxy, not c=0 proof.
    free = TM.contextual_familiarity(
        high, {'board_texture'}, 0.0, 0.20, 0.0, boundary_known=False)
    assert 0 < free < TM.contextual_familiarity(
        high, {'board_texture'}, 0.0, 0.20, 0.0, boundary_known=True)
    print('PASS: consulted existing skill, weakness, boundary and proxy')


def test_time_math_and_bank():
    t = {'pace': 2.8, 'tank': 1.2, 'mask': 0.0, 'clock': 0.0}
    k = 0.8
    old = TM.visible_seconds(t, .20, .10, .0, k, False, .25, 1.0)
    no_change = TM.visible_seconds(
        t, .20, .10, .0, k, False, .25, 1.0, familiarity=None)
    assert old == no_change
    short = TM.visible_seconds(t, .20, .10, .0, k, False, .25, 1.0,
                               familiarity=.70)
    assert short['reasoning'] < old['reasoning'], (short, old)
    assert short['visible'] >= 1.5
    assert math.isclose(
        short['reasoning'], old['reasoning'] * (1.0 - .30 * .70))
    assert TM.settle(short['visible'], 18.0, 60.0)['bank_used'] >= 0.0
    slow = {'pace': .6, 'tank': .2, 'mask': 1.0, 'clock': 0.0}
    x = TM.visible_seconds(slow, 0, 0, 0, k, True, 1.0, 1.0,
                           familiarity=.85)
    assert x['visible'] >= 1.5  # minimum clock remains a floor
    print('PASS: compatibility, shorter familiar reasoning, minimum time, bank')


def timed_once(skill, c, boundary_known=True):
    run = SE.HandRun.__new__(SE.HandRun)
    run.h = SimpleNamespace(
        pid_of=lambda seat: int(seat), hash='familiarity-test',
        rng=random.Random(20261008))
    run.timing = {'tour_seed': 20261008, 'fmt_key': 'standard',
                  'banks': {}, 'clock': 0.0, 'fingerprint': True}
    run.timing_log = []
    before = run.h.rng.getstate()
    result = run._timing_decide(
        2, 'preflop' if boundary_known else 'flop',
        profile(skill), c, 0.10, 0.0, 0.25, False, 0,
        {'pf_defend', 'potodds'}, boundary_known=boundary_known)
    assert before == run.h.rng.getstate()
    assert len(run.timing_log) == 1
    return result


def test_session_provenance_and_determinism():
    routine = timed_once(8.0, .10)
    repeat = timed_once(8.0, .10)
    low = timed_once(2.0, .10)
    hard = timed_once(8.0, .90)
    free = timed_once(8.0, 0.0, boundary_known=False)
    assert routine == repeat, (routine, repeat)
    assert routine['familiarity_class'] == 'familiar', routine
    assert low['familiarity_class'] != 'familiar', low
    assert hard['familiarity_class'] == 'uncertain', hard
    assert free['familiarity_class'] == 'familiar_proxy', free
    assert routine['familiarity'] > low['familiarity']
    assert routine['familiarity'] > hard['familiarity']
    assert set(routine['concepts_used']) == {'pf_defend', 'potodds'}
    print('PASS: session provenance, deterministic timing, strategy RNG unchanged')


def main():
    test_existing_skill_combination()
    test_time_math_and_bank()
    test_session_provenance_and_determinism()
    print('PASS: timing familiarity 3/3')


if __name__ == '__main__':
    main()
