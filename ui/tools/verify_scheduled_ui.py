#!/usr/bin/env python3
"""Real HTTP reservation, activation, deadline, reload/update/restart verification."""
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import live2 as L
import tournament_store as TS


def verify():
    with tempfile.TemporaryDirectory(prefix='t2_schedule_http_') as tmp:
        installation = Path(tmp) / 'T2'
        run = installation / 'system'
        data = installation / 'personal'
        # Keep the instant-action verifier's default off path. Admission checks
        # can also exercise the bot schedule with T2_VERIFY_SCHEDULE_TIMING=enforce.
        env = dict(os.environ, T2_INITIAL_CHIPS='10000',
                   T2_TIMING_V1=os.environ.get('T2_VERIFY_SCHEDULE_TIMING', 'off'),
                   T2_UI_DEFER=os.environ.get('T2_VERIFY_SCHEDULE_DEFER', '0'),
                   T2_TELEMETRY='0', T2_HERO_ACTION_SECONDS='3',
                   T2_TIMING_TEST_BASE='3', T2_TIMING_TEST_BANK='0')
        env.pop('T2_DATA_DIR', None)
        env.pop('T2_UI_REF', None)
        installer = ROOT / 'ui/tools/install_game.py'
        subprocess.run([sys.executable, str(installer), 'install', str(installation)],
                       check=True, stdout=subprocess.DEVNULL, env=env)
        minute = (int(time.time() // 60) + 1) % 60
        bots = int(os.environ.get('T2_VERIFY_SCHEDULE_BOTS', '2'))
        (data / 'schedule.json').write_text(json.dumps([dict(
            fmt='standard', minute=minute, buyin=1000, bot_entries=bots,
            late_minutes=10, max_reentries=2)]))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        log = open(Path(tmp) / 'server.log', 'w+')
        proc = None
        base = 'http://127.0.0.1:%d' % port

        def call(path, body=None):
            req = urllib.request.Request(base + path,
                data=None if body is None else json.dumps(body).encode(),
                headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as exc:
                return exc.code, json.load(exc)

        def start():
            nonlocal proc
            proc = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)],
                                    cwd=run, env=env, stdout=log, stderr=log,
                                    start_new_session=True)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    log.seek(0)
                    raise AssertionError(log.read())
                try:
                    if call('/api/wallet')[0] == 200:
                        return
                except OSError:
                    pass
                time.sleep(.1)
            raise AssertionError('HTTP startup timeout')

        def stop():
            nonlocal proc
            if proc:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=10)
                proc = None

        try:
            start()
            code, lobby = call('/api/lobby')
            assert code == 200 and lobby['wallet']['balance'] == 10000
            event = next(t for t in lobby['tournaments'] if t['status'] == 'scheduled')
            tid = event['id']
            late = os.environ.get('T2_VERIFY_SCHEDULE_LATE') == '1'
            if late:
                # Reproduce a late buy-in with no progressed snapshot yet.
                # Its paid admission must survive catching up, not return 409.
                with sqlite3.connect(data / 'tournaments.sqlite3') as db:
                    now = time.time()
                    late_age = float(os.environ.get('T2_VERIFY_SCHEDULE_LATE_SECONDS', '30'))
                    db.execute('UPDATE tournaments SET starts_at=?,closes_at=? WHERE id=?',
                               (now - late_age, now + 600, tid))
            for _ in range(3):
                code, reply = call('/api/register', {'tournament_id': tid,
                                                     'buyin': 1, 'payout': 999999})
                assert code == 200 and reply['wallet']['balance'] == 9000, reply
                if late:
                    assert reply['receipt']['status'] in ('waiting', 'playing'), reply
            assert call('/api/new', {'entries': 2})[0] == 409
            # Leaving the pre-start waiting room must release a presentation
            # request, so it cannot stop the reserved seat's future blinds.
            if not late:
                assert call('/api/enter', {'tournament_id': tid})[0] == 200
                time.sleep(2)
                with sqlite3.connect(data / 'tournaments.sqlite3') as db:
                    assert db.execute('SELECT value FROM meta WHERE key=?', ('enter:' + tid,)).fetchone()[0] == '0'
                # Start the isolated fixture imminently. A player already in its
                # waiting room can take over at the first hand boundary.
                with sqlite3.connect(data / 'tournaments.sqlite3') as db:
                    now = time.time()
                    db.execute('UPDATE tournaments SET starts_at=?,closes_at=? WHERE id=?',
                               (now + 1, now + 600, tid))
                    db.execute('UPDATE entries SET created_at=? WHERE tournament_id=?', (now, tid))
            code, reply = call('/api/enter', {'tournament_id': tid})
            assert code == 200, reply
            # Catching up is real work: every bot hand the field played before
            # the request must be simulated.  Judge the worker, not a fixed wall
            # clock: fail when no snapshot is committed for STALL seconds (the
            # waiting room stuck at 0%), or when catch-up runs slower than
            # MIN_RATE x tournament time.
            stall = float(os.environ.get('T2_VERIFY_SCHEDULE_STALL', '60'))
            min_rate = float(os.environ.get('T2_VERIFY_SCHEDULE_MIN_RATE', '5'))
            began = time.monotonic()
            progress = (-1.0, began)
            while True:
                code, view = call('/api/state')
                assert code == 200, view
                if not view.get('waiting'):
                    break
                now = time.monotonic()
                done = float(view.get('sync_seconds') or 0)
                if done > progress[0]:
                    progress = (done, now)
                assert now - progress[1] < stall, ('catch-up stalled', now - began, view)
                limit = max(90.0, 30 + float(view.get('sync_target_seconds') or 0) / min_rate)
                assert now - began < limit, ('catch-up slower than %.1fx' % min_rate, now - began, view)
                time.sleep(.5)
            catchup = time.monotonic() - began
            assert view['wallet']['balance'] == 9000, view
            assert view.get('view') or view.get('game_over'), view
            assert call('/api/wallet')[1]['balance'] == 9000
            code, tourney = call('/api/tournament')
            assert code == 200 and tourney['entries'] == bots + 1, tourney
            assert call('/api/ready')[1]['timing_on'] == (env['T2_TIMING_V1'] != 'off')
            # Refresh must reuse the same authoritative action deadline.
            if (view.get('view') or {}).get('type') == 'decision':
                token = view['token']
                assert call('/api/ready')[1]['action_deadline_ms'] is None
                first = call('/api/action-clock', {'token': token})[1]['action_deadline_ms']
                refreshed = call('/api/state')[1]
                second = call('/api/action-clock', {'token': refreshed['token']})[1]['action_deadline_ms']
                assert token == refreshed['token'] and first == second
                # The timing system now delays HERO until scheduled bot actions
                # finish. Use its actual server deadline, including that delay.
                while time.time() * 1000 < first + 250:
                    time.sleep(.2)
                # Timeout is applied by the one-second scheduler tick. Poll
                # through that tick without allowing the deadline to extend.
                deadline = time.monotonic() + 5
                while True:
                    advanced = call('/api/state')[1]
                    if advanced['token'] != token or advanced.get('game_over'):
                        break
                    assert time.monotonic() < deadline, advanced
                    assert call('/api/ready')[1]['action_deadline_ms'] == first
                    time.sleep(.2)
            # With no browser polling at all, play and blinds must continue.
            with sqlite3.connect(data / 'tournaments.sqlite3') as db:
                before = json.loads(db.execute('SELECT state FROM tournaments WHERE id=?', (tid,)).fetchone()[0])
            time.sleep(25)
            # Hand durations and worker completion vary. Keep the browser
            # absent while checking the durable snapshot, with a bounded wait.
            deadline = time.monotonic() + 60
            while True:
                with sqlite3.connect(data / 'tournaments.sqlite3') as db:
                    after = json.loads(db.execute('SELECT state FROM tournaments WHERE id=?', (tid,)).fetchone()[0])
                if after['field']['hand_no'] > before['field']['hand_no']:
                    break
                assert time.monotonic() < deadline, {
                    'before': before['field']['hand_no'], 'after': after['field']['hand_no'],
                    'offscreen': after.get('offscreen'), 'hand': after.get('hand_seed'),
                    'pending': after.get('vclock_settle_pending'),
                    'action_deadline': after.get('ui_action_deadline')}
                time.sleep(.5)
            # 2026-10-07: 자리 비움은 오프스크린으로 넘기지 않고 내 테이블을 실제처럼 계속 진행한다(sit-out).
            assert (after.get('offscreen') or after.get('busted') or after.get('away_next_deal')
                    or after.get('away_sitout')), after.keys()
            stop()
            # Remove the entire system folder. Personal files stay independent,
            # and a system-only update must restore code without a new grant.
            shutil.rmtree(run)
            env['T2_INITIAL_CHIPS'] = '777777'
            subprocess.run([sys.executable, str(installer), 'update', str(installation)],
                           check=True, stdout=subprocess.DEVNULL, env=env)
            start()
            wallet = call('/api/wallet')[1]
            assert wallet['balance'] == 9000, wallet
            assert sum(t['kind'] == 'initial' for t in wallet['transactions']) == 1
            assert sum(t['kind'] == 'buyin' for t in wallet['transactions']) == 1
            assert call('/api/register', {'tournament_id': tid})[1]['wallet']['balance'] == 9000
            with urllib.request.urlopen(base + '/') as response:
                html = response.read().decode()
                assert 'walletBalance' in html and 'id="entries"' not in html
            # Recreate the exact crash boundary after HERO busts but before
            # other-table settlement is published. Recovery must require no
            # browser readiness poll and must permit a paid re-entry afterward.
            stop()
            store = TS.Store(str(data))
            event = store.event(tid)
            st = event['state']
            field = L._load_field(st['field'])
            hero = field.players[field.hero_pid]
            winner = next(p for p in field.players.values()
                          if p['pid'] != field.hero_pid and p['stack'] > 0)
            winner['stack'] += hero['stack']
            hero['stack'] = 0
            st.setdefault('vclock_bust_times', {})[str(hero['pid'])] = float(
                st['field'].get('virtual_play_seconds') or 0)
            field._collect_busts()
            field._balance()
            st.update(field=L._dump(field), hand_seed=None, actions=[], decisions=[],
                      busted=True, offscreen=False, vclock_settle_pending=True,
                      background_pending={})
            store.save_state(tid, st)
            start()
            deadline = time.monotonic() + 90
            while True:
                event = store.event(tid)
                if (event['entries'][-1]['status'] == 'busted'
                        and not event['state'].get('vclock_settle_pending')
                        and event['state'].get('offscreen')):
                    break
                assert time.monotonic() < deadline, event['state'].keys()
                time.sleep(.2)
            while True:
                code, reply = call('/api/reenter', {'tournament_id': tid, 'entry_no': 1})
                if code == 200:
                    break
                assert reply.get('code') == 'synchronizing', reply
                assert time.monotonic() < deadline, reply
                time.sleep(.2)
            assert reply['wallet']['balance'] == 8000, reply
            assert reply['receipt']['entry_no'] == 2, reply
            for _ in range(2):
                code, repeat = call('/api/reenter', {'tournament_id': tid, 'entry_no': 1})
                assert code == 200 and repeat['wallet']['balance'] == 8000, repeat
            deadline = time.monotonic() + 90
            while True:
                code, reentered = call('/api/state')
                assert code == 200, reentered
                if not reentered.get('waiting'):
                    break
                assert time.monotonic() < deadline, reentered
                time.sleep(.2)
            assert reentered['my_entry']['entry_no'] == 2, reentered
            assert reentered['my_entry']['pid'] != hero['pid'], reentered
            assert call('/api/tournament')[1]['entries'] == bots + 2
            print('PASS scheduled HTTP: %s/replay, ignored client money, activation, '
                  'authoritative timeout, refresh, code update/restart, offline bust recovery and re-entry '
                  '(defer=%s, bots=%d, timing=%s, catch-up %.1fs)' % (
                      'late admission' if late else 'reservation',
                      env['T2_UI_DEFER'], bots, env['T2_TIMING_V1'], catchup))
        except Exception:
            log.flush()
            log.seek(0)
            print(log.read()[-16000:], file=sys.stderr)
            raise
        finally:
            stop()
            log.close()


if __name__ == '__main__':
    verify()
