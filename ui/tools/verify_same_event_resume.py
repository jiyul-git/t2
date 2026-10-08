"""Exercise the real enter handler: returning must preserve live computation."""
import ast
import copy
import pathlib
import threading
import time
from types import SimpleNamespace

root = pathlib.Path(__file__).resolve().parents[2]
tree = ast.parse((root / 'ui/server/ui_server.py').read_text())
handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'H')
fn = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == '_do_POST')

class Economy:
    def __init__(self, offscreen=False, status='playing', active='current'):
        self.active = active
        self.calls = []
        self.state = {'offscreen': offscreen, 'field': {'hero_pid': 0},
                      'hand_seed': 71}
        self.target = {'entries': [{'status': status, 'pid': 0}],
                       'starts_at': time.time()-60, 'state': self.state}
    def event(self, tid): return self.target
    def active_id(self): return self.active
    def load_active(self): return self.state
    def set_active(self, tid): self.calls.append('activate'); self.active = tid
    def request_enter(self, tid, requested=True): self.calls.append(('enter', requested))
    def wallet(self): return {'balance': 9000}

def run(offscreen=False, status='playing', active='current'):
    economy = Economy(offscreen, status, active)
    last = {'token': 73, 'view': {'type': 'decision'}}
    events = {'table2': [{'end': 240}]}
    clock = {'events': copy.deepcopy(events), 'coverage': 240, 'future': object()}
    resets = []
    def reset(): resets.append('clock'); clock.clear()
    ns = dict(LOCK=threading.Lock(), time=time, ECONOMY=economy,
              L=SimpleNamespace(STATE_STORE=None), _last=last,
              _clear_worker=lambda: resets.append('worker'), _vclock_reset=reset)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<enter-handler>', 'exec'), ns)
    h = SimpleNamespace(path='/api/enter', _body=lambda: {'tournament_id': 'current'},
                        _send=lambda code, body: (code, body))
    code, out = ns['_do_POST'](h)
    assert code == 200, out
    if not offscreen and status == 'playing' and active == 'current':
        assert not resets, ('returning to the same table discarded work', resets)
        assert ns['_last'] is last and clock['events'] == events
        assert clock['coverage'] == 240 and not economy.calls
    else:
        assert resets == ['worker', 'clock']
        assert ns['_last'] is None and ('enter', True) in economy.calls

run()
run(offscreen=True)
run(status='waiting')
run(status='reserved')
run(active=None)
print('PASS: same-table return preserves decision and speculative work; genuine admissions reset')
