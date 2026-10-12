#!/usr/bin/env python3
"""The test showdown rule reveals survivors without revealing folded hands."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import session as SE


class Book:
    def observe_showdown(self, *args):
        pass


def finish(muck_enabled, folded_finish=False):
    SE.SHOWDOWN_MUCK_ENABLED = muck_enabled
    hand = SimpleNamespace(
        seats=list(range(1, 10)), post_seats=[2, 1], button=9,
        stacks={s: 900 for s in range(1, 10)}, sb=50, bb=100,
        hero=3, hash='muck-toggle', pos={s: str(s) for s in range(1, 10)},
        hole={1: ['As', 'Qd'], 2: ['Kh', 'Kc'], 3: ['Ah', 'Ad']},
        board=['2c', '7d', '9s', 'Jh', '3c'], book=Book(), dyn=None,
        pid_of=lambda seat: seat,
    )
    run = SE.HandRun(hand)
    # This fixture isolates public showdown policy from personality updates.
    run._tilt_update = lambda *args: None
    live = [2] if folded_finish else [1, 2]
    return run._finish({1: 100, 2: 100, 3: 100}, 0,
                       set(hand.seats) - set(live), live, hand.board, 'showdown')


original = SE.SHOWDOWN_MUCK_ENABLED
try:
    exposed = finish(False)
    normal = finish(True)
    assert set(exposed['shown_hole']) == {1, 2}, exposed
    assert exposed['mucked'] == [] and not exposed['allin_show'], exposed
    assert set(normal['shown_hole']) == {2} and normal['mucked'] == [1], normal
    assert exposed['stacks'] == normal['stacks'] and exposed['pots'] == normal['pots']
    assert 3 not in exposed['shown_hole']
    fold = finish(False, folded_finish=True)
    assert not fold['showdown'] and not fold.get('shown_hole'), fold
finally:
    SE.SHOWDOWN_MUCK_ENABLED = original

print('OK muck off: both showdown hands public, folded hands private, payouts unchanged')
