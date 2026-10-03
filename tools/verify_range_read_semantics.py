"""Compare real checkpoint functions, including RNG and mutated response state.

Stage 9 B4 intentional changes (ledger "9단계 B4 통합") are excluded from the
identity comparison against BASE and checked as new contracts instead:
  - bias('hero_call'): bluffcatch skill now reduces the bias (mirror of bluff_fear);
  - decide_response no longer re-applies station/bluff_fear/hero_call — call
    threshold biases are applied once in persona.call_bias (calldown_need).
"""
import ast, copy, itertools, json, pathlib, random, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import persona as PS, ranges as R, plan as P
BASE='33df2ee4c113458b3977cf6a6ed419c3bdba940c'
def prior(module,names):
 s=subprocess.check_output(['git','show',BASE+':'+module.__name__+'.py'],cwd=ROOT,text=True)
 body=[n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name in names]
 ns=dict(vars(module));exec(compile(ast.Module(body=body,type_ignores=[]),'<prior>', 'exec'),ns);return ns
oldps=prior(PS,{'bias','read_opponent'})
oldr=prior(R,{'blend_action_range_by_grasp','perceived_range','perceived_continue_range','perceived_facing_bet_response'})
oldp=prior(P,{'decide_response'})
profiles=[]
for skill in (0,1.499999,1.5,2,4,7.38,8,10):
 p=PS.make_player(random.Random(7),.6,7);p['concepts']['range_read']=skill;profiles.append(p)
profiles += [{'type':'TAG'}, None]
counts={'read_and_bias':0,'range':0,'response_action_state_rng':0}
estimates=[None,{}, {'confidence':0,'n':20}, {'confidence':.8,'n':36}, {'confidence':1,'n':80,'bluff':9,'barrel':.8,'ftb':.1,'ftb_turn':.7,'sz_mean':1.2,'pf_3bet':.3}, {'confidence':.3,'n':5,'bluff':0,'ftb':None,'sz_mean':None}]
for p,e in itertools.product(profiles,estimates):
 assert PS.read_opponent(p,e)==oldps['read_opponent'](p,e);counts['read_and_bias']+=1
for p,st,name in itertools.product(profiles,['flop','turn','river',None],PS.BIAS_NAMES):
 if name=='hero_call':continue  # B4 intentional change
 if st is None and name=='bluff_fear':continue  # B5: street now required (no river fallback)
 assert PS.bias(p,name,st)==oldps['bias'](p,name,st);counts['read_and_bias']+=1
# stage9 B5: legacy exploit_weight / application weight retired (single weight
# _exploit_base_weight inside read_opponent, compared above).
base={c:float(1+i%3) for i,c in enumerate(R.ALL[:100])}
for p,st,b,size in itertools.product(profiles,['flop','turn','river'],[['Ac','7d','2s'],['Ac','7d','2s','Th','9c']],[0,.7,1.5]):
 for name in ('perceived_continue_range','perceived_facing_bet_response'):
  args=(base,b,st,size,p)
  assert getattr(R,name)(*args)==oldr[name](*args);counts['range']+=1
 args=(base,b,[(st,'bet',size)],p,None)
 assert R.perceived_range(*args)==oldr['perceived_range'](*args);counts['range']+=1
# Concept profiles: B4 removed the response-side bias re-application, so only
# concept-less profiles (no biases either way) keep byte identity with BASE.
for p,st,eq,need,layer in itertools.product(profiles[8:9],['flop','turn','river'],[.1,.4,.8],[.2,.5],[False,True]):
 a,b=random.Random(17),random.Random(17);sa={'rel':.3,'made':1};sb=copy.deepcopy(sa)
 args=(p,['As','Kd'],['Ac','7d','2s'],st,'showdown')
 kw={'allow_raise':False,'call_eq':eq if layer else None,'call_need':need if layer else None}
 ra=P.decide_response(*args,sa,eq,need,1,None,100,30,500,0,a,**kw)
 rb=oldp['decide_response'](*args,sb,eq,need,1,None,100,30,500,0,b,**kw)
 assert (ra,sa,a.getstate())==(rb,sb,b.getstate());counts['response_action_state_rng']+=1
# Actual boundary contracts: role-specific inputs affect distinct output objects.
full=R.range_select(base,list(base)[:20])
assert R.reconstruct_range_with_accuracy(base,full,2)!=R.reconstruct_range_with_accuracy(base,full,8)
e={'confidence':1,'n':30,'bluff':9}
low=PS.interpret_opponent_action_signals(e,1,0,1,.5)
high=PS.interpret_opponent_action_signals(e,1,1,1,.5)
assert low['bluff_gap']==0 and high['bluff_gap']==1 and low['w']==high['w']==.5
# B4 contract: biases enter the call threshold once (persona.call_bias); the
# response compares eq with the need it was given.
hc=PS.make_player(random.Random(3),.3,3);hc['concepts']['bluffcatch_river']=0.0;hc['temper']['aggression']=10.0
assert PS.bias(hc,'hero_call','river')>0 and PS.call_bias(hc,'river',1.0,1,0)<PS.call_bias(hc,'flop',0.3,1,0)
mx=copy.deepcopy(profiles[7]);mx['concepts']['bluffcatch_river']=10.0
assert PS.bias(mx,'hero_call','river')<=PS.bias(hc,'hero_call','river')
r=P.decide_response(profiles[7],['As','Kd'],['Ac','7d','2s','Th','9c'],'river','showdown',{'rel':.3,'made':1},.41,.40,1,None,100,30,500,0,random.Random(1),allow_raise=False)
assert r[0]=='call' and abs(r[2]-.40)<1e-12
print(json.dumps({'pass':True,'baseline':BASE,'comparisons':counts,'boundary_checks':4}))
