#!/usr/bin/env python3
"""Independent bot-table virtual clock + movement barrier regression."""
import copy, os, pathlib, sys

os.environ.setdefault('T2_BOT_LOG', '0')
os.environ.setdefault('T2_TABLE_WORKERS', '1')
os.environ.setdefault('T2_VCLOCK_SCALE', '1.0')

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fieldsim as FS
import live2 as L

# 1) Independent bot clocks advance ahead without touching the HERO table.
f = FS.Field(entries=27, hero_pid=0, seed=20261004, fmt='standard')
f.virtual_play_seconds = 0.0
f.level_minutes = 10
base = L._dump(f)
hero_tid, other_tids, _ = L._round_owners(base)
hero_before = copy.deepcopy(base['tables'][str(hero_tid)])

ahead = L.compute_vclock_ahead(base, 60.0, 3300.0)
assert ahead['mode'] == L.VCLOCK_AHEAD_MODE
assert ahead['hero_table'] == hero_tid
assert other_tids
assert ahead['coverage'] >= 0
assert base['tables'][str(hero_tid)] == hero_before
for tid in other_tids:
    row = ahead['tables'][str(tid)]
    assert row['events'], (tid, row)
    ends = [float(e['end']) for e in row['events']]
    assert ends == sorted(ends)
    assert float(row['covered_until']) == ends[-1]
print('PASS: bot-only tables advance on independent second clocks; HERO table is untouched')

# Calibration probe: with deep stacks, gather enough 9-max hands to report the
# raw action-shape mean. The production scale is set from this measured value.
cal = FS.Field(entries=27, start_stack=300000, hero_pid=0, seed=5150, fmt='standard')
cal.virtual_play_seconds = 0.0
cal.level_minutes = 10
cal_out = L.compute_vclock_ahead(L._dump(cal), 600.0, 3300.0)
durations = []
for row in cal_out['tables'].values():
    prev = 0.0
    for e in row['events']:
        end = float(e['end'])
        durations.append(end - prev)
        prev = end
if durations:
    raw_mean = sum(durations) / len(durations)
    recommended = (3600.0 / 70.0) / raw_mean
    print('VCLOCK_CAL raw_mean=%.3f n=%d recommended_scale=%.4f'
          % (raw_mean, len(durations), recommended))

# 2) A real movement barrier: 27 players starts 9/9/9. Two bot busts on one
# table create 9/9/7, so settle must invoke the actual TDA _balance path.
f2 = FS.Field(entries=27, hero_pid=0, seed=77, fmt='standard')
f2.virtual_play_seconds = 0.0
f2.level_minutes = 10
d2 = L._dump(f2)
hero2, bots2, _ = L._round_owners(d2)
tid = bots2[0]
row = copy.deepcopy(d2['tables'][str(tid)])
pids = [str(x) for x in row['pids']]
assert len(pids) == 9
players = {p: copy.deepcopy(d2['players'][p]) for p in pids}
for p in pids[:2]:
    players[p]['stack'] = 0
row['vclock_seconds'] = 20.0

synthetic = {
    str(tid): [{
        'tid': tid,
        'end': 20.0,
        'players': players,
        'table': row,
        'tilt': {},
        'book_set': {},
        'book_del': [],
        'notes': [],
        'bot_log': '',
        'barrier': 'bust',
    }]
}
st = {'field': d2}
applied = L.apply_vclock_events(
    st, synthetic, {str(tid): 0}, 20.0, barrier_time=20.0)
assert applied['invalidated'] and applied['barrier_due']
after = L._load_field(st['field'])
counts = sorted(tb.n() for tb in after.tables.values() if tb.n() > 0)
assert counts[-1] - counts[0] <= 1, counts
for p in pids[:2]:
    assert after.players[int(p)]['table'] is None
for t, tb in after.tables.items():
    if t != after.players[after.hero_pid]['table'] and tb.n() >= 2:
        assert tb.virtual_seconds >= 20.0
print('PASS: bust barrier settles through real _collect_busts/_balance and resets clocks at HERO boundary')

# 3) Table clock survives serialization exactly to sub-second precision.
for i, tid in enumerate(sorted(after.tables)):
    after.tables[tid].virtual_seconds = 123.25 + i / 10
roundtrip = L._load_field(L._dump(after))
for tid in after.tables:
    assert abs(roundtrip.tables[tid].virtual_seconds
               - after.tables[tid].virtual_seconds) < 1e-9
print('PASS: per-table virtual seconds persist through save/load')
