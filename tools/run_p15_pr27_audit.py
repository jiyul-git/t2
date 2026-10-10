#!/usr/bin/env python3
"""Run independent P15 gates and preserve per-check exit status/stdout/environment."""
import json,os,pathlib,platform,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE='3c434b28046643ba54c04447951ad148ae6f9c1c'
OUT=ROOT/'p15-ci-results';OUT.mkdir(exist_ok=True)
allowed={'tools/verify_p15_frozen_lifetime.py','tools/verify_p15_pr27_origins.py',
 'tools/verify_p15_pr27_two_tables.py','tools/run_p15_pr27_audit.py',
 '.github/workflows/p15-pr27-independent-audit.yml','docs/semantic_audit/P15_PR27_REMOTE_AUDIT_20261010.md'}
diff=subprocess.check_output(['git','diff','--name-status',BASE,'HEAD'],cwd=ROOT,text=True)
for row in diff.splitlines():
 status,name=row.split('\t',1)
 assert status=='A' and (name in allowed or name.startswith('docs/semantic_audit/p15_history/')),row
commands=[
 ('two_real_nonhero_tables',['tools/verify_p15_pr27_two_tables.py']),
 ('origins_and_paired_game_rng',['tools/verify_p15_pr27_origins.py']),
 ('independent_frozen_lifetime',['tools/verify_p15_frozen_lifetime.py']),
 ('partial_roster_and_sync_archive',['tools/verify_p13_parallel_epoch_lifetime.py']),
 ('stale_observed_vs_intentionally_frozen',['tools/verify_p13_field_epoch_freshness.py']),
 ('27_seed11_parallel_compatibility',['tools/verify_parallel_table_processes.py','27','0','11']),
 ('ownership_merge_bust_balance',['tools/verify_parallel_tables.py']),
 ('vclock_finish_ownership',['ui/tools/verify_vclock_finish_ownership.py']),
 ('async_refill_move_time_boundaries',['ui/tools/verify_async_refill.py']),
]
results=[]
with tempfile.TemporaryDirectory(prefix='p15_ci_state_') as td:
 env=dict(os.environ,PYTHONHASHSEED='0',PYTHONPATH=str(ROOT),T2_BOT_LOG='2',T2_TABLE_WORKERS='2',
  T2_LIVE_STATE=str(pathlib.Path(td)/'state.json'),T2_HAND_ARCHIVE=str(pathlib.Path(td)/'archive.jsonl'))
 for name,args in commands:
  r=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,text=True,capture_output=True)
  (OUT/(name+'.log')).write_text(r.stdout+r.stderr)
  results.append({'name':name,'command':[sys.executable,*args],'exit_code':r.returncode,'pass':r.returncode==0})
  print(json.dumps(results[-1]),flush=True)
  if name in ('two_real_nonhero_tables','origins_and_paired_game_rng') and r.returncode==0:
   (OUT/(name+'.json')).write_text(r.stdout)
record={'pass':all(r['pass'] for r in results),'base':BASE,
 'audit_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'python':platform.python_version(),'platform':platform.platform(),'processor':platform.machine(),
 'cpu_count':os.cpu_count(),'env':{k:env[k] for k in ('PYTHONHASHSEED','PYTHONPATH','T2_BOT_LOG','T2_TABLE_WORKERS')},
 'production_diff':[],'audit_additions':diff.splitlines(),'checks':results}
(OUT/'summary.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'pass':record['pass'],'passed':sum(r['pass'] for r in results),'failed':sum(not r['pass'] for r in results)}))
sys.exit(0 if record['pass'] else 1)
