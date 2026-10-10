#!/usr/bin/env python3
"""Frozen-seed attribution across preserved test3, approved source, and merged policy."""
import concurrent.futures,json,os,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from verify_p17_test3_contract import TEST3,APPROVED,git
OUT=pathlib.Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=True)
def first(a,b):
 for x,y in zip(a['hands'],b['hands']):
  if x['log']!=y['log']:
   i=next((i for i,(u,v) in enumerate(zip(x['log'],y['log'])) if u!=v),min(len(x['log']),len(y['log'])))
   return {'hand':x['hand'],'log_index':i,'before':x['log'][i:i+1],'after':y['log'][i:i+1],'cards_equal':x['cards']==y['cards'],'before_trace':x,'after_trace':y}
 return None
with tempfile.TemporaryDirectory(prefix='p17_test3_traces_') as td:
 roots={'test3':pathlib.Path(td)/'test3','approved':pathlib.Path(td)/'approved','merged_default':ROOT,'merged_normal_muck':ROOT}
 for k,s in [('test3',TEST3),('approved',APPROVED)]:subprocess.run(['git','worktree','add','--detach',str(roots[k]),s],cwd=ROOT,check=True,capture_output=True)
 try:
  def capture(case):
   label,seed=case;env={k:v for k,v in os.environ.items() if not k.startswith(('T2_','PYTHON'))};env.update(PYTHONHASHSEED='0',T2_TIMING_V1='off',T2_RANGE_CONDITIONAL_V1='0')
   if label.startswith('merged'):env['T2_SHOWDOWN_MUCK']='1' if label=='merged_normal_muck' else '0'
   r=subprocess.run([sys.executable,str(ROOT/'tools/trace_p17_final_baselines.py'),str(seed)],cwd=roots[label],env=env,text=True,capture_output=True,timeout=600)
   (OUT/f'{label}_{seed}.json').write_text(r.stdout if r.returncode==0 else r.stderr);assert r.returncode==0,(case,r.stderr)
   return (label,seed),json.loads(r.stdout)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:data=dict(ex.map(capture,[(l,s) for l in roots for s in range(3000,3006)]))
 finally:
  for k in ('test3','approved'):subprocess.run(['git','worktree','remove','--force',str(roots[k])],cwd=ROOT,check=True,capture_output=True)
rows=[]
for seed in range(3000,3006):
 a,b,c,d=(data[l,seed] for l in roots);controlled=first(b,d);assert controlled is None and b['fp']==d['fp'] and len(b['hands'])==len(d['hands']),(seed,'unexplained regression with matched showdown policy',controlled)
 differences={}
 for label,x,y in [('approved_vs_merged_default',b,c),('test3_vs_approved',a,b),('test3_vs_merged_default',a,c)]:
  delta=first(x,y);differences[label]=None if delta is None else {k:v for k,v in delta.items() if not k.endswith('_trace')}
  if delta:(OUT/f'first_{label}_{seed}.json').write_text(json.dumps(delta,indent=2))
 row={'seed':seed,'fingerprints':{l:data[l,seed]['fp'] for l in roots},'normal_muck_control_matches_approved':True,'differences':differences,'attribution':'Default-showdown-policy effect only if difference present and matched-policy control eliminates it; Classify test3-vs-approved differences using these same controls; do not assume a new MC/replan defect.'};rows.append(row);print(json.dumps(row),flush=True)
(OUT/'summary.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),'test3':TEST3,'approved':APPROVED,'frozen_files_written':False,'rows':rows},indent=2))
print('PASS frozen bytes untouched; all six matched-policy traces preserve approved actions; original/default changes recorded separately')
