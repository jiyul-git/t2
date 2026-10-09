import ast
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / 'server/ui_server.py'
if not path.exists():
    path = Path(__file__).resolve().parent / 'ui_server.py'
tree = ast.parse(path.read_text())
names = {'_hero_hand_numbers', '_display_hand_number', '_display_hand_response'}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
with tempfile.TemporaryDirectory() as td:
    archive = Path(td) / 'archive.jsonl'
    rows = [
        {'tournament_id': 'old', 'hand_no': 61, 'result': {}},
        {'tournament_id': 'new', 'hand_no': 41, 'result': {}},
        {'tournament_id': 'new', 'hand_no': 42, 'result': {}},
        {'tournament_id': 'new', 'hand_no': 66, 'result': {}},
        {'tournament_id': 'new', 'hand_no': 66, 'result': {}},
        {'tournament_id': 'new', 'hand_no': 67},
    ]
    archive.write_text('\n'.join(json.dumps(r) for r in rows)+'\n{unfinished')
    ns = {'json': json, 'os': os,
          '_SP': SimpleNamespace(resolve_read=lambda _: {'path': str(archive)})}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    st = {'tournament_id': 'new', 'field': {'hand_no': 80}, 'hand_seed': 123}
    before = copy.deepcopy(st)
    assert ns['_hero_hand_numbers'](st) == {41: 1, 42: 2, 66: 3}
    assert ns['_display_hand_number'](st) == 4
    response = {'token': '123:4', 'view': {'hand_no': 80},
                'opening_view': {'hand_no': 80}}
    original = copy.deepcopy(response)
    out = ns['_display_hand_response'](response, st)
    assert out['view'] == {'hand_no': 80, 'display_hand_no': 4}
    assert out['opening_view']['display_hand_no'] == 4
    assert out['token'] == response['token']
    assert st == before and response == original
    # Finishing the current hand keeps the same ordinal, then the next advances.
    with archive.open('a') as fp:
        fp.write('\n'+json.dumps({'tournament_id': 'new', 'hand_no': 80, 'result': {}})+'\n')
    assert ns['_display_hand_number'](st) == 4
    st['field']['hand_no'] = 81
    assert ns['_display_hand_number'](st) == 5
    st['hand_seed'] = None
    assert ns['_display_hand_number'](st) == 4
    st['pending_archive'] = {'tournament_id': 'new', 'hand_no': 81, 'result': {}}
    assert ns['_display_hand_number'](st) == 5
    # A new event starts at 1 even if off-screen bot work already reached 90.
    st = {'tournament_id': 'next', 'field': {'hand_no': 90}, 'hand_seed': 456}
    assert ns['_display_hand_number'](st) == 1
print('PASS: tournament reset, bot-counter gaps, dedup, refresh, pending archive, unchanged engine IDs')
