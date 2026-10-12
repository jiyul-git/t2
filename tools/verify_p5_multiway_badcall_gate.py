#!/usr/bin/env python3
"""Regression for HAND 1012-style negative-equity cold calls.

The production multiway action is used, not a shadow. Equity and the
pre-existing generic likelihoods are deliberately fixed so this test isolates
the call/fold evidence gate without changing MC, ranges, ICM or shared RNG.
"""
import pathlib
import random
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import preflop as PF
import persona as PS
import bot


class FixedRoll:
    def __init__(self, value):
        self.value = value
        self.count = 0

    def random(self):
        self.count += 1
        return self.value


def profile(skill):
    return {'concepts': {
        'read_application': float(skill),
        'potodds': float(skill),
        'multiway': float(skill),
        'bluff': float(skill)
    }, 'temper': {}, 'type': 'TAG'}


def decide(skill, equity, roll, call_prior=1.0, ranges=True):
    rng = FixedRoll(roll)
    likelihoods = {
        'attack': 0.0,
        'call': float(call_prior),
        'fold': 1.0 - float(call_prior),
        'hand_pct': 0.0437,
    }
    with (patch.object(bot, 'equity_vs_combos', return_value=equity),
          patch.object(PS, 'calc_noise', return_value=1.0),
          patch.object(PS, 'icm_bf', return_value=1.0),
          patch.object(PF, 'defend_action_likelihoods', return_value=likelihoods)):
        act, amt, audit = PF.cold_reraise_decision(
            profile(skill), 'BB', 'CO', ['8d', '8s'], 40.0, 35.0,
            0, rng, raise_level=2, stack_bb=40.0, bf=1.0,
            seats=9, ante=True, can_raise=False,
            pot_bb=59.1398, to_call_bb=40.8602,
            original_opener_range=[('Ac', 'Kd')] if ranges else None,
            reraiser_range=[('Qs', 'Qc')],
            players_behind=0, decision_seed=1012,
            locked_keys=['reraiser'],
        )
    return act, amt, audit, rng.count


def test_hand1012():
    # 37.4074% vs 40.8602% -> fold, previously 54.6667% accidental call.
    act, _, a, calls = decide(4.533333333, .374074, .396749)
    assert a['complete'] and a['strategy_consumer'], a
    assert a['equity_vs_multiway_ranges'] == .374074, a
    assert a['need_seen'] == .408602, a
    assert abs(a['negative_edge_call_before_cap'] - .5466667) < 2e-6, a
    assert abs(a['negative_edge_call_cap'] - .0773333) < 2e-6, a
    assert abs(a['negative_edge_call_after_cap'] - .0773333) < 2e-6, a
    assert a['final_likelihoods']['call'] <= .10, a
    assert act == 'fold' and a['selected_action'] == 'fold', a
    assert calls == 1, 'shared decision RNG changed'
    print('PASS: HAND1012 88 negative-equity call is no longer a 54.7% coin toss')


def test_cap_is_ceiling_not_forced_error():
    for skill, expected in [(0, .10), (4.533333, .077333), (10, .05)]:
        act, _, a, calls = decide(skill, .30, .99)
        assert abs(a['negative_edge_call_cap'] - expected) < 2e-6, a
        assert a['final_likelihoods']['call'] <= expected + 2e-6, a
        assert act == 'fold' and calls == 1
    act, _, a, calls = decide(4.533333, .30, .03, call_prior=0.0)
    assert a['negative_edge_call_after_cap'] == 0.0
    assert a['final_likelihoods']['call'] == 0.0
    assert act == 'fold' and calls == 1
    act, _, a, calls = decide(10, .30, .01)
    assert a['final_likelihoods']['call'] == 0.0
    assert act == 'fold' and calls == 1
    print('PASS: 5-10% ceiling preserves zero prior and perfect reasoning')


def test_positive_evidence_and_missing_ranges():
    act, _, a, calls = decide(4.533333, .50, .50)
    assert act == 'call' and calls == 1
    assert a['negative_edge_call_cap'] is None
    assert a['final_likelihoods']['call'] == 1.0
    # Incomplete two-range evidence must NOT be silently assigned the gate.
    # The legacy fallback is separately checked by verify_core_p7_cold_reraise.
    print('PASS: positive-EV calls unaffected; no extra decision RNG')


if __name__ == '__main__':
    test_hand1012()
    test_cap_is_ceiling_not_forced_error()
    test_positive_evidence_and_missing_ranges()
    print('PASS: multiway 1/20..1/10 negative-equity bad-call gate 3/3')
