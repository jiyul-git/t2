#!/usr/bin/env python3
"""그래픽 UI용 HTTP 래퍼. 판단 로직은 건드리지 않고 live2.step() 만 호출한다.

  python ui_server.py [--port 8765]

반드시 엔진을 **별도 폴더에 복사**해서 그 폴더에서 실행한다.
live2 는 아카이브·리딩 장부를 모듈 폴더에 쓰고, T2_LIVE_STATE 를 쓰면 경로와
무관하게 접미사가 '_alt' 하나라서 cli.py 세션과 같은 폴더면 파일을 공유한다.
그래서 이 폴더에 UI_SERVER_DIR 표시 파일이 없으면 시작하지 않는다.

엔드포인트 (전부 JSON)
  GET  /api/state             마지막 응답 (없으면 현재 상태를 재생해서 만든다)
  POST /api/new   {entries?, seed?, fmt?, start_stack?}
  POST /api/step  {action, amount, token}
       action: fold/check/call/bet/raise/allin, 또는 null(다음 핸드 딜)
       amount: 이번 스트리트 총 투입 목표(raise-to)
       token : 직전 응답의 token. 다르면 409 — 재전송으로 액션이 두 번 들어가는 것을 막는다.
"""
import json, os, sys, threading, traceback
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


def _token():
    try:
        st = L.load()
    except Exception:
        return None
    return '%s:%d' % (st.get('hand_seed'), len(st.get('actions') or []))


def _wrap(r):
    """step()/finish() 반환값에서 화이트리스트만 내보낸다 ('raw', 'result' 는 버린다)."""
    out = {'done': bool(r.get('done')), 'view': r.get('view')}
    if r.get('done'):
        out['busted'] = bool(r.get('busted')); out['rank'] = r.get('rank')
    out['token'] = _token()
    return out


def _game_over():
    st = L.load()
    return {'done': True, 'game_over': True, 'rank': st.get('rank'), 'view': None,
            'token': _token()}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers(); self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.end_headers()

    def do_GET(self):
        global _last
        if self.path != '/api/state':
            return self._send(404, {'error': 'not found'})
        with LOCK:
            try:
                if _last is None:
                    if not os.path.exists(L.ST):
                        return self._send(200, {'no_game': True})
                    if L.load().get('busted'):
                        _last = _game_over()
                    else:
                        _last = _wrap(L.step())
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
                if self.path == '/api/new':
                    kw = {k: body[k] for k in ('entries', 'seed', 'fmt', 'start_stack')
                          if body.get(k) is not None}
                    L.new_game(**kw)
                    _last = _wrap(L.step())
                    return self._send(200, _last)
                if self.path == '/api/step':
                    if not os.path.exists(L.ST):
                        return self._send(409, {'error': '진행 중인 게임 없음'})
                    if body.get('token') != _token():
                        return self._send(409, {'error': 'token 불일치 (중복 또는 오래된 요청)',
                                                'current': _last})
                    if L.load().get('busted'):
                        _last = _game_over(); return self._send(200, _last)
                    a = body.get('action')
                    if a is not None and a not in ACTIONS:
                        return self._send(400, {'error': '알 수 없는 액션: %s' % a})
                    amt = int(body.get('amount') or 0)
                    r = L.step(a, amt) if a is not None else L.step()
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
    port = 8765
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    print('상태 파일: %s' % L.ST)
    print('http://0.0.0.0:%d  (에뮬레이터: 10.0.2.2, 실기기: PC의 LAN IP)' % port)
    HTTPServer(('0.0.0.0', port), H).serve_forever()
