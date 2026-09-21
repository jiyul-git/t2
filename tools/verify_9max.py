#!/usr/bin/env python3
"""Fast structural verification for the 9-max migration.

No tournament hands are simulated.  This checks position ladders, format-driven
field capacity, 9-player table breaking, and live-state capacity round-trip.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import gto
import live2
import table as TB


EXPECTED_PRE = {
    2: ['SB', 'BB'],
    3: ['BTN', 'SB', 'BB'],
    4: ['UTG', 'BTN', 'SB', 'BB'],
    5: ['UTG', 'CO', 'BTN', 'SB', 'BB'],
    6: ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
    7: ['UTG', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
    8: ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
    9: ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
}


def check_orders():
    for n in range(2, 10):
        seat, pre, post = TB.orders(n)
        assert pre == EXPECTED_PRE[n], (n, pre)
        assert len(seat) == n and len(pre) == n and len(post) == n, (n, seat, pre, post)
        assert len(set(seat)) == n, (n, seat)
        if n == 2:
            assert seat == ['SB', 'BB']
            assert pre == ['SB', 'BB']
            assert post == ['BB', 'SB']
        else:
            assert seat[:3] == ['BTN', 'SB', 'BB'], (n, seat)
            assert post[:2] == ['SB', 'BB'], (n, post)

    assert gto.behind_of('CO', 5) == 3
    assert gto.behind_of('BTN', 5) == 2
    assert gto.behind_of('UTG', 5) == 4
    assert gto.behind_of('UTG+1', 5) == 4  # unknown label fallback; must not occur in orders(5)


def check_format_capacity():
    f = FS.Field(entries=100, seed=99001, fmt='standard')
    assert f.max_seat == 9, f.max_seat
    assert len(f.tables) == math.ceil(100 / 9), len(f.tables)
    assert all(len(tb.seats) == 9 for tb in f.tables.values())
    assert all(tb.n() <= 9 for tb in f.tables.values())

    main = FS.Field(entries=100, seed=99002, fmt='main')
    assert main.max_seat == 9
    assert len(main.tables) == math.ceil(100 / 9)

    deep = FS.Field(entries=17, seed=99003, fmt='deep')
    assert deep.max_seat == 8
    assert len(deep.tables) == math.ceil(17 / 8)
    assert all(len(tb.seats) == 8 for tb in deep.tables.values())


def check_final_table_break():
    f = FS.Field(entries=100, seed=99004, fmt='standard')
    keep = set(range(9))
    for pid, p in f.players.items():
        if pid not in keep:
            p['stack'] = 0
    f._collect_busts()
    f._balance()

    active = [tb for tb in f.tables.values() if tb.n() > 0]
    assert f.remaining() == 9
    assert len(active) == 1, [(tb.id, tb.n()) for tb in active]
    assert active[0].n() == 9
    assert len(active[0].seats) == 9

    for pid in range(5, 9):
        f.players[pid]['stack'] = 0
    f._collect_busts()
    f._balance()
    active = [tb for tb in f.tables.values() if tb.n() > 0]
    assert f.remaining() == 5
    assert len(active) == 1
    assert active[0].n() == 5
    assert TB.orders(5)[1] == EXPECTED_PRE[5]


def check_live_roundtrip():
    f = FS.Field(entries=18, seed=99005, fmt='standard')
    d = live2._dump(f)
    assert d.get('max_seat') == 9
    f2 = live2._load_field(d)
    assert f2.max_seat == 9
    assert all(tb.max_seat == 9 for tb in f2.tables.values())
    assert all(len(tb.seats) == 9 for tb in f2.tables.values())


def main():
    check_orders()
    check_format_capacity()
    check_final_table_break()
    check_live_roundtrip()
    print('PASS 9-max structural verification')
    print('standard=9, main=9, deep=8; final 9 -> one table; positions 2..9 explicit')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
