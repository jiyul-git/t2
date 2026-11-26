import json,gzip,glob,os,sys
import numpy as np
R='/home/user/t2/data/ft60/'
LAB=None
def load_used(k):
    return {e['node']:e for e in (json.loads(l) for l in gzip.open(R+f'step{k}/used_gross.jsonl.gz','rt'))}
def tab(k,node):
    p=R+f'step{k}/collect/tables_AB/node{node}.json'
    return {s['position']:(np.array(s['gross']),np.array(s['se'])) for s in json.load(open(p))['seats']}
u0,u1=load_used(0),load_used(1)
r0=json.load(open(R+'step0/collect/report.json'));r1=json.load(open(R+'step1/collect/report.json'))
# combos weights
sys.path.insert(0,'/home/user/t2/tools/gto_fulltree')
import importlib.util
sp=importlib.util.spec_from_file_location('ft60','/home/user/t2/tools/gto_fulltree/ft60.py');m=importlib.util.module_from_spec(sp);sys.argv=['x','none'];sp.loader.exec_module(m)
COMBOS=np.array(m.COMBOS)
t1={t['node']:j for j,t in r1['terminals'].items()};t0={t['node']:j for j,t in r0['terminals'].items()}
rows=[]
for node,j1 in t1.items():
    tj=json.load(open(R+f'step1/terms/term{int(j1):02d}.json'))
    for pl in tj['players']:
        pos=pl['position'];w=COMBOS*np.array(pl['class_keep_fraction']);W=w.sum()
        wm=lambda x:float((w*x).sum()/W)
        us1={s['position']:s for s in u1[node]['seats']}[pos]
        T1=np.array(us1['used_gross']);S=np.array(us1['static_gross'])
        V1,se1=tab(1,node)[pos]
        has0=node in t0
        if has0:
            us0={s['position']:s for s in u0[node]['seats']}[pos]
            T0=np.array(us0['used_gross']);V0,_=tab(0,node)[pos]
            tabled0=us0['used_gross']!=us0['static_gross']
        else: T0=V0=None;tabled0=None
        row=dict(node=node,pos=pos,line=tj['line'][-40:],matrix=r1['terminals'][j1]['matrix'] if 'matrix' in r1['terminals'][j1] else None,
                 U=r1['terminals'][j1]['seats'][pos]['U144'],D1=r1['terminals'][j1]['seats'][pos]['D'],tabled0=tabled0)
        if has0:
            row['d0']=wm(np.abs(V0-T0))                  # step0 D
            row['dV']=wm(np.abs(V1-V0))                  # V movement
            row['d1']=wm(np.abs(V1-T1))                  # step1 D
            a=V0-T0;b=V1-T1
            row['corr']=float((w*a*b).sum()/np.sqrt((w*a*a).sum()*(w*b*b).sum()+1e-30))
            row['sgn0']=wm(V0-T0);row['sgn1']=wm(V1-T1)
            row['T1_is_V0']=bool(np.allclose(T1,V0))
        rows.append(row)
json.dump(rows,open('/tmp/claude-0/diag_b_rows.json','w'),default=float)
tab_rows=[r for r in rows if r.get('tabled0')]
print('seats',len(rows),'common with step0',sum('dV' in r for r in rows),'tabled in step0 (seed nodes):',len(tab_rows))
com=[r for r in rows if 'dV' in r]
U=np.array([r['U'] for r in com]);dV=np.array([r['dV'] for r in com]);d0=np.array([r['d0'] for r in com]);d1=np.array([r['d1'] for r in com])
print('median U %.3f | median step0 D %.3f | median V movement |V1-V0| %.3f | median step1 D %.3f'%(np.median(U),np.median(d0),np.median(dV),np.median(d1)))
print('V movement / U: median %.2f ; share with |V1-V0|<=U: %.2f'%(np.median(dV/U),np.mean(dV<=U)))
print('first-tabled endpoints (T1=V0): D1 == V movement:',all(r['T1_is_V0'] for r in com if not r['tabled0']), 'n=',sum(not r['tabled0'] for r in com))
print('--- seed(tabled in step0) seats, T1=0.5T0+0.5V0')
for r in tab_rows: print(r['node'],r['pos'],'D0 %.2f D1 %.2f dV %.2f U %.2f corr(V0-T0,V1-T1) %+.2f signed0 %+.2f signed1 %+.2f'%(r['d0'],r['d1'],r['dV'],r['U'],r['corr'],r['sgn0'],r['sgn1']))
nt=[r for r in com if not r['tabled0']]
print('--- first-tabled seats: corr(V0-T0,V1-V0) not meaningful; signed shift sign flips (sgn0 vs V1-V0):')
import collections
fl=sum(1 for r in nt if np.sign(r['sgn0'])*np.sign(r['sgn1'])<0)
print('flipped sign',fl,'of',len(nt))
print('=== reversion test (first-tabled, T0=static S): r = <V1-V0,S-V0>/|S-V0|^2 (weighted); r~+1 reverts to static, ~0 unrelated, <0 keeps going')
rs=[];near=0;n=0
for node,j1 in t1.items():
    if node in (10,31) or node not in t0: continue
    tj=json.load(open(R+f'step1/terms/term{int(j1):02d}.json'))
    for pl in tj['players']:
        pos=pl['position'];w=COMBOS*np.array(pl['class_keep_fraction'])
        us0={s['position']:s for s in u0[node]['seats']}[pos]
        if us0['used_gross']!=us0['static_gross']: continue
        S=np.array(us0['static_gross']);V0=tab(0,node)[pos][0];V1=tab(1,node)[pos][0]
        a=V1-V0;b=S-V0
        rs.append(float((w*a*b).sum()/(w*b*b).sum()))
        n+=1;near+= (w*np.abs(V1-S)).sum()<(w*np.abs(V0-S)).sum()
print('seats',n,'median r %.2f  IQR [%.2f, %.2f]  V1 closer to static than V0: %d/%d'%(np.median(rs),np.percentile(rs,25),np.percentile(rs,75),near,n))
