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
against the allow-list, and sets a signed session cookie. The first sign-in of an allowed Google
account creates that player's account. Client-supplied user ids are never trusted.

Standard library only.
"""
import argparse
import hashlib
import hmac
import http.client
import json
import os
import secrets
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
    'allowed_emails': [],         # only these Google accounts may sign in ([] = nobody)
    'dev_login': False,           # POST /auth/dev {email}: local testing only, never on a public server
    'secure_cookie': True,        # set False only for plain-http local testing
    'max_backends': 4,            # game servers running at once; the least recently used is stopped
    'idle_seconds': 1800,         # stop a player's game server after this long without requests
    'backend_env': {},            # extra environment for game servers
}


def load_config(path):
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            cfg.update(json.load(f))
    for k in ('data_root', 'run_root', 'state_dir'):
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


class Accounts:
    """Google subject -> our user id. The user id is derived, so it is stable and not guessable."""

    def __init__(self, state_dir):
        os.makedirs(state_dir, exist_ok=True)
        self.path = os.path.join(state_dir, 'users.json')
        self.lock = threading.Lock()
        secret_path = os.path.join(state_dir, 'session.key')
        if not os.path.exists(secret_path):
            fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(secrets.token_hex(32))
        with open(secret_path) as f:
            self.secret = bytes.fromhex(f.read().strip())

    def _load(self):
        try:
            with open(self.path, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def upsert(self, ident):
        uid = 'u_' + hmac.new(self.secret, ('google:' + ident['sub']).encode(), hashlib.sha256).hexdigest()[:20]
        with self.lock:
            users = self._load()
            rec = users.get(uid) or {'created': int(time.time())}
            rec.update(email=ident['email'], name=ident['name'], last_login=int(time.time()))
            users[uid] = rec
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        return uid

    def get(self, uid):
        return self._load().get(uid)

    # signed, stateless session cookie: "<uid>.<expiry>.<mac>"
    def make_session(self, uid, now=None):
        exp = int((time.time() if now is None else now) + SESSION_DAYS * 86400)
        msg = '%s.%d' % (uid, exp)
        return msg + '.' + hmac.new(self.secret, msg.encode(), hashlib.sha256).hexdigest()

    def read_session(self, value, now=None):
        try:
            uid, exp, mac = value.split('.')
            exp = int(exp)
        except (ValueError, AttributeError):
            return None
        good = hmac.new(self.secret, ('%s.%d' % (uid, exp)).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, good) or exp < (time.time() if now is None else now):
            return None
        return uid if self.get(uid) else None


# ------------------------------------------------------------------------------------- game servers
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

    def _spawn(self, uid):
        run = os.path.join(self.cfg['run_root'], uid)
        data = os.path.join(self.cfg['data_root'], uid)
        os.makedirs(data, exist_ok=True)
        # copies the engine code into the player's run folder; the game state there is left alone
        subprocess.run(['sh', os.path.join(REPO, 'ui', 'tools', 'setup_run_dir.sh'), run],
                       check=True, stdout=subprocess.DEVNULL)
        port = self._free_port()
        env = dict(os.environ, IP='127.0.0.1', T2_DATA_DIR=data, T2_TELEMETRY='0',
                   **{k: str(v) for k, v in self.cfg['backend_env'].items()})
        log = open(os.path.join(run, 'server.log'), 'ab')
        proc = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)], cwd=run, env=env,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
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

    def _reaper(self):
        while True:
            time.sleep(30)
            cutoff = time.time() - self.cfg['idle_seconds']
            with self.lock:
                idle = [u for u, b in self.procs.items() if b['last'] < cutoff or b['proc'].poll() is not None]
            for u in idle:
                self.stop(u)


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
            for part in (self.headers.get('Cookie') or '').split(';'):
                k, _, v = part.strip().partition('=')
                if k == COOKIE:
                    return accounts.read_session(v)
            return None

        def _body(self, limit=1 << 20):
            n = int(self.headers.get('Content-Length') or 0)
            if n > limit:
                raise ValueError('too large')
            return self.rfile.read(n) if n else b''

        def _too_many_fails(self):
            ip = self.client_address[0]
            now = time.time()
            recent = [t for t in fails.get(ip, []) if now - t < 600]
            fails[ip] = recent
            return len(recent) >= 10

        def _signed_in(self, ident):
            if ident['email'] not in cfg['allowed_emails']:
                fails.setdefault(self.client_address[0], []).append(time.time())
                return self._json(403, {'error': '초대되지 않은 계정입니다 (%s)' % ident['email']})
            uid = accounts.upsert(ident)
            return self._json(200, {'ok': True, 'email': ident['email'], 'name': ident['name']},
                              cookie=self._cookie(accounts.make_session(uid), SESSION_DAYS * 86400))

        # ---- routes
        def do_GET(self):
            self._route('GET')

        def do_POST(self):
            self._route('POST')

        def do_HEAD(self):
            self._route('HEAD')

        def _route(self, method):
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
            if path == '/healthz':
                return self._json(200, {'ok': True})
            if path.startswith('/auth/'):
                return self._auth(method, path)
            uid = self._uid()
            if not uid:
                if method == 'GET' and not path.startswith('/api/'):
                    self.send_response(302)
                    self.send_header('Location', '/login')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                return self._json(401, {'error': '로그인이 필요합니다'})
            self._proxy(method, uid)

        def _auth(self, method, path):
            if method != 'POST' and path != '/auth/me':
                return self._json(405, {'error': 'POST only'})
            if path == '/auth/me':
                uid = self._uid()
                rec = accounts.get(uid) if uid else None
                return self._json(200 if rec else 401, {'email': rec['email'], 'name': rec['name']} if rec
                                  else {'error': '로그인이 필요합니다'})
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
            if path == '/auth/dev' and cfg['dev_login']:
                email = str(body.get('email') or '').strip().lower()
                return self._signed_in({'sub': 'dev:' + email, 'email': email, 'name': email.split('@')[0]})
            return self._json(404, {'error': 'not found'})

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
    print('T2 gateway on http://%s:%d  (players: %s)' % (cfg['host'], cfg['port'], ', '.join(cfg['allowed_emails']) or 'none'))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.backends.stop_all()


if __name__ == '__main__':
    main()
