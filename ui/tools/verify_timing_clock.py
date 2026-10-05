"""T5·T6: 시간 규칙이 켜진 UI 서버의 HERO 시계·누적 타임뱅크·봇 예정표.

  - HERO 시계 = 포맷 기본 초 + 누적 뱅크, 같은 토큰 재무장은 연장 안 됨
  - 기본 초를 넘겨 행동하면 넘긴 만큼 뱅크가 줄고, base+bank 를 넘기면 타임아웃(체크 가능 체크/아니면 폴드)·뱅크 0
  - 봇 이벤트는 절대 예정 시각을 싣고 순서대로 증가, 다음 HERO 시계는 예정표 끝 이후에만 시작
  - 재접속(/api/ready)은 같은 deadline·남은 예정표를 돌려준다
  - 시간 규칙을 끄면 응답에 timing_on=false (기존 동작)
테스트 전용: T2_TIMING_TEST_BASE / T2_TIMING_TEST_BANK 로 기본 초·시작 뱅크를 짧게 둔다.
"""
import json, os, pathlib, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]


def server(td, extra):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, T2_UI_DEFER='0', T2_ALLOW_PRACTICE_NEW='1', **extra)
    proc = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)],
                            cwd=td, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def request(path, body=None):
        req = urllib.request.Request(
            f'http://127.0.0.1:{port}' + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def stream(body):
        req = urllib.request.Request(
            f'http://127.0.0.1:{port}/api/step-stream', data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        lines = []
        with urllib.request.urlopen(req, timeout=120) as r:
            for raw in r:
                raw = raw.strip()
                if raw:
                    lines.append(json.loads(raw))
        return lines

    for _ in range(200):
        try:
            request('/api/ready')
            break
        except OSError:
            time.sleep(.05)
    return proc, request, stream


def legal_passive(view):
    legal = (view or {}).get('legal') or {}
    if legal.get('check'):
        return 'check'
    if legal.get('call') is not None:
        return 'call'
    return 'fold'


def main():
    with tempfile.TemporaryDirectory(prefix='t2_timing_clock_') as td:
        subprocess.run(['sh', str(ROOT / 'ui/tools/setup_run_dir.sh'), td],
                       check=True, stdout=subprocess.DEVNULL)
        proc, request, stream = server(td, {'T2_TIMING_V1': 'enforce', 'T2_TIMING_TEST_BASE': '1',
                                            'T2_TIMING_TEST_BANK': '2'})
        try:
            code, r = request('/api/new', {'entries': 9, 'seed': 5, 'level_minutes': 10})
            assert code == 200 and (r.get('view') or {}).get('type') == 'decision', r
            token = r['token']
            code, armed = request('/api/action-clock', {'token': token})
            assert code == 200 and armed['timing_on'] is True, armed
            started, base_dl, dl = armed['action_started_ms'], armed['action_base_deadline_ms'], armed['action_deadline_ms']
            assert abs((base_dl - started) - 1000) <= 2 and abs((dl - base_dl) - 2000) <= 2, armed
            time.sleep(.2)
            code, rearmed = request('/api/action-clock', {'token': token})
            assert rearmed['action_deadline_ms'] == dl, rearmed
            code, ready = request('/api/ready')
            assert ready['action_deadline_ms'] == dl and ready['action_base_deadline_ms'] == base_dl, ready
            print('PASS: HERO clock = base + bank; same token never extends; reconnect sees same deadlines')

            # 기본 1초를 0.5초 넘겨 행동 → 뱅크 2 → 약 1.5
            time.sleep(max(0.0, (base_dl - time.time() * 1000) / 1000.0) + 0.5)
            lines = stream({'token': token, 'action': legal_passive(r['view']), 'amount': 0})
            final = [x for x in lines if x['type'] == 'final'][-1]['payload']
            code, ready = request('/api/ready')
            assert 1.3 <= ready['hero_time_bank'] <= 1.55, ready['hero_time_bank']
            print('PASS: acting 0.5s past base uses 0.5s of the bank (%.2f left)' % ready['hero_time_bank'])

            # 봇 예정표: 절대 시각이 단조 증가하고 다음 HERO 시계는 그 뒤에 시작
            start_line = lines[0]
            assert start_line['type'] == 'stream_start' and start_line.get('server_now_ms'), start_line
            evs = [x['event'] for x in lines if x['type'] == 'bot_action']
            stamps = [e.get('act_at_ms') or e.get('at_ms') for e in evs]
            timed = [e for e in evs if e.get('act_at_ms')]
            assert all(b >= a for a, b in zip(stamps, stamps[1:])), stamps
            for e in timed:
                assert e['clock_started_ms'] <= e['act_at_ms'] <= e['bank_deadline_ms'] + 1, e
            if final.get('view', {}).get('type') == 'decision':
                code, armed2 = request('/api/action-clock', {'token': final['token']})
                if ready.get('bot_ready_at_ms'):
                    assert armed2['action_started_ms'] >= ready['bot_ready_at_ms'] - 1, (armed2, ready)
                # 예정표가 아직 남아 있으면 HERO 액션은 409
                if ready.get('bot_ready_at_ms') and ready['bot_ready_at_ms'] > time.time() * 1000 + 600:
                    code, early = request('/api/step', {'token': final['token'], 'action': 'fold', 'amount': 0})
                    assert code == 409, early
            print('PASS: %d timed bot events, schedule monotonic, HERO clock starts after it' % len(timed))

            # 타임아웃: base+bank 를 넘김 → 체크/폴드, 뱅크 0
            for _ in range(30):
                code, st = request('/api/state')
                if (st.get('view') or {}).get('type') == 'decision':
                    break
                code, st = request('/api/step', {'token': st['token'], 'action': None})
            token = st['token']
            code, armed3 = request('/api/action-clock', {'token': token})
            time.sleep(max(0.0, (armed3['action_deadline_ms'] - time.time() * 1000) / 1000.0) + 0.3)
            code, out = request('/api/step', {'token': token, 'action': 'raise', 'amount': 10 ** 9})
            assert code == 200 and out.get('auto_folded') is True, out
            code, ready = request('/api/ready')
            assert ready['hero_time_bank'] == 0.0, ready['hero_time_bank']
            print('PASS: past base+bank → timeout action, bank 0')
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    with tempfile.TemporaryDirectory(prefix='t2_timing_off_') as td:
        subprocess.run(['sh', str(ROOT / 'ui/tools/setup_run_dir.sh'), td],
                       check=True, stdout=subprocess.DEVNULL)
        proc, request, stream = server(td, {'T2_TIMING_TEST_BASE': '1'})
        try:
            code, r = request('/api/new', {'entries': 9, 'seed': 5, 'level_minutes': 10})
            code, armed = request('/api/action-clock', {'token': r['token']})
            assert armed['timing_on'] is False and armed['action_base_deadline_ms'] is None, armed
            lines = stream({'token': r['token'], 'action': legal_passive(r['view']), 'amount': 0})
            assert not any((x.get('event') or {}).get('act_at_ms') for x in lines), lines[:3]
            print('PASS: timing off → legacy clock, no schedule, test overrides inert')
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == '__main__':
    main()
