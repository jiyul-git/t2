#!/usr/bin/env python3
"""Independent divergent-history merge contract; original audits stay unchanged."""
import argparse,collections,json,os,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
TEST3='2781cd547128a616424facedf60ef8654f99d775'
APPROVED='2b81f8b5eb5f94c80f75218a9c919cea12d1e283'
MERGED_TREE='905c2e603e7863116d5792d13504baa71ae176c7'
ADDITIONS={'tools/verify_p17_test3_contract.py','tools/compare_p17_test3_traces.py','.github/workflows/p17-test3-integration.yml','docs/semantic_audit/P17_TEST3_INTEGRATION.md','tools/p17_clock_context.cjs','tools/verify_p17_late_break.py'}
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
 if isinstance(a,dict):
  rows=[]
  for k in sorted(a.keys()|b.keys()):
   if k not in a or k not in b:rows.append((p+(str(k),),a[k] if k in a else {'missing_key':True},b[k] if k in b else {'missing_key':True}))
   else:rows.extend(differences(a[k],b[k],p+(str(k),)))
  return rows
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
def parity(out):
 import concurrent.futures
 out.mkdir(parents=True,exist_ok=True)
 # Preserve the original default-policy failure and every original assertion.
 legacy=subprocess.run([sys.executable,'tools/verify_p17_final_integration.py','parity',str(out/'legacy')],cwd=ROOT,capture_output=True,text=True,timeout=1200)
 (out/'legacy_original.log').write_text(legacy.stdout+legacy.stderr)
 assert legacy.returncode==1 and "('0', 11, 'behavior changed')" in legacy.stdout+legacy.stderr
 with tempfile.TemporaryDirectory(prefix='p17_parity_') as td:
  roots={'test3':pathlib.Path(td)/'test3','approved':pathlib.Path(td)/'approved','merged_default':ROOT,'merged_normal_muck':ROOT}
  for label,sha in [('test3',TEST3),('approved',APPROVED)]:subprocess.run(['git','worktree','add','--detach',str(roots[label]),sha],cwd=ROOT,check=True,capture_output=True)
  try:
   def capture(case):
    label,mode,seed=case;env={k:v for k,v in os.environ.items() if not k.startswith(('T2_','PYTHON'))};env.update(PYTHONHASHSEED='0',T2_RANGE_CONDITIONAL_V1=mode)
    if label.startswith('merged'):env['T2_SHOWDOWN_MUCK']='1' if label=='merged_normal_muck' else '0'
    dest=out/f'{label}_{mode}_{seed}.json'
    r=subprocess.run([sys.executable,'tools/r2_baseline_sim.py',str(seed),'8',str(dest)],cwd=roots[label],env=env,capture_output=True,text=True,timeout=600)
    (out/f'{label}_{mode}_{seed}.log').write_text(r.stdout+r.stderr);assert r.returncode==0,(case,r.stderr)
    return case,json.loads(dest.read_text())
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:data=dict(pool.map(capture,[(l,m,s) for l in roots for m in ('0','1') for s in (11,12)]))
  finally:
   for label in ('test3','approved'):subprocess.run(['git','worktree','remove','--force',str(roots[label])],cwd=ROOT,check=True,capture_output=True)
 rows=[]
 for mode in ('0','1'):
  for seed in (11,12):
   t,a,i,c=(data[l,mode,seed] for l in roots)
   assert t['hands']==i['hands'],(mode,seed,'existing test3 actions/cards/chips not preserved')
   metadata=differences(t,i)
   for path,before,after in metadata:
    # The approved preflop contract explicitly records unavailable comparison
    # as None; original test3 omits this key. This permits neither action changes
    # nor deletion/replacement of any existing value or other metadata.
    assert len(path)==4 and path[0]=='pf' and path[2:] == ('seed','pf_calloff_compare') and before=={'missing_key':True} and after is None,(mode,seed,path,before,after)
   assert a==c,(mode,seed,'approved behavior not preserved under identical muck policy',differences(a,c)[:3])
   delta=differences(a,i);first=None
   for old,new in zip(a['hands'],i['hands']):
    if old['full_log']!=new['full_log']:
     j=next((j for j,(x,y) in enumerate(zip(old['full_log'],new['full_log'])) if x!=y),min(len(old['full_log']),len(new['full_log'])))
     first={'hand':old['hand_no'],'table':old['tid'],'hash':old['hash'],'before':old['full_log'][j:j+1],'after':new['full_log'][j:j+1],'hole':old['hole'],'board_before':old['board'],'board_after':new['board']};break
   rows.append({'mode':mode,'seed':seed,'test3_default_actions_cards_chips_equal':True,'test3_added_explicit_unavailable_comparison_metadata':metadata,'approved_matched_policy_full_json_equal':True,'default_policy_differences':len(delta),'first_action_difference':first})
 (out/'summary.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),'legacy_default_pr27_parity':'FAIL: preserved; policy controlled independently','rows':rows},indent=2));print('PASS independent OFF/ON both-history full JSON',json.dumps(rows))
def late_legacy(out):
 env={k:v for k,v in os.environ.items() if not k.startswith(('T2_','PYTHON'))}
 env.update(T2_TABLE_WORKERS='4',T2_VERIFY_SCHEDULE_BOTS='99',T2_VERIFY_SCHEDULE_DEFER='0',T2_VERIFY_SCHEDULE_LATE='1',T2_VERIFY_SCHEDULE_LATE_SECONDS='3300',T2_VERIFY_SCHEDULE_TIMING='enforce')
 r=subprocess.run([sys.executable,'ui/tools/verify_scheduled_ui.py'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=1200)
 text=r.stdout+r.stderr;(out/'original_55minute_fixture.log').write_text(text)
 assert r.returncode==1 and 'catch-up stalled' in text and '대회 휴식 중' in text and "'sync_seconds': 3300.0" in text,text[-2000:]
 (out/'legacy_summary.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),'exit_code':1,'status':'FAIL: original fixture treats independently verified scheduled break as worker stall; preserved unchanged','next_required_check':'real 99-bot full break/resume/admission with 60-second bound outside break'},indent=2))
 print('Recorded original FAIL; independent break-aware runtime check remains required')
def checks(out,group):
 groups={
 'timing':['tools/verify_timing_familiarity.py','tools/verify_timing_calloff_effort.py','tools/verify_timing_bank_recharge.py','tools/verify_timing_provenance.py','tools/verify_preflop_error_fallback.py','tools/verify_forced_blind_allin_showdown.py','tools/verify_forced_blind_allin_view.py','tools/verify_showdown_muck_toggle.py','tools/verify_hand130_part2.py','tools/verify_timing_strategy_invariance.py'],
 'http':['ui/tools/verify_action_timeout.py','ui/tools/verify_clock_ui.py','ui/tools/verify_timing_clock.py','ui/tools/verify_same_event_resume.py','ui/tools/verify_resume_snapshot.py','ui/tools/verify_stream_write_timeout.py','ui/tools/verify_break_boundary.py','ui/tools/verify_play_review.py','ui/tools/verify_ui.py --hands 6 --entries 18 --seed 20260920 --port 8799'],
 'browser':['ui/tools/verify_resume_ui.js','ui/tools/verify_video_ui_regressions.js','ui/tools/verify_break_transition.js','ui/tools/verify_forced_post_sequence.js','ui/tools/verify_menu_rank_swipe.js','ui/tools/verify_action_clock_js.js','ui/tools/verify_clock_ui_js.js','ui/tools/verify_continuous_clock.js'],
 }
 import shlex,time
 rows=[];legacy=[]
 for name in groups[group]:
  args=shlex.split(name);start=time.monotonic()
  env=dict(os.environ)
  if name=='ui/tools/verify_action_clock_js.js':
   diagnostic=subprocess.run(['node']+args,cwd=ROOT,capture_output=True,text=True,timeout=60)
   assert diagnostic.returncode==1 and 'heroTimeoutAction is not defined' in diagnostic.stderr
   (out/'legacy_incomplete_clock_context.log').write_text(diagnostic.stdout+diagnostic.stderr)
   legacy.append({'test':name,'exit_code':1,'status':'FAIL with omitted real dependency; original assertions unchanged'})
   # Load its actual production dependency, not a mocked return value.
   args=['--require',str(ROOT/'tools/p17_clock_context.cjs')]+args
  if name=='ui/tools/verify_clock_ui.py':
   # The unchanged HTTP fixture deliberately creates a practice tournament.
   # Use the same documented opt-in as verify_ui, with an isolated wallet.
   with tempfile.TemporaryDirectory(prefix='p17_clock_personal_') as td:
    diagnostic_env={k:v for k,v in env.items() if not k.startswith('T2_')};diagnostic_env['T2_DATA_DIR']=td
    diagnostic=subprocess.run([sys.executable]+args,cwd=ROOT,env=diagnostic_env,capture_output=True,text=True,timeout=180)
    assert diagnostic.returncode==1 and 'line 74' in diagnostic.stderr
    (out/'legacy_missing_practice_opt_in.log').write_text(diagnostic.stdout+diagnostic.stderr)
    legacy.append({'test':name,'exit_code':1,'status':'FAIL without required practice opt-in; security rejection preserved'})
    env.update(T2_DATA_DIR=td,T2_ALLOW_PRACTICE_NEW='1',T2_SCHEDULE_ENABLED='0')
    r=subprocess.run([sys.executable]+args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=3450)
  else:r=subprocess.run((['node'] if name.endswith('.js') else [sys.executable])+args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=3450)
  log=name.replace('/','_').replace(' ','_')+'.log';(out/log).write_text(r.stdout+r.stderr)
  row={'test':name,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3),'log':log};rows.append(row);print(json.dumps(row),flush=True)
 (out/'summary.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),'group':group,'checks':rows,'legacy_incomplete_conditions':legacy},indent=2))
 assert all(x['exit_code']==0 for x in rows),[x for x in rows if x['exit_code']]
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('group',choices=['guard','field','origins','parity','late-legacy','timing','http','browser']);ap.add_argument('out',nargs='?',type=pathlib.Path,default=ROOT/'p17-test3-results');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 if a.group=='guard':guard()
 elif a.group=='field':field(a.out)
 elif a.group=='origins':origins(a.out)
 elif a.group=='parity':parity(a.out)
 elif a.group=='late-legacy':late_legacy(a.out)
 else:checks(a.out,a.group)
