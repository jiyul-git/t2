# 질감 12칸 × 6장 구조는 그대로, 숫자 비율 + 숫자 짝 비율이 실제와 맞도록 담금질로 고른다.
import itertools, numpy as np, json, collections, random, sys
R='AKQJT98765432'; RK={r:i for i,r in enumerate(R)}
PA=json.load(open('panel_A.json')); Pst={k:v['probability'] for k,v in PA['strata'].items()}; ST=sorted(Pst)
deck=[r+s for r in R for s in 'cdhs']
def strat(f):
    rs=[c[0] for c in f]; ss=[c[1] for c in f]; nr=len(set(rs)); ns=len(set(ss))
    tex='paired' if nr<3 else ('monotone' if ns==1 else 'rainbow' if ns==3 else 'twotone')
    hi=min(RK[r] for r in rs); return tex+'/'+('A' if hi==0 else 'KQ' if hi<=2 else 'J_or_lower')
PI=[(a,b) for a in range(13) for b in range(a,13)]; PIX={p:i for i,p in enumerate(PI)}
def fv(f):
    v=np.zeros(13+len(PI)); rs=sorted(RK[c[0]] for c in f)
    for r in rs: v[r]+=1
    for a,b in itertools.combinations(rs,2): v[13+PIX[(a,b)]]+=1
    return v
by=collections.defaultdict(list); tru=collections.defaultdict(lambda:0)
for f in itertools.combinations(deck,3):
    s=strat(f); by[s].append(''.join(f))
DI={c:i for i,c in enumerate(deck)}
def norm(f): return ''.join(sorted([f[0:2],f[2:4],f[4:6]],key=DI.get))
FV={}
for s in ST:
    for f in by[s]: FV[f]=fv([f[0:2],f[2:4],f[4:6]])
target=sum(Pst[s]*np.mean([FV[f] for f in by[s]],axis=0) for s in ST)
# 숫자 칸과 짝 칸 가중: 숫자 오차를 더 무겁게
wvec=np.r_[np.full(13,4.0),np.full(len(PI),1.0)]
def score(panel):
    est=sum(Pst[s]*np.mean([FV[norm(f)] for f in panel[s]],axis=0) for s in ST)
    return float((wvec*((est-target)/np.maximum(target,1e-3))**2).sum())
def anneal(seed,steps=60000):
    rnd=random.Random(seed); panel={s:rnd.sample(by[s],6) for s in ST}; cur=score(panel); T=1.0
    for i in range(steps):
        s=rnd.choice(ST); j=rnd.randrange(6); old=panel[s][j]; new=rnd.choice(by[s])
        if new in panel[s]: continue
        panel[s][j]=new; sc=score(panel)
        if sc<cur or rnd.random()<np.exp((cur-sc)/T): cur=sc
        else: panel[s][j]=old
        T*=0.9999
    return panel,cur
def rnd_panel(seed):
    rnd=random.Random(seed); return {s:rnd.sample(by[s],6) for s in ST}
if __name__=='__main__':
    out={}
    for name,seed in [('BAL_A',101),('BAL_B',202)]:
        p,sc=anneal(seed); out[name]=p; print(name,'score',round(sc,3),flush=True)
    print('random panel scores',[round(score(rnd_panel(s)),2) for s in range(5)])
    print('old A',round(score({s:[x['board'] for x in PA['panel'] if x['stratum']==s] for s in ST}),2))
    PB=json.load(open('panel_B.json')); print('old B',round(score({s:[x['board'] for x in PB['panel'] if x['stratum']==s] for s in ST}),2))
    json.dump(out,open('bal_panels.json','w'))
