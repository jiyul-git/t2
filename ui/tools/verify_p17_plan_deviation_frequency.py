#!/usr/bin/env python3
"""P17 explicit plan deviation policy: statistical, decision-path, RNG and EV checks.

This tests the actual plan.attach_intent/plan.decide_response consumers, not
just a standalone Bernoulli formula. A 7.5% policy ceiling is explicitly user
requested and is not an empirical equity estimate.
"""
import random
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import plan as P

TRIALS = 12000
LOW, HIGH = .05, .10
CAP = .075

assert P.EXPLICIT_PLAN_DEVIATION_CAP == CAP
for p, expected in ((0, 0), (-1, 0), (.03, .03), (.075, CAP),
                    (.12, CAP), (.2656, CAP), (.4962, CAP), (1, CAP)):
    got = P.explicit_plan_deviation_probability(p)
    assert abs(got - expected) < 1e-12, (p, got, expected)

def free_action(seed, intended_plan, raw, text):
    state = {'plan': intended_plan, 'rel': .4, 'trace': []}
    with mock.patch.object(P, 'decide_aggression', return_value=(raw, text)), \
         mock.patch.object(P, 'decide_size', return_value=.45):
        out = P.attach_intent(
            state, ['As', 'Ks'], ['7h', '4c', '2d'],
            None, None, {'aggr': 5}, 1000, 5000, 'flop',
            random.Random(seed), 1, 0, False, True)
    aggression = [e for e in out.get('trace', []) if e.get('kind') == 'aggression']
    assert len(aggression) == 1
    cap_events = [e for e in out.get('trace', [])
                  if e.get('kind') == 'explicit_plan_deviation_gate']
    return out['intents']['flop']['act'], aggression[0], cap_events, out

for name, strategy, p, why, want_cap in [
    ('HAND1024 flop check-plan/cbet', 'showdown', .4962, 'DEVIATE:포기 계획이나 지속벳', True),
    ('HAND1024 turn delayed cbet', 'giveup', .2656, 'DEVIATE:포기 계획이나 지연씨벳', True),
    ('planned ordinary value bet', 'value_3street', .50, '밸류 계획 실행', False),
    ('planned ordinary bluff bet', 'bluff_2street', .50, '블러프 기본 실행률', False),
]:
    count = 0
    for i in range(TRIALS):
        act, trace, caps, out = free_action(i, strategy, p, why)
        count += act == 'bet'
        if i == 0:
            assert bool(caps) is want_cap, (name, caps)
            assert abs(trace['p'] - (CAP if want_cap else p)) <= .0005, (name, trace)
            if want_cap:
                assert abs(caps[0]['original_p'] - p) < 1e-6
                assert caps[0]['policy_cap'] == CAP
                assert caps[0]['final_p'] == CAP
    rate = count / TRIALS
    if want_cap:
        assert LOW <= rate <= HIGH, (name, rate)
    else:
        assert .46 <= rate <= .54, (name, rate)
    print('PASS', name, count, '/', TRIALS, 'rate', round(rate, 4))


# Response path: weak giveup hand facing a bet may deviate only with a positive
# raise-EV gate; underpriced or unavailable action cannot become random call.
def facing(seed, ev_allow):
    st = {'plan': 'giveup', 'made': 0, 'rel': .12, 'trace': []}
    with mock.patch.object(P, '_nonvalue_raise_ev_gate', return_value={
        'allow': bool(ev_allow), 'ev': 1.0 if ev_allow else -2.0
    }), mock.patch.object(P.PS, 'sk', return_value=10.0), \
         mock.patch.object(P.PS, 'temper', return_value=0.0):
        result = P.decide_response(
            {'concepts': {'reraise': 10, 'bluff': 10}}, ['2c', '3d'],
            ['Ah', 'Kd', '9s'], 'flop', 'giveup', st, .20, .50, 0,
            None, 400, 100, 1000, False, random.Random(seed))
    audits = [e for e in st.get('trace', [])
              if e.get('kind') == 'explicit_plan_deviation_gate']
    return result, audits, st

for flag in (True, False):
    nraise = 0
    for seed in range(TRIALS):
        response, gate, st = facing(seed, flag)
        nraise += response[0] == 'raise'
        if seed == 0:
            assert len(gate) == 1
            assert gate[0]['original_p'] == .28, gate
            assert gate[0]['final_p'] == CAP, gate
            assert gate[0]['ev_allowed'] is flag, gate
        if not flag:
            assert response[0] == 'fold', response
    rate = nraise / TRIALS
    if flag:
        assert LOW <= rate <= HIGH, ('giveup EV+ override', rate)
    else:
        assert nraise == 0, nraise
    print('PASS giveup response EV allowed=', flag, 'rate', round(rate, 4))

# Do not accept a plan override if the caller's computed equity is unavailable.
v, events, st = facing(0, False)
assert v[0] == 'fold'
print('PASS: plan deviation <= 7.5% when eligible; non-deviation policy unchanged; EV veto enforced')
