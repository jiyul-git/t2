"""Stage4: compare actual old consumers, not duplicated formulas."""
import ast, copy, itertools, json, pathlib, random, subprocess, sys
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import persona as PS, preflop as PF, reads as RD, money_pressure as MP, bot
BASE='b4869696a217272a5878841e29efc17b33e0df0c'
def prior(module,names):
 s=subprocess.check_output(['git','show',BASE+':'+module.__name__+'.py'],cwd=ROOT,text=True)
 ns=dict(vars(module));body=[n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name in names]
 exec(compile(ast.Module(body=body,type_ignores=[]),'<prior>', 'exec'),ns);return ns
oldr=prior(RD,{'obs_from_profile'})
oldm=prior(MP,{'exploit_realization','pressure_opportunity'})
oldp=prior(PF,{'multiway_reraise_decision'})
counts={'observation':0,'pressure':0,'multiway_controlled_equity':0,'multiway_real_equity':0}
for rr,att,st in itertools.product([0,4,10],repeat=3):
 p={'concepts':{'range_read':rr,'sizing_tell':st},'temper':{'attention':att,'adaptability':7,'consistency':3}}
 assert RD.obs_from_profile(p)==oldr['obs_from_profile'](p);counts['observation']+=1
for p in [{},{'temper':{}},{'temper':{'attention':5,'adaptability':4,'consistency':3},'concepts':{}}]:
 assert RD.obs_from_profile(p)==oldr['obs_from_profile'](p);counts['observation']+=1
for rr,mj,att in itertools.product([None,0,4,10],repeat=3):
 actor=dict(range_read=rr,money_jump=mj,fold_equity=6,attention=att,adaptability=7,aggression=8)
 assert MP.exploit_realization(actor)==oldm['exploit_realization'](actor);counts['pressure']+=1
 for read in (None,{'w':.7,'fold_gap':.3},{'w':.8,'f2tb_gap':-.3}):
  args=({'stack_start_bb':40,'covered_by_yet_to_act':1},{'stack_start_bb':20},actor,read,'preflop_3bet')
  assert MP.pressure_opportunity(*args)==oldm['pressure_opportunity'](*args);counts['pressure']+=1
pools={'1':[('Qc','Qd'),('Jh','Js')],'2':[('9h','9d'),('8s','8c')]}
def paired(p,can_raise,locked,seed):
 a,b=random.Random(seed),random.Random(seed)
 args=(p,'BB','BTN',['As','Kd'],30,8,1)
 kw=dict(raise_level=2,stack_bb=30,seats=9,can_raise=can_raise,pot_bb=20,to_call_bb=6,opponent_ranges=pools,players_behind=1,decision_seed=42,locked_keys=locked)
 ra=PF.multiway_reraise_decision(*copy.deepcopy(args),a,**copy.deepcopy(kw))
 rb=oldp['multiway_reraise_decision'](*copy.deepcopy(args),b,**copy.deepcopy(kw))
 assert (ra,a.getstate())==(rb,b.getstate()),(ra,rb)
for rr,eq,can_raise,locked,seed in itertools.product([0,5,10],[0,.3,.8],[False,True],[[],['1']],[0,17]):
 p=PS.make_player(random.Random(7),.6,7);p['concepts']['range_read']=rr
 with patch.object(bot,'equity_vs_combos',return_value=eq):paired(p,can_raise,locked,seed)
 counts['multiway_controlled_equity']+=1
p=PS.make_player(random.Random(7),.6,7)
for can_raise,locked in itertools.product([False,True],[[],['1']]):
 paired(p,can_raise,locked,17);counts['multiway_real_equity']+=1
# Role inputs and consumers have separate contracts; no new shared global skill.
assert RD.observation_accuracy_from_capabilities(5,0,5)!=RD.observation_accuracy_from_capabilities(5,10,5)
assert MP.pressure_application_capacity(5,5,0,5,5,5)!=MP.pressure_application_capacity(5,5,10,5,5,5)
assert PF.multiway_evidence_application_capacity(0,5,5)!=PF.multiway_evidence_application_capacity(10,5,5)
assert PF.apply_multiway_call_evidence(.3,.4,.2,.5,0)==(.3,.39999999999999997)
assert PF.apply_multiway_call_evidence(.3,.4,.2,.5,1)==(0.,.7)
print(json.dumps({'pass':True,'baseline':BASE,'comparisons':counts,'boundary_checks':5}))
