#!/usr/bin/env python3
"""Gateway check with real game servers: sign-in rules, per-player isolation, streaming, idle stop.

    python3 gateway/verify_gateway.py

Google is replaced by a fake token checker (tokens are "good:<sub>:<email>"), so this runs offline.
"""
import hashlib, hmac, io, json, os, shutil, socket, sqlite3, stat, subprocess, sys, tarfile, tempfile, threading, time
import urllib.error, urllib.request

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


class Tee:
    """Keeps what the gateway logs to stderr so we can check it never holds an e-mail address."""
    def __init__(self, real):
        self.real, self.text = real, []

    def write(self, s):
        self.text.append(s)
        return self.real.write(s)

    def flush(self):
        self.real.flush()


def free_port():
    sk = socket.socket(); sk.bind(('127.0.0.1', 0)); p = sk.getsockname()[1]; sk.close()
    return p


def start(root, **over):
    """A gateway on its own port over <root>; returns (srv, base, cfg)."""
    cfg = G.load_config(None)
    cfg.update(port=free_port(), data_root=os.path.join(root, 'users'), run_root=os.path.join(root, 'run'),
               state_dir=os.path.join(root, 'gw'), backup_dir=os.path.join(root, 'backups'),
               google_client_ids=['web-client'], secure_cookie=False, max_backends=3, idle_seconds=1800,
               backend_env={'T2_SCHEDULE_ENABLED': '0'})
    cfg.update(over)
    srv = G.serve(cfg, verify_token=fake_google)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, 'http://127.0.0.1:%d' % cfg['port'], cfg


def stop(srv):
    srv.shutdown()
    srv.server_close()
    srv.backends.stop_all()


def uid_of(c):
    return c.cookie.split('=', 1)[1].split('.')[0]


def login(base, sub, email, nick=None):
    c = Client(base)
    st, r, _ = c.call('POST', '/auth/google', {'id_token': 'good:%s:%s' % (sub, email)})
    ok(st == 200, 'sign-in %s: %s %r' % (sub, st, r))
    if nick:
        st, r, _ = c.call('POST', '/auth/register', {'nickname': nick, 'avatar': 1, 'agree': True})
        ok(st == 200, 'sign-up %s: %s %r' % (nick, st, r))
    return c


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def admin(cfgfile, *args, stdin=None):
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin.py'),
                        '--config', cfgfile] + list(args), input=stdin, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def open_suite(root):
    os.makedirs(root)
    srv, base, cfg = start(root, signup_mode='open', max_accounts=3, allowed_emails=[], dev_login=True)
    cfgfile = os.path.join(root, 'gateway.json')
    with open(cfgfile, 'w') as f:
        json.dump({k: cfg[k] for k in ('data_root', 'run_root', 'state_dir', 'backup_dir', 'signup_mode', 'max_accounts')}, f)
    sd = cfg['state_dir']
    try:
        # open signup: nobody needs to be on a list; the account count is capped
        a = login(base, '301', 'Alice@Example.com', '앨리스')
        b = login(base, '302', 'bob@example.com', '밥')
        c = login(base, '303', 'carol@example.com')                      # signed in, not signed up
        uid_a, uid_b, uid_c = uid_of(a), uid_of(b), uid_of(c)
        ok(len({uid_a, uid_b, uid_c}) == 3 and all(len(u) == 22 and u.startswith('u_') for u in (uid_a, uid_b, uid_c)), 'random uids')
        st, r, _ = Client(base).call('POST', '/auth/google', {'id_token': 'good:304:dave@example.com'})
        ok(st == 403 and '정원' in r['error'], 'full house refuses a new account: %s %r' % (st, r))
        st, r, _ = Client(base).call('POST', '/auth/google', {'id_token': 'good:301:alice@example.com'})
        ok(st == 200 and r['registered'] is True and r['email'] == 'alice@example.com', 'existing account still gets in: %r' % (r,))
        st, r, _ = Client(base).call('POST', '/auth/dev', {'email': 'erin@example.com'})
        ok(st == 403, 'dev login obeys max_accounts: %s' % st)
        st, r, _ = c.call('POST', '/auth/register', {'nickname': '캐롤', 'avatar': 3, 'agree': True})
        ok(st == 200, 'pending account signs up')
        st, r, _ = c.call('POST', '/auth/register', {'nickname': '캐롤2', 'avatar': 3, 'agree': True})
        ok(st == 409, 'sign-up only once: %s' % st)
        with open(os.path.join(sd, 'accounts.json')) as f:
            acc = json.load(f)
        rec = acc['accounts'][uid_a]
        ok(acc['version'] == 2 and acc['by_sub']['301'] == uid_a and rec['status'] == 'active' and rec['terms'] == '2026-10'
           and rec['agreed_at'] and rec['email'] == 'alice@example.com' and rec['sub'] == '301', 'accounts.json v2: %r' % (rec,))
        ok(not ({'name', 'nickname'} & set(rec)) and '앨리스' not in json.dumps(acc, ensure_ascii=False), 'no name or nickname stored')

        # permissions, and no e-mail inside the player folders
        ok(mode(os.path.join(sd, 'accounts.json')) == 0o600 and mode(os.path.join(sd, 'session.key')) == 0o600, 'state files are 0600')
        for d in (sd, cfg['data_root'], cfg['run_root'], os.path.join(cfg['data_root'], uid_a), os.path.join(cfg['run_root'], uid_a)):
            ok(mode(d) == 0o700, 'private folder 0700: %s %o' % (d, mode(d)))
        n = 0
        for dp, _, fs in os.walk(os.path.join(cfg['data_root'], uid_a)):
            for fn in fs:
                with open(os.path.join(dp, fn), 'rb') as f:
                    blob = f.read()
                n += 1
                ok(b'example.com' not in blob.lower() and b'alice' not in blob.lower(), 'no e-mail in %s' % fn)
        ok(n >= 2, 'player folder has files to check: %d' % n)
        st, r, _ = a.call('GET', '/api/lobby')
        bal, nick = r['wallet']['balance'], '앨리스'

        # session.key rotation: sessions end, the wallet comes back on re-login
        stop(srv)
        with open(os.path.join(sd, 'session.key'), 'w') as f:
            f.write('ab' * 32)
        srv, base, cfg = start(root, signup_mode='open', max_accounts=3, allowed_emails=[], dev_login=True)
        a.base = b.base = c.base = base
        st, _, _ = a.call('GET', '/api/lobby')
        ok(st == 401, 'old session ends after key rotation: %s' % st)
        a = login(base, '301', 'alice@example.com')
        ok(uid_of(a) == uid_a, 'same uid after key rotation')
        st, r, _ = a.call('GET', '/api/lobby')
        ok(st == 200 and r['wallet']['balance'] == bal, 'same wallet after key rotation')
        st, r, _ = a.call('GET', '/api/profile')
        ok(r['profile']['nickname'] == nick, 'same profile after key rotation: %r' % (r,))
        b = login(base, '302', 'bob@example.com')

        # admin.py list
        rc, out, err = admin(cfgfile, 'list')
        ok(rc == 0 and uid_a in out and 'alice@example.com' in out and '앨리스' in out and '100,000' in out and 'active' in out
           and 'pending' not in out and '3 account' in out, 'admin list: %r %r' % (out, err))

        # disable: the cookie stops working at once, the game server is stopped, sign-in is refused; enable undoes it
        st, _, _ = b.call('GET', '/api/profile')
        ok(st == 200 and uid_b in srv.backends.procs, 'bob is playing')
        rc, out, err = admin(cfgfile, 'disable', 'BOB@example.com')
        ok(rc == 0 and 'disabled' in out, 'admin disable: %r %r' % (out, err))
        st, r, h = b.call('GET', '/api/profile')
        ok(st == 401 and 'Max-Age=0' in (h.get('Set-Cookie') or ''), 'disabled account is refused and its cookie cleared: %s' % st)
        ok(uid_b not in srv.backends.procs, 'disabled account game server stopped')
        st, r, _ = Client(base).call('POST', '/auth/google', {'id_token': 'good:302:bob@example.com'})
        ok(st == 403 and '중지' in r['error'], 'disabled account cannot sign in: %s %r' % (st, r))
        b2 = Client(base)
        b2.cookie = a.cookie.split('=')[0] + '=' + G.Accounts(cfg['state_dir']).make_session(uid_b)
        for path in ('/auth/me', '/api/lobby'):
            st, _, _ = b2.call('GET', path)
            ok(st == 401, 'old cookie of a disabled account refused on %s: %s' % (path, st))
        rc, out, _ = admin(cfgfile, 'list')
        ok('disabled' in out, 'admin list shows disabled')
        rc, out, err = admin(cfgfile, 'enable', uid_b)
        ok(rc == 0 and 'active' in out, 'admin enable: %r %r' % (out, err))
        b = login(base, '302', 'bob@example.com')
        st, r, _ = b.call('GET', '/api/profile')
        ok(st == 200 and r['profile']['nickname'] == '밥', 're-enabled account plays on with its data: %r' % (r,))
        rc, _, err = admin(cfgfile, 'disable', 'nobody@example.com')
        ok(rc != 0, 'admin: unknown target fails')

        # backup
        bdir = cfg['backup_dir']
        os.makedirs(bdir, mode=0o700)
        for i in range(8):
            open(os.path.join(bdir, 't2-2020010%d-0000.tar.gz' % (i + 1)), 'wb').close()
        rc, out, err = admin(cfgfile, 'backup')
        files = sorted(os.listdir(bdir))
        ok(rc == 0 and len(files) == 7 and 't2-20200101-0000.tar.gz' not in files and files[-1] not in ('t2-20200108-0000.tar.gz',)
           and any(f.startswith('t2-2') and f > 't2-2021' for f in files), 'backup keeps newest 7: %r %r %r' % (files, out, err))
        new = files[-1]
        ok(mode(os.path.join(bdir, new)) == 0o600, 'backup file is 0600')
        with tarfile.open(os.path.join(bdir, new)) as t:
            names = t.getnames()
            ok(any(n.endswith('accounts.json') for n in names) and any(n.endswith('/%s/profile.json' % uid_a) for n in names), 'backup holds accounts and profile: %r' % names)
            ex = os.path.join(root, 'extract')
            t.extractall(ex, filter='data')
        wal = [os.path.join(dp, f) for dp, _, fs in os.walk(ex) for f in fs if f == 'tournaments.sqlite3' and uid_a in dp][0]
        db = sqlite3.connect(wal)
        ok(db.execute("SELECT balance FROM players WHERE id='hero'").fetchone()[0] == bal and db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok',
           'backed-up wallet is intact')
        db.close()

        # delete through the API
        c = login(base, '303', 'carol@example.com')
        st, r, _ = c.call('POST', '/auth/delete', {'confirm': 'x'})
        ok(st == 400, 'delete needs the confirm word: %s' % st)
        st, r, _ = c.call('POST', '/auth/delete', {})
        ok(st == 400, 'delete needs the confirm word: %s' % st)
        st, r, _ = Client(base).call('POST', '/auth/delete', {'confirm': '삭제'})
        ok(st == 401, 'delete needs sign-in: %s' % st)
        st, _, _ = c.call('GET', '/api/profile')
        ok(st == 200 and uid_c in srv.backends.procs, 'carol is playing')
        ok(os.path.isdir(os.path.join(cfg['data_root'], uid_c)) and os.path.isdir(os.path.join(cfg['run_root'], uid_c)), 'carol folders exist')
        st, r, h = c.call('POST', '/auth/delete', {'confirm': '삭제'})
        ok(st == 200 and 'Max-Age=0' in (h.get('Set-Cookie') or ''), 'delete: %s %r' % (st, r))
        ok(not os.path.exists(os.path.join(cfg['data_root'], uid_c)) and not os.path.exists(os.path.join(cfg['run_root'], uid_c)), 'folders removed')
        ok(uid_c not in srv.backends.procs, 'game server stopped on delete')
        with open(os.path.join(sd, 'accounts.json')) as f:
            acc = json.load(f)
        ok(uid_c not in acc['accounts'] and '303' not in acc['by_sub'] and 'carol' not in json.dumps(acc), 'account record removed')
        st, _, _ = c.call('GET', '/auth/me')
        ok(st == 401, 'deleted account has no session: %s' % st)
        c = login(base, '303', 'carol@example.com')
        st, r, _ = c.call('GET', '/auth/me')
        ok(r['registered'] is False and uid_of(c) != uid_c, 'same Google account starts over as pending: %r' % (r,))
        st, r, _ = c.call('GET', '/api/lobby')
        ok(st == 403 and r.get('signup'), 'new account has to sign up again')

        # admin delete: asks first
        rc, out, err = admin(cfgfile, 'delete', 'bob@example.com', stdin='n\n')
        ok(rc != 0 and os.path.isdir(os.path.join(cfg['data_root'], uid_b)), 'admin delete: no keeps the account: %r' % out)
        rc, out, err = admin(cfgfile, 'delete', 'bob@example.com', stdin='y\n')
        ok(rc == 0 and not os.path.exists(os.path.join(cfg['data_root'], uid_b)) and G.Accounts(sd).find(uid_b) is None,
           'admin delete: yes removes folders and record: %r %r' % (out, err))
        st, _, _ = b.call('GET', '/api/lobby')
        ok(st == 401, 'deleted by admin: next request refused: %s' % st)
        rc, out, err = admin(cfgfile, 'delete', uid_a, '--yes')
        ok(rc == 0 and not os.path.exists(os.path.join(cfg['data_root'], uid_a)), 'admin delete --yes: %r %r' % (out, err))
    finally:
        stop(srv)


def migration_suite(root):
    """A v1 users.json account keeps its old folder; its new accounts.json record gets the Google sub on sign-in."""
    os.makedirs(os.path.join(root, 'gw'))
    key = bytes.fromhex('cd' * 32)
    with open(os.path.join(root, 'gw', 'session.key'), 'w') as f:
        f.write(key.hex())
    old = lambda sub: 'u_' + hmac.new(key, ('google:' + sub).encode(), hashlib.sha256).hexdigest()[:20]
    u_reg, u_pend = old('501'), old('502')
    v1 = {u_reg: {'email': 'old@example.com', 'name': 'Old Name', 'created': 1700000000, 'last_login': 1700000500,
                  'registered': 1700000100, 'nickname': '옛닉'},
          u_pend: {'email': 'half@example.com', 'name': 'Half', 'created': 1700000000, 'last_login': 1700000500}}
    with open(os.path.join(root, 'gw', 'users.json'), 'w') as f:
        json.dump(v1, f)
    data = os.path.join(root, 'users', u_reg)
    os.makedirs(data)
    with open(os.path.join(data, 'profile.json'), 'w') as f:
        json.dump({'nickname': '옛닉', 'avatar': 4, 'deck': 'navy'}, f)
    srv, base, cfg = start(root, signup_mode='open', max_accounts=3)
    try:
        sd = cfg['state_dir']
        ok(os.path.exists(os.path.join(sd, 'users.json.v1.bak')) and not os.path.exists(os.path.join(sd, 'users.json')), 'v1 file renamed to .v1.bak')
        with open(os.path.join(sd, 'accounts.json')) as f:
            acc = json.load(f)
        ok(acc['version'] == 2 and acc['accounts'][u_reg]['status'] == 'active' and acc['accounts'][u_pend]['status'] == 'pending'
           and acc['accounts'][u_reg]['email'] == 'old@example.com' and acc['by_sub'] == {}, 'migrated: %r' % (acc,))
        ok('Old Name' not in json.dumps(acc) and '옛닉' not in json.dumps(acc, ensure_ascii=False) and mode(os.path.join(sd, 'accounts.json')) == 0o600,
           'name and nickname dropped')
        st, r, _ = Client(base).call('POST', '/auth/google', {'id_token': 'good:900:n1@example.com'})
        ok(st == 200, 'new account fits (migrated ones count: 2 of 3)')
        st, r, _ = Client(base).call('POST', '/auth/google', {'id_token': 'good:901:n2@example.com'})
        ok(st == 403, 'migrated accounts count toward max_accounts: %s' % st)
        c = Client(base)
        st, r, _ = c.call('POST', '/auth/google', {'id_token': 'good:501:old@example.com'})
        ok(st == 200 and r['registered'] is True and uid_of(c) == u_reg, 'migrated account signs in to its old uid: %r' % (r,))
        st, r, _ = c.call('GET', '/api/profile')
        ok(st == 200 and r['profile']['nickname'] == '옛닉' and r['profile']['deck'] == 'navy', 'old folder carries on: %r' % (r,))
        st, r, _ = c.call('GET', '/auth/me')
        ok(r == {'email': 'old@example.com', 'registered': True}, 'me: %r' % (r,))
        d = Client(base)
        st, r, _ = d.call('POST', '/auth/google', {'id_token': 'good:502:half@example.com'})
        ok(st == 200 and r['registered'] is False and uid_of(d) == u_pend, 'half-registered account stays pending')
        with open(os.path.join(sd, 'accounts.json')) as f:
            acc = json.load(f)
        ok(acc['by_sub']['501'] == u_reg and acc['accounts'][u_reg]['sub'] == '501', 'sub linked')
    finally:
        stop(srv)


def main():
    log = sys.stderr = Tee(sys.__stderr__)
    root = tempfile.mkdtemp(prefix='t2_gw_')
    port = socket.socket(); port.bind(('127.0.0.1', 0)); p = port.getsockname()[1]; port.close()
    cfg = G.load_config(None)
    cfg.update(port=p, data_root=os.path.join(root, 'users'), run_root=os.path.join(root, 'run'),
               state_dir=os.path.join(root, 'gw'), google_client_ids=['web-client', 'android-client'],
               signup_mode='invite', allowed_emails=['me@gmail.com', 'friend@gmail.com'], secure_cookie=False, max_backends=1,
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
        st, img, h = a.call('GET', '/pub/portraits/01.png', raw=True)
        ok(st == 200 and img[:4] == b'\x89PNG' and h['Content-Type'] == 'image/png', 'sign-up pictures open before sign-in')
        for bad in ('/pub/../server/ui_server.py', '/pub/portraits/10.png', '/pub/lobby.js'):
            st, _, _ = a.call('GET', bad, raw=True)
            ok(st == 404, 'only listed pictures are public: %s %s' % (bad, st))

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
        ok(st == 200 and r['email'] == 'me@gmail.com' and r['registered'] is False, 'me: %r' % (r,))

        # signed in but not signed up yet: the game is closed until sign-up
        st, r, _ = a.call('GET', '/api/lobby')
        ok(st == 403 and r.get('signup') is True, 'unregistered API asks for sign-up: %s %r' % (st, r))
        st, _, h = a.call('GET', '/')
        ok(st == 302 and h['Location'] == '/login#signup', 'unregistered page goes to sign-up: %s' % st)
        for bad in ({'nickname': '', 'avatar': 0, 'agree': True}, {'nickname': 'x' * 17, 'avatar': 0, 'agree': True},
                    {'nickname': '나', 'avatar': 9, 'agree': True}, {'nickname': '나', 'avatar': True, 'agree': True},
                    {'nickname': '나', 'avatar': 0, 'agree': False}):
            st, r, _ = a.call('POST', '/auth/register', bad)
            ok(st == 400 and 'error' in r, 'sign-up refuses %r: %s %r' % (bad, st, r))
        st, r, _ = Client(base).call('POST', '/auth/register', {'nickname': '나', 'avatar': 0, 'agree': True})
        ok(st == 401, 'sign-up needs Google sign-in first: %s' % st)
        t0 = time.time()
        st, r, _ = a.call('POST', '/auth/register', {'nickname': ' 나 ', 'avatar': 2, 'agree': True})
        ok(st == 200 and r['nickname'] == '나', 'sign-up: %s %r' % (st, r))
        print('  sign-up (server start) %.1fs' % (time.time() - t0))
        st, r, _ = a.call('GET', '/auth/me')
        ok(r['registered'] is True and 'nickname' not in r, 'me after sign-up: %r' % (r,))
        st, r, _ = a.call('GET', '/api/profile')
        ok(r['profile'] == {'nickname': '나', 'avatar': 2, 'deck': 'jade'}, 'sign-up made my profile: %r' % (r,))

        st, r, _ = a.call('GET', '/api/lobby')
        ok(st == 200 and 'wallet' in r, 'lobby through the gateway: %s %r' % (st, str(r)[:200]))
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
        ok(st == 200 and r.get('registered') is False, 'friend signs in, not signed up yet: %r' % (r,))
        st, r, _ = b.call('POST', '/auth/register', {'nickname': '친구', 'avatar': 0, 'agree': True})
        ok(st == 200, 'friend signs up')
        st, r, _ = b.call('GET', '/api/profile')
        ok(st == 200 and r['profile'].get('nickname') == '친구', 'friend does not see my profile: %r' % (r,))
        st, r, _ = b.call('GET', '/api/lobby')
        ok(st == 200 and r['wallet']['balance'] == bal_a, 'friend has a fresh wallet of their own')
        users = sorted(os.listdir(cfg['data_root']))
        ok(len(users) == 2 and all(u.startswith('u_') and 'gmail' not in u for u in users), 'two private folders: %r' % users)
        ok(os.path.exists(os.path.join(cfg['data_root'], uid_a, 'profile.json')), 'my profile is in my folder')
        with open(os.path.join(cfg['data_root'], b.cookie.split('=', 1)[1].split('.')[0], 'profile.json')) as f:
            ok('나' not in f.read(), 'nothing written to the friend folder by me')

        # max_backends=1: my server was stopped to make room; my next request brings it back with my data
        ok(len([x for x in srv.backends.procs.values() if x['proc'].poll() is None]) == 1, 'one game server at a time')
        st, r, _ = a.call('GET', '/api/profile')
        ok(st == 200 and r['profile'].get('nickname') == '나', 'my data survives being stopped and restarted: %r' % (r,))

        # signing in again later remembers the sign-up
        st, r, _ = a.call('POST', '/auth/google', {'id_token': 'good:111:me@gmail.com'})
        ok(st == 200 and r.get('registered') is True, 'returning player skips sign-up: %r' % (r,))

        # idle stop
        srv.backends.stop_all()
        ok(not srv.backends.procs, 'game servers stop')

        st, r, _ = a.call('POST', '/auth/logout', {})
        st, _, _ = a.call('GET', '/api/lobby')
        ok(st == 401, 'after logout the API is refused: %s' % st)
        ok(sorted(r.keys()) == ['ok'], 'logout reply: %r' % (r,))
        st, r, _ = b.call('GET', '/auth/me')
        ok(st == 200 and sorted(r) == ['email', 'registered'], 'me has only email and registered: %r' % (r,))

        # a browser reuses one connection: logout's unread body must not spoil the next request ('{}GET')
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', p, timeout=10)
        for path in ('/auth/logout', '/auth/me', '/auth/google'):
            conn.request('POST', path, body=b'{}', headers={'Content-Type': 'application/json'})
            conn.getresponse().read()
            conn.request('GET', '/healthz')
            resp = conn.getresponse()
            ok(resp.status == 200 and json.loads(resp.read()) == {'ok': True},
               'next request on the same connection after %s is intact: %s' % (path, resp.status))
        conn.close()
    finally:
        stop(srv)
        shutil.rmtree(root, ignore_errors=True)
    tmp = tempfile.mkdtemp(prefix='t2_gw2_')
    try:
        open_suite(os.path.join(tmp, 'open'))
        migration_suite(os.path.join(tmp, 'mig'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    logged = ''.join(log.text)
    ok('[gw]' in logged and '@' not in logged and 'gmail' not in logged, 'access log never holds an e-mail address')
    print('verify_gateway OK (%d checks)' % checks)


if __name__ == '__main__':
    main()
