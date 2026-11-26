"""step<k+1> 표의 같은 끝점 두 자리 값 합을 팟에 맞춘다(사용자 결정 2026-11-10): 두 자리 모두 클래스 값에 같은 상수를 빼서
가중평균(own range = 직전 단계 terms 의 class_keep_fraction × 콤보 수) 합 = pot. 원본은 tables_raw/ 에 둔다. 사용: project_tables_to_pot.py <k>"""
import json,sys,os,csv,shutil,importlib.util
import numpy as np
k=int(sys.argv[1])
sp=importlib.util.spec_from_file_location('ft60','/home/user/t2/tools/gto_fulltree/ft60.py');m=importlib.util.module_from_spec(sp);sys.argv=['x','none'];sp.loader.exec_module(m)
C=np.array(m.COMBOS);R='/home/user/t2/data/ft60/'
td=R+f'step{k+1}/tables/';raw=R+f'step{k+1}/tables_raw/'
if not os.path.exists(raw): shutil.copytree(td,raw)
terms={int(r['node']):json.load(open(R+f"step{k}/terms/term{int(r['term']):02d}.json")) for r in csv.DictReader(open(R+f'step{k}/bundles.tsv'),delimiter='\t') if r['panel']=='A'}
log=[];neg=0
for node,tj in terms.items():
    p=td+f'node{node}.json'
    if not os.path.exists(p): continue
    t=json.load(open(raw+f'node{node}.json'))
    ws={};E=0
    for s in t['seats']:
        pl=next(q for q in tj['players'] if q['position']==s['position']);w=C*np.array(pl['class_keep_fraction']);ws[s['position']]=w/w.sum()
        E+=float((ws[s['position']]*np.array(s['gross'])).sum())
    delta=E-tj['pot_bb'];b4=delta
    for s in t['seats']:
        g=np.array(s['gross'])-delta/2;neg+=int((g<0).sum());s['gross']=[float(x) for x in g]
    E2=sum(float((ws[s['position']]*np.array(s['gross'])).sum()) for s in t['seats'])-tj['pot_bb']
    t.setdefault('provenance',{})['projection']={'kind':'subtract delta/2 from every class value of both seats so that range-weighted sum == pot','delta_bb':delta,'ranges':f'step{k} terms','residual':E2}
    json.dump(t,open(p,'w'));log.append({'node':node,'pot':tj['pot_bb'],'delta_before':b4,'residual':E2})
d=np.array([abs(x['delta_before']) for x in log])
print('projected',len(log),'| |sum-pot| before: median %.3f max %.3f | after max %.2e | classes pushed below 0: %d'%(np.median(d),d.max(),max(abs(x['residual']) for x in log),neg))
json.dump(log,open(R+f'step{k+1}/projection_log.json','w'),indent=1)
