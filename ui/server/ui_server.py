#!/usr/bin/env python3
"""그래픽 UI용 HTTP 래퍼. 판단 로직은 건드리지 않고 live2.step() 만 호출한다.

  python ui_server.py [--port 8765]

반드시 엔진을 **별도 폴더에 복사**해서 그 폴더에서 실행한다.
live2 는 아카이브·리딩 장부를 모듈 폴더에 쓴다. sidecar 이름은 이제 상태
파일 경로에서 나오므로(`storage_paths`) 상태가 다르면 파일도 갈리지만,
같은 폴더에서 같은 상태로 돌리면 여전히 겹친다.
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
import formats as FM
from table import BLINDS
import storage_paths as _SP   # 아카이브 경로는 엔진과 같은 resolver 를 쓴다

LOCK = threading.Lock()
_last = None
ACTIONS = {'fold', 'check', 'call', 'bet', 'raise', 'allin'}

def _lobby_payload():
    """UI-only tournament catalog; formats.py remains the rules source."""
    bb0 = int(BLINDS[0][2]) if BLINDS else 200
    tournaments = []
    for key in FM.names():
        f = FM.get(key)
        tournaments.append({
            'key': key,
            'name': f['name'],
            'start_bb': int(f['start_bb']),
            'start_stack': int(f['start_bb']) * bb0,
            'hands_per_level': int(f['hpl']),
            'seats': int(f['seats']),
            'itm_frac': float(f['itm_frac']),
            'reentry': bool(f['reentry']),
            'buyin_level': float(f['buyin_level']),
            'payout_flat': float(f['payout_flat']),
        })

    current = None
    if os.path.exists(L.ST):
        try:
            st = L.load()
            f = L._load_field(st['field'])
            hero = f.players.get(f.hero_pid)
            fmt = getattr(f, 'fmt', {}) or {}
            current = {
                'fmt': fmt.get('key', FM.DEFAULT),
                'name': fmt.get('name', FM.get().get('name')),
                'entries': int(f.entries),
                'remaining': int(f.remaining()),
                'hand_no': int(f.hand_no),
                'level': int(f.level),
                'stack': int((hero or {}).get('stack', 0)),
                'busted': bool(st.get('busted')),
                'rank': st.get('rank'),
            }
        except Exception:
            current = {'error': 'current_state_unreadable'}
    return {'tournaments': tournaments, 'current': current, 'can_play': True}


# ---------- 다른 테이블 정산을 결과 반환 뒤로 미룬다 ----------
# 비-HERO 테이블은 HERO 핸드가 끝난 뒤가 아니라 **같은 라운드 시작 시점**에
# 별도 프로세스에서 시작한다. 워커는 비-HERO 테이블만 진행하고
# bust 수거/밸런싱은 하지 않는다. 두 쪽 결과가 합쳐진 뒤 메인에서 한 번만 한다.
#
# 다른 테이블들끼리는 기존 step_others 순서를 그대로 유지한다. 병렬화 경계는
# HERO table vs all other tables 두 갈래뿐이다.
DEFER = os.environ.get('T2_UI_DEFER', '1') != '0'
POOL = None
PENDING = {'future': None, 'base_key': None}
COUNT = {'attempt': 0, 'hit': 0, 'mismatch': 0, 'fallback': 0,
         'worker_exception': 0, 'worker_join': 0, 'pool_unavailable': 0,
         'round_start': 0, 'round_restart': 0,
         'round_ready_before_finish': 0, 'round_ready_after_finish': 0,
         # 다음 라운드 직전까지도 worker가 안 끝나 실제로 기다린 시간.
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


_count_resume()


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


def _clear_worker():
    PENDING['future'] = None
    PENDING['base_key'] = None


def _submit_parallel(field_dump, restart=False):
    """라운드 시작 스냅샷으로 비-HERO worker를 한 번만 시작한다."""
    if not DEFER:
        return
    key = L._others_key(field_dump)
    fut = PENDING.get('future')
    if fut is not None and PENDING.get('base_key') == key:
        return
    if fut is not None:
        # 서로 다른 라운드 worker가 겹치면 상태를 섞지 않는다.
        if not fut.done():
            return
        _clear_worker()

    p = _pool()
    if p is None:
        return
    COUNT['attempt'] += 1
    COUNT['round_restart' if restart else 'round_start'] += 1
    try:
        PENDING['future'] = p.submit(L.compute_others_parallel, field_dump)
        PENDING['base_key'] = key
    except Exception:
        COUNT['worker_exception'] += 1
        _clear_worker()


def _peek_others():
    """완료됐을 때만 결과를 본다. 아직 진행 중이면 절대 기다리지 않는다."""
    fut = PENDING.get('future')
    if fut is None or not fut.done():
        return None
    try:
        return fut.result()
    except Exception:
        COUNT['worker_exception'] += 1
        traceback.print_exc()
        _clear_worker()
        return None


def _take_others(wait):
    """다음 라운드 직전에는 필요하면 join하고, 그 외에는 non-blocking."""
    fut = PENDING.get('future')
    if fut is None:
        return None
    if not wait and not fut.done():
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
    finally:
        _clear_worker()


def _ensure_round_worker(st):
    """서버가 핸드 중간에 재시작됐어도 현재 round worker를 복구한다."""
    if not DEFER or not st or st.get('others_pending'):
        return
    if st.get('hand_seed') is None:
        return
    if PENDING.get('future') is None:
        _submit_parallel(st['field'], restart=True)


def _kick_pending_worker():
    """HERO 결과가 먼저 끝났는데 worker가 없을 때의 crash/fallback 안전망."""
    if not DEFER or PENDING.get('future') is not None:
        return
    try:
        st = L.load()
    except Exception:
        return
    if not st.get('others_pending'):
        return
    base = st.get('others_base')
    if st.get('others_mode') == L.PARALLEL_TABLES_MODE and base:
        _submit_parallel(base, restart=True)
        return
    p = _pool()
    if p is None:
        return
    COUNT['attempt'] += 1
    try:
        PENDING['future'] = p.submit(L.compute_others, st['field'])
        PENDING['base_key'] = L._others_key(st['field'])
    except Exception:
        COUNT['worker_exception'] += 1
        _clear_worker()


def _step(action=None, amount=0, on_bot_action=None):
    """HERO 진행과 비-HERO round worker를 병렬로 조정한다."""
    st0 = None
    try:
        if os.path.exists(L.ST):
            st0 = L.load()
    except Exception:
        st0 = None

    others = None
    if DEFER and st0 is not None:
        if st0.get('others_pending'):
            # 다음 라운드는 settlement 전에는 시작하지 않는다.
            others = _take_others(wait=True)
        else:
            _ensure_round_worker(st0)
            # 완료된 결과는 넘기되 Future는 유지한다. 이번 HERO 액션이
            # 핸드를 끝내지 않아도 같은 결과를 다음 요청에 다시 쓸 수 있다.
            others = _peek_others()

    kw = {'defer_others': True, 'others': others} if DEFER else {}
    if DEFER:
        kw['on_round_start'] = _submit_parallel
    if on_bot_action is not None:
        kw['on_bot_action'] = on_bot_action

    r = L.step(action, amount, **kw) if action is not None else L.step(**kw)

    if DEFER:
        try:
            st1 = L.load()
        except Exception:
            st1 = None

        if r.get('done') and st1 is not None:
            if st1.get('others_pending'):
                # final action 계산 중 worker가 끝났다면 결과 화면을 막지 않고
                # 지금 즉시 merge한다. 아직이면 worker는 그대로 계속 돈다.
                ready = _peek_others()
                if ready is not None:
                    L.resume_others(st1, ready)
                    COUNT['round_ready_after_finish'] += 1
                    _clear_worker()
                else:
                    _kick_pending_worker()
            else:
                if others is not None:
                    COUNT['round_ready_before_finish'] += 1
                _clear_worker()

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



def _archive_status():
    """아카이브 출처 metadata. **'없음'과 '모호'를 가른다.**

    빈 목록 하나로 접으면 사용자가 "기록이 없다"와 "옛 공유 기록이 있는데
    이 세션 것인지 증명할 수 없어 안 쓴다"를 구분할 수 없다. 두 번째는
    데이터가 어딘가에 있다는 뜻이라 대응이 완전히 다르다.
    """
    r = _SP.resolve_read('archive')
    out = {'archive_source': r['source'], 'archive_warning': None,
           'legacy_archive': None}
    if r['source'] == _SP.SRC_LEGACY_AMBIGUOUS:
        out['legacy_archive'] = os.path.basename(r['legacy_path'] or '')
        out['archive_warning'] = (
            '옛 공유 아카이브(%s)가 있으나 이 상태의 기록인지 증명할 수 없어 '
            '사용하지 않았습니다. 과거에는 모든 custom state 가 이 한 파일에 '
            '썼습니다.' % out['legacy_archive'])
    return out


def _public_history():
    """현재 토너먼트의 완료 핸드를 UI용으로 안전하게 반환한다.

    중요:
    - hero 홀카드는 항상 허용
    - 상대 카드는 실제 shown_hole 만 허용
    - archive 의 top-level/result hole 전체는 절대 반환하지 않는다
    """
    # 엔진 상태의 namespace 를 그대로 따른다. UI 전용 아카이브를 만들지
    # 않는다. 예전에는 접미사 없는 이름을 고정으로 읽어서, T2_LIVE_STATE 를
    # 쓰는 세션을 띄우면 **다른 상태의 아카이브**를 보고 있었다.
    # 엔진 상태의 namespace 를 그대로 따른다. 옛 공유 `_alt` 는 **쓰지
    # 않는다** — 과거에는 모든 custom state 가 그 한 파일에 썼으므로 다른
    # 세션의 핸드가 섞여 있을 수 있다. 현재 핸드 기록에 섞어 보여주면
    # 화면상 구분이 불가능해진다.
    _r = _SP.resolve_read('archive')
    fn = _r['path']

    if not fn:
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

    def _stream_start(self):
        """봇 진행 이벤트를 계산 즉시 NDJSON으로 흘려보낸다."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

    def _stream_line(self, obj):
        try:
            b = (json.dumps(obj, ensure_ascii=False, default=str) + '\n').encode()
            self.wfile.write(b)
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError):
            # 클라이언트가 사라져도 엔진 계산/저장은 중단하지 않는다.
            return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header(
            'Access-Control-Allow-Headers',
            'Content-Type'
        )
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.end_headers()

    def do_GET(self):
        global _last
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == '/api/ready':
            # 워커가 아직 다른 테이블을 돌리는 중인가. 결과 화면이 이걸 보고
            # 정산이 끝난 뒤에 다음 핸드로 넘어간다 — 빈 로딩 화면을 없앤다.
            # LOCK 을 잡지 않는다. 잡으면 진행 중인 요청 뒤에 줄을 서게 된다.
            fut = PENDING.get('future')
            return self._send(200, {'working': bool(fut and not fut.done())})
        if path == '/api/stats':
            return self._send(200, {'defer': DEFER, 'counters': dict(COUNT)})
        if path == '/api/lobby':
            return self._send(200, _lobby_payload())

        if path == '/api/memos':
            with LOCK:
                try:
                    return self._send(200, {'memos': _hero_memos()})
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {'error': '%s: %s' % (type(e).__name__, e)})

        if path == '/api/history':
            # 공개 관전 화면에서도 읽을 수 있는 sanitized 완료 핸드 기록.
            # 숨은 상대 hole / profiles / reads / intents 는 포함하지 않는다.
            # 목록과 **출처 metadata** 를 함께 준다. 'hands' 키는 그대로라
            # 기존 클라이언트가 깨지지 않는다.
            _h = {'hands': _public_history()}
            _h.update(_archive_status())
            return self._send(200, _h)
        if path == '/play/':
            self.send_response(302)
            self.send_header('Location', '/play')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        if path == '/watch' or path.startswith('/watch/'):
            return self._send(404, {'error': '관전 모드는 제거되었습니다'})

        if path in ('/', '/lobby'):
            return self._serve_static('/lobby.html')
        if path == '/play':
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
                    _clear_worker()             # 새 게임이면 밀린 것도 버린다
                    L.new_game(**kw)
                    _last = _wrap(_step())
                    return self._send(200, _last)
                if self.path in ('/api/step', '/api/step-stream'):
                    stream = self.path == '/api/step-stream'
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

                    # 일반 /api/step 은 기존 호환 경로. 실제 플레이 액션만
                    # 스트림 경로를 쓰며, 1.5초 모션 템포는 프론트가 그대로 유지한다.
                    if stream:
                        self._stream_start()
                        alive = [True]

                        def _emit_bot(event):
                            if alive[0]:
                                alive[0] = self._stream_line({
                                    'type': 'bot_action',
                                    'event': event,
                                })

                        try:
                            r = (_step(a, amt, on_bot_action=_emit_bot)
                                 if a is not None else _step())
                        except Exception as e:
                            traceback.print_exc()
                            if alive[0]:
                                self._stream_line({
                                    'type': 'error',
                                    'error': '%s: %s' % (type(e).__name__, e),
                                })
                            return
                        v = r.get('view') or {}
                        if (not r.get('done') and v.get('error') and _last
                                and (_last.get('view') or {}).get('type') == 'decision'):
                            out = dict(_last)
                            out['view'] = dict(_last['view'], error=v['error'])
                            out['token'] = _token()
                            _last = out
                        else:
                            _last = _wrap(r)
                        if alive[0]:
                            self._stream_line({
                                'type': 'final',
                                'payload': _last,
                            })
                        return

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
    print('로비 주소: http://127.0.0.1:%d' % port)
    print('테이블 주소: http://127.0.0.1:%d/play' % port)
    print('다른 기기: http://<이 기기의 LAN IP>:%d' % port)
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
