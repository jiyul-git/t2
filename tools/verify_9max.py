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
    assert 'UTG+1' not in TB.orders(5)[1]


def check_format_capacity():
    f = FS.Field(entries=100, seed=99001, fmt='standard')
    assert f.max_seat == 9, f.max_seat
    assert len(f.tables) == math.ceil(100 / 9), len(f.tables)
    assert all(len(tb.seats) == 9 for tb in f.tables.values())
    sizes = sorted(tb.n() for tb in f.tables.values())
    assert sizes[0] >= 2, sizes
    assert sizes[-1] - sizes[0] <= 1, sizes
    assert sum(sizes) == 100, sizes
    assert all(tb.n() <= 9 for tb in f.tables.values())

    main = FS.Field(entries=100, seed=99002, fmt='main')
    assert main.max_seat == 9
    assert len(main.tables) == math.ceil(100 / 9)

    deep = FS.Field(entries=17, seed=99003, fmt='deep')
    assert deep.max_seat == 8
    assert len(deep.tables) == math.ceil(17 / 8)
    assert all(len(tb.seats) == 8 for tb in deep.tables.values())


def check_balance_boundary():
    f = FS.Field(entries=10, seed=99006, fmt='standard')
    active = [tb.n() for tb in f.tables.values() if tb.n() > 0]
    assert len(active) == 2, active
    assert max(active) - min(active) <= 1, active


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


def check_one_hand_each_n():
    old_log = FS.Field.BOT_LOG
    old_strict = FS.STRICT
    FS.Field.BOT_LOG = 0
    FS.STRICT = True
    try:
        for n in range(2, 10):
            f = FS.Field(entries=n, seed=99100 + n, fmt='standard')
            tb = next(iter(f.tables.values()))
            assert tb.n() == n, (n, tb.n())
            ok = f._play_table(tb)
            assert ok is True, (n, f.errors)
            assert not f.errors, (n, f.errors)
    finally:
        FS.Field.BOT_LOG = old_log
        FS.STRICT = old_strict


def check_live_roundtrip():
    f = FS.Field(entries=18, seed=99005, fmt='standard')
    d = live2._dump(f)
    assert d.get('max_seat') == 9
    f2 = live2._load_field(d)
    assert f2.max_seat == 9
    assert all(tb.max_seat == 9 for tb in f2.tables.values())
    assert all(len(tb.seats) == 9 for tb in f2.tables.values())

    # Legacy dump: old standard games had eight physical seat slots and no
    # max_seat key.  Restoring them must not silently convert them to 9-max.
    legacy = live2._dump(FS.Field(entries=16, seed=99007, fmt='deep'))
    legacy['fmt'] = 'standard'   # old standard was 8-max; current standard is 9-max
    legacy.pop('max_seat', None)
    for tv in legacy['tables'].values():
        tv['seats'] = list(tv['seats'][:8])
    old = live2._load_field(legacy)
    assert old.max_seat == 8
    assert all(tb.max_seat == 8 for tb in old.tables.values())
    assert all(len(tb.seats) == 8 for tb in old.tables.values())

    # Current 8-max formats must also round-trip without being widened.
    deep = FS.Field(entries=16, seed=99008, fmt='deep')
    deep2 = live2._load_field(live2._dump(deep))
    assert deep2.max_seat == 8
    assert all(tb.max_seat == 8 for tb in deep2.tables.values())
    assert all(len(tb.seats) == 8 for tb in deep2.tables.values())


def main():
    check_orders()
    check_format_capacity()
    check_balance_boundary()
    check_final_table_break()
    check_one_hand_each_n()
    check_live_roundtrip()
    print('PASS 9-max structural verification')
    print('standard=9, main=9, deep=8; initial fields balanced; final 9 -> one table')
    print('positions 2..9 explicit; one bot hand completed for every size; legacy 8-slot restore PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
