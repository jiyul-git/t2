#!/usr/bin/env python3
"""/api/profile: the player's nickname, deck and avatar are kept with the account, not the browser.

Starts a real ui_server in a temporary run folder with a temporary personal data folder, then checks:
an empty profile, saving, merging a partial change, refusing bad values (nothing half-written),
the file landing next to the wallet, and the profile surviving a server restart.
"""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = 'verify-profile-key'
checks = 0


def ok(cond, msg):
    global checks
    checks += 1
    if not cond:
        raise SystemExit('FAIL: ' + msg)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def call(port, method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (port, path), data=data, method=method,
                                 headers={'Content-Type': 'application/json', 'X-T2-Play-Key': KEY,
                                          'X-T2-Client-Mode': 'play'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def start(run, personal, port):
    env = dict(os.environ, T2_PLAY_KEY=KEY, T2_SCHEDULE_ENABLED='0', T2_DATA_DIR=personal, T2_TELEMETRY='0')
    srv = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)], cwd=run, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(150):
        if srv.poll() is not None:
            raise SystemExit('FAIL: server did not start: ' + srv.stderr.read().decode()[-400:])
        try:
            call(port, 'GET', '/api/profile')
            return srv
        except OSError:
            time.sleep(0.2)
    raise SystemExit('FAIL: server did not answer')


def main():
    run = tempfile.mkdtemp(prefix='t2_profile_run_')
    personal = tempfile.mkdtemp(prefix='t2_profile_data_')
    srv = None
    try:
        subprocess.run(['sh', os.path.join(HERE, 'setup_run_dir.sh'), run], check=True, stdout=subprocess.DEVNULL)
        port = free_port()
        srv = start(run, personal, port)

        st, r = call(port, 'GET', '/api/profile')
        ok(st == 200 and r == {'profile': {}}, 'new account starts with an empty profile: %r' % (r,))

        st, r = call(port, 'POST', '/api/profile', {'profile': {'nickname': '  지율  ', 'deck': 'navy', 'avatar': 3}})
        ok(st == 200 and r['profile'] == {'nickname': '지율', 'deck': 'navy', 'avatar': 3}, 'save: %r' % (r,))

        st, r = call(port, 'POST', '/api/profile', {'profile': {'deck': 'ivory'}})
        ok(st == 200 and r['profile'] == {'nickname': '지율', 'deck': 'ivory', 'avatar': 3}, 'partial change merges: %r' % (r,))

        for bad in ({'deck': 'gold'}, {'avatar': -1}, {'avatar': True}, {'avatar': '2'}, {'nickname': ''},
                    {'nickname': 'x' * 17}, {'wallet': 999999}, {}, None, {'deck': 'navy', 'avatar': 999}):
            st, r = call(port, 'POST', '/api/profile', {'profile': bad})
            ok(st == 400 and 'error' in r, 'refuses %r: %s %r' % (bad, st, r))
        st, r = call(port, 'GET', '/api/profile')
        ok(r['profile'] == {'nickname': '지율', 'deck': 'ivory', 'avatar': 3}, 'refused changes write nothing: %r' % (r,))

        files = os.listdir(personal)
        ok('profile.json' in files and 'tournaments.sqlite3' in files, 'profile sits next to the wallet: %r' % files)

        srv.terminate(); srv.wait(10)
        srv = start(run, personal, port)
        st, r = call(port, 'GET', '/api/profile')
        ok(r['profile'] == {'nickname': '지율', 'deck': 'ivory', 'avatar': 3}, 'profile survives a restart: %r' % (r,))
    finally:
        if srv and srv.poll() is None:
            srv.terminate()
            try: srv.wait(10)
            except subprocess.TimeoutExpired: srv.kill()
        shutil.rmtree(run, ignore_errors=True)
        shutil.rmtree(personal, ignore_errors=True)
    print('verify_profile_api OK (%d checks)' % checks)


if __name__ == '__main__':
    main()
