#!/usr/bin/env python3
"""Integration checks for TDA blind anchors through live2 persistence/HandRun.

Uses a temporary namespace and does not read/write the user's live state.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import copy
import os
import tempfile

os.environ.setdefault('T2_BOT_LOG', '0')
TMP = tempfile.mkdtemp(prefix='t2_tda_live_')
os.environ['T2_LIVE_STATE'] = os.path.join(TMP, 'state.json')

import fieldsim as FS
import live2 as L
import play
import session as SE


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


# One full 9-max table.
f = FS.Field(entries=9, start_stack=30000, hero_pid=0, seed=20260927,
             hands_per_level=12, itm_frac=0.15, fmt='standard')
tb = next(iter(f.tables.values()))
lay0 = tb.hand_layout()
old_btn, old_sb, old_bb = lay0['button'], lay0['sb'], lay0['bb']
need(old_btn is not None and old_sb is not None and old_bb is not None,
     'initial blind anchors missing')

# Exact user bug class: current BB busts. Actual finish order advances blind state
# before _collect_busts removes the physical seat.
bust = tb.player_at(old_bb)
need(bust is not None, 'current BB player missing')
bust['stack'] = 0
expected_bb = tb._next_live_after(old_bb)

tb.advance_button()
need(tb.button_seat == old_sb, 'old SB did not become BTN')
need(tb.sb_seat == old_bb, 'old BB physical seat did not become dead SB marker')
need(tb.bb_seat == expected_bb, 'next live player did not become BB')

f._collect_busts()
lay1 = tb.hand_layout()
need(lay1['dead_sb'], 'BB bust did not produce dead SB hand')
need(lay1['pos'].get(expected_bb) == 'BB', 'expected BB label missing')
need('SB' not in lay1['pos'].values(), 'dead SB was compressed onto a live player')

# New state round-trip preserves all three physical markers exactly.
dump = L._dump(f)
need(dump.get('blind_state') == 'tda_dead_button_v1',
     'blind_state schema marker missing')
row = dump['tables'][str(tb.id)]
for k in ('button_seat', 'sb_seat', 'bb_seat'):
    need(k in row, 'table persistence missing %s' % k)

f2 = L._load_field(copy.deepcopy(dump))
tb2 = f2.tables[tb.id]
need((tb2.button_seat, tb2.sb_seat, tb2.bb_seat) ==
     (tb.button_seat, tb.sb_seat, tb.bb_seat),
     'blind anchors changed after round-trip')
need(tb2.hand_layout()['pos'] == lay1['pos'],
     'position map changed after round-trip')

# Old playable state migration: it had only button_seat. If the physical seat
# immediately after the saved BTN is vacant, recover it as dead SB exactly once.
legacy = copy.deepcopy(dump)
legacy.pop('blind_state', None)
lr = legacy['tables'][str(tb.id)]
lr.pop('sb_seat', None)
lr.pop('bb_seat', None)
f3 = L._load_field(legacy)
tb3 = f3.tables[tb.id]
lay3 = tb3.hand_layout()
need(tb3.sb_seat == old_bb and tb3.bb_seat == expected_bb,
     'legacy state did not recover dead SB / next BB')
need(lay3['dead_sb'], 'legacy migration lost dead SB')

# Real HandRun on a dead-SB layout: no fictitious SB posts, no compressed role,
# full bot hand must finish and preserve chips.
alive = tb2.ordered_alive()
layout = tb2.hand_layout()
seats = [tb2.seat_of(p['pid']) for p in alive]
profiles = {str(tb2.seat_of(p['pid'])): p['prof'] for p in alive}
stacks = {tb2.seat_of(p['pid']): p['stack'] for p in alive}
sb_amt, bb_amt = f2.blinds()
h = play.Hand(
    seats, profiles, stacks, layout['button'], sb_amt, bb_amt, hero=None,
    seed=123456,
    position_map=layout['pos'],
    pre_seats=layout['pre_seats'],
    post_seats=layout['post_seats'],
    sb_seat=layout['sb'], bb_seat=layout['bb'])
h.seat_pid = {tb2.seat_of(p['pid']): p['pid'] for p in alive}
h.table_id = tb2.id
h.table_max_seat = tb2.max_seat
f2.stamp(h)
before = sum(h.stacks.values())
rr = SE.HandRun(h).start()
need(isinstance(rr, dict) and rr.get('done'),
     'bot-only HandRun did not finish')
need(sum(h.stacks.values()) == before,
     'dead-SB HandRun changed table chip total')
need('SB' not in h.seat_of and h.seat_of.get('BB') == expected_bb,
     'Hand compressed dead SB into a live role')

print({
    'new_state_roundtrip': True,
    'legacy_dead_sb_migration': True,
    'dead_sb_handrun': True,
    'chip_total': before,
    'button': tb2.button_seat,
    'dead_sb': tb2.sb_seat,
    'bb': tb2.bb_seat,
})
print('PASS TDA live-state / HandRun integration')
