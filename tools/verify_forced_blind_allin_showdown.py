#!/usr/bin/env python3
"""SB/BB 강제 올인이 액션 없이도 정상 쇼다운되는지 검증한다.

재현 조건:
- HERO(SB) 스택이 SB와 정확히 같아 블라인드 게시 즉시 0.
- 상대(BB)도 BB 게시 즉시 0.
- 히어로 액션 yield 없이 핸드가 끝나야 한다.
- HERO가 져도 board 5장, showdown/allin_show, 양쪽 공개 카드가 남아야 한다.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import session as SE


class Book:
    d = {}

    def observe_preflop(self, *args, **kwargs):
        pass

    def observe_3bet(self, *args, **kwargs):
        pass

    def observe_4bet(self, *args, **kwargs):
        pass

    def observe_showdown(self, *args, **kwargs):
        pass


class Hand:
    seats = [1, 2]
    PRE = ['SB', 'BB']
    POST = ['BB', 'SB']
    seat_of = {'SB': 1, 'BB': 2}
    pos = {1: 'SB', 2: 'BB'}
    stacks = {1: 500, 2: 1000}
    sb = 500
    bb = 1000
    ante = 0
    hero = 1
    hash = 'forced-blind-allin-showdown'
    button = 1

    # HERO: A-high only. BB: pair of kings -> HERO must lose.
    hole = {
        1: ['As', 'Qd'],
        2: ['Kh', 'Kc'],
    }
    board = ['2c', '7d', '9s', 'Jh', '3c']

    book = Book()
    dyn = None

    def pid_of(self, seat):
        return seat


h = Hand()
run = SE.HandRun(h)
out = run.start()

assert out.get('done') is True, out
res = run.result
assert res, out

assert res['how'] == 'showdown', res
assert res['showdown'] is True, res
assert res['allin_show'] is True, res
assert res['board'] == h.board, res['board']
assert res['winners'] == [2], res['winners']
assert res['stacks'][1] == 0, res['stacks']
assert res['stacks'][2] == 1500, res['stacks']

shown = {
    int(k): list(v)
    for k, v in (res.get('shown_hole') or {}).items()
}
assert shown == h.hole, shown
assert res.get('mucked') == [], res.get('mucked')
assert sorted(res.get('show_order') or []) == [1, 2], res.get('show_order')

# 블라인드 자체는 액션 로그가 아니다. 그래도 공개/쇼다운은 되어야 한다.
assert res.get('full_log') == [], res.get('full_log')

print('OK forced blind all-in losing HERO -> full board/showdown/show-all')
