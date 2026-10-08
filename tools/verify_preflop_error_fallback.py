#!/usr/bin/env python3
"""Regression: failed preflop decisions must not auto-call a large all-in."""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU
import session as SE


def fake_run():
    run = SE.HandRun.__new__(SE.HandRun)
    run.h = SimpleNamespace(
        pos={1: 'BTN', 2: 'BB'},
        hole={1: ['Qs', '4s'], 2: ['Jh', '3c']},
        pf_seed={2: {'pf_act': 'call', 'pf_line': [{'act': 'call'}]}})
    run.preflop_errors = []
    return run


def test_j3o_45bb_bad_raise_folds_instead_of_calling():
    rnd = RU.Round(
        None, [1, 2], {1: 0, 2: 44}, 1,
        current_bet=45, min_raise=44, contrib={1: 45, 2: 1})
    rnd.allin.add(1)
    try:
        rnd.apply(2, 'raise', 90)
        raise AssertionError('fixture must reject a dead raise')
    except ValueError as exc:
        run = fake_run()
        run._preflop_error_fallback(rnd, 2, exc, proposed='raise')
    assert rnd.log[-1][1] == 'fold', rnd.log
    assert rnd.stacks[2] == 44, rnd.stacks
    assert run.preflop_errors[-1]['to_call'] == 44
    assert run.preflop_errors[-1]['fallback'] == 'fold'
    assert run.h.pf_seed[2]['pf_act'] == 'fold'
    assert run.h.pf_seed[2]['pf_line'][-1]['act'] == 'fold'
    assert run.h.pf_seed[2]['pf_execution_error']['proposed'] == 'raise'
    print('PASS: J3o facing 45bb, invalid raise cannot turn into a 44bb call')


def test_free_check_and_replay_are_safe():
    rnd = RU.Round(None, [1, 2], {1: 10, 2: 10}, 1,
                   current_bet=1, contrib={1: 1, 2: 1})
    run = fake_run()
    run._preflop_error_fallback(
        rnd, 2, ValueError('synthetic failure'), proposed='raise', replay=True)
    assert rnd.log[-1][1] == 'check', rnd.log
    assert run.h.pf_seed[2]['pf_act'] == 'call'  # replay must not rewrite earlier seed
    assert run.preflop_errors[-1]['replay'] is True
    print('PASS: free decision checks; failed replay does not alter prior plan')


def test_strict_mode_exposes_original_exception():
    rnd = RU.Round(None, [1, 2], {1: 0, 2: 44}, 1,
                   current_bet=45, contrib={1: 45, 2: 1})
    rnd.allin.add(1)
    run = fake_run()
    old = os.environ.get('T2_STRICT')
    try:
        os.environ['T2_STRICT'] = '1'
        err = ValueError('exact original failure')
        try:
            run._preflop_error_fallback(rnd, 2, err, proposed='raise')
            raise AssertionError('strict mode should raise')
        except ValueError as got:
            assert got is err
        assert not rnd.log, rnd.log
        assert not run.preflop_errors
    finally:
        if old is None:
            os.environ.pop('T2_STRICT', None)
        else:
            os.environ['T2_STRICT'] = old
    print('PASS: strict verifier raises original error rather than hiding it')


def main():
    test_j3o_45bb_bad_raise_folds_instead_of_calling()
    test_free_check_and_replay_are_safe()
    test_strict_mode_exposes_original_exception()
    print('PASS: preflop execution fallback 3/3')


if __name__ == '__main__':
    main()
