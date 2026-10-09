"""Run with python3 tools/verify_river_nuts_value.py in the repository.

Actual evaluator and response code; deterministic opponent continuation models
isolate sizing decisions from range-estimation changes.
"""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'plan.py').exists():
    ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot

tree = ast.parse((ROOT / 'plan.py').read_text())
names = {'river_nut_value_response', 'decide_response'}
code = ast.Module(body=[n for n in tree.body
                       if isinstance(n, ast.FunctionDef) and n.name in names],
                  type_ignores=[])
mode = 'all'
def items(pool):
    return list(pool.items()) if isinstance(pool, dict) else [(tuple(c), 1.) for c in pool]
def cont(pool, board, street, price, profile=None):
    return pool if mode == 'all' or price <= 1/3 else {}
ns = {'bot': bot, 'R': SimpleNamespace(range_items=items,
                                      perceived_continue_range=cont)}
exec(compile(code, str(ROOT / 'plan.py'), 'exec'), ns)
choose = ns['river_nut_value_response']
board = ['Js', '6h', 'Tc', '3h', 'Qs']
hero = ['Ac', 'Ks']
pool = {('Td', 'Jh'): 3., ('Ad', 'Kh'): 1., ('Ac', 'Qd'): 100.}
ctx = {'facing_stack': 20000., 'facing_contrib': 1000.}
def run(**changes):
    args = dict(profile={}, hero=hero, board=board, street='river',
                opp_range=pool, pot=10000, tocall=1000, stack=40000,
                hero_contrib=0, response_context=ctx, n_opp=1,
                allow_raise=True)
    args.update(changes)
    return choose(**args)

r = run()
assert r[0] == 'raise' and r[2]['target'] == 21000, r
assert r[2]['exact_nuts'] and r[2]['call_ev'] == 8625, r
assert all(0 <= c['continue_p'] <= 1 for c in r[2]['candidates'])
mode = 'small'
r = run()
assert r[0] == 'raise' and r[2]['target'] == 6000, r
assert r[2]['candidates'][-1]['continue_p'] == 0
mode = 'all'
assert run(allow_raise=False)[0] == 'call'
assert run(response_context={'facing_stack': 0, 'facing_contrib': 1000})[0] == 'call'
assert run(stack=1000)[0] == 'call'
assert run(hero=['9c', '8s']) is None  # lower straight, AK beats it
assert run(board=['Jh', '6h', 'Th', '3c', 'Qs']) is None  # flush beats AK
assert run(street='turn', board=board[:4]) is None
assert run(board=['As', 'Ks', 'Qs', 'Js', 'Ts'], hero=['2c', '3d']) is None
assert run(hero_contrib=2000, tocall=1000,
           response_context={'facing_stack': 20000, 'facing_contrib': 3000})[2]['target'] == 23000
assert run(opp_range={}, n_opp=2)[0] == 'raise'

class NoFrequencyRoll:
    def random(self):
        raise AssertionError('exact river nuts must not roll a call frequency')

for concepts in (False, True):
    for plan in ('value_3street', 'trap', 'giveup'):
        state = {'rel': .2}
        result = ns['decide_response'](
            {'concepts': concepts, 'aggr': 1}, hero, board, 'river',
            plan, state, .9925, .3908, 4, pool, 10000, 1000, 40000,
            False, NoFrequencyRoll(), response_context=ctx)
        assert result[0] == 'raise', result
        assert state['_last_river_nuts_value']['exact_nuts']

print('PASS: Hand61 nuts, no frequency call, value size/all-in EV, blockers, ties, legality, non-nuts')
