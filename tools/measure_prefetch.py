#!/usr/bin/env python3
"""prefetch 가 실제로 대기 시간을 줄이는지 잰다 (읽기 전용).

  python3 tools/measure_prefetch.py --hands 8 --pauses 0,3,6,10

**의미 보존 검증(tools/verify_defer.py)이 통과한 뒤에만 의미가 있다.**
여기서는 시간만 잰다. 엔진도 UI 서버도 고치지 않는다. 서버를 띄워 HTTP 로 칠 뿐이다.

대기가 어디에 실리는지가 모드마다 다르다. 한 지점만 재면 안 된다.

  prefetch OFF   핸드를 끝낸 액션의 응답 안에서 다른 테이블을 전부 돌린다.
                 그래서 **결과 화면이 늦게 뜬다.** 그 뒤 '다음 핸드'는 즉시.
  prefetch ON    핸드가 끝나면 즉시 결과를 돌려주고 워커에 던진다.
                 히어로가 결과를 읽는 동안 겹쳐 돌고, '다음 핸드'에서
                 남은 만큼만 기다린다.

그래서 세 가지를 다 잰다.
  끝액션    핸드를 끝낸 요청의 응답 시간 (= 결과 화면이 뜨기까지)
  다음핸드  '다음 핸드'를 누르고 화면이 돌아올 때까지
  핸드당    그 핸드에서 사용자가 실제로 멈춰 있던 시간의 합
            pause 는 사용자가 화면을 보는 시간이라 빼고 센다

pause
  핸드 종료부터 '다음 핸드' 클릭까지의 초. 이게 겹칠 수 있는 시간이다.
  UI 의 결과 화면 자동 넘김이 5초라 그 근처가 실전에 가깝다.
  prefetch 가 줄일 수 있는 최대치는 pause 와 정산 시간 중 작은 쪽이다.
"""
import argparse, json, os, shutil, socket, statistics as S, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = os.path.join(os.path.dirname(HERE), 'ui', 'tools', 'setup_run_dir.sh')

CLIENT = r"""
import os, json, time, urllib.request, urllib.error
PORT = int(os.environ['PORT']); HANDS = int(os.environ['HANDS'])
ENTRIES = int(os.environ['ENTRIES']); SEED = int(os.environ['SEED'])
PAUSE = float(os.environ['PAUSE'])
BASE = 'http://127.0.0.1:%d' % PORT

def call(path, obj=None):
    req = (urllib.request.Request(BASE+path, data=json.dumps(obj).encode(),
                                  headers={'Content-Type': 'application/json'})
           if obj is not None else urllib.request.Request(BASE+path))
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as f:
            return f.status, json.load(f), time.time()-t
    except urllib.error.HTTPError as e:
        return e.code, json.load(e), time.time()-t

for _ in range(300):
    try:
        call('/api/state'); break
    except Exception:
        time.sleep(0.2)
# ui_server 는 소켓을 열기 전에 풀을 예열한다. 따로 기다릴 것이 없다.

c, r, dt = call('/api/new', {'entries': ENTRIES, 'seed': SEED, 'start_stack': 30000})
deal, act, endact, per_hand = [], [], [], []
last = dt                              # 직전 요청의 응답 시간
cur = dt                               # 이 핸드에서 사용자가 멈춰 있던 시간의 합
n = 0
while n < HANDS:
    if r.get('game_over'):
        break
    if r.get('done'):
        n += 1
        endact.append(last)            # 이 핸드를 끝낸 요청 = 결과 화면이 뜨기까지
        per_hand.append(cur)
        cur = 0.0
        if r.get('busted') or n >= HANDS:
            break
        if PAUSE:
            time.sleep(PAUSE)          # 히어로가 결과를 보는 시간. 측정에서 뺀다
        c, r, dt = call('/api/step', {'action': None, 'amount': 0, 'token': r['token']})
        deal.append(dt); cur += dt; last = dt
        continue
    v = r.get('view') or {}
    if v.get('type') != 'decision':
        break
    lg = v['legal']; me = [s for s in v['seats'] if s['hero']][0]
    a = ('check' if lg['check'] else
         ('call' if lg['call'] is not None and lg['call'] <= 0.25*me['stack'] else 'fold'))
    c, r, dt = call('/api/step', {'action': a, 'amount': 0, 'token': r['token']})
    act.append(dt); cur += dt; last = dt
    if c != 200:
        break
c, stats, _ = call('/api/stats')
print(json.dumps({'deal': deal, 'act': act, 'endact': endact,
                  'per_hand': per_hand, 'hands': n, 'stats': stats}))
"""


def run(defer, pause, entries, hands, seed):
    tmp = tempfile.mkdtemp(prefix='t2_pf_%d_' % int(defer))
    subprocess.run(['sh', SETUP, tmp], check=True, stdout=subprocess.DEVNULL)
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, T2_UI_DEFER='1' if defer else '0')
    env.setdefault('T2_BOT_LOG', '1')
    srv = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)],
                           cwd=tmp, env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE)
    open(os.path.join(tmp, 'client.py'), 'w').write(CLIENT)
    cenv = dict(os.environ, PORT=str(port), HANDS=str(hands), ENTRIES=str(entries),
                SEED=str(seed), PAUSE=str(pause))
    p = subprocess.run([sys.executable, 'client.py'], cwd=tmp, env=cenv,
                       capture_output=True, text=True)
    srv.terminate()
    try: srv.wait(timeout=10)
    except Exception: srv.kill()
    shutil.rmtree(tmp, ignore_errors=True)
    if p.returncode or not p.stdout.strip():
        return {'error': (p.stderr or '')[-800:]}
    return json.loads(p.stdout.strip().splitlines()[-1])


def med(xs):
    return round(S.median(xs), 2) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hands', type=int, default=8)
    ap.add_argument('--seed', type=int, default=777)
    ap.add_argument('--pauses', default='0,3,6,10')
    a = ap.parse_args()
    pauses = [float(x) for x in a.pauses.split(',')]

    print('entries %d, seed %d, %d핸드. 단위는 초, median.\n' % (a.entries, a.seed, a.hands))
    print('%-6s %-4s %8s %9s %8s  %s'
          % ('pause', 'pf', '끝액션', '다음핸드', '핸드당', '워커대기합'))
    rows = {}
    for pause in pauses:
        for defer in (False, True):
            r = run(defer, pause, a.entries, a.hands, a.seed)
            if 'error' in r:
                print('%-6s %-4s 실행 실패: %s'
                      % (pause, 'ON' if defer else 'OFF', r['error'][:200]))
                continue
            rows[(pause, defer)] = r
            wq = ((r.get('stats') or {}).get('counters') or {}).get('worker_wait_ms', 0)
            print('%-6s %-4s %8s %9s %8s  %s'
                  % (pause, 'ON' if defer else 'OFF',
                     med(r['endact']), med(r['deal']), med(r['per_hand']),
                     '%.1fs' % (wq/1000.0) if defer else '-'))
        off, on = rows.get((pause, False)), rows.get((pause, True))
        if off and on:
            d = med(on['per_hand']) - med(off['per_hand'])
            print('%-6s %-4s %8s %9s %8s  (핸드당 %+.2fs)'
                  % ('', '차', '', '', '%+.2f' % d, d))
    print('\n핸드당 = 그 핸드에서 사용자가 멈춰 있던 시간의 합 (pause 제외).')
    print('prefetch 가 줄일 수 있는 최대치는 pause 와 정산 시간 중 작은 쪽이다.')


if __name__ == '__main__':
    main()
