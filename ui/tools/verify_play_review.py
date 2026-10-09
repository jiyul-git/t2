"""Public history must identify its event and reveal only dealt board cards."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

ROOT = Path(__file__).resolve().parents[2]
tree = ast.parse((ROOT / 'ui/server/ui_server.py').read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_public_history')
with tempfile.TemporaryDirectory() as td:
    archive = Path(td) / 'archive.jsonl'
    def hand(no, event=None, board=None):
        return dict(hand_no=no, tournament_id=event, hero=9,
                    seat_pid={'1': 41, '9': 100},
                    hole={'9': ['Ac', 'Kd'], '1': ['As', 'Ad']},
                    board=['2c', '3c', '4c', '5c', '6c'],
                    result={'board': board or [], 'shown_hole': {}})
    archive.write_text('\n'.join(json.dumps(h) for h in [
        hand(103), hand(1, 'old'), hand(2, 'current'),
        hand(3, 'current', ['2c', '3c', '4c'])]))
    state = {'tournament_id': 'current'}
    ns = {'json': json, 'L': SimpleNamespace(load=lambda: state),
          '_SP': SimpleNamespace(resolve_read=lambda _: {'path': str(archive)})}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<history>', 'exec'), ns)
    result = ns['_public_history']()
    assert [h['hand_no'] for h in result] == [3, 2]
    assert result[0]['board'] == ['2c', '3c', '4c']
    assert result[1]['board'] == []
    assert all(h['shown'] == {} and h['hero_hole'] == ['Ac', 'Kd'] for h in result)
    assert all(h['seat_pid'] == {'1': 41, '9': 100} for h in result)
    state.clear()
    assert [h['hand_no'] for h in ns['_public_history']()] == [103]
print('PASS: event isolation, preflop/flop board privacy, legacy standalone history')

# Recording a size veto must not change the action or consume another draw.
import random
import sys
from unittest.mock import patch
sys.path.insert(0, str(ROOT))
import plan
rng = random.Random(71)
expected = random.Random(71)
expected.random()
with patch.object(plan, 'decide_aggression', return_value=(1.0, 'test')), \
     patch.object(plan, 'decide_size', return_value=0):
    result = plan.attach_intent({'plan': 'bluff_2street', 'rel': 0.2},
        ['Ks', 'Qs'], ['7s', 'Ad', '7h', '7c', '2c'], None, None,
        {}, 19600, 6337, 'river', rng, 1, 0, False, True)
assert result['intents']['river']['act'] == 'check'
assert result['trace'][-1]['kind'] == 'size_veto'
assert rng.getstate() == expected.getstate()
print('PASS: zero-size veto explains final check without changing RNG')
