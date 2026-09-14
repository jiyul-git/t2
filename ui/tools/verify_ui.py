#!/usr/bin/env python3
"""UI 서버 자동 검증. 엔진과 ui_view/ui_server 를 건드리지 않고 밖에서만 본다.

  python3 ui/tools/verify_ui.py [--hands 12] [--entries 100] [--seed 20260911]
                                [--port 8799] [--keep]

**항상 임시 폴더를 새로 만들어서** 거기에 엔진을 복사하고 검사한다.
검사는 /api/new 를 부르므로, 실제 실행 폴더(~/t2_ui_run)에서 돌리면
진행 중인 게임이 날아간다. 그래서 대상 폴더를 인자로 받지 않는다.

검사 항목
  1 칩 보존      한 핸드 안에서 Σstack + pot_total 이 일정한가
  2 누출         아카이브의 홀카드와 대조. 쇼다운 좌석 외 공개가 있는가
  3 내부값 누출  응답 JSON 어디에도 plan/eq/why/rel/outs/profile 이 없는가
  4 token        오래된 token 재전송이 409 를 받는가
  5 최소 미달    미달 레이즈가 error 를 주고 token 이 그대로인가
  6 legal 일치   legal 이 허용한 액션이 error 없이 통과하는가
  7 워크 핸드    딜 직후 곧바로 result 가 오는 경우를 처리하는가
  8 지연         진행 중 / 핸드 종료 각각의 중앙값과 최대값
  9 정적 파일    GET / 가 web/index.html 을 주는가, ../ 로 폴더를 벗어날 수 있는가
"""
import argparse, json, os, random, shutil, subprocess, sys, tempfile, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# 라이브 화면에 절대 나오면 안 되는 키. 값이 아니라 키 이름으로 찾는다.
FORBIDDEN = ('"plan"', '"eq"', '"why"', '"rel"', '"outs"', '"profile"',
             '"made"', '"intents"', '"eq_delta"', '"eq_current"')


class Client:
    def __init__(self, base):
        self.base = base
        self.lat_mid = []      # 진행 중 액션
        self.lat_end = []      # 핸드를 끝낸 액션
        self.bodies = []       # 원문. 내부값 누출 검사용

    def _call(self, path, obj=None):
        t = time.time()
        if obj is None:
            req = urllib.request.Request(self.base + path)
        else:
            req = urllib.request.Request(
                self.base + path, data=json.dumps(obj).encode(),
                headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=120) as f:
                code, raw = f.status, f.read().decode()
        except urllib.error.HTTPError as e:
            code, raw = e.code, e.read().decode()
        self.bodies.append(raw)
        return code, json.loads(raw), time.time() - t

    def new(self, **kw):
        c, r, dt = self._call('/api/new', kw)
        return c, r

    def state(self):
        c, r, dt = self._call('/api/state')
        return c, r

    def step(self, action, amount, token):
        c, r, dt = self._call('/api/step',
                              {'action': action, 'amount': amount, 'token': token})
        (self.lat_end if r.get('done') else self.lat_mid).append(dt)
        return c, r


def check_static(base):
    """2단계에서 추가한 정적 파일 제공. web/ 밖으로는 절대 나가면 안 된다."""
    fail = []

    def raw(path):
        try:
            with urllib.request.urlopen(base + path, timeout=20) as f:
                return f.status, f.headers.get('Content-Type', ''), f.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get('Content-Type', ''), e.read()

    code, ctype, body = raw('/')
    if code != 200:
        fail.append('GET / 가 %d' % code)
    elif b'<div id="app">' not in body:
        fail.append('GET / 가 index.html 이 아님')
    elif 'text/html' not in ctype:
        fail.append('GET / 의 Content-Type 이 %r' % ctype)

    code, ctype, body = raw('/app.js')
    if code != 200:
        fail.append('GET /app.js 가 %d' % code)
    elif 'javascript' not in ctype:
        fail.append('GET /app.js 의 Content-Type 이 %r' % ctype)

    for p in ('/../ui_server.py', '/%2e%2e/ui_server.py', '/../../etc/passwd'):
        code, ctype, body = raw(p)
        if code == 200:
            fail.append('폴더 밖 파일이 열림: %s' % p)
    code, _, _ = raw('/nope.js')
    if code != 404:
        fail.append('없는 파일이 404 가 아니라 %d' % code)
    return fail


def med(xs):
    if not xs: return None
    xs = sorted(xs)
    return round(xs[len(xs) // 2], 2)


def run(args):
    tmp = tempfile.mkdtemp(prefix='t2_ui_verify_')
    fail = []
    note = []
    try:
        subprocess.run(['sh', os.path.join(HERE, 'setup_run_dir.sh'), tmp],
                       check=True, stdout=subprocess.DEVNULL)
        srv = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(args.port)],
                               cwd=tmp, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
        cli = Client('http://127.0.0.1:%d' % args.port)
        for _ in range(100):
            if srv.poll() is not None:
                return ['서버가 뜨지 않았습니다: %s'
                        % srv.stderr.read().decode()[-400:]], note, {}
            try:
                cli.state(); break
            except Exception:
                time.sleep(0.2)
        else:
            return ['서버 응답 없음'], note, {}

        fail += check_static('http://127.0.0.1:%d' % args.port)

        rng = random.Random(args.seed)
        stats = dict(hands=0, decisions=0, walks=0, chip_checks=0, chip_bad=0,
                     legal_violations=0, err_checked=0, results=0, showdowns=0)
        pot_of = {}            # hand_no -> Σstack + pot_total
        exposed = {}           # hand_no -> 화면에 나온 카드 집합
        shown_seats = {}       # hand_no -> 쇼다운으로 공개된 좌석
        token_case_done = False

        c, r = cli.new(entries=args.entries, seed=args.seed,
                       start_stack=30000)
        if c != 200:
            return ['POST /api/new 가 %d' % c], note, stats

        while stats['hands'] < args.hands:
            v = r.get('view') or {}

            if r.get('game_over'):
                note.append('히어로 탈락 — %d핸드에서 종료 (rank %s)'
                            % (stats['hands'], r.get('rank')))
                break

            if r.get('done'):
                stats['hands'] += 1; stats['results'] += 1
                hn = v.get('hand_no')
                if v.get('showdown'):
                    stats['showdowns'] += 1
                    shown_seats[hn] = set(int(s) for s in (v.get('shown') or {}))
                else:
                    shown_seats[hn] = set()
                    if v.get('shown'):
                        fail.append('핸드 %s: 쇼다운이 아닌데 shown 이 비어있지 않음' % hn)
                exposed.setdefault(hn, set()).update(
                    x for cards in (v.get('shown') or {}).values() for x in cards)
                exposed[hn].update(v.get('board') or [])
                if stats['hands'] >= args.hands:
                    break
                # 다음 핸드 딜. 여기서 곧바로 done 이 오면 워크 핸드다.
                c, r = cli.step(None, 0, r['token'])
                if c != 200:
                    fail.append('딜(step null)이 %d: %s' % (c, r.get('error'))); break
                if r.get('done') and not r.get('game_over'):
                    stats['walks'] += 1
                continue

            if v.get('type') != 'decision':
                fail.append('알 수 없는 view type: %r' % v.get('type')); break

            hn = v['hand_no']
            stats['decisions'] += 1
            exposed.setdefault(hn, set()).update(v.get('hero_hole') or [])
            exposed[hn].update(v.get('board') or [])

            # --- 1 칩 보존 ---
            tot = sum(s['stack'] for s in v['seats']) + v['pot_total']
            stats['chip_checks'] += 1
            if hn in pot_of and pot_of[hn] != tot:
                stats['chip_bad'] += 1
                fail.append('핸드 %s 칩 불일치: %d -> %d' % (hn, pot_of[hn], tot))
            pot_of[hn] = tot

            lg = v['legal']
            hero = next(s for s in v['seats'] if s['hero'])

            # --- 4 오래된 token / 5 최소 미달 레이즈 (핸드당 한 번씩만) ---
            if not token_case_done:
                token_case_done = True
                before = r['token']
                c2, r2 = cli.step('check' if lg['check'] else 'fold', 0, 'stale-token')
                stats['err_checked'] += 1
                if c2 != 409:
                    fail.append('오래된 token 이 409 가 아니라 %d' % c2)
                c3, r3 = cli.state()
                if (r3.get('token') or before) != before:
                    fail.append('409 뒤 token 이 바뀜: %s -> %s' % (before, r3.get('token')))

            rz = lg.get('raise')
            if rz and not rz['allin_only'] and stats['err_checked'] < 2:
                stats['err_checked'] += 1
                cur = v['to_call'] + hero['bet']       # 이번 스트리트 현재 벳 라인
                bad = cur + 1
                if bad < rz['min_to']:
                    before = r['token']
                    c4, r4 = cli.step('raise', bad, before)
                    v4 = r4.get('view') or {}
                    if not v4.get('error'):
                        fail.append('최소 미달 레이즈(%d < %d)가 error 를 주지 않음'
                                    % (bad, rz['min_to']))
                    if r4.get('token') != before:
                        fail.append('error 응답에서 token 이 바뀜: %s -> %s'
                                    % (before, r4.get('token')))
                    if v4.get('type') != 'decision':
                        fail.append('error 응답의 view type 이 decision 이 아님: %r'
                                    % v4.get('type'))
                    r = dict(r4, token=r4.get('token') or before)
                    continue

            # --- 6 legal 이 허용한 액션만 보낸다 ---
            roll = rng.random()
            if rz and not rz['allin_only'] and roll < 0.15:
                a, amt = 'raise', rz['min_to']
            elif lg['check']:
                a, amt = 'check', 0
            elif lg['call'] is not None and (lg['call'] <= 0.12 * hero['stack']
                                             or roll < 0.35):
                a, amt = 'call', 0
            else:
                a, amt = 'fold', 0

            c, r = cli.step(a, amt, r['token'])
            if c != 200:
                fail.append('%s %s 가 HTTP %d: %s' % (a, amt, c, r.get('error'))); break
            if (r.get('view') or {}).get('error'):
                stats['legal_violations'] += 1
                fail.append('legal 이 허용한 %s %s 가 거부됨: %s'
                            % (a, amt, r['view']['error']))
                r = dict(r, token=r.get('token'))

        srv.terminate(); srv.wait(timeout=10)

        # --- 2 누출: 아카이브의 홀카드와 대조 ---
        arch = os.path.join(tmp, 'hand_archive2.jsonl')
        checked = 0
        if os.path.exists(arch):
            for line in open(arch):
                if not line.strip(): continue
                rec = json.loads(line)
                hn = rec['hand_no']
                if hn not in exposed: continue
                checked += 1
                heros = rec['hero']
                for seat, hole in (rec.get('hole') or {}).items():
                    s = int(seat)
                    if s == heros or s in shown_seats.get(hn, set()): continue
                    hit = set(hole) & exposed[hn]
                    if hit:
                        fail.append('핸드 %s 좌석 %d 홀카드 누출: %s' % (hn, s, sorted(hit)))
        else:
            note.append('아카이브 파일이 없어 누출 대조를 못 했습니다')
        stats['leak_hands_checked'] = checked

        # --- 3 내부값 키 누출 ---
        for body in cli.bodies:
            for k in FORBIDDEN:
                if k + ':' in body.replace(' ', ''):
                    fail.append('응답에 금지 키 %s 가 있음' % k)
                    break

        stats['lat_mid_med'] = med(cli.lat_mid)
        stats['lat_mid_max'] = round(max(cli.lat_mid), 2) if cli.lat_mid else None
        stats['lat_end_med'] = med(cli.lat_end)
        stats['lat_end_max'] = round(max(cli.lat_end), 2) if cli.lat_end else None
        return fail, note, stats
    finally:
        if args.keep:
            print('임시 폴더 유지: %s' % tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hands', type=int, default=12)
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--seed', type=int, default=20260911)
    ap.add_argument('--port', type=int, default=8799)
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()

    t0 = time.time()
    fail, note, stats = run(args)
    print('=== verify_ui  (entries %d, seed %d, %.0f초) ==='
          % (args.entries, args.seed, time.time() - t0))
    for k in ('hands', 'results', 'decisions', 'walks', 'showdowns',
              'chip_checks', 'chip_bad', 'leak_hands_checked',
              'legal_violations', 'err_checked'):
        if k in stats: print('  %-18s %s' % (k, stats[k]))
    print('  %-18s 중앙 %s / 최대 %s 초'
          % ('지연(진행 중)', stats.get('lat_mid_med'), stats.get('lat_mid_max')))
    print('  %-18s 중앙 %s / 최대 %s 초'
          % ('지연(핸드 종료)', stats.get('lat_end_med'), stats.get('lat_end_max')))
    for n in note: print('  note: %s' % n)
    if fail:
        print('\n실패 %d건' % len(fail))
        for f in fail[:30]: print('  - %s' % f)
        return 1
    print('\n통과')
    return 0


if __name__ == '__main__':
    sys.exit(main())
