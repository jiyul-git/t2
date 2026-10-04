"""Delayed donor: keep dealing; never mutate an active hand or duplicate a player."""
import pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBE = r'''
import copy, json, time
import ui_server as S
L = S.L
L.new_game(entries=27, seed=700, fmt='standard')
st = L.load()
st['vclock_session_v2'] = True
st['field']['virtual_play_seconds'] = 120.0
st['field']['level_minutes'] = 10
f = L._load_field(st['field'])
ht = f.tables[f.players[f.hero_pid]['table']]
for p in [p for p in ht.players if p['pid'] != f.hero_pid][:2]:
    p['stack'] = 0
st['field'] = L._dump(f)
st['vclock_settle_pending'] = True
st['pending_archive'] = {'test_marker': True}
st['hand_seed'] = None
# An unfinished worker must never be awaited, even from _step(wait=True).
calls = []
def unready(st, wait=False, target=None):
    calls.append(wait)
    assert not wait, 'normal hand blocked on a donor/worker'
    return False
S._vclock_pump = unready
ok, fin = S._vclock_settle(st, wait=True)
assert ok and fin and not st.get('vclock_settle_pending')
assert not st.get('pending_archive') and st.get('vclock_refill')
assert st['vclock_refill']['requested_at'] == 120
req = copy.deepcopy(st['vclock_refill'])
# Request survives repeated checks and state serialization (server restart).
st = json.loads(json.dumps(L.load()))
L.vclock_request_refill(st)
assert st['vclock_refill'] == req
L.save(st)
# Play TWO real HERO hands while worker is deliberately unavailable.
for expected in (1, 2):
    r = S._step()
    for _ in range(30):
        if r['done']: break
        legal = r['view'].get('legal') or {}
        r = S._step('check' if legal.get('check') else 'fold')
    assert r['done'] and L.load()['field']['hand_no'] == expected
    assert not L.load().get('vclock_settle_pending')
assert calls and not any(calls)
print('PASS: two actual HERO hands and archives finish while worker stays unavailable')
# A donor completes at 135. HERO is in the following hand: prepare only.
st = L.load()
st['field']['virtual_play_seconds'] = 135
f = L._load_field(st['field'])
hero_tid = f.players[f.hero_pid]['table']
donor = next(t for t in f.tables.values() if t.id != hero_tid and t.n() == 9)
donor.hands += 1
donor.virtual_seconds = 135
fd = L._dump(f)
e = {'tid': donor.id, 'end': 135.0, 'table': fd['tables'][str(donor.id)],
     'players': {str(p['pid']): fd['players'][str(p['pid'])] for p in donor.players}}
events = {str(donor.id): [e]}
st['hand_seed'] = 123
before = copy.deepcopy(st['field'])
L.vclock_find_refill(st, events, {}, 134)
assert 'candidate' not in st['vclock_refill']
L.vclock_find_refill(st, events, {}, 135)
assert st['vclock_refill']['candidate']['end'] == 135
assert st['field'] == before
# Worker may already have a later speculative hand. Reservation pins departure
# to 135 and prevents publishing that later hand with the departed player.
future = copy.deepcopy(e)
future['end'] = 170.0
future['table']['hands'] += 1
future['table']['vclock_seconds'] = 170.0
events[str(donor.id)].append(future)
L.vclock_find_refill(st, events, {}, 180)
assert st['vclock_refill']['candidate']['end'] == 135
try:
    L.apply_vclock_events(st, events, {}, 135, independent_hero=True)
except ValueError: pass
else: raise AssertionError('merged into active hand')
assert st['field'] == before
print('PASS: 135s candidate cannot arrive at 134s or modify ongoing hand/pot')
# At next deal boundary apply donor result, transfer exactly once, invalidate future.
st['hand_seed'] = None
pid = st['vclock_refill']['candidate']['pid']
chips = sum(p['stack'] for p in st['field']['players'].values())
st['field']['virtual_play_seconds'] = 180
out = L.apply_vclock_events(st, events, {}, 180, independent_hero=True)
assert out['invalidated']
assert out['cursors'][str(donor.id)] == 1, 'source played past reserved departure'
f = L._load_field(st['field'])
assert f.players[pid]['table'] == hero_tid
assert sum(pid in [p['pid'] for p in t.players] for t in f.tables.values()) == 1
assert sum(p['stack'] for p in st['field']['players'].values()) == chips
assert len(st['vclock_transfers']) == 1
L.apply_vclock_events(st, events, out['cursors'], 135, independent_hero=True)
assert len(st['vclock_transfers']) == 1
assert f.tables[hero_tid].n() == 8
print('PASS: one transfer; unique player ownership, chip conservation, replay idempotence')
# Late-arriving earlier bot busts must be ordered by tournament time, not by
# the order the worker happened to finish relative to HERO.
rank_st = copy.deepcopy(st)
rf = L._load_field(rank_st['field'])
ids = list(rf.players)[:3]
rf.busted_order = [ids[0], ids[1], ids[2]]
rank_st['vclock_bust_times'] = {str(ids[0]): 120, str(ids[1]): 100, str(ids[2]): 135}
L._vclock_order_busts(rank_st, rf)
assert rf.busted_order == [ids[1], ids[0], ids[2]]
# Global balancing cannot move HERO/its players in normal mode.
protected = L._dump(f)['tables'][str(hero_tid)]
f._balance(protected_tid=hero_tid)
assert L._dump(f)['tables'][str(hero_tid)] == protected
# Sync exceptions must still refuse readiness when their worker is unavailable.
for kind in ('break', 'h4h', 'hero_bust', 'alone'):
    L.new_game(entries=19 if kind == 'h4h' else 27, seed=77, fmt='standard')
    s = L.load(); s['hand_seed'] = None; s['vclock_settle_pending'] = True
    s['field']['virtual_play_seconds'] = 120; s['vclock_session_v2'] = True
    ff = L._load_field(s['field'])
    if kind == 'break': s['ui_break_pending'] = True; s['ui_break_at'] = 120
    if kind == 'h4h': ff.itm = 18
    if kind == 'hero_bust': ff.players[ff.hero_pid]['stack'] = 0
    if kind == 'alone':
        for p in ff.tables[ff.players[ff.hero_pid]['table']].players:
            if p['pid'] != ff.hero_pid: p['stack'] = 0
    s['field'] = L._dump(ff)
    assert L.vclock_needs_sync(s), kind
    assert S._vclock_settle(s, wait=False) == (False, None), kind
    assert s['vclock_settle_pending']
print('PASS: break, H4H, HERO bust, solitary HERO still synchronize')
'''
with tempfile.TemporaryDirectory(prefix='t2_async_refill_') as td:
    subprocess.run(['sh', str(ROOT/'ui/tools/setup_run_dir.sh'), td], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, '-c', PROBE], cwd=td, check=True)
