#!/usr/bin/env python3
"""Trace exact PR27 vs integrated 30-hand frozen seeds; never saves a baseline."""
import concurrent.futures, hashlib, json, os, pathlib, subprocess, sys, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE='3c434b28046643ba54c04447951ad148ae6f9c1c'
OUT=pathlib.Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=True)
MATRIX=json.loads((ROOT/'docs/semantic_audit/p17-integration-20261011/baseline_comparison_matrix.json').read_text())
for row in MATRIX:
 p=ROOT/'tools'/row['file']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==row['file_sha256']
 assert row['stored_fp']==row['frozen_replay_fp']
 assert subprocess.check_output(['git','rev-parse',row['baseline_sha']],cwd=ROOT,text=True).strip()==row['baseline_sha']
ENV={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','T2_'))}
ENV.update(PYTHONHASHSEED='0',T2_TIMING_V1='off',T2_RANGE_CONDITIONAL_V1='0')
def first(a,b):
 for x,y in zip(a['hands'],b['hands']):
  if x['log']!=y['log']:
   idx=next((i for i,(u,v) in enumerate(zip(x['log'],y['log'])) if u!=v),min(len(x['log']),len(y['log'])))
   return {'hand':x['hand'],'log_index':idx,'base_action':x['log'][idx:idx+1],'integrated_action':y['log'][idx:idx+1], 'cards_equal':x['cards']==y['cards'],'base_trace':x,'integrated_trace':y}
 return None
with tempfile.TemporaryDirectory(prefix='p17_frozen_base_') as td:
 base=pathlib.Path(td)/'base';subprocess.run(['git','worktree','add','--detach',str(base),BASE],cwd=ROOT,check=True,capture_output=True)
 try:
  def run(case):
   label,root,seed=case
   r=subprocess.run([sys.executable,str(ROOT/'tools/trace_p17_final_baselines.py'),str(seed)],cwd=root,env=ENV,capture_output=True,text=True,timeout=300)
   (OUT/(label+'_'+str(seed)+'.json')).write_text(r.stdout if r.returncode==0 else r.stderr)
   assert r.returncode==0,(label,seed,r.stderr)
   return (label,seed),json.loads(r.stdout)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
   data=dict(ex.map(run,[(label,root,s) for label,root in [('base',base),('integrated',ROOT)] for s in range(3000,3006)]))
 finally:subprocess.run(['git','worktree','remove','--force',str(base)],cwd=ROOT,check=True,capture_output=True)
summary=[]
for seed in range(3000,3006):
 a,b=data['base',seed],data['integrated',seed]
 d=first(a,b)
 if d:(OUT/('first_difference_'+str(seed)+'.json')).write_text(json.dumps(d,indent=2))
 row={'seed':seed,'base_fp':a['fp'],'integrated_fp':b['fp'],'action_equal':d is None,'old_current_fp':next(r['stored_fp'] for r in MATRIX if r['baseline']=='current' and r['seed']==seed),'first_new_difference':None if d is None else {k:v for k,v in d.items() if k not in ('base_trace','integrated_trace')}}
 summary.append(row);print(json.dumps(row),flush=True)
(OUT/'summary.json').write_text(json.dumps({'base':BASE,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'historical_evidence':'reused prior local trace matrix; exact stored files verified; not a new historical replay','seeds':summary},indent=2))
# New differences fail this parity gate. Historical mismatches are reported,
# never hidden by replacing or regenerating their stored fingerprints.
sys.exit(0 if all(r['action_equal'] for r in summary) else 1)
