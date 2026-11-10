import sys,os,csv,json,gzip,shutil,hashlib,importlib.util
import numpy as np
sp=importlib.util.spec_from_file_location('ft60','/home/user/t2/tools/gto_fulltree/ft60.py');m=importlib.util.module_from_spec(sp);sys.argv=['x','none'];sp.loader.exec_module(m)
R='/home/user/t2/data/ft60/'; V='/home/user/gto_ckpt/verify0/'; T='/home/user/gto_ckpt/verify0/diag_a/'
shutil.rmtree(T,ignore_errors=True);os.makedirs(T+'step1/terms')
ck='/home/user/gto_ckpt/ft60/solve_s1/ck.gtop'
rows=list(csv.DictReader(open(R+'step1/bundles.tsv'),delimiter='\t'))
lines={}
for r in rows: lines[int(r['term'])]=r['line']
order=sorted(lines)
info=m.export(ck,[lines[j] for j in order],T+'export1450.jsonl',R+'step1/tables/manifest.json')
cfg=json.load(open(m.CFG))
shift=[]
newsha={}
for j,e in zip(order,info):
    tj=m.term_json(e,lines[j],cfg['stack'],cfg['ante'])
    old=json.load(open(R+f'step1/terms/term{j:02d}.json'))
    assert tj['node']==old['node']
    f=T+f'step1/terms/term{j:02d}.json';json.dump(tj,open(f,'w'));newsha[j]=hashlib.sha256(open(f,'rb').read()).hexdigest()
    for a,b in zip(old['players'],tj['players']):
        ka,kb=np.array(a['class_keep_fraction']),np.array(b['class_keep_fraction'])
        w=np.array(m.COMBOS)*np.array(m.PRIOR)
        shift.append(dict(term=j,node=tj['node'],pos=a['position'],l1=float((w*np.abs(ka-kb)).sum()/ (w*ka).sum()),mass_old=float((w*ka).sum()),mass_new=float((w*kb).sum())))
json.dump(shift,open(T+'range_shift.json','w'))
l1=np.array([s['l1'] for s in shift]);print('range shift (L1 / old range mass, 950 -> 1450): median %.4f  p90 %.4f  max %.4f'%(np.median(l1),np.percentile(l1,90),l1.max()))
# bundles.tsv with new term sha
cols=list(rows[0].keys());
with open(T+'step1/bundles.tsv','w') as f:
    f.write('\t'.join(cols)+'\n')
    for r in rows:
        r=dict(r);r['term_sha256']=newsha[int(r['term'])];r['term_file']=T+f"step1/terms/term{int(r['term']):02d}.json"
        f.write('\t'.join(str(r[c]) for c in cols)+'\n')
with gzip.open(T+'step1/used_gross.jsonl.gz','wt') as f:
    f.write(open(T+'export1450.jsonl').read())
# patch and run collect
orig_fetch=m.fetch_results
def fake(k,out):
    got={}
    for r in csv.DictReader(open(T+'step1/bundles.tsv'),delimiter='\t'):
        d=json.load(open(f"/home/user/gto_ckpt/ft60/collect_s1/{r['bundle']}/done.json"));d['term_sha256']=r['term_sha256'];got[r['bundle']]=d
    return got
m.fetch_results=fake;m.D=T;m.WORK='/home/user/gto_ckpt/ft60'
m.collect(1)
