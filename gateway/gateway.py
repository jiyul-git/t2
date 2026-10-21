#!/usr/bin/env python3
"""T2 online gateway: Google sign-in in front of one game server per player.

    python3 gateway/gateway.py [--config gateway/gateway.json]

The game server (ui/server/ui_server.py) keeps one game in process memory, so instead of turning it
into a multi-user server, the gateway starts a separate copy for each signed-in player:

    phone / browser --HTTPS--> gateway (this file, public) --> 127.0.0.1:<port>  ui_server for player A
                                sign-in, session cookie        127.0.0.1:<port>  ui_server for player B
                                start / stop game servers

Each player gets  <data_root>/<uid>/  (wallet, profile, history; T2_DATA_DIR)  and  <run_root>/<uid>/
(the engine's run folder, where the live game state lives). Nothing is shared between players.

Sign-in: the client gets a Google ID token (web: Google Identity Services button on /login;
Android app: native Google sign-in) and posts it to /auth/google. The gateway checks it with Google
(signature via the tokeninfo endpoint, audience = our client IDs, verified e-mail), checks the e-mail
against the allow-list (only in signup_mode "invite"), and sets a signed session cookie. The first
sign-in of a Google account creates that player's account. Client-supplied user ids are never trusted.
Account data layout and privacy rules: docs/ACCOUNT_DATA.md.

Standard library only.
"""
import argparse
import hashlib
import hmac
import http.client
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
COOKIE = 't2s'
SESSION_DAYS = 30
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
               'transfer-encoding', 'upgrade', 'host', 'cookie', 'content-length'}

DEFAULTS = {
    'host': '127.0.0.1',          # put a TLS front (Caddy / Cloudflare Tunnel) in front for the public
    'port': 8080,
    'data_root': '~/t2_online/users',
    'run_root': '~/t2_online/run',
    'state_dir': '~/t2_online/gateway',
    'google_client_ids': [],      # OAuth client IDs (web + Android) whose tokens we accept
    'signup_mode': 'open',        # "open": any Google account may sign up; "invite": only allowed_emails
    'allowed_emails': [],         # used only in "invite" mode ([] = nobody)
    'max_accounts': 20,           # new sign-ups are refused beyond this many accounts
    'backup_dir': '~/t2_online/backups',   # used by admin.py backup
    'dev_login': False,           # POST /auth/dev {email}: local testing only, never on a public server
    'secure_cookie': True,        # set False only for plain-http local testing
    'max_backends': 4,            # game servers running at once; the least recently used is stopped
    'idle_seconds': 1800,         # stop a player's game server after this long without requests
    'busy_idle_seconds': 21600,   # ... but one with a tournament in progress is kept this long (6 h)
    'backend_env': {},            # extra environment for game servers
}


def load_config(path):
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            cfg.update(json.load(f))
    if cfg['signup_mode'] not in ('open', 'invite'):
        raise SystemExit('signup_mode는 "open" 또는 "invite"여야 합니다')
    for k in ('data_root', 'run_root', 'state_dir', 'backup_dir'):
        cfg[k] = os.path.abspath(os.path.expanduser(cfg[k]))
    cfg['allowed_emails'] = [e.strip().lower() for e in cfg['allowed_emails']]
    return cfg


# ---------------------------------------------------------------------------------------------- sign-in
class AuthError(Exception):
    pass


def google_tokeninfo(id_token):
    """Ask Google to check the ID token's signature and expiry; returns its claims."""
    url = 'https://oauth2.googleapis.com/tokeninfo?' + urllib.parse.urlencode({'id_token': id_token})
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:                      # 400 for a bad or expired token
        raise AuthError('Google 토큰 확인 실패') from e


def check_google_claims(claims, client_ids, now=None):
    now = time.time() if now is None else now
    if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise AuthError('발급자가 구글이 아닙니다')
    if claims.get('aud') not in client_ids:
        raise AuthError('이 앱용 토큰이 아닙니다')
    if str(claims.get('email_verified')).lower() != 'true':
        raise AuthError('확인되지 않은 이메일입니다')
    if float(claims.get('exp', 0)) < now:
        raise AuthError('만료된 토큰입니다')
    if not claims.get('sub') or not claims.get('email'):
        raise AuthError('토큰에 계정 정보가 없습니다')
    return {'sub': str(claims['sub']), 'email': str(claims['email']).lower(), 'name': claims.get('name') or ''}


def mkdir_private(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)


def delete_user_files(cfg, uid):
    for root in (cfg['data_root'], cfg['run_root']):
        shutil.rmtree(os.path.join(root, uid), ignore_errors=True)


class Accounts:
    """accounts.json (version 2): uid -> {sub, email, status, ...} plus by_sub (Google sub -> uid).

    The uid is random and only stored here, so losing or rotating session.key never orphans a wallet.
    The file is re-read when it changes on disk, so admin.py edits apply on the next request."""

    def __init__(self, state_dir):
        mkdir_private(state_dir)
        self.path = os.path.join(state_dir, 'accounts.json')
        self.legacy = os.path.join(state_dir, 'users.json')
        self.lock = threading.RLock()
        self._data, self._stamp = {'version': 2, 'accounts': {}, 'by_sub': {}}, None
        secret_path = os.path.join(state_dir, 'session.key')
        if not os.path.exists(secret_path):
            fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(secrets.token_hex(32))
        with open(secret_path) as f:
            self.secret = bytes.fromhex(f.read().strip())
        with self.lock:
            if not os.path.exists(self.path) and os.path.exists(self.legacy):
                self._migrate()

    def _migrate(self):
        """v1 users.json (uid -> record, no sub) -> v2. Accounts get their sub on their next sign-in."""
        try:
            with open(self.legacy, encoding='utf-8') as f:
                old = json.load(f)
        except (OSError, ValueError):
            old = {}
        accts = {}
        for uid, r in old.items():
            if not isinstance(r, dict):
                continue
            accts[uid] = {'sub': None, 'email': r.get('email', ''), 'status': 'active' if r.get('registered') else 'pending',
                          'created': r.get('created', int(time.time())), 'last_login': r.get('last_login'),
                          'agreed_at': r.get('registered') or None, 'terms': None}
        self._write({'version': 2, 'accounts': accts, 'by_sub': {}})
        os.replace(self.legacy, self.legacy + '.v1.bak')

    def _write(self, data):
        tmp = self.path + '.tmp'
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self._data, self._stamp = data, self._stat()

    def _stat(self):
        try:
            st = os.stat(self.path)
            return (st.st_mtime_ns, st.st_size, st.st_ino)
        except OSError:
            return None

    def _load(self):
        with self.lock:
            stamp = self._stat()
            if stamp != self._stamp:
                try:
                    with open(self.path, encoding='utf-8') as f:
                        d = json.load(f)
                    d.setdefault('accounts', {})
                    d.setdefault('by_sub', {})
                    self._data, self._stamp = d, stamp
                except (OSError, ValueError):
                    if stamp is None:
                        self._data, self._stamp = {'version': 2, 'accounts': {}, 'by_sub': {}}, None
            return self._data

    def _mutate(self, fn):
        with self.lock:
            d = self._load()
            res, changed = fn(d)          # fn returns (result, whether accounts.json changed)
            if changed:
                self._write(d)
            return res

    def legacy_uid(self, sub):
        return 'u_' + hmac.new(self.secret, ('google:' + sub).encode(), hashlib.sha256).hexdigest()[:20]

    def sign_in(self, ident, max_accounts):
        """-> (status, uid): 'ok' | 'disabled' | 'full'. Creates a pending account for a new Google sub."""
        sub, now = ident['sub'], int(time.time())

        def fn(d):
            uid = d['by_sub'].get(sub)
            if uid not in d['accounts']:
                uid = self.legacy_uid(sub)
                if uid in d['accounts'] and not d['accounts'][uid].get('sub'):
                    d['accounts'][uid]['sub'] = sub            # migrated v1 account: keep its old folder
                else:
                    if len(d['accounts']) >= max_accounts:
                        return ('full', None), False
                    uid = 'u_' + secrets.token_hex(10)
                    d['accounts'][uid] = {'sub': sub, 'email': '', 'status': 'pending', 'created': now,
                                          'last_login': None, 'agreed_at': None, 'terms': None}
                d['by_sub'][sub] = uid
            rec = d['accounts'][uid]
            if rec.get('status') == 'disabled':
                return ('disabled', uid), True
            rec.update(email=ident['email'], last_login=now)
            return ('ok', uid), True

        return self._mutate(fn)

    def get(self, uid):
        rec = self._load()['accounts'].get(uid)
        return dict(rec) if rec else None

    def all(self):
        return {u: dict(r) for u, r in self._load()['accounts'].items()}

    def find(self, target):
        """uid or e-mail -> uid (None if no match)."""
        accts = self._load()['accounts']
        if target in accts:
            return target
        t = target.strip().lower()
        return next((u for u, r in accts.items() if (r.get('email') or '').lower() == t), None)

    def register(self, uid, terms='2026-10'):
        """Pending -> active. False if the account is missing or not pending."""
        def fn(d):
            rec = d['accounts'].get(uid)
            if not rec or rec.get('status') != 'pending':
                return False, False
            rec.update(status='active', agreed_at=int(time.time()), terms=terms)
            return True, True
        return self._mutate(fn)

    def set_status(self, uid, status):
        def fn(d):
            if uid not in d['accounts']:
                return False, False
            d['accounts'][uid]['status'] = status
            return True, True
        return self._mutate(fn)

    def delete(self, uid):
        def fn(d):
            if d['accounts'].pop(uid, None) is None:
                return False, False
            for k in [k for k, v in d['by_sub'].items() if v == uid]:
                del d['by_sub'][k]
            return True, True
        return self._mutate(fn)

    # signed, stateless session cookie: "<uid>.<expiry>.<mac>"
    def make_session(self, uid, now=None):
        exp = int((time.time() if now is None else now) + SESSION_DAYS * 86400)
        msg = '%s.%d' % (uid, exp)
        return msg + '.' + hmac.new(self.secret, msg.encode(), hashlib.sha256).hexdigest()

    def read_session(self, value, now=None):
        """Valid signature and not expired -> uid (the account itself may be gone; callers check)."""
        try:
            uid, exp, mac = value.split('.')
            exp = int(exp)
        except (ValueError, AttributeError):
            return None
        good = hmac.new(self.secret, ('%s.%d' % (uid, exp)).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, good) or exp < (time.time() if now is None else now):
            return None
        return uid


# ------------------------------------------------------------------------------------- game servers

def default_nickname():
    """새 플레이어의 기본 닉네임: 'T-' + 8자리 숫자(봇 이름과 같은 꼴)."""
    return 'T-%08d' % secrets.randbelow(10 ** 8)

class Backends:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.procs = {}       # uid -> {'proc', 'port', 'last'}
        self.starting = {}    # uid -> Event
        threading.Thread(target=self._reaper, daemon=True).start()

    def _free_port(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    @staticmethod
    def _kill_stale(run):
        """Stop a game server still running in this run folder from an earlier gateway.

        Backends start in their own session, so when the gateway itself is killed (Android
        SIGKILL) they keep running. A second server in the same folder then saves the same
        state file and both break. Only a process whose command is ui_server.py and whose
        working directory is this run folder is touched.
        """
        pidfile = os.path.join(run, 'server.pid')
        try:
            pid = int(open(pidfile).read().strip())
        except (OSError, ValueError):
            return
        try:
            cmd = open('/proc/%d/cmdline' % pid, 'rb').read().split(b'\0')
            cwd = os.path.realpath('/proc/%d/cwd' % pid)
        except OSError:
            return                                   # not running (or not ours to inspect)
        if b'ui_server.py' not in cmd or cwd != os.path.realpath(run):
            return
        import signal
        os.kill(pid, signal.SIGTERM)                 # ui_server saves its state on the way out
        for _ in range(200):
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.1)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def _spawn(self, uid):
        run = os.path.join(self.cfg['run_root'], uid)
        data = os.path.join(self.cfg['data_root'], uid)
        mkdir_private(data)
        mkdir_private(run)
        # copies the engine code into the player's run folder; the game state there is left alone
        subprocess.run(['sh', os.path.join(REPO, 'ui', 'tools', 'setup_run_dir.sh'), run],
                       check=True, stdout=subprocess.DEVNULL)
        port = self._free_port()
        env = dict(os.environ, IP='127.0.0.1', T2_DATA_DIR=data, T2_TELEMETRY='0',
                   **{k: str(v) for k, v in self.cfg['backend_env'].items()})
        self._kill_stale(run)
        log = open(os.path.join(run, 'server.log'), 'ab')
        proc = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)], cwd=run, env=env,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        with open(os.path.join(run, 'server.pid'), 'w') as f:
            f.write(str(proc.pid))
        for _ in range(300):
            if proc.poll() is not None:
                raise RuntimeError('게임 서버가 시작하지 못했습니다 (로그: %s)' % os.path.join(run, 'server.log'))
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                    return proc, port
            except OSError:
                time.sleep(0.1)
        proc.kill()
        raise RuntimeError('게임 서버 응답 없음')

    def port_for(self, uid):
        while True:
            with self.lock:
                b = self.procs.get(uid)
                if b and b['proc'].poll() is None:
                    b['last'] = time.time()
                    return b['port']
                ev = self.starting.get(uid)
                if ev is None:
                    ev = self.starting[uid] = threading.Event()
                    mine = True
                else:
                    mine = False
            if not mine:
                ev.wait(60)
                continue
            try:
                self._make_room(exclude=uid)
                proc, port = self._spawn(uid)
                with self.lock:
                    self.procs[uid] = {'proc': proc, 'port': port, 'last': time.time()}
                return port
            finally:
                with self.lock:
                    self.starting.pop(uid, None)
                ev.set()

    def _make_room(self, exclude):
        with self.lock:
            live = [(b['last'], u) for u, b in self.procs.items() if u != exclude and b['proc'].poll() is None]
            live.sort()
            victims = [u for _, u in live[:max(0, len(live) - self.cfg['max_backends'] + 1)]]
        for u in victims:
            self.stop(u)

    def stop(self, uid):
        with self.lock:
            b = self.procs.pop(uid, None)
        if b and b['proc'].poll() is None:
            b['proc'].terminate()          # ui_server saves its state; the next start resumes it
            try:
                b['proc'].wait(20)
            except subprocess.TimeoutExpired:
                b['proc'].kill()

    def stop_all(self):
        for uid in list(self.procs):
            self.stop(uid)

    def _busy(self, port):
        """True while the player's game server has a tournament in progress (lobby payload `current`)."""
        try:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            try:
                conn.request('GET', '/api/lobby', headers={'X-T2-Client-Mode': 'play'})
                cur = (json.loads(conn.getresponse().read() or b'{}') or {}).get('current')
            finally:
                conn.close()
            return isinstance(cur, dict) and not cur.get('error') and not cur.get('busted')
        except Exception:
            return False

    def reap_once(self, now=None):
        """Stop game servers that died or sat idle. Someone in a tournament is not idle: that server stays
        (idle_seconds does not apply) until busy_idle_seconds without any request, so a tournament running
        while the app is in the background is not cut off."""
        now = time.time() if now is None else now
        cutoff = now - self.cfg['idle_seconds']
        busy_cutoff = now - self.cfg.get('busy_idle_seconds', 21600)
        with self.lock:
            cand = [(u, b['port'], b['last'], b['proc'].poll() is not None) for u, b in self.procs.items()
                    if b['last'] < cutoff or b['proc'].poll() is not None]
        for u, port, last, dead in cand:
            if not dead and last >= busy_cutoff and self._busy(port):
                continue
            self.stop(u)

    def _reaper(self):
        while True:
            time.sleep(30)
            self.reap_once()


# ------------------------------------------------------------------------------------------ http
def make_handler(cfg, accounts, backends, verify_token):
    login_page = open(os.path.join(HERE, 'login.html'), encoding='utf-8').read()
    login_page = login_page.replace('__CLIENT_ID__', json.dumps((cfg['google_client_ids'] or [''])[0]))
    login_page = login_page.replace('__DEV_LOGIN__', 'true' if cfg['dev_login'] else 'false')
    fails = {}   # ip -> [times] of failed sign-ins, to slow down guessing

    class H(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            sys.stderr.write('[gw] %s %s\n' % (self.address_string(), fmt % args))

        # ---- helpers
        def _json(self, code, obj, cookie=None):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            if cookie is None and getattr(self, 'stale', False):
                cookie = self._cookie('', 0)
            if cookie is not None:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(body)

        def _cookie(self, value, max_age):
            parts = ['%s=%s' % (COOKIE, value), 'Path=/', 'HttpOnly', 'SameSite=Lax', 'Max-Age=%d' % max_age]
            if cfg['secure_cookie']:
                parts.append('Secure')
            return '; '.join(parts)

        def _uid(self):
            """Signed-in uid, or None. A valid cookie whose account is gone or disabled stops that
            player's game server and is cleared (self.stale)."""
            for part in (self.headers.get('Cookie') or '').split(';'):
                k, _, v = part.strip().partition('=')
                if k == COOKIE:
                    uid = accounts.read_session(v)
                    if uid is None:
                        return None
                    rec = accounts.get(uid)
                    if not rec or rec.get('status') == 'disabled':
                        self.stale = True
                        backends.stop(uid)
                        return None
                    return uid
            return None

        def _body(self, limit=1 << 20):
            n = int(self.headers.get('Content-Length') or 0)
            if n > limit:
                raise ValueError('too large')
            self.body_read = True
            return self.rfile.read(n) if n else b''

        def _too_many_fails(self):
            ip = self.client_address[0]
            now = time.time()
            recent = [t for t in fails.get(ip, []) if now - t < 600]
            fails[ip] = recent
            return len(recent) >= 10

        def _signed_in(self, ident):
            if cfg['signup_mode'] == 'invite' and ident['email'] not in cfg['allowed_emails']:
                fails.setdefault(self.client_address[0], []).append(time.time())
                return self._json(403, {'error': '초대되지 않은 계정입니다 (%s)' % ident['email']})
            res, uid = accounts.sign_in(ident, cfg['max_accounts'])
            if res == 'disabled':
                return self._json(403, {'error': '이용이 중지된 계정입니다'})
            if res == 'full':
                return self._json(403, {'error': '정원이 찼습니다'})
            rec = accounts.get(uid)
            return self._json(200, {'ok': True, 'email': ident['email'], 'name': ident['name'],
                                    'registered': rec['status'] == 'active'},
                              cookie=self._cookie(accounts.make_session(uid), SESSION_DAYS * 86400))

        # ---- routes
        def do_GET(self):
            self._handle('GET')

        def do_POST(self):
            self._handle('POST')

        def do_HEAD(self):
            self._handle('HEAD')

        def _handle(self, method):
            self.body_read = False
            self._route(method)
            # a request body we answered without reading would be taken as the start of the next
            # request on this keep-alive connection (e.g. '{}GET'): read it off, or close if it is huge
            n = int(self.headers.get('Content-Length') or 0)
            if n and not self.body_read:
                if n <= 1 << 20:
                    self.rfile.read(n)
                else:
                    self.close_connection = True

        def _route(self, method):
            self.stale = False
            path = urllib.parse.urlsplit(self.path).path
            if path == '/login' and method in ('GET', 'HEAD'):
                body = login_page.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                if method == 'GET':
                    self.wfile.write(body)
                return
            if path.startswith('/pub/') and method in ('GET', 'HEAD'):
                return self._static(path[len('/pub/'):], method)
            if path == '/healthz':
                return self._json(200, {'ok': True})
            if path.startswith('/auth/'):
                return self._auth(method, path)
            uid = self._uid()
            if not uid:
                if method == 'GET' and not path.startswith('/api/'):
                    self.send_response(302)
                    self.send_header('Location', '/login')
                    if self.stale:
                        self.send_header('Set-Cookie', self._cookie('', 0))
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                return self._json(401, {'error': '로그인이 필요합니다'})
            if (accounts.get(uid) or {}).get('status') != 'active':
                if method == 'GET' and not path.startswith('/api/'):
                    self.send_response(302)
                    self.send_header('Location', '/login#signup')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                return self._json(403, {'error': '회원가입을 마쳐 주세요', 'signup': True})
            self._proxy(method, uid)

        def _static(self, rel, method):
            # only these public pictures are served before sign-in
            allowed = {'portraits/%02d.png' % i: 'image/png' for i in range(1, 10)}
            allowed['lobby_hero_night.webp'] = 'image/webp'
            if rel not in allowed:
                return self._json(404, {'error': 'not found'})
            src = os.path.join(REPO, 'ui', 'web', 'assets', 'portraits' if rel.startswith('portraits/') else 't2-airport',
                               rel.split('/')[-1])
            with open(src, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', allowed[rel])
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            if method == 'GET':
                self.wfile.write(data)

        def _auth(self, method, path):
            if method != 'POST' and path != '/auth/me':
                return self._json(405, {'error': 'POST only'})
            if path == '/auth/me':
                uid = self._uid()
                rec = accounts.get(uid) if uid else None
                return self._json(200 if rec else 401, {'email': rec['email'], 'registered': rec['status'] == 'active'}
                                  if rec else {'error': '로그인이 필요합니다'})
            if path == '/auth/logout':
                return self._json(200, {'ok': True}, cookie=self._cookie('', 0))
            if self._too_many_fails():
                return self._json(429, {'error': '잠시 후 다시 시도해 주세요'})
            try:
                body = json.loads(self._body() or b'{}')
            except ValueError:
                return self._json(400, {'error': 'JSON이 필요합니다'})
            if path == '/auth/google':
                token = body.get('id_token')
                if not isinstance(token, str) or not 20 < len(token) < 8192:
                    return self._json(400, {'error': 'id_token이 없습니다'})
                if not cfg['google_client_ids']:
                    return self._json(503, {'error': '구글 로그인이 설정되지 않았습니다'})
                try:
                    ident = check_google_claims(verify_token(token), cfg['google_client_ids'])
                except AuthError as e:
                    fails.setdefault(self.client_address[0], []).append(time.time())
                    return self._json(401, {'error': str(e)})
                return self._signed_in(ident)
            if path == '/auth/register':
                uid = self._uid()
                if not uid:
                    return self._json(401, {'error': '로그인이 필요합니다'})
                if accounts.get(uid)['status'] != 'pending':
                    return self._json(409, {'error': '이미 가입한 계정입니다'})
                # 가입 때는 닉네임을 묻지 않는다(사용자 결정 2026-10-20). 'T-' + 8자리 숫자를
                # 붙여 주고, 바꾸고 싶으면 나중에 설정에서 바꾼다. 예전 앱이 보낸 닉네임은 그대로 쓴다.
                nick = str(body.get('nickname') or '').strip() or default_nickname()
                av = body.get('avatar')
                if not 1 <= len(nick) <= 16:
                    return self._json(400, {'error': '닉네임은 1~16자로 정해 주세요'})
                if not (isinstance(av, int) and not isinstance(av, bool) and 0 <= av < 9):
                    return self._json(400, {'error': '캐릭터를 골라 주세요'})
                if body.get('agree') is not True:
                    return self._json(400, {'error': '이용 안내에 동의해 주세요'})
                # the game server keeps the profile; create the player's wallet and profile there
                try:
                    st, r = self._backend_json(uid, 'POST', '/api/profile',
                                               {'profile': {'nickname': nick, 'avatar': av, 'deck': 'jade'}})
                except Exception as e:
                    return self._json(503, {'error': str(e)})
                if st != 200:
                    return self._json(st, r)
                accounts.register(uid)
                return self._json(200, {'ok': True, 'nickname': nick})
            if path == '/auth/delete':
                uid = self._uid()
                if not uid:
                    return self._json(401, {'error': '로그인이 필요합니다'})
                if body.get('confirm') != '삭제':
                    return self._json(400, {'error': '확인 문구로 "삭제"를 입력해 주세요'})
                accounts.delete(uid)          # first, so no request can start the game server again
                backends.stop(uid)
                delete_user_files(cfg, uid)
                return self._json(200, {'ok': True}, cookie=self._cookie('', 0))
            if path == '/auth/dev' and cfg['dev_login']:
                email = str(body.get('email') or '').strip().lower()
                return self._signed_in({'sub': 'dev:' + email, 'email': email, 'name': email.split('@')[0]})
            return self._json(404, {'error': 'not found'})

        def _backend_json(self, uid, method, path, obj):
            port = backends.port_for(uid)
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=60)
            try:
                conn.request(method, path, body=json.dumps(obj).encode(),
                             headers={'Content-Type': 'application/json', 'X-T2-Client-Mode': 'play'})
                resp = conn.getresponse()
                return resp.status, json.loads(resp.read() or b'{}')
            finally:
                conn.close()

        def _proxy(self, method, uid):
            try:
                port = backends.port_for(uid)
            except Exception as e:
                return self._json(503, {'error': str(e)})
            try:
                body = self._body(limit=8 << 20)
            except ValueError:
                return self._json(413, {'error': '요청이 너무 큽니다'})
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=600)
            try:
                conn.request(method, self.path, body=body or None, headers=headers)
                resp = conn.getresponse()
            except OSError as e:
                conn.close()
                return self._json(502, {'error': '게임 서버 연결 실패: %s' % e})
            try:
                self.send_response(resp.status, resp.reason)
                length = resp.getheader('Content-Length')
                for k, v in resp.getheaders():
                    if k.lower() not in HOP_HEADERS or k.lower() == 'content-length':
                        self.send_header(k, v)
                if length is None:
                    self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()
                if method == 'HEAD':
                    return
                # the game streams moves as they happen (ndjson): pass each piece on at once
                while True:
                    chunk = resp.read1(65536)
                    if not chunk:
                        break
                    if length is None:
                        self.wfile.write(b'%x\r\n%s\r\n' % (len(chunk), chunk))
                    else:
                        self.wfile.write(chunk)
                    self.wfile.flush()
                if length is None:
                    self.wfile.write(b'0\r\n\r\n')
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                conn.close()

    return H


def serve(cfg, verify_token=google_tokeninfo):
    for k in ('data_root', 'run_root'):
        mkdir_private(cfg[k])
    accounts = Accounts(cfg['state_dir'])
    backends = Backends(cfg)
    srv = ThreadingHTTPServer((cfg['host'], cfg['port']), make_handler(cfg, accounts, backends, verify_token))
    srv.daemon_threads = True
    srv.backends = backends
    return srv


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--config', default=os.path.join(HERE, 'gateway.json'))
    cfg = load_config(ap.parse_args().config)
    if cfg['dev_login'] and cfg['host'] not in ('127.0.0.1', 'localhost'):
        sys.exit('dev_login은 127.0.0.1에서만 켤 수 있습니다')
    srv = serve(cfg)
    who = ('invite only: %s' % (', '.join(cfg['allowed_emails']) or 'nobody') if cfg['signup_mode'] == 'invite'
           else 'open signup')
    print('T2 gateway on http://%s:%d  (%s, max %d accounts)' % (cfg['host'], cfg['port'], who, cfg['max_accounts']))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.backends.stop_all()


if __name__ == '__main__':
    main()
