#!/usr/bin/env python3
"""Independent divergent-history merge contract; original audits stay unchanged."""
import argparse,collections,json,os,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
TEST3='2781cd547128a616424facedf60ef8654f99d775'
APPROVED='2b81f8b5eb5f94c80f75218a9c919cea12d1e283'
MERGED_TREE='905c2e603e7863116d5792d13504baa71ae176c7'
ADDITIONS={'tools/verify_p17_test3_contract.py','tools/compare_p17_test3_traces.py','.github/workflows/p17-test3-integration.yml','docs/semantic_audit/P17_TEST3_INTEGRATION.md'}
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def guard():
 expected=git('merge-tree','--write-tree',TEST3,APPROVED);assert expected==MERGED_TREE,expected
 paths=set()
 for row in git('ls-tree','-r',expected).splitlines():
  meta,p=row.split('\t');mode,kind,sha=meta.split();assert kind=='blob';paths.add(p)
  assert (ROOT/p).exists() and git('hash-object',p)==sha,p
 tracked=set(git('ls-files').splitlines());assert tracked-paths==ADDITIONS,tracked-paths
 ancestor=git('merge-base',TEST3,APPROVED);assert ancestor=='76437820195909cda6be7ffea2813262d785bb38'
 left=set(git('diff','--name-only',ancestor,TEST3).splitlines());right=set(git('diff','--name-only',ancestor,APPROVED).splitlines())
 for p in left-right:assert git('hash-object',p)==git('rev-parse',TEST3+':'+p),p
 for p in right-left:assert git('hash-object',p)==git('rev-parse',APPROVED+':'+p),p
 for p in left&right:
  if p not in ('session.py','live2.py'):assert git('rev-parse',TEST3+':'+p)==git('rev-parse',APPROVED+':'+p)==git('hash-object',p),p
 assert git('hash-object','tools/audit_p9_pr30_mc_contract.py')=='1538f0c8ea79ebbfd605344f2b10305f2f754171'
 from verify_p17_c4_integration import runtime
 runtime()
 print('PASS exact two-parent merge tree; all original files/test3-only paths/approved sources/frozen/P9 preserved')
def differences(a,b,p=()):
 if type(a)!=type(b):return [(p,a,b)]
 if isinstance(a,dict):return [d for k in sorted(a.keys()|b.keys()) for d in differences(a.get(k),b.get(k),p+(str(k),))]
 if isinstance(a,list):
  if len(a)!=len(b):return [(p+('length',),len(a),len(b))]
  return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,p+(str(i),))]
 return [] if a==b else [(p,a,b)]
def origins(out):
 import verify_p15_pr27_origins as p
 out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='p17_origins_') as td:
  old=pathlib.Path(td)/'approved';subprocess.run(['git','worktree','add','--detach',str(old),APPROVED],cwd=ROOT,check=True,capture_output=True)
  try:
   report=[]
   for mode in ('off','on'):
    values={}
    for label,root,muck in [('approved',old,None),('merged_default',ROOT,'0'),('merged_normal_muck',ROOT,'1')]:
     state=pathlib.Path(td)/(label+mode);state.mkdir()
     env={k:v for k,v in os.environ.items() if not k.startswith(('T2_','PYTHON'))}
     env.update(T2_LIVE_STATE=str(state/'state.json'),T2_HAND_ARCHIVE=str(state/'hands.jsonl'),T2_BOT_LOG='0',T2_TABLE_WORKERS='1',T2_TIMING_V1=mode,PYTHONHASHSEED='0')
     if muck is not None:env['T2_SHOWDOWN_MUCK']=muck
     r=subprocess.run([sys.executable,str(ROOT/'tools/verify_p15_pr27_origins.py'),'--probe','--root',str(root)],cwd=state,env=env,capture_output=True,text=True,timeout=180)
     assert r.returncode==0,(label,mode,r.stderr);d=json.loads(r.stdout);values[label]=d
     (out/(label+'_'+mode+'.json')).write_text(json.dumps(d,sort_keys=True))
     p.verify_origins(d)
    assert values['approved']['outcomes']==values['merged_normal_muck']['outcomes'],mode
    delta=differences(values['approved']['outcomes'],values['merged_default']['outcomes'])
    assert delta, 'fixture must observe existing test3 show-all behavior'
    for path,a,b in delta:
     observation=('state' in path and 'field' in path and (('book' in path and path[-1] in ('showdowns','sd_strong')) or ('tilt' in path and 'shown' in path)))
     assert observation,(mode,path,a,b)
    report.append({'timing':mode,'normal_muck_full_state_actions_chips_rng_equal':True,'default_show_all_observation_differences':len(delta),'kinds':dict(collections.Counter(path[-1] for path,a,b in delta)),'first_difference':delta[0],'epoch_origins':p.verify_origins(values['merged_default'])})
   # Keep and execute the historical exact-PR27 audit. Its failed equality is
   # recorded as a diagnostic, not relabelled PASS. The new controlled contract
   # above proves the specific default-showdown difference and full RNG/state.
   legacy=subprocess.run([sys.executable,str(ROOT/'tools/verify_p15_pr27_origins.py')],cwd=ROOT,capture_output=True,text=True,timeout=180)
   (out/'original_pr27_equality.log').write_text(legacy.stdout+legacy.stderr)
   assert legacy.returncode==1 and 'game/state/RNG changed: off' in legacy.stderr
   (out/'summary.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),'approved':APPROVED,'legacy_exact_pr27_equality_exit':legacy.returncode,'legacy_status':'FAIL: incompatible blanket equality; existing test3 show-all observations independently attributed','results':report},indent=2))
   print(json.dumps(report,ensure_ascii=False));print('PASS independent synchronous/deferred/vclock/legacy origins, controlled whole-state/RNG and default-show-all attribution')
  finally:subprocess.run(['git','worktree','remove','--force',str(old)],cwd=ROOT,check=True,capture_output=True)
def field(out):
 import verify_p17_final_integration as p
 p.GROUPS['field']=[x for x in p.GROUPS['field'] if x!='tools/verify_p15_pr27_origins.py']
 p.run_group('field',out);origins(out/'origins')
def checks(out,group):
 groups={
 'timing':['tools/verify_timing_familiarity.py','tools/verify_timing_calloff_effort.py','tools/verify_timing_bank_recharge.py','tools/verify_timing_provenance.py','tools/verify_preflop_error_fallback.py','tools/verify_forced_blind_allin_showdown.py','tools/verify_forced_blind_allin_view.py','tools/verify_showdown_muck_toggle.py','tools/verify_hand130_part2.py','tools/verify_timing_strategy_invariance.py'],
 'http':['ui/tools/verify_action_timeout.py','ui/tools/verify_clock_ui.py','ui/tools/verify_timing_clock.py','ui/tools/verify_same_event_resume.py','ui/tools/verify_resume_snapshot.py','ui/tools/verify_stream_write_timeout.py','ui/tools/verify_break_boundary.py','ui/tools/verify_play_review.py','ui/tools/verify_ui.py --hands 6 --entries 18 --seed 20260920 --port 8799'],
 'browser':['ui/tools/verify_resume_ui.js','ui/tools/verify_video_ui_regressions.js','ui/tools/verify_break_transition.js','ui/tools/verify_forced_post_sequence.js','ui/tools/verify_menu_rank_swipe.js','ui/tools/verify_action_clock_js.js','ui/tools/verify_clock_ui_js.js','ui/tools/verify_continuous_clock.js'],
 }
 import shlex,time
 rows=[]
 for name in groups[group]:
  args=shlex.split(name);start=time.monotonic()
  r=subprocess.run((['node'] if args[0].endswith('.js') else [sys.executable])+args,cwd=ROOT,capture_output=True,text=True,timeout=1800)
  log=name.replace('/','_').replace(' ','_')+'.log';(out/log).write_text(r.stdout+r.stderr)
  row={'test':name,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3),'log':log};rows.append(row);print(json.dumps(row),flush=True)
 (out/'summary.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),'group':group,'checks':rows},indent=2))
 assert all(x['exit_code']==0 for x in rows),[x for x in rows if x['exit_code']]
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('group',choices=['guard','field','origins','timing','http','browser']);ap.add_argument('out',nargs='?',type=pathlib.Path,default=ROOT/'p17-test3-results');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 if a.group=='guard':guard()
 elif a.group=='field':field(a.out)
 elif a.group=='origins':origins(a.out)
 else:checks(a.out,a.group)
