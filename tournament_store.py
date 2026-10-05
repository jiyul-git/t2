"""Durable play-chip wallet and scheduled tournaments (one local HERO account).

Wallet, entry receipts and the authoritative engine snapshot share a SQLite
transaction. Runtime code/assets are replaceable; T2_DATA_DIR is user data.
"""
import contextlib
import hashlib
import json
import os
import sqlite3
import time
from decimal import Decimal, ROUND_FLOOR

import formats as FM
import personal_data as PD
from table import BLINDS

PLAYER = 'hero'
DEFAULT_SCHEDULE = [
    dict(fmt='standard', minute=0, buyin=1000, bot_entries=99,
         late_minutes=60, max_reentries=2),
    dict(fmt='turbo', minute=20, buyin=500, bot_entries=44,
         late_minutes=30, max_reentries=2),
    dict(fmt='deep', minute=40, buyin=5000, bot_entries=179,
         late_minutes=90, max_reentries=2),
]


class TournamentError(ValueError):
    def __init__(self, message, code='conflict'):
        super().__init__(message)
        self.code = code


def active_seconds(elapsed):
    """55 minutes play / 5 minutes break, aligned to tournament start."""
    elapsed = max(0.0, float(elapsed))
    cycles, phase = divmod(elapsed, 3600.0)
    return cycles * 3300.0 + min(phase, 3300.0)


def prizes(pool, n_paid, flat):
    """Integer-chip payouts, normalized and conserving every chip."""
    weights = [Decimal(str(x)) for x in FM.payouts(n_paid, flat)]
    total = sum(weights)
    raw = [Decimal(pool) * w / total for w in weights]
    amounts = [int(x.to_integral_value(rounding=ROUND_FLOOR)) for x in raw]
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - amounts[i]), i))
    for i in order[:pool - sum(amounts)]:
        amounts[i] += 1
    return amounts


def can_reenter(event, now=None):
    now = time.time() if now is None else now
    entries = [e for e in event['entries'] if e['status'] != 'cancelled']
    return bool(entries and entries[-1]['status'] == 'busted'
                and not event['closed'] and not event['finished'] and now < event['closes_at']
                and event['rules']['reentry']
                and len(entries) <= event['rules']['max_reentries']
                and event['rules']['bot_entries'] + len(entries) < event['rules']['max_entries'])


class Store:
    def __init__(self, root=None, initial_chips=None, schedule=None):
        self.root = str(PD.normalized(root) if root is not None else
                        PD.resolve_data_dir(os.path.dirname(__file__)))
        os.makedirs(self.root, exist_ok=True)
        self.path = os.path.join(self.root, 'tournaments.sqlite3')
        self.initial = int(initial_chips if initial_chips is not None else
                           os.environ.get('T2_INITIAL_CHIPS', '100000'))
        if not 0 <= self.initial < 10**12:
            raise ValueError('초기 칩 범위 오류')
        config = os.path.join(self.root, 'schedule.json')
        if schedule is None and os.path.exists(config):
            with open(config, encoding='utf-8') as fp:
                schedule = json.load(fp)
        self.schedule = schedule if schedule is not None else DEFAULT_SCHEDULE
        for spec in self.schedule:
            if any(not isinstance(spec[key], int) or isinstance(spec[key], bool) for key in
                   ('minute', 'buyin', 'bot_entries', 'late_minutes', 'max_reentries')):
                raise ValueError('바이인·인원·시간·횟수는 정수여야 합니다.')
            if (spec['fmt'] not in FM.FORMATS or not 0 <= spec['minute'] < 60
                    or not 1 <= spec['buyin'] < 10**9
                    or not 2 <= spec['bot_entries'] < 1000
                    or not 1 <= spec['late_minutes'] <= 180
                    or not 0 <= spec['max_reentries'] <= 100):
                raise ValueError('예약 토너먼트 설정 오류')
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY, balance INTEGER NOT NULL CHECK(balance >= 0));
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY, event_key TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL, tournament_id TEXT, entry_no INTEGER,
                    delta INTEGER NOT NULL, balance_after INTEGER NOT NULL,
                    created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS tournaments (
                    id TEXT PRIMARY KEY, starts_at REAL NOT NULL, closes_at REAL NOT NULL,
                    rules TEXT NOT NULL, state TEXT, revision INTEGER NOT NULL DEFAULT 0,
                    closed INTEGER NOT NULL DEFAULT 0, finished INTEGER NOT NULL DEFAULT 0,
                    prize_table TEXT);
                CREATE TABLE IF NOT EXISTS entries (
                    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
                    entry_no INTEGER NOT NULL, created_at REAL NOT NULL,
                    pid INTEGER, status TEXT NOT NULL, rank INTEGER, payout INTEGER,
                    PRIMARY KEY(tournament_id, entry_no));
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            ''')
            # executescript commits its preceding transaction. Re-open it so
            # the first grant and account creation are indivisible as well.
            db.execute('BEGIN IMMEDIATE')
            if db.execute('PRAGMA user_version').fetchone()[0] == 0:
                db.execute('PRAGMA user_version=1')
            if not db.execute('SELECT 1 FROM players WHERE id=?', (PLAYER,)).fetchone():
                db.execute('INSERT INTO players VALUES (?, ?)', (PLAYER, self.initial))
                db.execute('INSERT INTO ledger(event_key,kind,delta,balance_after,created_at) '
                           'VALUES (?,?,?,?,?)', ('initial:hero', 'initial', self.initial,
                                                 self.initial, time.time()))

    @contextlib.contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _money(self, db, key, delta, kind, tid, entry_no, now):
        if db.execute('SELECT 1 FROM ledger WHERE event_key=?', (key,)).fetchone():
            return
        balance = db.execute('SELECT balance FROM players WHERE id=?', (PLAYER,)).fetchone()[0]
        if balance + delta < 0:
            raise TournamentError('보유 칩이 부족합니다.', 'insufficient_chips')
        db.execute('UPDATE players SET balance=? WHERE id=?', (balance + delta, PLAYER))
        db.execute('INSERT INTO ledger(event_key,kind,tournament_id,entry_no,delta,'
                   'balance_after,created_at) VALUES (?,?,?,?,?,?,?)',
                   (key, kind, tid, entry_no, delta, balance + delta, now))

    def wallet(self):
        with self._db() as db:
            return {'balance': db.execute('SELECT balance FROM players WHERE id=?',
                                         (PLAYER,)).fetchone()[0],
                    'transactions': [dict(r) for r in db.execute(
                        'SELECT kind,tournament_id,entry_no,delta,balance_after,created_at '
                        'FROM ledger ORDER BY id DESC LIMIT 30')]}

    def ensure_schedule(self, now=None):
        now = time.time() if now is None else now
        hour = int(now // 3600) * 3600
        with self._db() as db:
            for h in range(hour - 7200, hour + 86400, 3600):
                for spec in self.schedule:
                    start = h + spec['minute'] * 60
                    # On first installation, don't simulate expired past tournaments.
                    if start + spec['late_minutes'] * 60 <= now:
                        continue
                    key = '%s:%d' % (spec['fmt'], start)
                    fmt = FM.get(spec['fmt'])
                    rules = dict(spec, name=fmt['name'], seats=9, max_entries=1000,
                                 start_stack=int(fmt['start_bb']) * int(BLINDS[0][2]),
                                 level_minutes=FM.level_minutes(spec['fmt']),
                                 itm_frac=fmt['itm_frac'], payout_flat=fmt['payout_flat'],
                                 reentry=spec['max_reentries'] > 0,
                                 seed=int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'big'))
                    db.execute('INSERT OR IGNORE INTO tournaments(id,starts_at,closes_at,rules) '
                               'VALUES (?,?,?,?)',
                               (key, start, start + spec['late_minutes'] * 60, json.dumps(rules)))

    def _event(self, db, tid):
        row = db.execute('SELECT * FROM tournaments WHERE id=?', (tid,)).fetchone()
        if row is None:
            raise TournamentError('토너먼트를 찾을 수 없습니다.', 'not_found')
        out = dict(row)
        out['rules'] = json.loads(out['rules'])
        out['state'] = json.loads(out['state']) if out['state'] else None
        out['entries'] = [dict(r) for r in db.execute(
            'SELECT * FROM entries WHERE tournament_id=? ORDER BY entry_no', (tid,))]
        request = db.execute('SELECT value FROM meta WHERE key=?', ('enter:' + tid,)).fetchone()
        out['enter_requested'] = bool(request and request[0] == '1')
        timestamp = db.execute('SELECT value FROM meta WHERE key=?', ('enter_time:' + tid,)).fetchone()
        out['enter_requested_at'] = float(timestamp[0]) if timestamp else None
        return out

    def event(self, tid):
        with self._db() as db:
            return self._event(db, tid)

    def active_id(self):
        with self._db() as db:
            r = db.execute("SELECT value FROM meta WHERE key='active'").fetchone()
            return r[0] if r else None

    def set_active(self, tid):
        with self._db() as db:
            ev = self._event(db, tid)
            if not ev['entries'] or ev['entries'][-1]['status'] == 'cancelled':
                raise TournamentError('먼저 바이인해 주세요.')
            db.execute("INSERT OR REPLACE INTO meta VALUES ('active',?)", (tid,))
        return ev

    def load_active(self):
        tid = self.active_id()
        if not tid:
            return None
        return self.event(tid)['state']

    def request_enter(self, tid, requested=True, now=None):
        now = time.time() if now is None else now
        with self._db() as db:
            ev = self._event(db, tid)
            if not ev['entries'] or ev['entries'][-1]['status'] == 'cancelled':
                raise TournamentError('먼저 바이인해 주세요.')
            if requested and ev['enter_requested']:
                return
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',
                       ('enter:' + tid, '1' if requested else '0'))
            if requested:
                db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',
                           ('enter_time:' + tid, str(now)))
            if ev['state'] is not None and not requested:
                ev['state']['hero_ready'] = False
                db.execute('UPDATE tournaments SET state=? WHERE id=?',
                           (json.dumps(ev['state']), tid))
            db.execute('UPDATE tournaments SET revision=revision+1 WHERE id=?', (tid,))

    def reserve(self, tid, reentry=False, expected_entry=None, now=None):
        now = time.time() if now is None else now
        with self._db() as db:
            if reentry and (not isinstance(expected_entry, int) or isinstance(expected_entry, bool)
                            or expected_entry < 1):
                raise TournamentError('이전 참가 번호는 양의 정수여야 합니다.')
            ev = self._event(db, tid)
            rules = ev['rules']
            existing = ev['entries']
            latest = existing[-1] if existing else None
            if latest and latest['status'] != 'cancelled':
                if not reentry:
                    return dict(latest, duplicate=True)
                if expected_entry is None or isinstance(expected_entry, bool):
                    raise TournamentError('이전 참가 번호가 필요합니다.')
                if latest['entry_no'] == expected_entry + 1:
                    return dict(latest, duplicate=True)
                if latest['entry_no'] != expected_entry or latest['status'] != 'busted':
                    raise TournamentError('탈락한 참가에 대해서만 재참가할 수 있습니다.')
                if not rules['reentry'] or sum(e['status'] != 'cancelled' for e in existing) > rules['max_reentries']:
                    raise TournamentError('이 대회의 재참가 횟수를 모두 사용했습니다.')
            elif reentry:
                raise TournamentError('재참가할 이전 참가가 없습니다.')
            if ev['closed'] or ev['finished'] or now >= ev['closes_at']:
                raise TournamentError('참가 등록이 마감되었습니다.', 'registration_closed')
            # Late entry needs the actual progressed field, never a fresh stack field.
            if now >= ev['starts_at']:
                st = ev['state'] or {}
                if st.get('background_seconds', -1) + 2 < active_seconds(now - ev['starts_at']):
                    raise TournamentError('대회 진행을 동기화하고 있습니다. 잠시 후 다시 참가해 주세요.',
                                          'synchronizing')
            count = sum(x['status'] != 'cancelled' for x in existing)
            if rules['bot_entries'] + count >= rules['max_entries']:
                raise TournamentError('최대 1,000엔트리에 도달했습니다.')
            number = (latest['entry_no'] if latest else 0) + 1
            self._money(db, 'buyin:%s:%d' % (tid, number), -rules['buyin'],
                        'reentry' if reentry else 'buyin', tid, number, now)
            status = 'reserved' if now < ev['starts_at'] else 'waiting'
            db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?)',
                       (tid, number, now, None, status, None, None))
            db.execute('UPDATE tournaments SET revision=revision+1 WHERE id=?', (tid,))
            return dict(tournament_id=tid, entry_no=number, status=status, duplicate=False)

    def cancel(self, tid, number, now=None):
        now = time.time() if now is None else now
        with self._db() as db:
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                raise TournamentError('참가 번호는 양의 정수여야 합니다.')
            ev = self._event(db, tid)
            entry = next((e for e in ev['entries'] if e['entry_no'] == number), None)
            if not entry:
                raise TournamentError('참가 내역이 없습니다.')
            if entry['status'] == 'cancelled':
                return
            if now >= ev['starts_at'] or entry['status'] != 'reserved':
                raise TournamentError('대회 시작 전 예약만 취소할 수 있습니다.')
            self._money(db, 'refund:%s:%d' % (tid, number), ev['rules']['buyin'],
                        'refund', tid, number, now)
            db.execute("UPDATE entries SET status='cancelled' WHERE tournament_id=? AND entry_no=?",
                       (tid, number))
            db.execute('UPDATE tournaments SET revision=revision+1 WHERE id=?', (tid,))
            active = db.execute("SELECT value FROM meta WHERE key='active'").fetchone()
            if active and active[0] == tid:
                db.execute("DELETE FROM meta WHERE key='active'")
            db.execute('DELETE FROM meta WHERE key IN (?,?)', ('enter:' + tid, 'enter_time:' + tid))

    def save_state(self, tid, st, expected_revision=None, assignments=None, now=None):
        now = time.time() if now is None else now
        with self._db() as db:
            ev = self._event(db, tid)
            if expected_revision is not None and ev['revision'] != expected_revision:
                return False
            for number, pid in (assignments or {}).items():
                db.execute("UPDATE entries SET pid=?,status='playing' "
                           "WHERE tournament_id=? AND entry_no=? AND status IN ('reserved','waiting')",
                           (pid, tid, number))
            self._settle(db, ev, st, now)
            db.execute('UPDATE tournaments SET state=?,revision=revision+1 WHERE id=?',
                       (json.dumps(st, separators=(',', ':')), tid))
            return True

    def save_active(self, st):
        tid = self.active_id()
        if st.get('tournament_id') != tid:
            raise TournamentError('다른 대회의 저장 상태입니다.')
        self.save_state(tid, st)

    def _settle(self, db, ev, st, now):
        fd = st.get('field') or {}
        players = fd.get('players') or {}
        alive = sum(p.get('stack', 0) > 0 for p in players.values())
        rows = [dict(r) for r in db.execute('SELECT * FROM entries WHERE tournament_id=?', (ev['id'],))]
        waiting = sum(e['status'] in ('reserved', 'waiting') for e in rows)
        entrants = ev['rules']['bot_entries'] + sum(e['status'] != 'cancelled' for e in rows)
        itm = max(1, int(round(entrants * ev['rules']['itm_frac'])))
        pool = entrants * ev['rules']['buyin']
        closed = bool(ev['closed'] or now >= ev['closes_at'] or
                      (players and not waiting and alive <= itm))
        if closed and not ev['prize_table']:
            table = prizes(pool, itm, ev['rules']['payout_flat'])
            db.execute('UPDATE tournaments SET closed=1,prize_table=? WHERE id=?',
                       (json.dumps(table), ev['id']))
        else:
            table = json.loads(ev['prize_table']) if ev['prize_table'] else None
        busts = fd.get('busted_order') or []
        pending = st.get('others_pending') or st.get('vclock_settle_pending')
        for entry in rows:
            pid = entry['pid']
            p = players.get(str(pid)) if pid is not None else None
            if not p or entry['status'] in ('cancelled', 'finished'):
                continue
            rank = None
            if p.get('stack', 0) <= 0 and pid in busts and not pending:
                rank = alive + len(busts) - busts.index(pid)
            elif alive == 1 and p.get('stack', 0) > 0 and not waiting and not pending:
                rank = 1
            if rank is None or waiting:
                continue
            # No ITM credit while registration/entry insertion remains open.
            if not closed and rank <= itm:
                continue
            payout = table[rank - 1] if table and rank <= len(table) else 0
            if payout:
                self._money(db, 'prize:%s:%d' % (ev['id'], entry['entry_no']), payout,
                            'prize', ev['id'], entry['entry_no'], now)
            db.execute('UPDATE entries SET status=?,rank=?,payout=? '
                       'WHERE tournament_id=? AND entry_no=?',
                       ('finished' if rank == 1 else 'busted', rank, payout,
                        ev['id'], entry['entry_no']))
            if pid == fd.get('hero_pid'):
                st['busted'] = rank != 1
                st['rank'] = rank
        if players and alive <= 1 and not waiting and not pending:
            db.execute('UPDATE tournaments SET finished=1 WHERE id=?', (ev['id'],))
        st['registration_closed'] = closed
        st['prize_pool'] = pool
        if fd.get('format_rules') is not None:
            fd['format_rules']['reentry'] = bool(ev['rules']['reentry'] and not closed)

    def jobs(self, now=None):
        now = time.time() if now is None else now
        with self._db() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM tournaments '
                   'WHERE starts_at<=? AND finished=0 ORDER BY starts_at', (now,))]
            return [self._event(db, tid) for tid in ids]

    def catalog(self, now=None):
        now = time.time() if now is None else now
        self.ensure_schedule(now)
        with self._db() as db:
            ids = {r[0] for r in db.execute('SELECT id FROM tournaments '
                   'WHERE starts_at>? ORDER BY starts_at LIMIT 90', (now - 7200,))}
            # Old participation history must never crowd future events out of
            # the catalog. Retain the latest receipts and the selected event.
            ids.update(r[0] for r in db.execute('SELECT tournament_id FROM entries '
                       'GROUP BY tournament_id ORDER BY MAX(created_at) DESC LIMIT 30'))
            active = db.execute("SELECT value FROM meta WHERE key='active'").fetchone()
            if active and active[0]:
                ids.add(active[0])
            events = []
            for tid in sorted(ids, key=lambda key: db.execute(
                    'SELECT starts_at FROM tournaments WHERE id=?', (key,)).fetchone()[0]):
                ev = self._event(db, tid)
                r = ev['rules']
                fd = (ev['state'] or {}).get('field') or {}
                last = ev['entries'][-1] if ev['entries'] else None
                closed = ev['closed'] or now >= ev['closes_at'] or ev['finished']
                count = r['bot_entries'] + sum(e['status'] != 'cancelled' for e in ev['entries'])
                public_rules = {key: value for key, value in r.items() if key != 'seed'}
                events.append(dict(public_rules, id=tid, key=r['fmt'], starts_at=ev['starts_at'],
                                   closes_at=ev['closes_at'], entries=count,
                                   remaining=sum(p.get('stack', 0) > 0 for p in fd.get('players', {}).values()) if fd else count,
                                   status='finished' if ev['finished'] else
                                          'scheduled' if now < ev['starts_at'] else
                                          'closed' if closed else 'late_registration',
                                   prize_pool=count * r['buyin'],
                                   registration_open=not closed,
                                   my_entry=last,
                                   can_reenter=can_reenter(ev, now),
                                   active=bool(active and active[0] == tid)))
        return {'tournaments': events, 'wallet': self.wallet(), 'server_now': now,
                'can_play': True, 'active_tournament': active[0] if active else None}
