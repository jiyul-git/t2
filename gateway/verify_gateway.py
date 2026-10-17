#!/usr/bin/env python3
"""Gateway check with real game servers: sign-in rules, per-player isolation, streaming, idle stop.

    python3 gateway/verify_gateway.py

Google is replaced by a fake token checker (tokens are "good:<sub>:<email>"), so this runs offline.
"""
import json, os, shutil, socket, sys, tempfile, threading, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gateway as G

checks = 0


def ok(cond, msg):
    global checks
    checks += 1
    if not cond:
        raise SystemExit('FAIL: ' + msg)


def fake_google(token):
    parts = token.split(':')
    if parts[0] == 'good' and len(parts) == 3:
        return {'iss': 'accounts.google.com', 'aud': 'web-client', 'email_verified': 'true',
                'exp': str(int(time.time()) + 600), 'sub': parts[1], 'email': parts[2], 'name': parts[1]}
    if parts[0] == 'otherapp':
        return {'iss': 'accounts.google.com', 'aud': 'someone-else', 'email_verified': 'true',
                'exp': str(int(time.time()) + 600), 'sub': '9', 'email': 'a@x.com'}
    raise G.AuthError('Google 토큰 확인 실패')


class Client:
    def __init__(self, base):
        self.base, self.cookie = base, None

    def call(self, method, path, body=None, raw=False):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
        if self.cookie:
            req.add_header('Cookie', self.cookie)
        opener = urllib.request.build_opener(NoRedirect)
        try:
            r = opener.open(req, timeout=60)
        except urllib.error.HTTPError as e:
            r = e
        sc = r.headers.get('Set-Cookie')
        if sc:
            self.cookie = sc.split(';')[0]
        body = r.read()
        return r.status, (body if raw else (json.loads(body) if body and body[:1] in b'{[' else body)), r.headers


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def main():
    root = tempfile.mkdtemp(prefix='t2_gw_')
    port = socket.socket(); port.bind(('127.0.0.1', 0)); p = port.getsockname()[1]; port.close()
    cfg = G.load_config(None)
    cfg.update(port=p, data_root=os.path.join(root, 'users'), run_root=os.path.join(root, 'run'),
               state_dir=os.path.join(root, 'gw'), google_client_ids=['web-client', 'android-client'],
               allowed_emails=['me@gmail.com', 'friend@gmail.com'], secure_cookie=False, max_backends=1,
               idle_seconds=1800, backend_env={'T2_SCHEDULE_ENABLED': '0'})
    srv = G.serve(cfg, verify_token=fake_google)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:%d' % p
    try:
        a = Client(base)
        st, _, h = a.call('GET', '/')
        ok(st == 302 and h['Location'] == '/login', 'signed-out page goes to /login: %s' % st)
        st, r, _ = a.call('GET', '/api/lobby')
        ok(st == 401, 'signed-out API is refused: %s' % st)
        st, page, _ = a.call('GET', '/login', raw=True)
        ok(st == 200 and b'web-client' in page and b't2SignIn' in page, 'login page carries the client id')

        st, r, _ = a.call('POST', '/auth/google', {'id_token': 'bad-token-xxxxxxxxxxxxxxxx'})
        ok(st == 401 and a.cookie is None, 'bad token refused: %s %r' % (st, r))
        st, r, _ = a.call('POST', '/auth/google', {'id_token': 'otherapp:xxxxxxxxxxxxxxxxxxxxx'})
        ok(st == 401, 'token for another app refused: %s %r' % (st, r))
        st, r, _ = a.call('POST', '/auth/google', {'id_token': 'good:777:stranger@gmail.com'})
        ok(st == 403 and a.cookie is None, 'not-invited account refused: %s %r' % (st, r))
        st, r, _ = a.call('POST', '/auth/dev', {'email': 'me@gmail.com'})
        ok(st == 404, 'dev login is off by default: %s' % st)

        st, r, _ = a.call('POST', '/auth/google', {'id_token': 'good:111:Me@Gmail.com'})
        ok(st == 200 and a.cookie and a.cookie.startswith('t2s='), 'invited account signs in: %s %r' % (st, r))
        st, r, _ = a.call('GET', '/auth/me')
        ok(st == 200 and r['email'] == 'me@gmail.com', 'me: %r' % (r,))

        t0 = time.time()
        st, r, _ = a.call('GET', '/api/lobby')
        ok(st == 200 and 'wallet' in r, 'lobby through the gateway starts my game server: %s %r' % (st, str(r)[:200]))
        print('  first request (server start) %.1fs' % (time.time() - t0))
        bal_a = r['wallet']['balance']
        st, r, _ = a.call('POST', '/api/profile', {'profile': {'nickname': '나', 'deck': 'navy'}})
        ok(st == 200, 'profile save through gateway: %s %r' % (st, r))
        st, page, h = a.call('GET', '/', raw=True)
        ok(st == 200 and b'lounge' in page, 'lobby page served')

        # a forged or tampered cookie is not accepted
        b = Client(base)
        b.cookie = a.cookie[:-4] + 'abcd'
        st, _, _ = b.call('GET', '/api/lobby')
        ok(st == 401, 'tampered cookie refused: %s' % st)
        uid_a = a.cookie.split('=', 1)[1].split('.')[0]
        b.cookie = 't2s=%s.%d.%s' % (uid_a, int(time.time()) + 999, '0' * 64)
        st, _, _ = b.call('GET', '/api/lobby')
        ok(st == 401, 'forged cookie refused: %s' % st)

        # the friend gets a separate wallet and profile
        b = Client(base)
        st, r, _ = b.call('POST', '/auth/google', {'id_token': 'good:222:friend@gmail.com'})
        ok(st == 200, 'friend signs in')
        st, r, _ = b.call('GET', '/api/profile')
        ok(st == 200 and r['profile'] == {}, 'friend does not see my profile: %r' % (r,))
        st, r, _ = b.call('GET', '/api/lobby')
        ok(st == 200 and r['wallet']['balance'] == bal_a, 'friend has a fresh wallet of their own')
        users = sorted(os.listdir(cfg['data_root']))
        ok(len(users) == 2 and all(u.startswith('u_') and 'gmail' not in u for u in users), 'two private folders: %r' % users)
        ok(os.path.exists(os.path.join(cfg['data_root'], uid_a, 'profile.json')), 'my profile is in my folder')
        ok(not os.path.exists(os.path.join(cfg['data_root'], b.cookie.split('=', 1)[1].split('.')[0], 'profile.json')),
           'nothing written to the friend folder by me')

        # max_backends=1: my server was stopped to make room; my next request brings it back with my data
        ok(len([x for x in srv.backends.procs.values() if x['proc'].poll() is None]) == 1, 'one game server at a time')
        st, r, _ = a.call('GET', '/api/profile')
        ok(st == 200 and r['profile'].get('nickname') == '나', 'my data survives being stopped and restarted: %r' % (r,))

        # idle stop
        srv.backends.stop_all()
        ok(not srv.backends.procs, 'game servers stop')

        st, r, _ = a.call('POST', '/auth/logout', {})
        st, _, _ = a.call('GET', '/api/lobby')
        ok(st == 401, 'after logout the API is refused: %s' % st)
    finally:
        srv.shutdown()
        srv.backends.stop_all()
        shutil.rmtree(root, ignore_errors=True)
    print('verify_gateway OK (%d checks)' % checks)


if __name__ == '__main__':
    main()
