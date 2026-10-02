#!/usr/bin/env python3
"""Compare extracted semantic boundaries to the actual pre-refactor functions.

No frozen baseline is updated. Full action/RNG captures are a separate gate.
"""
import ast,copy,itertools,json,pathlib,random,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import plan as P,ranges as R,persona as PS,preflop as PF,bot
BASE='4b9d33d5f951fce4b292f6e6e79caaf141b106d2'
def legacy(module,names):
 source=subprocess.check_output(['git','show',BASE+':'+module.__name__+'.py'],cwd=ROOT,text=True)
 tree=ast.parse(source);body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 ns=dict(vars(module));exec(compile(ast.Module(body=body,type_ignores=[]),'<pristine-functions>','exec'),ns)
 return ns
oldp=legacy(P,{'checkraise_decision','cbet_freq','river_fix'})
oldr=legacy(R,{'_continue_range','_call_range','perceived_range','perceived_continue_range','perceived_facing_bet_response'})
checks=0
profiles=[PS.make_player(random.Random(k),0.6,k) for k in [7,21,98]]+[{'type':'TAG','aggr':5,'bluff':5}]
for p,street,plan,outs,rel,seed in itertools.product(profiles,['flop','turn','river'],['trap','semibluff','bluff_2street','river_bluff','showdown'],[0,7,8,12],[.0,.62,.72,.89,.94],[0,17]):
 st={'plan':plan,'outs':outs,'rel':rel};args=(['As','Kd'],['2c','7h','Ts'],p,st,2000,600,9000,street)
 assert P.checkraise_decision(*args,seed=seed)==oldp['checkraise_decision'](*args,seed=seed);checks+=1
boards=[['Ac','7d','2s'],['Ac','7d','2s','Th'],['Ac','7d','2s','Th','9c']]
for p,street,board,n in itertools.product(profiles,['flop','turn','river','unknown'],boards,[1,3]):
 args=(p,board,n,street,False,.72)
 assert P.cbet_freq(*args,range_adv=.18)==oldp['cbet_freq'](*args,range_adv=.18);checks+=1
base={c:float(1+i%3) for i,c in enumerate(R.ALL[:140])}
for p,street,board,size in itertools.product(profiles,['flop','turn','river'],boards,[0,.35,.7,1.5]):
 for name in ['_continue_range','_call_range']:
  args=(base,board,street,size,.75);assert getattr(R,name)(*args)==oldr[name](*args);checks+=1
 for name in ['perceived_continue_range','perceived_facing_bet_response']:
  args=(base,board,street,size,p);assert getattr(R,name)(*args)==oldr[name](*args);checks+=1
 args=(base,board,[('flop','bet',size)],p,None)
 assert R.perceived_range(*args)==oldr['perceived_range'](*args);checks+=1
for p,plan,rel,hand in itertools.product(profiles,['value_2street','pot_control','semibluff','showdown'],[.1,.6,.94],[['As','Kd'],['9d','9h']]):
 a=random.Random(18);b=random.Random(18);st={'plan':plan,'rel':rel,'outs':9}
 args=(st,hand,boards[-1],p,None)
 assert P.river_fix(*copy.deepcopy(args),rng=a)==oldp['river_fix'](*copy.deepcopy(args),rng=b)
 assert a.getstate()==b.getstate();checks+=1
for hand in R.ALL:
 assert PF.legacy_preflop_order_percentile(hand)==PF.PCT[PF.cls(hand)]==PF.pct(hand);checks+=1
assert P.draw_completion_supports_value(3,.619999) is False
assert P.draw_completion_supports_value(4,0) is True
assert P.strength_improvement_supports_value(.7,.7) is False
assert P.strength_improvement_supports_value(.700001,.7) is True
print(json.dumps({'pass':True,'comparisons':checks,'baseline':BASE,'river_rng_states_equal':True}))
