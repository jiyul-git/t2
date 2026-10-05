#!/usr/bin/env python3
"""사람 포함 테이블 실측(시간 규칙 ON) — 실제 UI 서버를 실시간으로 돌리고 HERO 를 자동으로 친다.

서버는 그대로다(봇 예정표·HERO 시계·타임뱅크·타임아웃 모두 실제 경로). 클라이언트는 브라우저가 하는
기다림만 재현한다:
  - HERO 액션은 봇 예정표가 끝난 뒤(bot_ready_at)에만, 그다음 HERO 고민 시간만큼 기다렸다가
  - 핸드가 끝나면 남은 예정표(관전 꼬리)가 끝날 때까지 + 화면 결과 표시 2.0초 + 카드 수거 0.54초
    (ui/web/app.js RESULT_HOLD, COLLECT_MS) 뒤에 다음 핸드
HERO 고민 시간과 플레이 정책은 실제 사람이 아니라 가정이다(결과에 그대로 적는다).

  python tools/timing_live_measure.py OUT.json MINUTES HERO_MODE SEED [ENTRIES]
    HERO_MODE = instant  (액션바가 뜨면 0.5초 안에 행동 — 봇+기계 시간만의 상한)
              | human    (로그정규 중앙 4초, σ 0.6 — 가정)
"""
import json, math, os, random, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_HOLD = 2.0 + 0.54


def main():
    out_path, minutes, mode, seed = sys.argv[1], float(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    entries = int(sys.argv[5]) if len(sys.argv) > 5 else 90
    rng = random.Random(seed * 7 + 1)
    with tempfile.TemporaryDirectory(prefix='t2_live_measure_', ignore_cleanup_errors=True) as td:
        subprocess.run([sys.executable, os.path.join(ROOT, 'ui/tools/setup_run_dir.py'), td],
                       check=True, stdout=subprocess.DEVNULL)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, T2_TIMING_V1='enforce', T2_ALLOW_PRACTICE_NEW='1')
        env.pop('T2_TIMING_TEST_BASE', None); env.pop('T2_TIMING_TEST_BANK', None)
        proc = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)], cwd=td,
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def request(path, body=None):
            req = urllib.request.Request(
                'http://127.0.0.1:%d%s' % (port, path),
                data=None if body is None else json.dumps(body).encode(),
                headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                return e.code, json.load(e)

        for _ in range(200):
            try:
                request('/api/ready')
                break
            except OSError:
                time.sleep(.05)

        def sleep_until_ms(ms):
            d = (float(ms or 0) / 1000.0) - time.time()
            if d > 0:
                time.sleep(d)

        def hero_think():
            if mode == 'instant':
                return rng.uniform(0.2, 0.5)
            return min(30.0, math.exp(rng.gauss(math.log(4.0), 0.6)))

        def policy(v):
            lg = v.get('legal') or {}
            tocall = lg.get('call') or 0
            pot = v.get('pot_total') or v.get('pot') or 1
            if v.get('stage') == 'preflop':
                if lg.get('check'):
                    return 'check'
                return 'call' if (lg.get('call') is not None and rng.random() < 0.22) else 'fold'
            if lg.get('check'):
                return 'check'
            if lg.get('call') is not None and tocall <= 0.5 * pot and rng.random() < 0.5:
                return 'call'
            return 'fold'

        t_start = time.time()
        hands, hero_dec, sched_all, hero_think_s = [], 0, [], []
        code, r = request('/api/new', {'entries': entries, 'seed': seed, 'level_minutes': 10})
        hand_t0 = time.time()
        cur_hand = (r.get('view') or {}).get('hand_no')
        timeouts = 0
        try:
            while time.time() - t_start < minutes * 60:
                v = r.get('view') or {}
                sched_all.extend(r.get('bot_schedule') or [])
                if r.get('game_over') or r.get('busted'):
                    break
                if v.get('type') == 'decision':
                    sleep_until_ms(r.get('bot_ready_at_ms'))
                    code, armed = request('/api/action-clock', {'token': r['token']})
                    think = hero_think()
                    hero_think_s.append(think)
                    time.sleep(think)
                    hero_dec += 1
                    code, r2 = request('/api/step', {'token': r['token'], 'action': policy(v), 'amount': 0})
                    if code != 200:
                        code, r2 = request('/api/state')
                    if r2.get('auto_folded'):
                        timeouts += 1
                    r = r2
                    continue
                if r.get('done') or v.get('type') == 'result':
                    # 관전 꼬리(예정표) 끝 + 결과 표시·카드 수거
                    sleep_until_ms(r.get('bot_ready_at_ms'))
                    time.sleep(RESULT_HOLD)
                    hands.append({'hand_no': cur_hand, 'seconds': time.time() - hand_t0})
                    code, r = request('/api/step', {'token': r['token'], 'action': None})
                    hand_t0 = time.time()
                    cur_hand = (r.get('view') or {}).get('hand_no')
                    continue
                code, r = request('/api/state')
                time.sleep(0.2)
            code, ready = request('/api/ready')
        finally:
            proc.terminate()
            proc.wait(timeout=10)
    elapsed = time.time() - t_start
    seen, bot = set(), []
    for e in sched_all:
        if not e.get('act_at_ms'):
            continue
        k = (e.get('clock_started_ms'), e.get('seat'))
        if k in seen:
            continue
        seen.add(k)
        bot.append({'seat': e['seat'], 'elapsed': (e['act_at_ms'] - e['clock_started_ms']) / 1000.0,
                    'base': (e['base_deadline_ms'] - e['clock_started_ms']) / 1000.0,
                    'bank': (e['bank_deadline_ms'] - e['base_deadline_ms']) / 1000.0})
    res = {'mode': mode, 'seed': seed, 'entries': entries, 'minutes': round(elapsed / 60, 2),
           'hands': len(hands), 'hands_per_hour': round(3600.0 * len(hands) / max(1.0, sum(h['seconds'] for h in hands)), 1),
           'hand_seconds': sorted(round(h['seconds'], 2) for h in hands),
           'hero_decisions': hero_dec, 'hero_think': hero_think_s, 'hero_timeouts': timeouts,
           'hero_bank_left': ready.get('hero_time_bank'), 'bot_events': bot}
    json.dump(res, open(out_path, 'w'), indent=1)
    print(json.dumps({k: res[k] for k in ('mode', 'seed', 'minutes', 'hands', 'hands_per_hour',
                                          'hero_decisions', 'hero_timeouts', 'hero_bank_left')}))


if __name__ == '__main__':
    main()
