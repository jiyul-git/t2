#!/usr/bin/env python3
import json,pathlib,subprocess,sys,random
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE='3f30cc82540dc6d69fbf22295f49da20194626a4';FIX='b83db843514b37ff5680380f8e81f709ade3c46b'
def source(sha,p):return subprocess.check_output(['git','show',sha+':'+p],cwd=ROOT)
def guard():
 selected=['plan.py','runner.py','tools/verify_replan_contract.py','tools/verify_p11_c4_runtime.py','.github/workflows/p11-replan-c4.yml']
 for p in selected:assert (ROOT/p).read_bytes()==source(FIX,p),p
 allowed=set(selected)|{'tools/verify_p17_c4_integration.py','.github/workflows/p17-c4-final.yml','docs/semantic_audit/P17_C4_FINAL.md'}
 changed=set(subprocess.check_output(['git','diff','--name-only',BASE,'HEAD'],cwd=ROOT,text=True).splitlines())
 assert changed<=allowed,changed-allowed
 for p in list(ROOT.glob('*.py'))+list(ROOT.glob('*.json'))+list((ROOT/'tools').glob('baseline_9max*.json')):
  name=str(p.relative_to(ROOT))
  if name not in ('plan.py','runner.py'):assert p.read_bytes()==source(BASE,name),name
 for p in ['ui/tools/setup_run_dir.py','ui/tools/setup_run_dir.sh','ui/tools/predeploy_check.sh']:assert (ROOT/p).read_bytes()==source(BASE,p),p
 for r in json.loads((ROOT/'docs/semantic_audit/p17-integration-20261011/selected_sources.json').read_text()):
  if r['path']!='plan.py':assert (ROOT/r['path']).read_bytes()==source(r['source_sha'],r['path']),r['path']
 assert subprocess.check_output(['git','hash-object','tools/audit_p9_pr30_mc_contract.py'],cwd=ROOT,text=True).strip()=='1538f0c8ea79ebbfd605344f2b10305f2f754171'
 print('PASS exact PR32 five files; PR31 packaging/protected sources/P9/frozen bytes preserved')
def runtime():
 from unittest.mock import patch
 import plan,runner
 class Reached(Exception):pass
 seen=[]
 def revised(*args,**kw):
  assert kw['tilt']==7.25 and kw['bb_chips']==333
  seen.append('update_to_revise');raise Reached()
 before=random.getstate()
 with patch.object(runner,'revise_plan',side_effect=revised):
  try:plan.update_plan({'plan':'value_3street'},['Ac','Kh'],['2c','7c','9h','Tc'],[],[],{'concepts':{}},1000,2000,'turn',seed=11,n_opp=1,behind=0,oop=False,initiative=True,prev_board=['2c','7c','9h'],tilt=7.25,bb_chips=333)
  except Reached:pass
 assert seen==['update_to_revise']
 def make(*args,**kw):
  assert kw['tilt']==7.25 and kw['bb_chips']==333
  seen.append('revise_to_make');return {'plan':'value_3street'}
 with patch.object(plan,'make_plan',side_effect=make):
  runner.revise_plan({},['Ac','Kh'],['2c','7c','9h','Tc'],[],[],{'concepts':{}},1000,2000,'turn',11,1,0,['2c','7c','9h'],tilt=7.25,bb_chips=333)
 assert seen==['update_to_revise','revise_to_make'] and random.getstate()==before
 print('PASS nonzero tilt7.25 and BB333 forwarded unchanged at both actual boundaries; shared RNG preserved')
def a6(path):
 d=json.loads(pathlib.Path(path).read_text());assert d['old_event_count']==d['new_event_count']==849
 for arm in ['bb_only','fixed']:
  v=d['arms'][arm];assert v['decision_changed']==1 and v['diff_kinds'].get('size')==1 and v['diff_kinds'].get('stackoff')==21
  assert all(v['diff_kinds'].get(k,0)==0 for k in ['plan','act','rng'])
 assert d['arms']['tilt_only']['decision_changed']==0
 assert d['live'].get('live_tournament_action_changed')==1
 assert all(d['live'].get(k,0)==0 for k in ['live_final_stack_changed','live_rng_changed','live_busted_order_changed'])
 e=next(e for e in d['examples'] if e['event']==143 and e['arm']=='fixed');assert e['street']=='river'
 a,b=e['before'],e['after'];assert a['plan']==b['plan']=='value_3street' and a['act']==b['act']=='bet'
 assert a['size']==0.656 and b['size']==0.615
 print('PASS independent 849-event review, one sizing change,21 stackoff changes,event143 bet0.656->0.615; final stacks/RNG/bust preserved')
if __name__=='__main__':
 if sys.argv[1]=='a6':a6(sys.argv[2])
 else:guard();runtime()
