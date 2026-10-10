#!/usr/bin/env python3
"""P17 exact-source integration gates. No production mutation or baseline writes."""
import argparse, concurrent.futures, hashlib, json, os, pathlib, platform, subprocess, sys, tempfile, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE='3c434b28046643ba54c04447951ad148ae6f9c1c'
P29='a2fdc02ab874371b04469ff36d917009542f0ab8'
P30='2c2acdcc10874c0c6efb205f6684423ac37b04e2'
GROUPS={
'mc': ['tools/audit_p9_pr30_mc_contract.py','tools/verify_p10_postflop_mc_unavailable.py','tools/verify_p10_range_provenance.py','tools/verify_f3_checkraise_response.py','tools/verify_f4_facing_bet.py','tools/verify_f5_backaction.py','tools/verify_river_nuts_value.py','tools/verify_postflop_events.py','tools/verify_hand130_mc_contract.py','tools/verify_hand130_b37_replay.py','tools/verify_hand130_calloff_isolation.py','tools/verify_hand130_exact_icm.py','tools/verify_hand130_partial_call_icm.py','tools/verify_hand130_skill_semantics.py','tools/verify_calloff_price_routing.py','tools/verify_hand130_mc_sensitivity.py','tools/verify_hand130_conditioned_posterior.py','tools/review_p5_pr27_final.py'],
'field': ['tools/verify_pr21_actor_bf_provenance.py','tools/verify_pr24_p8_epoch_evidence_endtoend.py','tools/verify_pr27_p8_27player_3table_epoch_range.py','tools/review_p5_pr27_real_27_field.py','tools/verify_pr16_p5_provenance.py','tools/verify_p13_complete_field_bf.py','tools/verify_p13_bf_observer_likelihood.py','tools/verify_p13_runtime_provenance.py','tools/verify_p13_field_epoch_freshness.py','tools/verify_p13_parallel_epoch_lifetime.py','tools/verify_p15_pr27_two_tables.py','tools/verify_p15_frozen_lifetime.py','tools/verify_p15_pr27_origins.py','tools/verify_parallel_tables.py','tools/verify_parallel_table_processes.py 27 0 11','tools/verify_parallel_table_processes.py 18 0 11','ui/tools/verify_vclock_finish_ownership.py','ui/tools/verify_async_refill.py'],
'install': ['ui/tools/verify_fresh_install_startup.py','ui/tools/verify_personal_installation.py'],
}

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def env_for(path):
 env={k:v for k,v in os.environ.items() if not k.startswith(('T2_','PYTHON'))}
 env.update(PYTHONHASHSEED='0',T2_BOT_LOG='2',T2_TABLE_WORKERS='2',T2_TIMING_V1='off',T2_TELEMETRY='0',T2_LIVE_STATE=str(path/'state.json'),T2_HAND_ARCHIVE=str(path/'archive.jsonl'))
 return env

def guard():
 expected=json.loads((ROOT/'docs/semantic_audit/p17-integration-20261011/selected_sources.json').read_text())
 for row in expected:
  assert (ROOT/row['path']).read_bytes()==subprocess.check_output(['git','show',row['source_sha']+':'+row['path']],cwd=ROOT),row['path']
 changed=git('diff','--name-only',BASE,'HEAD').splitlines()
 for name in changed:
  assert name in {r['path'] for r in expected} or name.startswith(('tools/','docs/semantic_audit/p17-integration-20261011/','.github/workflows/p17-')),name
 for name in ['bot.py','preflop.py','session.py','range_posterior_v1.py','icm.py','play.py','live2.py','field.py','fieldsim.py','tourney.py']:
  assert (ROOT/name).read_bytes()==subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT),name
 assert git('hash-object','tools/audit_p9_pr30_mc_contract.py')=='1538f0c8ea79ebbfd605344f2b10305f2f754171'
 for name in ROOT.glob('tools/baseline_9max*.json'):
  assert name.read_bytes()==subprocess.check_output(['git','show',BASE+':'+str(name.relative_to(ROOT))],cwd=ROOT),name
 print('PASS exact P29/P30 selected bytes; P9 audit, engine, default flags and frozen files preserved')

def installed_mc(out):
 with tempfile.TemporaryDirectory(prefix='p17_installed_mc_') as td:
  tmp=pathlib.Path(td);installed=tmp/'runtime';env=env_for(tmp)
  env['HOME']=str(tmp/'home');(tmp/'home').mkdir()
  subprocess.run([sys.executable,str(ROOT/'ui/tools/setup_run_dir.py'),str(installed)],cwd=ROOT,env=env,check=True,capture_output=True)
  # Unchanged audit scripts resolve parents[1], therefore execute from the
  # real install's tools directory. Isolated Python cannot see the checkout.
  (installed/'tools').mkdir()
  names=['audit_p9_pr30_mc_contract.py','verify_p10_postflop_mc_unavailable.py','verify_p10_range_provenance.py']
  for name in names:(installed/'tools'/name).write_bytes((ROOT/'tools'/name).read_bytes())
  for name in names:
   r=subprocess.run([sys.executable,'-I','tools/'+name],cwd=installed,env=env,capture_output=True,text=True,timeout=180)
   (out/('installed_'+name+'.log')).write_text(r.stdout+r.stderr)
   assert r.returncode==0,(name,r.stdout+r.stderr)
  assert (installed/'plan.py').read_bytes()==(ROOT/'plan.py').read_bytes()
 print('PASS installed P17-B2, float(None), unchanged P9 13 cases and P10 provenance')

def run_group(group,out):
 if group=='guard':guard();return
 if group=='installed-mc':installed_mc(out);return
 if group=='parity':
  with tempfile.TemporaryDirectory(prefix='p17_base_') as td:
   base=pathlib.Path(td)/'base';subprocess.run(['git','worktree','add','--detach',str(base),BASE],cwd=ROOT,check=True,capture_output=True)
   try:
    r=subprocess.run([sys.executable,'ui/tools/verify_installation_paired_behavior.py',str(base),str(out)],cwd=ROOT,env=env_for(out),capture_output=True,text=True,timeout=1200)
    (out/'paired.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr)
    assert r.returncode==0,('parity failed',r.returncode)
   finally:subprocess.run(['git','worktree','remove','--force',str(base)],cwd=ROOT,check=True,capture_output=True)
  return
 rows=[]
 def run(name):
  label=name.replace('/','_').replace(' ','_');start=time.monotonic()
  with tempfile.TemporaryDirectory(prefix='p17_state_') as td:
   args=[sys.executable,*name.split()]
   if name=='ui/tools/verify_fresh_install_startup.py':args.append(str(out/'fresh-install'))
   try:
    r=subprocess.run(args,cwd=ROOT,env=env_for(pathlib.Path(td)),capture_output=True,text=True,timeout=600)
    code=r.returncode;log=r.stdout+r.stderr
   except subprocess.TimeoutExpired as e:code=124;log=str(e)
  (out/(label+'.log')).write_text(log)
  row={'test':name,'exit_code':code,'seconds':round(time.monotonic()-start,3),'log':label+'.log'}
  print(json.dumps(row),flush=True)
  return row
 with concurrent.futures.ThreadPoolExecutor(max_workers=2 if group=='field' else 3) as ex:
  rows=list(ex.map(run,GROUPS[group]))
 (out/'summary.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),'python':platform.python_version(),'platform':platform.platform(),'group':group,'checks':rows,'passed':sum(r['exit_code']==0 for r in rows),'failed':sum(r['exit_code']!=0 for r in rows)},indent=2))
 assert all(r['exit_code']==0 for r in rows),[r for r in rows if r['exit_code']!=0]

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('group',choices=[*GROUPS,'guard','installed-mc','parity']);ap.add_argument('output',type=pathlib.Path)
 a=ap.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
 run_group(a.group,a.output)
