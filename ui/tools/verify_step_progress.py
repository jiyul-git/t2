"""Real HTTP handler: progress stays readable during a disconnected stream.

The engine is paused after its first emitted action while it holds LOCK. The
test uses the actual publication / request handlers, with a controlled engine
instead of rerunning private tournament records.
"""
import ast
import json
import os
import pathlib
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

root = pathlib.Path(__file__).resolve().parents[2]
tree = ast.parse((root / 'ui/server/ui_server.py').read_text())
handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'H')
methods = {'_send', '_body', '_stream_start', '_stream_line', '_play_tracked',
           'do_GET', 'do_POST', '_do_GET', '_do_POST'}
functions = {'_play_absent', '_step_progress_open', '_step_progress_emit', '_step_progress_read'}
assignments = {'PLAY_PATHS', 'PLAY_INFLIGHT', 'LAST_PLAY_PRESENCE'}
nodes = [n for n in tree.body if
         isinstance(n, ast.FunctionDef) and n.name in functions or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in assignments for t in n.targets)]
nodes.append(ast.ClassDef(name='H', bases=handler.bases, keywords=[], decorator_list=[],
                         body=[n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name in methods]))
emitted, release = threading.Event(), threading.Event()
request_id = '12345678-1234-1234-1234-123456789abc'
namespace = dict(BaseHTTPRequestHandler=BaseHTTPRequestHandler, threading=threading,
                 time=time, json=json, os=os, urllib=urllib, traceback=traceback,
                 LOCK=threading.Lock(), PLAY_INFLIGHT_LOCK=threading.Lock(),
                 STEP_PROGRESS={}, STEP_PROGRESS_LOCK=threading.Lock(),
                 TIMING_ON=False, ACTIONS={'fold'}, _last=None,
                 _TS=SimpleNamespace(TournamentError=type('TournamentError', (Exception,), {})),
                 ECONOMY=SimpleNamespace(active_id=lambda:None),
                 _managed_play_state=lambda:None, _token=lambda:17,
                 _stream_gate_open=lambda:'stream1', _stream_gate_close=lambda sid:None,
                 _wrap=lambda r:r)

def step(action, amount, on_bot_action):
    assert namespace['PLAY_INFLIGHT'] == 1
    assert not namespace['_play_absent'](time.time()+100), 'active stream misclassified as absent'
    on_bot_action({'kind':'bot_action','street':'river','seat':3,'action':'check','amount':0})
    emitted.set()
    assert release.wait(3)
    # Still published when the first socket write failed.
    on_bot_action({'kind':'bot_action','street':'river','seat':4,'action':'check','amount':0})
    return {'token':18,'done':True,'view':{'type':'result','hand_no':87}}

namespace['_step'] = step
with tempfile.NamedTemporaryFile() as state:
    namespace['L'] = SimpleNamespace(ST=state.name, load=lambda:{'field':{}},
        _load_field=lambda fd:SimpleNamespace(remaining=lambda:9))
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 '<progress HTTP handlers>', 'exec'), namespace)
    class Disconnected(namespace['H']):
        def _stream_line(self, obj): return False
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1',0), Disconnected)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base = 'http://127.0.0.1:%d' % server.server_port
    errors = []
    def post():
        try:
            req = urllib.request.Request(base+'/api/step-stream',
                data=json.dumps({'token':17,'action':'fold','request_id':request_id}).encode(),
                headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response: response.read()
        except Exception as exc: errors.append(exc)
    client = threading.Thread(target=post)
    client.start()
    try:
        assert emitted.wait(3)
        t0 = time.monotonic()
        with urllib.request.urlopen(base+'/api/step-progress?request_id='+request_id, timeout=1) as response:
            progress = json.load(response)
        assert time.monotonic()-t0 < 1
        assert [m['type'] for m in progress['messages']] == ['stream_start','bot_action']
        assert progress['messages'][1]['seq'] == 1
        release.set()
        client.join(3)
        assert not client.is_alive() and not errors, errors
        with urllib.request.urlopen(base+'/api/step-progress?request_id='+request_id+'&after=2', timeout=1) as response:
            tail = json.load(response)
        assert [m['type'] for m in tail['messages']] == ['bot_action','final']
        assert tail['messages'][0]['seq'] == 2
        assert tail['messages'][1]['payload']['token'] == 18
        assert tail['cursor'] == 4
        assert namespace['PLAY_INFLIGHT'] == 0
        # Retention is bounded; expired requests are not readable.
        for i in range(40): namespace['_step_progress_open']('request-number-%08d' % i)
        assert len(namespace['STEP_PROGRESS']) == 32
        key = next(iter(namespace['STEP_PROGRESS']))
        namespace['STEP_PROGRESS'][key]['updated'] -= 121
        assert namespace['_step_progress_read'](key,0) is None
        print('PASS: progress HTTP responds while gameplay lock is held; disconnected stream retains all events/final; stream protects presence; bounded retention')
    finally:
        release.set()
        server.shutdown()
        server.server_close()
