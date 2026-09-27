#!/usr/bin/env python3
"""TDA dead-button / heads-up / table-balance position contract."""

import fieldsim as FS
import play


def _mk(live_seats, button, sb, bb, max_seat=9):
    players = []
    for s in live_seats:
        players.append({
            'pid': 100 + s,
            'prof': {'type': 'reg'},
            'stack': 10000,
            'table': 0,
            'seat': s - 1,
        })
    tb = FS.Table(0, players, button=0, max_seat=max_seat)
    tb.seats = [None] * max_seat
    for p, s in zip(players, live_seats):
        tb.seats[s - 1] = p['pid']
        p['seat'] = s - 1
    tb.restore_positions(0, button, sb, bb)
    return tb


def _kill(tb, *seats):
    for s in seats:
        p = tb.player_at(s)
        assert p is not None, (s, tb.seats)
        p['stack'] = 0


def _state(tb):
    return (tb.button_seat, tb.sb_seat, tb.bb_seat)


checks = 0

# 1. 정상 9-handed: BTN/SB/BB가 한 단계씩 진행.
tb = _mk(list(range(1, 10)), 1, 2, 3)
tb.advance_button()
assert _state(tb) == (2, 3, 4), _state(tb)
checks += 1

# 2. BB bust: 이전 SB가 BTN, 이전 BB 자리는 dead SB, 이전 UTG가 BB.
tb = _mk(list(range(1, 10)), 1, 2, 3)
_kill(tb, 3)
tb.advance_button()
assert _state(tb) == (2, 3, 4), _state(tb)
lay = tb.hand_layout()
assert lay['dead_sb'] and not lay['dead_button'], lay
assert lay['pos'][2] == 'BTN' and lay['pos'][4] == 'BB', lay
assert 'SB' not in lay['pos'].values(), lay
assert lay['pre_seats'][-1] == 4, lay
checks += 1

# 3. SB bust: dead button, 이전 BB가 SB, 다음 생존자가 BB.
tb = _mk(list(range(1, 10)), 1, 2, 3)
_kill(tb, 2)
tb.advance_button()
assert _state(tb) == (2, 3, 4), _state(tb)
lay = tb.hand_layout()
assert lay['dead_button'] and not lay['dead_sb'], lay
assert 'BTN' not in lay['pos'].values(), lay
assert lay['pos'][3] == 'SB' and lay['pos'][4] == 'BB', lay
checks += 1

# 4. SB+BB bust: dead button + dead SB, BB만 다음 생존자에게.
tb = _mk(list(range(1, 10)), 1, 2, 3)
_kill(tb, 2, 3)
tb.advance_button()
assert _state(tb) == (2, 3, 4), _state(tb)
lay = tb.hand_layout()
assert lay['dead_button'] and lay['dead_sb'], lay
assert 'BTN' not in lay['pos'].values() and 'SB' not in lay['pos'].values(), lay
assert lay['pos'][4] == 'BB', lay
checks += 1

# 5. SB/BB/UTG 동시 bust: BB는 탈락자를 모두 건너 다음 생존자.
tb = _mk(list(range(1, 10)), 1, 2, 3)
_kill(tb, 2, 3, 4)
tb.advance_button()
assert _state(tb) == (2, 3, 5), _state(tb)
checks += 1

# 6. dead-SB 핸드 다음: dead SB 자리가 다음 dead BTN, 직전 BB가 SB.
tb = _mk(list(range(1, 10)), 1, 2, 3)
_kill(tb, 3)
tb.advance_button()            # hand 2: BTN2 / dead SB3 / BB4
# 실제 collect처럼 busted BB를 자리에서 제거.
dead_pid = tb.seats[2]
tb.seats[2] = None
tb.players = [p for p in tb.players if p['pid'] != dead_pid]
tb.advance_button()            # hand 3
assert _state(tb) == (3, 4, 5), _state(tb)
assert tb.hand_layout()['dead_button'], tb.hand_layout()
checks += 1

# 7. 3 -> HU: 가장 최근 BB였던 생존자가 BTN/SB, 상대가 BB.
tb = _mk([1, 2, 3], 1, 2, 3, max_seat=3)
_kill(tb, 2)
tb.advance_button()
assert _state(tb) == (3, 3, 1), _state(tb)
lay = tb.hand_layout()
assert lay['pre_seats'] == [3, 1] and lay['post_seats'] == [1, 3], lay
checks += 1

# 8. HU는 BTN=SB, 매 핸드 BB 교대.
tb.advance_button()
assert _state(tb) == (1, 1, 3), _state(tb)
checks += 1

# 9. dead button에서도 postflop 첫 액션은 물리 BTN 왼쪽 첫 생존자.
tb = _mk([1, 3, 4, 5, 6, 7, 8, 9], 2, 3, 4)
lay = tb.hand_layout()
assert lay['dead_button'], lay
assert lay['post_seats'][0] == 3 and lay['post_seats'][-1] == 1, lay
checks += 1

# 10. balance source는 '다음 BB 예정자'.
tb = _mk([1, 2, 3, 4, 5], 1, 2, 3, max_seat=6)
assert tb.next_bb_player()['pid'] == 103
checks += 1

# 11. balance destination은 SB를 절대 고르지 않고, BB가 가장 빨리 오는 자리.
tb = _mk([1, 3, 5], 1, 3, 5, max_seat=6)
seat = tb.worst_open_seat()
assert seat is not None and seat != tb.sb_seat, (seat, tb.sb_seat)
checks += 1

# 12. broken-table 유입은 BTN~SB 사이 좌석을 제외.
tb = _mk([1, 4, 6], 1, 4, 6, max_seat=9)
allowed = tb.broken_open_seats()
assert 2 not in allowed and 3 not in allowed, allowed
checks += 1

# 13. TDA 36-B: dead BTN 뒤 여러 빈 자리가 있으면 BTN을 SB 직전까지
#     전진시켜 incoming seat를 최대화하되 SB/BB 진행은 보존한다.
#     공식 예: BTN9 / SB1 / empty2,3 / BB4, SB1 bust -> BTN3 / SB4 / BB5.
tb = _mk([1, 4, 5, 6, 7, 8, 9], 9, 1, 4)
_kill(tb, 1)
tb.advance_button()
assert _state(tb) == (3, 4, 5), _state(tb)
checks += 1

# 14. Hand가 dead SB/BTN을 live player로 압축하지 않는다.
tb = _mk([1, 2, 4, 5, 6, 7, 8, 9], 2, 3, 4)
lay = tb.hand_layout()
profiles = {str(s): {'type': 'reg'} for s in lay['pos']}
stacks = {s: 10000 for s in lay['pos']}
h = play.Hand(
    list(lay['pos']), profiles, stacks, lay['button'], 100, 200,
    position_map=lay['pos'],
    pre_seats=lay['pre_seats'],
    post_seats=lay['post_seats'],
    sb_seat=lay['sb'], bb_seat=lay['bb'], seed=1)
assert h.button == 2 and 'SB' not in h.seat_of and h.seat_of['BB'] == 4
checks += 1

print({
    'checks': checks,
    'dead_button': True,
    'dead_sb': True,
    'heads_up_transition': True,
    'balance_source_next_bb': True,
    'balance_destination_not_sb': True,
    'broken_table_between_btn_sb_excluded': True,
    'rule36b_dead_button_maximize_incoming': True,
})
print('PASS TDA dead-button / heads-up / balance position contract')
