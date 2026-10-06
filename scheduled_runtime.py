"""Off-screen real-time tournament progression. Workers return snapshots only.

Reuse the existing per-table hand duration and chronological event merge; insert
paid late/re-entry seats only between hands. SQLite revision rejects stale jobs.
"""
import copy
import os
import time

import fieldsim as FS
import live2 as L
import persona as PS
import formats as FM
from tournament_store import active_seconds


def _enter_time(event):
    return active_seconds(max(0, (event.get('enter_requested_at') or event['starts_at'])
                              - event['starts_at']))


def choose_job(jobs, cursor, active_id):
    """Catch up pending paid admissions first, then rotate fairly within a tier."""
    def priority(job):
        ev = job[0]
        waiting = any(e['status'] in ('reserved', 'waiting') for e in ev['entries'])
        if ev['id'] == active_id and (waiting or ev.get('enter_requested')):
            return 0
        if waiting or ev.get('enter_requested'):
            return 1
        return 2 if any(e['status'] != 'cancelled' for e in ev['entries']) else 3
    first = min(map(priority, jobs))
    candidates = [job for job in jobs if priority(job) == first]
    return candidates[cursor % len(candidates)]


def _close_admission(st, event, f):
    # A queued late request may discover that the real field reached ITM before
    # it could be seated. Close at that simulated boundary and refund the unused
    # receipt atomically when the publisher commits this snapshot.
    if f.remaining() > f.itm:
        return False
    st['admission_closed'] = True
    refunded = st.setdefault('refunded_entries', [])
    for entry in event['entries']:
        if entry['status'] in ('reserved', 'waiting') and entry.get('pid') is None:
            if entry['entry_no'] not in refunded:
                refunded.append(entry['entry_no'])
            entry['status'] = 'cancelled'
    return True


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
    if _close_admission(st, event, f):
        return assignments
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


def _tail_mini(base, tid, queued):
    """테이블 하나의 상태 + 아직 병합하지 않은 그 테이블 이벤트(시간순)를 덧씌운 것."""
    mini = L._table_mini(base, tid)
    key = str(int(tid))
    for e in queued:
        mini['players'].update(e.get('players') or {})
        mini['tables'][key] = e['table']
        mini['tilt'].update({p: v for p, v in (e.get('tilt') or {}).items() if v is not None})
        book = mini['book']
        for k in e.get('book_del') or []:
            book.pop(k, None)
        book.update(e.get('book_set') or {})
        mini['time_banks'].update(e.get('time_banks') or {})
    return mini


# 예약 대회 오프스크린 진행에서 테이블들을 한 번에 미리 계산하는 대회 시간 창(초).
# 탈락이 나면 다른 테이블의 선계산은 버려지므로(보수적 재시작) 너무 길면 낭비가 커진다.
LOOKAHEAD_SECONDS = max(1.0, float(os.environ.get('T2_SCHEDULE_LOOKAHEAD_SECONDS', '45')))


def _merge_batch(st, event, pending, target, hero_table):
    """시간순으로 한 번에 확정해도 한 핸드씩 확정한 것과 같은 이벤트 묶음.

    모든 대기 테이블의 다음 핸드 끝을 알고 있는 구간(각 대기열 끝의 최솟값, target 이하)만
    확정한다. 탈락(테이블 재배치)·유료 좌석 배정 시각·HERO 입장 시각에 걸리는 이벤트에서는
    그 이벤트(같은 시각 이벤트 포함)까지만 묶어, 그 경계 처리는 한 핸드씩과 같은 시점에 한다.
    반환: ({tid: 이벤트 수}, 마지막 시각에 끝난 테이블들, 마지막 시각, 확정 시각 수).
    """
    horizon = min(min(float(q[-1]['end']) for q in pending.values()), float(target))
    rows = sorted((float(e['end']), int(tid), i, e)
                  for tid, q in pending.items() for i, e in enumerate(q)
                  if float(e['end']) <= horizon + 1e-9)
    if not rows:
        return {}, {}, None, 0
    admit_at = min((active_seconds(max(0.0, e['created_at'] - event['starts_at']))
                    for e in event['entries']
                    if e['status'] in ('reserved', 'waiting') and e.get('pid') is None),
                   default=None)
    hero_at = (_enter_time(event) if event.get('enter_requested') and not st.get('hero_ready')
               and hero_table is not None else None)
    stop = len(rows) - 1
    for k, (end, tid, _i, e) in enumerate(rows):
        if (e.get('barrier') or (admit_at is not None and end >= admit_at - 1e-9)
                or (hero_at is not None and tid == int(hero_table) and end >= hero_at - 1e-9)):
            stop = k
            break
    when = rows[stop][0]
    while stop + 1 < len(rows) and rows[stop + 1][0] <= when + 1e-9:
        stop += 1
    rows = rows[:stop + 1]
    batch = {}
    for _end, tid, _i, _e in rows:
        batch[str(tid)] = batch.get(str(tid), 0) + 1
    due = {str(tid): [e] for end, tid, _i, e in rows if end >= when - 1e-9}
    steps = len({round(end, 9) for end, _t, _i, _e in rows})
    return batch, due, when, steps


# 선계산 대기열은 스냅샷이 아니라 이 워커 프로세스에만 둔다. 99명 필드에서 대기열이
# 상태 JSON 의 약 70%(3.4MB)였고, 발행자가 LOCK 안에서 그것을 여러 번 파싱·저장하는 동안
# 대기실 요청이 수 초~수십 초 막혔다. 스냅샷에는 대기열이 만들어진 필드의 키만 남긴다.
# 키가 맞지 않으면(재시작, 다른 프로세스, 외부에서 바뀐 필드) 대기열 없이 다시 계산한다.
_PENDING_CACHE = {}


def _pending_key(st):
    fd = st['field']
    tables = sorted((str(t), row.get('hands'), round(float(row.get('vclock_seconds', 0) or 0), 6),
                     tuple(row.get('pids') or ())) for t, row in fd['tables'].items())
    return repr((fd.get('hand_no'), round(float(st.get('background_seconds', 0) or 0), 6),
                 len(fd['players']), tables))


def _cache_pending(event_id, st):
    pending = st.get('background_pending') or {}
    _PENDING_CACHE.pop(event_id, None)
    st['background_pending'] = {}
    st.pop('background_pending_key', None)
    if pending:
        key = _pending_key(st)
        _PENDING_CACHE[event_id] = (key, pending)
        st['background_pending_key'] = key


def _take_cached_pending(event_id, st):
    key, pending = _PENDING_CACHE.pop(event_id, (None, {}))
    if not pending or st.get('background_pending_key') != key or _pending_key(st) != key:
        return {}
    return pending


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
                     format_rules={'seats': 9, 'reentry': rules['reentry'],
                                   'field_backend': rules.get('field_backend', 'real')})
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
    for key, queued in list(pending.items()):
        if isinstance(queued, dict):          # 예전 스냅샷: 테이블당 이벤트 1개
            pending[key] = [queued]
    if not pending:
        pending.update(_take_cached_pending(event['id'], st))
    f0 = L._load_field(st['field'])
    _close_admission(st, event, f0)
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
        f.format_rules['reentry'] = not (event['closed'] or st.get('admission_closed')) and rules['reentry']
        f.fmt['reentry'] = f.format_rules['reentry']
        frozen = f.field_snapshot()
        hero_table = f.players.get(f.hero_pid, {}).get('table')
        active = [tb for tb in f.tables.values() if tb.n() >= 2
                  and not (event.get('enter_requested') and st.get('hero_ready')
                           and tb.id == hero_table)]
        # Build the next completed hand for every live table before publishing
        # any result, so a slower CPU cannot reorder eliminations.
        missing = [tb for tb in active if not pending.get(str(tb.id))
                   and float(getattr(tb, 'virtual_seconds', 0)) < target]
        if missing:
            # 비어 있는 테이블만 계산하면 병합 뒤 그 테이블 하나만 비어 워커가 1개만 일한다.
            # 아직 대기 이벤트가 남은 테이블도 그 마지막 이벤트 상태에서 이어 함께 계산한다
            # (테이블 이동·탈락이 없는 구간이므로 테이블 몫만으로 이어 갈 수 있다).
            def tail(tb):
                q = pending.get(str(tb.id))
                return float(q[-1]['end']) if q else float(getattr(tb, 'virtual_seconds', 0))
            # 모든 테이블을 같은 대회 시각 창(horizon)까지 함께 계산한다. 끝나는 시각이 비슷해
            # 다음 라운드도 거의 모든 테이블이 같이 비므로 워커가 고르게 일한다.
            horizon = min(float(target), min(tail(tb) for tb in missing) + LOOKAHEAD_SECONDS)
            extend = [tb for tb in active if pending.get(str(tb.id))
                      and not pending[str(tb.id)][-1].get('barrier')
                      and tail(tb) < horizon]
            order = (sorted(missing, key=lambda x: (getattr(x, 'virtual_seconds', 0), x.id)) +
                     sorted(extend, key=lambda x: (tail(x), x.id)))
            selected = order[:budget - work]
            pool = L._table_pool() if parallel and len(selected) > 1 else None
            base = L._dump(f)
            results = []
            h4h_now = L._vclock_h4h(f)
            for tb in selected:
                queued = pending.get(str(tb.id)) or []
                mini = _tail_mini(base, tb.id, queued)
                start = float(mini['tables'][str(tb.id)].get('vclock_seconds', 0) or 0)
                # horizon 을 넘는 첫 핸드·다음 탈락·H4H 한 핸드 중 먼저 오는 곳까지.
                args = (mini, tb.id, max(horizon, start + 0.001), float('inf'), frozen,
                        '_schedule_' + str(rules['seed']), h4h_now)
                kw = {'max_hands': 1} if h4h_now else {}
                results.append((tb.id, pool.submit(L._vclock_table_task, *args, **kw) if pool else
                                L._vclock_table_task(*args, **kw)))
            for tid, result in results:
                out = result.result() if pool else result
                if out.get('errors') or not out['events']:
                    raise RuntimeError('Scheduled table failed: %s' % out.get('errors'))
                pending.setdefault(str(tid), []).extend(out['events'])
                work += len(out['events'])
            continue
        if not pending:
            st['background_seconds'] = max(st.get('background_seconds', 0), target)
            break
        h4h = L._vclock_h4h(f)
        heads = {tid: q[0] for tid, q in pending.items()}
        if h4h:
            when = max(e['end'] for e in heads.values())
            if when > target + 1e-9:
                st['background_seconds'] = max(st.get('background_seconds', 0), target)
                break
            due = dict((tid, [e]) for tid, e in heads.items())
            batch = {tid: 1 for tid in due}
            steps = 1
        else:
            batch, due, when, steps = _merge_batch(st, event, pending, target, hero_table)
            if not batch:
                st['background_seconds'] = max(st.get('background_seconds', 0), target)
                break
        merged = L.apply_vclock_events(
            st, {tid: pending[tid][:n] for tid, n in batch.items()}, {}, when,
            barrier_time=when if h4h else None)
        st['field']['virtual_play_seconds'] = when
        st['field']['hand_no'] += steps
        if merged['invalidated']:
            # 탈락·이동 뒤에는 다른 테이블의 선계산이 낡았다(기존 보수적 재시작 그대로).
            pending.clear()
        else:
            for tid, n in batch.items():
                del pending[tid][:n]
                if not pending[tid]:
                    pending.pop(tid)
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
    _cache_pending(event['id'], st)
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
