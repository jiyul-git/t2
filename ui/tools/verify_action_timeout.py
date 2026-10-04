"""Server-authoritative HERO decision deadline and automatic fold."""
import json, os, pathlib, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory(prefix='t2_action_clock_') as td:
    subprocess.run(['sh', str(ROOT/'ui/tools/setup_run_dir.sh'), td],
                   check=True, stdout=subprocess.DEVNULL)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, T2_UI_DEFER='0', T2_HERO_ACTION_SECONDS='1')
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
        assert code == 200 and out.get('auto_folded') is True, out

        code, ready = request('/api/ready')
        assert code == 200 and ready['action_deadline_ms'] is None, ready
        print('PASS: arm-on-visible, same-token no reset, late action overridden, stale deadline cleared')
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
