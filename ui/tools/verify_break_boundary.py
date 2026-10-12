"""Scheduled 55:00 crossing after a hand result must return a break response."""
import ast
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import tournament_store as TS
import time

tree = ast.parse((ROOT / 'ui/server/ui_server.py').read_text())
names = {'_clock_values', '_sync_clock', '_ui_timing'}
ns = {'time': time, 'math': math, '_TS': TS, 'PLAY_WINDOW_SECONDS': 3300}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                             and n.name in names], type_ignores=[]), '<clock>', 'exec'), ns)
state = {'tournament_id': 'standard:test', 'tournament_started_at': 1000,
         'hand_seed': 123, 'field': {'virtual_play_seconds': 3290, 'level_minutes': 5}}
ns['_sync_clock'](state, 4324)
assert not state.get('ui_break_pending'), 'finish the active hand first'
state['hand_seed'] = None
# Run the actual next-deal HTTP gate, with no previously saved break flag.
gate = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
            and "_st.get('ui_break_pending')" in ast.unparse(n.test)
            and any(isinstance(v, ast.Constant) and v.value == 'break_active'
                    for v in ast.walk(n)))
sync = ast.parse('_sync_clock(_st)').body[0]
fn = ast.FunctionDef(name='gate', args=ast.arguments(posonlyargs=[], args=[],
    kwonlyargs=[], kw_defaults=[], defaults=[]), body=[sync, gate], decorator_list=[])
module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
saved = []
ns.update(_st=state, _last={'token': 69}, L=SimpleNamespace(save=lambda st: saved.append(st)),
          self=SimpleNamespace(_send=lambda status, payload: (status, payload)))
exec(compile(module, '<actual-next-deal-gate>', 'exec'), ns)
with patch.object(time, 'time', return_value=4324):
    status, response = ns['gate']()
assert status == 409 and response['code'] == 'break_active', response
assert response['break_remaining'] == 276 and saved
assert ns['_ui_timing'](state, 4399)['break_remaining'] == 201
ns['_sync_clock'](state, 4600)
assert not state['ui_break_pending']
assert ns['_ui_timing'](state, 4600)['break_remaining'] == 0
print('PASS: active hand finishes at 55:24; break gate returns 4:36, expires at 60:00')
