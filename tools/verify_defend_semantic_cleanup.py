"""Compare real pre-checkpoint defend policy with extracted pipeline (9-max first)."""
import ast, itertools, json, pathlib, random, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import preflop as PF
import persona as PS
BASE = '6feaf56319fe2369e1738a4d6dca0c8b755a6c8b'
source = subprocess.check_output(['git', 'show', BASE + ':preflop.py'], cwd=ROOT, text=True)
names = {'defend_thresholds', 'defend_action_likelihoods', 'defend_decision'}
body = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in names]
old = dict(vars(PF))
exec(compile(ast.Module(body=body, type_ignores=[]), '<checkpoint-defend>', 'exec'), old)
profiles = [PS.make_player(random.Random(seed), .6, seed) for seed in (7, 21, 98)] + ['TAG', {'type': 'TAG'}]
counts = {'thresholds': 0, 'likelihoods': 0, 'actions_and_rng': 0}
original = PS.PREFLOP_REASONING_V3
try:
 for optin in (False, True):
  PS.PREFLOP_REASONING_V3 = optin
  for prof, seats, bb, level, callers, positions in itertools.product(profiles, (9, 8), (5, 15, 30, 100), (1, 2, 3, 4, 7), (0, 1, 3), (('BB','BTN'), ('BTN','UTG'), ('BB','SB'))):
   args=(prof, *positions, bb)
   kw=dict(open_bb=2.5, n_callers=callers, raise_level=level, seats=seats, ante=True)
   assert PF.defend_thresholds(*args, **kw) == old['defend_thresholds'](*args, **kw), (optin, args, kw)
   counts['thresholds'] += 1
  for prof, hand, level, bb, allin in itertools.product(profiles[:3], (['As','Ad'], ['Ah','Qd'], ['7c','6c'], ['3h','2d']), (1,2,3,5), (8,30), (False,True)):
   args=(prof,'BB','BTN',hand,bb,bb if allin else 2.5,1)
   kw=dict(raise_level=level,stack_bb=bb,seats=9,ante=True,opener_allin=allin,can_raise=not allin,pot_bb=bb+4,to_call_bb=bb if allin else 1.5)
   assert PF.defend_action_likelihoods(*args,**kw)==old['defend_action_likelihoods'](*args,**kw)
   counts['likelihoods']+=1
   for seed in (0,17):
    a,b=random.Random(seed),random.Random(seed)
    assert PF.defend_decision(*args,a,**kw)==old['defend_decision'](*args,b,**kw)
    assert a.getstate()==b.getstate()
    counts['actions_and_rng']+=1
finally:
 PS.PREFLOP_REASONING_V3=original
print(json.dumps({'pass':True,'baseline':BASE,'comparisons':counts,'seats':'9 primary, 8 compatibility','optin':[False,True]}))
