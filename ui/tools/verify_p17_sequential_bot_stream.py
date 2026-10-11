#!/usr/bin/env python3
"""Real HTTP contract for opt-in sequential hero-table bot clocks.

Runs against an isolated installation; no real wallet, server or test3 changes.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def get_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    with tempfile.TemporaryDirectory(prefix='p17_bot_clock_') as td:
        subprocess.run(['sh', str(ROOT / 'ui/tools/setup_run_dir.sh'), td],
                       check=True, stdout=subprocess.DEVNULL)
        port = get_port()
        base = 'http://127.0.0.1:%d' % port
        env = dict(os.environ, T2_UI_DEFER='0', T2_ALLOW_PRACTICE_NEW='1',
                   T2_SCHEDULE_ENABLED='0', T2_TIMING_V1='enforce',
                   T2_TIMING_TEST_BASE='2', T2_TIMING_TEST_BANK='0',
                   T2_UI_SEQUENTIAL_BOTS='1')
        proc = subprocess.Popen(
            [sys.executable, 'ui_server.py', '--port', str(port)],
            cwd=td, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        def req(path, body=None, timeout=100):
            raw = None if body is None else json.dumps(body).encode()
            request = urllib.request.Request(
                base + path, data=raw, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)

        try:
            for _ in range(150):
                try:
                    req('/api/ready', timeout=2)
                    break
                except (OSError, ValueError):
                    time.sleep(.1)
            else:
                raise AssertionError('server did not start')

            received = 0
            settled = False
            result_seen = False
            for seed in (5, 11, 13, 17):
                state = req('/api/new', {'entries': 9, 'seed': seed})
                v = state.get('view') or {}
                assert v.get('type') == 'decision', v
                ready_at = float(state.get('bot_ready_at_ms') or 0) / 1000.0
                if ready_at:
                    time.sleep(max(0.0, ready_at - time.time()) + .3)
                body = json.dumps({'token': state['token'], 'action': 'fold',
                                   'amount': 0}).encode()
                request = urllib.request.Request(
                    base + '/api/step-stream', data=body,
                    headers={'Content-Type': 'application/json'})
                last_begin = None
                last_acked = 0
                settled = False
                result_seen = False
                with urllib.request.urlopen(request, timeout=160) as response:
                    for row in response:
                        msg = json.loads(row)
                        if msg.get('type') == 'error':
                            raise AssertionError(msg)
                        if msg.get('type') == 'final':
                            assert settled and result_seen, ('missing terminal/result event', received)
                            break
                        if msg.get('type') != 'bot_action':
                            continue
                        event = msg['event']
                        if event['kind'] == 'bot_begin':
                            assert not settled, 'new bot calculation after terminal river/fold'
                            assert event['clock_started_ms'] >= last_acked - 30, (
                                event, last_acked)
                            last_begin = event
                        elif event['kind'] == 'bot_action':
                            assert not settled, 'bot action after terminal betting round'
                            assert last_begin is not None, ('missing bot_begin', event)
                            assert last_begin['seat'] == event['seat'], (last_begin, event)
                            dt = event['act_at_ms'] - last_begin['clock_started_ms']
                            assert dt >= 1490, ('under 1.5s', dt, event)
                            model = float(event['model_elapsed_seconds'])
                            actual = float(event['actual_compute_seconds'])
                            assert dt / 1000.0 + .04 >= max(1.5, model, actual), (
                                dt, model, actual)
                            received += 1
                            last_begin = None
                        elif event['kind'] == 'hand_settle_begin':
                            assert last_begin is None, 'terminal started inside bot computation'
                            assert not settled, 'duplicate terminal boundary'
                            assert event.get('mode') in ('showdown', 'uncontested'), event
                            settled = True
                        elif event['kind'] == 'hand_result_ready':
                            assert settled and not result_seen, 'early result out of order'
                            assert event.get('mode') in ('showdown', 'uncontested'), event
                            assert isinstance(event.get('shown'), dict)
                            assert isinstance(event.get('winners'), list)
                            assert isinstance(event.get('board'), list)
                            assert event.get('hash'), 'result requires the true hand identity'
                            assert 'hole' not in event, 'unshown cards must never leak'
                            result_seen = True
                        # Browser ACKs on actual motion completion, not calculation.
                        time.sleep(.08)
                        ack = req('/api/step-ack', {'stream_id': msg['stream_id'],
                                                       'seq': msg['seq']}, timeout=5)
                        assert ack['ok'], ack
                        last_acked = time.time() * 1000.0
                if received:
                    break
            assert received >= 1, 'no actual post-hero bot decision was observed'
            assert settled and result_seen, 'no verified terminal transition and early public result'
            print('PASS: %d real bot turns, strict ACK order, explicit terminal boundary and muck-safe early result' % received)
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()


if __name__ == '__main__':
    main()
