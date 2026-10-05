"""Off-screen real-time tournament progression. Workers return snapshots only.

Reuse the existing per-table hand duration and chronological event merge; insert
paid late/re-entry seats only between hands. SQLite revision rejects stale jobs.
"""
import copy
import time

import fieldsim as FS
import live2 as L
import persona as PS
import formats as FM
from tournament_store import active_seconds


def _enter_time(event):
    return active_seconds(max(0, (event.get('enter_requested_at') or event['starts_at'])
                              - event['starts_at']))


def _seat(f, tid=None):
    candidates = [tb for tb in f.tables.values()
                  if tb.n() < f.max_seat and tb.broken_open_seats()
                  and (tid is None or tb.id == tid)]
    if candidates:
        return min(candidates, key=lambda tb: (tb.n(), tb.id))
    if tid is not None:
        return None
    new = max(f.tables, default=-1) + 1
    tb = FS.Table(new, [], max_seat=f.max_seat)
    f.tables[new] = tb
    return tb


def _insert(st, event, at, available=None):
    assignments = {}
    f = L._load_field(st['field'])
    for entry in event['entries']:
        if entry['status'] not in ('reserved', 'waiting') or entry.get('pid') is not None:
            continue
        eligible = active_seconds(max(0.0, entry['created_at'] - event['starts_at']))
        if eligible > at + 1e-9:
            continue
        tb = _seat(f, available)
        if tb is None and available is not None and all(t.n() == f.max_seat for t in f.tables.values()):
            tb = _seat(f)  # Open another table at this completed-hand boundary.
        if tb is None:
            continue
        pid = max(f.players, default=-1) + 1
        prof = PS.make_player(f.rng, 0.9, pid)
        p = {'pid': pid, 'prof': prof, 'stack': f.start_stack,
             'table': tb.id, 'seat': None}
        f.players[pid] = p
        tb.players.append(p)
        tb.sit(p, seat=tb.broken_open_seats()[0])
        if tb.n() >= 2:
            tb.reconcile_next_hand()
        tb.virtual_seconds = max(float(getattr(tb, 'virtual_seconds', 0)), at)
        f.entries += 1
        f.itm = max(1, int(round(f.entries * event['rules']['itm_frac'])))
        f.payouts = FM.payouts(f.itm, event['rules']['payout_flat'])
        f.hero_pid = pid
        f.sitout_pids = {pid}
        st['tournament_entry_no'] = entry['entry_no']
        st['busted'] = False
        st['rank'] = None
        st['hero_memos'] = {}
        assignments[entry['entry_no']] = pid
        entry['pid'] = pid
        entry['status'] = 'playing'
        # Reserve -> seat assignment has one owner. A job may retry, but its
        # revision must still match before these assignments can be committed.
        st['background_pending'] = {}
        if event.get('enter_requested') and at >= _enter_time(event):
            st['hero_ready'] = True
        f._balance()
    st['field'] = L._dump(f)
    return assignments


def advance(event, target, budget=18, parallel=True):
    """Compute a bounded batch; target is a play-time timestamp, not CPU time."""
    event = copy.deepcopy(event)
    rules = event['rules']
    st = event['state']
    assignments = {}
    if st is None:
        f = FS.Field(entries=rules['bot_entries'], start_stack=rules['start_stack'],
                     hero_pid=-1, seed=rules['seed'], fmt=rules['fmt'],
                     hands_per_level=FM.get(rules['fmt'])['hpl'], itm_frac=rules['itm_frac'],
                     format_rules={'seats': 9, 'reentry': rules['reentry']})
        f.virtual_play_seconds = 0.0
        f.level_minutes = rules['level_minutes']
        f.sitout_pids = set()
        st = {'tournament_id': event['id'], 'tournament_started_at': event['starts_at'],
              'field': L._dump(f), 'hand_seed': None, 'actions': [], 'decisions': [],
              'seed': rules['seed'], 'notes': [], 'hero_memos': {},
              'telemetry_session_id': event['id'], 'busted': False, 'rank': None,
              'background_seconds': 0.0, 'background_pending': {}, 'offscreen': True,
              'vclock_session_v2': True, 'ui_clock_started_at': event['starts_at'],
              'ui_clock_paused_seconds': 0.0, 'ui_next_break': 3300,
              'ui_break_seconds': 0}
        assignments.update(_insert(st, event, 0.0))
    if st.get('hand_seed') is not None or st.get('others_pending') or st.get('vclock_settle_pending'):
        raise ValueError('An unfinished interactive hand must settle before off-screen advancement')

    pending = st.setdefault('background_pending', {})
    f0 = L._load_field(st['field'])
    hero_table = f0.players.get(f0.hero_pid, {}).get('table')
    if (event.get('enter_requested') and hero_table is not None
            and str(hero_table) not in pending and
            float(f0.tables[hero_table].virtual_seconds) >= _enter_time(event)):
        st['hero_ready'] = True
    work = 0
    while work < budget:
        f = L._load_field(st['field'])
        if f.remaining() <= 1:
            break
        f.format_rules['reentry'] = not event['closed'] and rules['reentry']
        f.fmt['reentry'] = f.format_rules['reentry']
        frozen = f.field_snapshot()
        hero_table = f.players.get(f.hero_pid, {}).get('table')
        active = [tb for tb in f.tables.values() if tb.n() >= 2
                  and not (event.get('enter_requested') and st.get('hero_ready')
                           and tb.id == hero_table)]
        # Build the next completed hand for every live table before publishing
        # any result, so a slower CPU cannot reorder eliminations.
        missing = [tb for tb in active if str(tb.id) not in pending
                   and float(getattr(tb, 'virtual_seconds', 0)) < target]
        if missing:
            selected = sorted(missing, key=lambda x: (getattr(x, 'virtual_seconds', 0), x.id))[:budget - work]
            pool = L._table_pool() if parallel and len(selected) > 1 else None
            base = L._dump(f)
            results = []
            for tb in selected:
                start = float(getattr(tb, 'virtual_seconds', 0))
                mini = dict(base)
                mini['book'] = L._vclock_book_subset(base.get('book'), base['tables'][str(tb.id)]['pids'])
                args = (mini, tb.id, start + 0.001, float('inf'), frozen,
                        '_schedule_' + str(rules['seed']), True)
                results.append((tb.id, pool.submit(L._vclock_table_task, *args) if pool else
                                L._vclock_table_task(*args)))
            for tid, result in results:
                out = result.result() if pool else result
                if out.get('errors') or not out['events']:
                    raise RuntimeError('Scheduled table failed: %s' % out.get('errors'))
                pending[str(tid)] = out['events'][0]
            work += len(selected)
            continue
        if not pending:
            st['background_seconds'] = max(st.get('background_seconds', 0), target)
            break
        h4h = L._vclock_h4h(f)
        when = (max(e['end'] for e in pending.values()) if h4h
                else min(e['end'] for e in pending.values()))
        if when > target + 1e-9:
            st['background_seconds'] = max(st.get('background_seconds', 0), target)
            break
        due = {tid: [e] for tid, e in pending.items() if h4h or e['end'] <= when + 1e-9}
        merged = L.apply_vclock_events(st, due, {}, when,
                                      barrier_time=when if h4h else None)
        st['field']['virtual_play_seconds'] = when
        st['field']['hand_no'] += 1
        if merged['invalidated']:
            pending.clear()
        else:
            for tid in due:
                pending.pop(tid, None)
        st['background_seconds'] = max(st.get('background_seconds', 0), when)
        # Only tables whose current hand just ended may receive a paid seat.
        for tid in sorted(due, key=int):
            assigned = _insert(st, event, when, available=int(tid))
            assignments.update(assigned)
            if assigned:
                pending = st['background_pending']
                break
        if (event.get('enter_requested') and str(hero_table) in due
                and when >= _enter_time(event)):
            st['hero_ready'] = True
            pending.pop(str(hero_table), None)
        work += 1
    f = L._load_field(st['field'])
    latest = next((e for e in reversed(event['entries']) if e.get('pid') is not None), None)
    if latest:
        p = f.players.get(latest['pid'], {})
        st['busted'] = p.get('stack', 0) <= 0
        if st['busted'] and latest['pid'] in f.busted_order:
            st['rank'] = f.rank_of(latest['pid'])
    return {'id': event['id'], 'revision': event['revision'], 'state': st,
            'assignments': assignments, 'work': work}


def worker_ready():
    return True
