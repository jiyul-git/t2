#!/usr/bin/env python3
"""머니점프 관측 배선: 스택분포/자리/커버관계가 행동과 분리돼 기록되는지 검사."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU
import session as SE


class H:
    bb = 1000
    pos = {1: 'CO', 2: 'BTN', 3: 'SB', 4: 'BB'}
    seat_pid = {1: 10, 2: 20, 3: 30, 4: 40}
    _start_stacks = {1: 20000, 2: 30000, 3: 8000, 4: 15000}
    field_stacks = (50000, 30000, 20000, 15000, 8000, 4000)
    field_avg_stack = 21166.6667
    field_remaining = 6
    field_itm = 5
    money_jump = {
        'current_prize': 0.0,
        'next_prize': 5.0,
        'next_jump': 5.0,
        'players_to_jump': 1,
    }


profile = {
    'concepts': {'money_jump': 8.0, 'icm': 7.0, 'stack_decay': 6.0},
    'temper': {},
}
r = RU.Round(None, [1, 2, 3, 4], dict(H._start_stacks), H.bb)
r.last_idx = -1
obs = SE._money_jump_observe(H(), 1, r, 'preflop', profile, 500, 1500,
                             facing_seat=2)

assert obs['pos'] == 'CO', obs
assert obs['players_to_jump'] == 1, obs
assert obs['money_jump_skill'] == 8.0, obs
assert obs['n_shorter'] == 3, obs
assert obs['players_yet_to_act'] == 3, obs
assert obs['covers_yet_to_act'] == 2, obs
assert obs['covered_by_yet_to_act'] == 1, obs
assert obs['blind_targets_yet_to_act'] == 2, obs
assert [x['pos'] for x in obs['targets_yet_to_act']] == ['BTN', 'SB', 'BB'], obs
assert obs['facing_target']['seat'] == 2, obs
assert obs['facing_target']['covers_me'] is True, obs
assert obs['shorter_minus_needed'] == 2, obs
assert obs['shorter_to_needed_ratio'] == 3.0, obs

r.apply(1, 'raise', 2500)
SE._money_jump_attach_action(obs, r)
assert obs['action'] == 'raise', obs
assert obs['amount'] == 2500, obs

print('OK money-jump observation stack/position/topology/action')
