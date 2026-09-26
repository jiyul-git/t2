#!/usr/bin/env python3
"""Tournament dealer/blind rotation regression.

Checks the bug where Table.button was a compressed alive-list index:
when a seat disappeared or a balancing move changed list membership, the
same numeric index could point at a different physical seat and repeat/skip
BTN/SB/BB.

No production state is read or written.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fieldsim as FS
from table import orders


def p(pid):
    return {'pid': pid, 'prof': {'type': 'TAG'}, 'stack': 10000,
            'table': 0, 'seat': None}


def posmap(tb):
    alive = tb.ordered_alive()
    seats = [tb.seat_of(x['pid']) for x in alive]
    dealer = tb.dealer_seat()
    order, _, _ = orders(len(seats))
    i = seats.index(dealer)
    return {seats[(i+k) % len(seats)]: order[k] for k in range(len(seats))}


def main():
    players = [p(i) for i in range(1, 10)]
    # legacy button index 5 => sixth live physical seat, seat 6.
    tb = FS.Table(0, players, button=5, max_seat=9)

    assert tb.dealer_seat() == 6, (tb.dealer_seat(), tb.seats)
    pm = posmap(tb)
    assert pm[7] == 'SB', pm

    # End of hand: dealer must move to physical seat 7.
    tb.advance_button()
    assert tb.dealer_seat() == 7, tb.dealer_seat()

    # Unrelated seat disappears, then a newcomer fills that physical hole.
    # Dealer must NOT drift because the compressed live list changed.
    gone = players[1]  # seat 2
    gone['stack'] = 0
    tb.players.remove(gone)
    tb.stand(gone['pid'])

    newcomer = p(10)
    tb.players.append(newcomer)
    assert tb.sit(newcomer) == 2

    assert tb.dealer_seat() == 7, (tb.dealer_seat(), tb.seats)
    pm = posmap(tb)
    assert pm[7] == 'BTN', pm

    # players append order may differ from physical order after balancing.
    # The next-BB selector must still use seat order, not append order.
    nxt_bb = tb.player_after_button(2)
    assert nxt_bb is not None
    bb_seat = tb.seat_of(nxt_bb['pid'])
    pm = posmap(tb)
    assert pm[bb_seat] == 'BB', (bb_seat, pm)

    # Removing a non-button seat must not move the dealer.
    victim = next(x for x in tb.players
                  if x['stack'] > 0 and tb.seat_of(x['pid']) == 4)
    victim['stack'] = 0
    tb.players.remove(victim)
    tb.stand(victim['pid'])
    assert tb.dealer_seat() == 7, (tb.dealer_seat(), tb.seats)

    # Persistence shape used by live2: constructor first, fixed slots restored,
    # then restore_button() with saved physical button seat.
    saved_seats = list(tb.seats)
    saved_button = tb.button
    saved_button_seat = tb.button_seat
    live_players = list(tb.players)
    tb2 = FS.Table(0, live_players, button=saved_button, max_seat=9,
                   button_seat=saved_button_seat)
    tb2.seats = saved_seats
    tb2.restore_button(saved_button, saved_button_seat)
    assert tb2.dealer_seat() == 7, (tb2.dealer_seat(), tb2.seats)
    assert posmap(tb2)[7] == posmap(tb)[7]

    print('PASS button seat anchor')
    print({'dealer_seat': tb.dealer_seat(),
           'hero_seat': 7,
           'hero_pos': posmap(tb)[7],
           'button_index_compat': tb.button})


if __name__ == '__main__':
    main()
