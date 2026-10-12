"""Server-authoritative HERO decision deadline and automatic fold."""
import json, os, pathlib, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory(prefix='t2_action_clock_') as td:
    subprocess.run(['sh', str(ROOT/'ui/tools/setup_run_dir.sh'), td],
                   check=True, stdout=subprocess.DEVNULL)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    # 예전 고정 HERO 시계(fallback 경로) 검증이라 시간 규칙을 끈다. 시간 규칙 ON 은 verify_timing_clock.
    env = dict(os.environ, T2_UI_DEFER='0', T2_ALLOW_PRACTICE_NEW='1',
               T2_HERO_ACTION_SECONDS='1', T2_TIMING_V1='off', T2_UI_ACK_TIMEOUT='0.1')
    proc = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)],
                            cwd=td, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)

    def request(path, body=None):
        req = urllib.request.Request(
            f'http://127.0.0.1:{port}' + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    try:
        for _ in range(100):
            try:
                request('/api/ready')
                break
            except OSError:
                time.sleep(.05)

        code, r = request('/api/new', {'entries': 9, 'seed': 5, 'level_minutes': 10})
        assert code == 200 and (r.get('view') or {}).get('type') == 'decision', r
        token = r['token']

        code, before = request('/api/ready')
        assert code == 200 and before['action_deadline_ms'] is None, before

        code, armed = request('/api/action-clock', {'token': token})
        assert code == 200 and armed['action_deadline_ms'], armed
        deadline = armed['action_deadline_ms']

        time.sleep(.2)
        code, rearmed = request('/api/action-clock', {'token': token})
        assert code == 200 and rearmed['action_deadline_ms'] == deadline, rearmed

        time.sleep(1.0)
        legal = (r.get('view') or {}).get('legal') or {}
        if legal.get('check'):
            late = 'check'
        elif legal.get('call') is not None:
            late = 'call'
        else:
            late = 'fold'
        code, out = request('/api/step', {'token': token, 'action': late, 'amount': 0})
        expected = 'fold' if legal.get('fold') else 'check'
        assert code == 200 and out.get('auto_action') == expected, out
        assert out.get('auto_folded') is (expected == 'fold'), out

        # Exercise both free-check and facing-bet decisions through the actual
        # HTTP server, including a request that expires before it reaches it.
        tested = {expected}
        for _ in range(60):
            if tested == {'check', 'fold'}:
                break
            code, state = request('/api/state')
            v = state.get('view') or {}
            if v.get('type') != 'decision':
                if state.get('game_over'):
                    code, state = request('/api/new', {'entries': 9, 'seed': 15})
                else:
                    code, state = request('/api/step', {'token': state['token'], 'action': None})
                continue
            legal = v.get('legal') or {}
            expected = 'fold' if legal.get('fold') else 'check'
            if expected not in tested:
                request('/api/action-clock', {'token': state['token']})
                time.sleep(1.1)
                req = urllib.request.Request(
                    f'http://127.0.0.1:{port}/api/step-stream',
                    data=json.dumps({'token': state['token'], 'action': 'fold', 'amount': 0}).encode(),
                    headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=60) as response:
                    events = [json.loads(line) for line in response if line.strip()]
                start = next(e for e in events if e['type'] == 'stream_start')
                final = next(e['payload'] for e in events if e['type'] == 'final')
                assert start['hero_action'] == expected and start['hero_amount'] == 0, start
                assert final['auto_action'] == expected, final
                assert final['auto_folded'] is (expected == 'fold'), final
                tested.add(expected)
            else:
                passive = 'check' if legal.get('check') else 'call' if legal.get('call') else 'fold'
                code, state = request('/api/step', {'token': state['token'], 'action': passive})
        assert tested == {'check', 'fold'}, tested

        code, ready = request('/api/ready')
        assert code == 200 and ready['action_deadline_ms'] is None, ready
        print('PASS: deadline, check/fold timeout, accepted stream action, stale deadline cleared')
    finally:
        proc.terminate()
        proc.wait(timeout=5)

# JS regression: once HERO commits an action, local countdown must disappear
# immediately and periodic /api/ready must not resurrect the same deadline.
js = (ROOT / 'ui' / 'web' / 'app.js').read_text(encoding='utf-8')
assert 'S.actionSubmitted = true;\n    stopActionClock();' in js
assert 'if (S.actionSubmitted) return;\n  if (!deadlineMs' in js
assert 'if (S.actionSubmitted) return;\n  if (!v || v.type' in js
assert 'if (!S.actionSubmitted && ready.action_token === S.token' in js
queued = js.index('if (action !== null && S.replayDone)')
stopped = js.rfind('stopActionClock();', 0, queued)
assert stopped >= 0
print('PASS: committed/queued HERO action hides countdown and blocks deadline re-arm')
