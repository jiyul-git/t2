"""Independent HERO protection must not prevent a required table break."""
import copy
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import fieldsim as FS
import live2 as L

f = FS.Field(entries=27, hero_pid=1, seed=13)
hero_tid = f.players[f.hero_pid]['table']
for tid, tb in f.tables.items():
    keep_count = 4 if tid == hero_tid else 5
    alive = [p for p in tb.players if p['stack'] > 0]
    alive.sort(key=lambda p: (p['pid'] != f.hero_pid, p['pid']))
    for p in alive[keep_count:]: p['stack'] = 0
f._collect_busts()
assert sorted(tb.n() for tb in f.tables.values()) == [4,5,5]
chips = sum(p['stack'] for p in f.players.values())
st = {'field': L._dump(f), 'hand_seed': None,
      'vclock_refill': {'hero_tid': hero_tid, 'requested_at': 0}}
original = copy.deepcopy(st)
active = copy.deepcopy(st)
active['hand_seed'] = 123
before_active = copy.deepcopy(active)
try:
    L.apply_vclock_events(active, {}, {}, 100, independent_hero=True)
except ValueError:
    pass
else:
    raise AssertionError('Must not move seats in an active HERO hand')
assert active == before_active

result = L.apply_vclock_events(st, {}, {}, 100, independent_hero=True)
settled = L._load_field(st['field'])
assert result['invalidated'] # speculative hands must be discarded after moves
assert sorted(tb.n() for tb in settled.tables.values()) == [7,7]
assert settled.remaining() == 14
assert sum(p['stack'] for p in settled.players.values()) == chips
pids = [pid for tb in settled.tables.values() for pid in tb.seats if pid is not None]
assert len(pids) == len(set(pids)) == 14
for tid, tb in settled.tables.items():
    for p in tb.players:
        assert p['table'] == tid and tb.seat_of(p['pid']) is not None
assert settled.hero_moves == 1 and any('테이블 브레이크' in n for n in result['notes'])
if st.get('vclock_refill'):
    assert st['vclock_refill']['hero_tid'] == settled.players[settled.hero_pid]['table']
again = L.apply_vclock_events(st, {}, {}, 100, independent_hero=True)
assert not again['invalidated']
print('independent HERO table break: PASS (14 players -> 2 tables, no duplicates/chip changes, active-hand guard)')
