#!/usr/bin/env python3
"""그래픽 UI용 HTTP 래퍼. 판단 로직은 건드리지 않고 live2.step() 만 호출한다.

  python ui_server.py [--port 8765]

반드시 엔진을 **별도 폴더에 복사**해서 그 폴더에서 실행한다.
live2 는 아카이브·리딩 장부를 모듈 폴더에 쓰고, T2_LIVE_STATE 를 쓰면 경로와
무관하게 접미사가 '_alt' 하나라서 cli.py 세션과 같은 폴더면 파일을 공유한다.
그래서 이 폴더에 UI_SERVER_DIR 표시 파일이 없으면 시작하지 않는다.

엔드포인트
  GET  /                      web/index.html (없으면 404)
  GET  /<경로>                web/ 아래 정적 파일. 같은 출처라 CORS 가 필요 없다.
  GET  /api/state             마지막 응답 (없으면 현재 상태를 재생해서 만든다)
  POST /api/new   {entries?, seed?, fmt?, start_stack?}
  GET  /api/stats             정산 지연 카운터 (attempt/hit/mismatch/fallback…)
  GET  /api/memos             플레이어 전용 봇 메모 조회
  POST /api/memo  {pid, memo}  플레이어 전용 봇 메모 저장
  POST /api/step  {action, amount, token}
       action: fold/check/call/bet/raise/allin, 또는 null(다음 핸드 딜)
       amount: 이번 스트리트 총 투입 목표(raise-to)
       token : 직전 응답의 token. 다르면 409 — 재전송으로 액션이 두 번 들어가는 것을 막는다.
"""
import hmac, secrets, json, mimetypes, os, posixpath, sys, threading, time, traceback, urllib.parse, socket
from concurrent.futures import ProcessPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler

D = os.path.dirname(os.path.abspath(__file__))
if D not in sys.path:
    sys.path.insert(0, D)
if not os.path.exists(os.path.join(D, 'UI_SERVER_DIR')):
    sys.exit('중단: 이 폴더에 UI_SERVER_DIR 파일이 없습니다. 엔진을 별도 폴더에 복사한 뒤 '
             '그 폴더에 빈 UI_SERVER_DIR 파일을 만들고 실행하세요.')

import ui_view
sys.modules['view'] = ui_view          # live2 가 import 하기 전에 주입
import live2 as L

LOCK = threading.Lock()
_last = None
ACTIONS = {'fold', 'check', 'call', 'bet', 'raise', 'allin'}

PLAY_KEY_FILE = os.path.join(D, '.play_key')

def _play_key():
    key = os.environ.get('T2_PLAY_KEY')
    if key:
        return key.strip()

    try:
        with open(PLAY_KEY_FILE, encoding='utf-8') as fp:
            key = fp.read().strip()
        if key:
            return key
    except OSError:
        pass

    key = secrets.token_urlsafe(24)

    with open(PLAY_KEY_FILE, 'w', encoding='utf-8') as fp:
        fp.write(key)

    try:
        os.chmod(PLAY_KEY_FILE, 0o600)
    except OSError:
        pass

    return key

PLAY_KEY = _play_key()


# ---------- 다른 테이블 정산을 결과 반환 뒤로 미룬다 ----------
# 핸드 종료 요청 시간의 75% 가 live2.finish 안의 step_others 다(실측).
# 히어로 결과를 먼저 돌려주고, 사용자가 결과 화면을 보는 동안 워커가 계산한다.
# 다음 요청에서 join 해 그 결과를 live2 에 넘긴다. 못 받았으면 live2 가
# 딜 직전에 직접 돌린다 — 그때가 지금과 같은 속도이고, 더 느려지지 않는다.
#
# **워커는 상태 파일을 쓰지 않는다.** compute_others 는 필드 덤프를 받아
# 필드 덤프를 돌려줄 뿐이고, 파일 쓰기는 전부 이 락 안의 메인 스레드가 한다.
#
# 스레드가 아니라 프로세스인 이유
#   1) GIL — 스레드면 히어로 테이블 봇 판단과 CPU 를 다툰다
#   2) live2._load_field 가 프로필 dict 를 덤프와 공유한다. 프로세스면
#      pickle 왕복이 자동으로 깊은 복사가 된다
DEFER = os.environ.get('T2_UI_DEFER', '1') != '0'
POOL = None
PENDING = {'future': None}
COUNT = {'attempt': 0, 'hit': 0, 'mismatch': 0, 'fallback': 0,
         'worker_exception': 0, 'worker_join': 0, 'pool_unavailable': 0,
         # 워커가 아직 안 끝나서 실제로 기다린 시간. 최악의 경우의 비용이다.
         'worker_wait_ms': 0, 'worker_wait_max_ms': 0}


def _count_resume():
    """live2.resume_others 의 판정을 센다. 엔진은 고치지 않는다."""
    _orig = L.resume_others
    def wrapped(st, others=None):
        how = _orig(st, others)
        if how:
            COUNT[how] = COUNT.get(how, 0) + 1
        return how
    L.resume_others = wrapped


_count_resume()          # 정의 직후에 건다. import 지점에서는 아직 없다.


def _pool():
    global POOL
    if not DEFER:
        return None
    if POOL is None:
        try:
            POOL = ProcessPoolExecutor(max_workers=1)
        except Exception:
            COUNT['pool_unavailable'] += 1
            return None
    return POOL


def _take_others():
    """직전에 던져둔 워커 결과를 회수한다. 아직이면 여기서 기다린다."""
    fut = PENDING.pop('future', None)
    PENDING['future'] = None
    if fut is None:
        return None
    COUNT['worker_join'] += 1
    _t = time.time()
    try:
        r = fut.result()
        _ms = int((time.time() - _t) * 1000)
        COUNT['worker_wait_ms'] += _ms
        COUNT['worker_wait_max_ms'] = max(COUNT['worker_wait_max_ms'], _ms)
        return r
    except Exception:
        COUNT['worker_exception'] += 1
        traceback.print_exc()
        return None


def _kick_worker():
    """상태에 밀린 진행이 남아 있으면 워커에 던진다."""
    if not DEFER:
        return
    try:
        st = L.load()
    except Exception:
        return
    if not st.get('others_pending'):
        return
    COUNT['attempt'] += 1
    p = _pool()
    if p is None:
        return
    try:
        PENDING['future'] = p.submit(L.compute_others, st['field'])
    except Exception:
        COUNT['worker_exception'] += 1
        PENDING['future'] = None


def _step(action=None, amount=0):
    """live2.step 호출을 한 곳으로 모은다. 회수 → 진행 → 던지기."""
    others = _take_others()
    kw = {'defer_others': True, 'others': others} if DEFER else {}
    r = L.step(action, amount, **kw) if action is not None else L.step(**kw)
    _kick_worker()
    return r

WEB = os.path.join(D, 'web')          # setup_run_dir.sh 가 ui/web 을 여기로 복사한다
# 확장자별 타입. mimetypes 에 없거나 OS 마다 다른 것만 직접 못박는다.
MIME = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
        '.webmanifest': 'application/manifest+json; charset=utf-8',
        '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon'}


def _resolve(path):
    """URL 경로를 web/ 아래 실제 파일로. 밖으로 나가면 None."""
    rel = posixpath.normpath(urllib.parse.unquote(path))
    if rel in ('/', '', '.'):
        rel = '/index.html'
    rel = rel.lstrip('/')
    full = os.path.realpath(os.path.join(WEB, rel))
    root = os.path.realpath(WEB)
    if full != root and not full.startswith(root + os.sep):
        return None                    # ../ 로 폴더를 빠져나가려는 요청
    return full if os.path.isfile(full) else None



def _public_history():
    """현재 토너먼트의 완료 핸드를 UI용으로 안전하게 반환한다.

    중요:
    - hero 홀카드는 항상 허용
    - 상대 카드는 실제 shown_hole 만 허용
    - archive 의 top-level/result hole 전체는 절대 반환하지 않는다
    """
    fn = os.path.join(D, 'hand_archive2.jsonl')

    if not os.path.exists(fn):
        return []

    out = []

    with open(fn, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                h = json.loads(line)
            except Exception:
                # 쓰는 순간의 마지막 불완전 행 등은 건너뛴다.
                continue

            r = h.get('result') or {}
            hand_no = h.get('hand_no')

            if hand_no is None or not isinstance(r, dict):
                continue

            hero = h.get('hero')

            # 실제 공개된 카드만 상대 카드로 전달한다.
            raw_shown = r.get('shown_hole') or {}
            shown = {}

            if isinstance(raw_shown, dict):
                for seat, cards in raw_shown.items():
                    if isinstance(cards, (list, tuple)):
                        shown[str(seat)] = list(cards)

            # hero_hole 이 결과에 없을 때만 내부 hole 에서
            # 'hero 자신의 카드만' 복구한다.
            hero_hole = r.get('hero_hole') or []

            if not hero_hole and hero is not None:
                raw_hole = h.get('hole') or {}

                if isinstance(raw_hole, dict):
                    hero_hole = (
                        raw_hole.get(str(hero))
                        or raw_hole.get(hero)
                        or []
                    )

            out.append({
                'type': 'result',
                'hand_no': hand_no,
                'hash': r.get('hash') or h.get('hash'),

                'hero_seat': hero,
                'hero_hole': list(hero_hole or []),

                'board': r.get('board') or h.get('board') or [],
                'pot': r.get('pot') or 0,
                'pots': r.get('pots') or [],

                'how': r.get('how'),
                'showdown': bool(r.get('showdown')),
                'allin_show': bool(r.get('allin_show')),

                'shown': shown,
                'show_order': r.get('show_order') or [],
                'mucked': r.get('mucked') or [],

                'winners': r.get('winners') or [],
                'main_winners': r.get('main_winners') or [],
                'best_five': r.get('best_five') or {},

                'pos': r.get('pos') or h.get('pos') or {},
                'stacks': r.get('stacks') or {},

                # UI 상세 기록에서 사용하는 필드
                'log': h.get('full_log') or [],
                'notes': h.get('notes') or []
            })

    def hand_key(x):
        try:
            return int(x.get('hand_no'))
        except Exception:
            return -1

    out.sort(key=hand_key, reverse=True)
    return out

def _hero_memos():
    """현재 대회의 사용자 봇 메모. 공개 관전 API에는 절대 섞지 않는다."""
    if not os.path.exists(L.ST):
        return {}

    st = L.load()
    raw = st.get('hero_memos') or {}
    out = {}

    if isinstance(raw, dict):
        for pid, memo in raw.items():
            txt = str(memo or '').strip()
            if txt:
                out[str(pid)] = txt

    return out


def _save_hero_memo(pid, memo):
    """pid 메모를 상태 파일에 저장하고, 아직 쓰기 전인 핸드 기록에도 반영한다."""
    if not os.path.exists(L.ST):
        raise RuntimeError('진행 중인 게임 없음')

    st = L.load()
    players = ((st.get('field') or {}).get('players') or {})
    key = str(pid)

    if key not in players:
        raise ValueError('현재 대회에 없는 플레이어 pid: %s' % key)

    memos = dict(st.get('hero_memos') or {})

    if memo:
        memos[key] = memo
    else:
        memos.pop(key, None)

    st['hero_memos'] = memos

    # 핸드 종료 직후 worker 정산을 기다리는 동안 메모를 고쳤다면,
    # pending_archive도 같은 값으로 맞춰야 방금 끝난 핸드에 최신 메모가 남는다.
    rec = st.get('pending_archive')
    if isinstance(rec, dict):
        seated = {
            str(v)
            for v in (rec.get('seat_pid') or {}).values()
        }

        if key in seated:
            hm = dict(rec.get('hero_memos') or {})
            if memo:
                hm[key] = memo
            else:
                hm.pop(key, None)
            rec['hero_memos'] = hm

    L.save(st)
    return dict(memos)


def _token():
    try:
        st = L.load()
    except Exception:
        return None
    return '%s:%d' % (st.get('hand_seed'), len(st.get('actions') or []))


def _wrap(r):
    """step()/finish() 반환값 중 UI에 필요한 값만 내보낸다."""
    out = {
        'done': bool(r.get('done')),
        'view': r.get('view')
    }

    if r.get('opening_view') is not None:
        out['opening_view'] = r.get('opening_view')

    if r.get('done'):
        out['busted'] = bool(r.get('busted'))
        out['rank'] = r.get('rank')
        out['bust_pending'] = bool(
            r.get('bust_pending')
        )

        try:
            fd = L.load().get('field') or {}

            out['remaining'] = sum(
                1
                for p in (fd.get('players') or {}).values()
                if (p.get('stack') or 0) > 0
            )

            out['entries'] = len(
                fd.get('players') or {}
            )

        except Exception:
            pass

    if r.get('game_over'):
        out['game_over'] = True
        out['won'] = bool(r.get('won'))
        out['busted'] = bool(r.get('busted'))
        out['rank'] = r.get('rank')

        if r.get('remaining') is not None:
            out['remaining'] = r.get('remaining')

        if r.get('entries') is not None:
            out['entries'] = r.get('entries')

    out['token'] = _token()
    return out


def _game_over():
    st = L.load()
    f = L._load_field(st['field'])
    remaining = f.remaining()
    hero = f.players.get(f.hero_pid)
    busted = bool(st.get('busted')) or not hero or hero.get('stack', 0) <= 0
    won = bool(not busted and remaining <= 1)
    rank = 1 if won else st.get('rank')
    return {
        'done': True,
        'game_over': True,
        'won': won,
        'busted': busted,
        'rank': rank,
        'remaining': remaining,
        'entries': f.entries,
        'view': None,
        'token': _token(),
    }


class H(BaseHTTPRequestHandler):
    def handle(self):
        # 브라우저가 응답 도중 탭을 닫거나 새로고침하면 BrokenPipe 가 난다.
        # 정상적인 잡음이라 트레이스백을 찍지 않는다.
        try:
            BaseHTTPRequestHandler.handle(self)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _can_play(self):
        # 기존 헤더 방식도 호환용으로 남긴다.
        supplied = self.headers.get('X-T2-Play-Key') or ''
        if supplied and hmac.compare_digest(supplied, PLAY_KEY):
            return True

        # /play?k=... 로 최초 인증하면 서버가 이 쿠키를 발급한다.
        # 이후 액션 요청에는 브라우저가 자동으로 쿠키를 붙인다.
        raw = self.headers.get('Cookie') or ''
        for part in raw.split(';'):
            if '=' not in part:
                continue
            name, value = part.strip().split('=', 1)
            if name == 't2_play' and hmac.compare_digest(value, PLAY_KEY):
                return True

        return False

    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers(); self.wfile.write(b)

    def _send_bytes(self, code, body, ctype, extra_headers=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        # 개발 중에 고친 파일이 바로 반영되게 한다.
        # no-cache 는 '검증 후 재사용'이라 검증자(ETag 등)가 없으면 브라우저가
        # 옛 파일을 계속 쓰는 경우가 있었다. no-store 는 저장 자체를 막는다.
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, path, extra_headers=None):
        full = _resolve(path)
        if full is None:
            return self._send(404, {'error': 'not found'})
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext) or mimetypes.guess_type(full)[0] or 'application/octet-stream'
        try:
            with open(full, 'rb') as fp:
                body = fp.read()
        except OSError as e:
            return self._send(500, {'error': str(e)})
        return self._send_bytes(200, body, ctype, extra_headers)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header(
            'Access-Control-Allow-Headers',
            'Content-Type, X-T2-Play-Key, X-T2-Client-Mode'
        )
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.end_headers()

    def do_GET(self):
        global _last
        path = self.path.split('?', 1)[0]
        if path == '/api/ready':
            # 워커가 아직 다른 테이블을 돌리는 중인가. 결과 화면이 이걸 보고
            # 정산이 끝난 뒤에 다음 핸드로 넘어간다 — 빈 로딩 화면을 없앤다.
            # LOCK 을 잡지 않는다. 잡으면 진행 중인 요청 뒤에 줄을 서게 된다.
            fut = PENDING.get('future')
            return self._send(200, {'working': bool(fut and not fut.done())})
        if path == '/api/stats':
            return self._send(200, {'defer': DEFER, 'counters': dict(COUNT)})

        if path == '/api/memos':
            if not self._can_play():
                return self._send(403, {'error': '플레이어만 메모를 볼 수 있습니다'})
            with LOCK:
                try:
                    return self._send(200, {'memos': _hero_memos()})
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {'error': '%s: %s' % (type(e).__name__, e)})

        if path == '/api/history':
            # 공개 관전 화면에서도 읽을 수 있는 sanitized 완료 핸드 기록.
            # 숨은 상대 hole / profiles / reads / intents 는 포함하지 않는다.
            return self._send(200, {'hands': _public_history()})
        if path == '/play/':
            self.send_response(302)
            self.send_header('Location', '/play')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        if path.startswith('/play/'):
            supplied = urllib.parse.unquote(
                path[len('/play/'):]
            ).strip('/')

            if supplied and hmac.compare_digest(supplied, PLAY_KEY):
                # 인증 주소에서는 UI를 직접 띄우지 않는다.
                # 쿠키를 발급한 뒤 /play 로 보내야 CSS/JS 상대경로가 정상이다.
                self.send_response(302)
                self.send_header('Location', '/play')
                self.send_header(
                    'Set-Cookie',
                    't2_play=%s; Path=/; Max-Age=2592000; '
                    'Secure; HttpOnly; SameSite=Lax'
                    % PLAY_KEY
                )
                self.send_header('Content-Length', '0')
                self.end_headers()
                return

            return self._send(403, {'error': '잘못된 플레이 주소'})

        if path == '/play':
            return self._serve_static('/index.html')

        if path == '/watch':
            return self._serve_static('/index.html')
        if path in ('/play', '/watch'):
            return self._serve_static('/index.html')
        if path != '/api/state':
            return self._serve_static(path)
        with LOCK:
            try:
                if _last is None:
                    if not os.path.exists(L.ST):
                        return self._send(200, {'no_game': True})
                    _st = L.load()
                    _f = L._load_field(_st['field'])
                    if _st.get('busted') or _f.remaining() <= 1:
                        _last = _game_over()
                    else:
                        _last = _wrap(_step())
                return self._send(200, _last)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {'error': '%s: %s' % (type(e).__name__, e)})

    def do_POST(self):
        global _last
        try:
            body = self._body()
        except ValueError:
            return self._send(400, {'error': 'JSON 파싱 실패'})
        mutating = self.path in ('/api/new', '/api/step', '/api/memo')

        # 같은 브라우저가 예전에 /play 인증을 받아 t2_play 쿠키를 가지고 있어도
        # /watch 페이지에서는 절대 상태 변경 API를 실행하지 못하게 한다.
        # 쿠키는 "누가 플레이어인가", 이 헤더는 "현재 어느 UI 모드인가"를 가른다.
        if mutating and self.headers.get('X-T2-Client-Mode') != 'play':
            return self._send(
                403,
                {'error': '관전 페이지에서는 게임을 조작할 수 없습니다'}
            )

        if mutating and not self._can_play():
            return self._send(403, {'error': '플레이어 인증이 필요합니다'})

        with LOCK:
            try:
                if self.path == '/api/memo':
                    if not os.path.exists(L.ST):
                        return self._send(409, {'error': '진행 중인 게임 없음'})

                    try:
                        pid = int(body.get('pid'))
                    except (TypeError, ValueError):
                        return self._send(400, {'error': 'pid가 올바르지 않습니다'})

                    memo = body.get('memo', '')
                    if memo is None:
                        memo = ''
                    if not isinstance(memo, str):
                        return self._send(400, {'error': 'memo는 문자열이어야 합니다'})

                    memo = memo.strip()
                    if len(memo) > 2000:
                        return self._send(400, {'error': '메모는 2000자 이하만 저장할 수 있습니다'})

                    try:
                        memos = _save_hero_memo(pid, memo)
                    except ValueError as e:
                        return self._send(400, {'error': str(e)})

                    return self._send(200, {
                        'ok': True,
                        'pid': pid,
                        'memo': memo,
                        'memos': memos
                    })

                if self.path == '/api/new':
                    kw = {k: body[k] for k in ('entries', 'seed', 'fmt', 'start_stack')
                          if body.get(k) is not None}
                    PENDING['future'] = None      # 새 게임이면 밀린 것도 버린다
                    L.new_game(**kw)
                    _last = _wrap(_step())
                    return self._send(200, _last)
                if self.path == '/api/step':
                    if not os.path.exists(L.ST):
                        return self._send(409, {'error': '진행 중인 게임 없음'})
                    if body.get('token') != _token():
                        # 결과 화면에서 '다음 핸드'(action=null)가 중복 도착한 경우:
                        # 첫 요청이 이미 새 핸드를 만들었다면 두 번째 요청으로
                        # 또 한 핸드를 넘기지 않는다. 현재 화면만 다시 돌려준다.
                        if body.get('action') is None and _last is not None:
                            return self._send(200, _last)
                        return self._send(409, {'error': 'token 불일치 (중복 또는 오래된 요청)',
                                                'current': _last})
                    _st = L.load()
                    _f = L._load_field(_st['field'])
                    if _st.get('busted') or _f.remaining() <= 1:
                        _last = _game_over(); return self._send(200, _last)
                    a = body.get('action')
                    if a is not None and a not in ACTIONS:
                        return self._send(400, {'error': '알 수 없는 액션: %s' % a})
                    amt = int(body.get('amount') or 0)
                    r = _step(a, amt) if a is not None else _step()
                    v = r.get('view') or {}
                    if (not r.get('done') and v.get('error') and _last
                            and (_last.get('view') or {}).get('type') == 'decision'):
                        # 엔진의 오류 응답에는 stacks/contrib 가 빠져 있어 좌석 값이 틀린다.
                        # 상태는 바뀌지 않았으므로(token 동일) 직전 정상 화면에 오류만 붙인다.
                        out = dict(_last); out['view'] = dict(_last['view'], error=v['error'])
                        out['token'] = _token()
                        return self._send(200, out)
                    _last = _wrap(r)
                    return self._send(200, _last)
                return self._send(404, {'error': 'not found'})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {'error': '%s: %s' % (type(e).__name__, e)})

    def log_message(self, fmt, *args):
        sys.stderr.write('[ui] ' + fmt % args + '\n')


if __name__ == '__main__':
    host = os.environ.get('IP', '0.0.0.0')
    port = int(os.environ.get('PORT', '8765'))
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    # 워커는 **소켓을 열기 전에** 미리 띄운다. 서버가 돈 뒤에 fork 하면
    # 자식이 듣기 소켓을 물려받는다.
    if DEFER and _pool() is None:
        print('경고: 워커 프로세스를 못 만들었습니다. 정산 지연이 꺼진 것과 같게 동작합니다.')
    print('정산 지연: %s  (끄려면 T2_UI_DEFER=0)' % ('켬' if DEFER else '끔'))
    print('상태 파일: %s' % L.ST)
    print('정적 파일: %s%s' % (WEB, '' if os.path.isdir(WEB) else '  (없음 — API 만 동작)'))
    print('폰에서 직접: http://127.0.0.1:%d' % port)
    print('다른 기기에서: http://<이 기기의 LAN IP>:%d' % port)
    if ':' in host:
        class _HTTPServer6(HTTPServer):
            address_family = socket.AF_INET6
        srv = _HTTPServer6((host, port), H)
    else:
        srv = HTTPServer((host, port), H)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n종료 중…')
    finally:
        # 워커가 계산 중이어도 기다리지 않는다. 기다리면 Ctrl+C 후에도
        # 30초쯤 포트를 붙들고 있어 바로 다시 켤 수 없다.
        srv.server_close()
        if POOL is not None:
            try: POOL.shutdown(wait=False, cancel_futures=True)
            except TypeError: POOL.shutdown(wait=False)   # 파이썬 3.8 이하
        os._exit(0)
