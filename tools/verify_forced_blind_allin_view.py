#!/usr/bin/env python3
"""강제 블라인드 올인 좌석이 UI 뷰에서 폴드처럼 사라지지 않는지 검증한다."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import view


class Hand:
    bb = 1000
    hero = 1
    pos = {1: 'SB', 2: 'BB'}
    seat_of = {'SB': 1, 'BB': 2}
    seats = [1, 2]
    # 실제 엔진에서도 올인으로 0이 된 좌석은 hand.stacks가 0이다.
    stacks = {1: 0, 2: 2500}


raw = {
    'stage': 'preflop',
    'hash': 'forced-blind-allin',
    'hole': ['As', 'Kd'],
    'stack': 0,
    'pot': 1500,
    'tocall': 0,
    'min_raise': 2000,
    'can_raise': False,
    'live': [1, 2],
    'allin': [1],
    'contrib': {1: 500, 2: 1000},
    'stacks': {1: 0, 2: 2500},
    'log': [],
}

v = view.build(raw, Hand(), hand_no=1)
rows = {r['seat']: r for r in v['seats']}

assert rows[1]['live'] is True, rows[1]
assert rows[1]['allin'] is True, rows[1]
assert rows[2]['live'] is True, rows[2]
assert v['n_live'] == 2, v['n_live']

print('OK forced blind all-in remains live for showdown UI')
