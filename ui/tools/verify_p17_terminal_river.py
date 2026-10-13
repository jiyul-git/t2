#!/usr/bin/env python3
"""Real heads-up river path: final river action -> showdown, NOT another bot clock.

Runs only against its own temporary install and wallet/state.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def request(base, path, body=None, timeout=140):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def main():
    with tempfile.TemporaryDirectory(prefix='p17_river_') as td:
        subprocess.run(['sh', str(ROOT / 'ui/tools/setup_run_dir.sh'), td],
            stdout=subprocess.DEVNULL, check=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = 'http://127.0.0.1:%d' % port
        env = dict(os.environ, T2_UI_DEFER='0',
            T2_ALLOW_PRACTICE_NEW='1', T2_SCHEDULE_ENABLED='0',
            T2_TIMING_V1='enforce', T2_TIMING_TEST_BASE='1',
            T2_TIMING_TEST_BANK='0', T2_UI_SEQUENTIAL_BOTS='1')
        proc = subprocess.Popen([sys.executable, 'ui_server.py',
            '--port', str(port)], cwd=td, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for _ in range(150):
                try:
                    request(base, '/api/ready', timeout=2)
                    break
                except (OSError, ValueError):
                    time.sleep(.1)
            else:
                raise AssertionError('isolated server did not start')
            init = request(base, '/api/new', {'entries': 2, 'seed': 13})
            state = init
            seen_river = False
            seen_terminal = False
            seen_early = False
            for turn in range(22):
                v = (state.get('view') or {})
                if v.get('type') == 'result':
                    break
                assert v.get('type') == 'decision', v
                legal = v.get('legal') or {}
                action = ('check' if legal.get('check') else 'call'
                          if legal.get('call') is not None else 'fold')
                assert action != 'fold', ('cannot continue to river', turn, legal)
                ready_at = float(state.get('bot_ready_at_ms') or 0) / 1000
                if ready_at:
                    time.sleep(max(0.0, ready_at - time.time()) + .2)
                req = urllib.request.Request(base + '/api/step-stream',
                    data=json.dumps({'token': state['token'],
                                     'action': action, 'amount': 0}).encode(),
                    headers={'Content-Type': 'application/json'})
                had_terminal = False
                had_early = False
                with urllib.request.urlopen(req, timeout=160) as resp:
                    for line in resp:
                        item = json.loads(line)
                        if item.get('type') == 'error':
                            raise AssertionError(item)
                        if item.get('type') == 'final':
                            assert item.get('payload'), item
                            state = item['payload']
                            break
                        if item.get('type') != 'bot_action':
                            continue
                        event = item['event']
                        kind = event.get('kind')
                        if kind == 'street' and event.get('street') == 'river':
                            seen_river = True
                        if kind == 'hand_settle_begin':
                            assert not had_terminal
                            had_terminal = True
                            assert event.get('mode') == 'showdown', event
                            assert event.get('street') == 'river', event
                            seen_terminal = True
                        if kind == 'bot_begin' and had_terminal:
                            raise AssertionError('phantom bot after river closure')
                        if kind == 'hand_result_ready':
                            assert had_terminal and not had_early, event
                            assert event.get('mode') == 'showdown', event
                            assert len(event.get('board') or []) == 5, event
                            assert event.get('shown') is not None
                            assert 'hole' not in event, 'hidden mucked cards leaked'
                            had_early = True
                            seen_early = True
                        ack = request(base, '/api/step-ack',
                            {'stream_id': item['stream_id'], 'seq': item['seq']},
                            timeout=5)
                        assert ack.get('ok'), ack
                if state.get('done'):
                    break
            assert state.get('done'), 'did not reach a terminal result'
            assert seen_river and seen_terminal and seen_early, (
                'missing river/showdown/early-result boundaries',
                seen_river, seen_terminal, seen_early)
            print('PASS: actual river, terminal showdown, public result before final; zero ghost bot turns')
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()


if __name__ == '__main__':
    main()
