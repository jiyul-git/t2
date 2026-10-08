import ast
import pathlib
import sys
from copy import deepcopy

server_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[2] / 'ui/server/ui_server.py'
source = ast.parse(server_path.read_text())
nodes = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == '_resume_response']
ns = {'_ui_timing': lambda st, now: {
    'server_now_ms': int(now * 1000), 'action_deadline_ms': st['deadline'],
    'action_base_deadline_ms': st['base'], 'hero_time_bank': 0,
    'bot_schedule': [e for e in st['schedule'] if e['act_at_ms'] > now * 1000]}}
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<resume>', 'exec'), ns)
schedule = [{'act_at_ms': 500}, {'act_at_ms': 2000}]
cached = {'server_now_ms': 200, 'view': {'hand_no': 61}, 'token': '61:4', 'bot_schedule': schedule}
before = deepcopy(cached)
st = {'deadline': 15000, 'base': 15000, 'schedule': schedule}
out = ns['_resume_response'](cached, st, 1)
assert out['server_now_ms'] == 1000 and out['resume'] is True
assert out['token'] == cached['token'] and out['view'] == cached['view']
assert out['action_deadline_ms'] == 15000 and out['hero_time_bank'] == 0
assert out['bot_schedule'] == schedule # retain timestamps for elapsed actions too
assert cached == before # reading a snapshot never changes cached gameplay
out2 = ns['_resume_response'](cached, st, 2)
assert out2['server_now_ms'] == 2000 and out2['action_deadline_ms'] == 15000
print('resume response: PASS (fresh time, unchanged token/deadline, elapsed schedule)')
