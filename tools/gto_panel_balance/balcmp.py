import json,gzip,numpy as np,sys
cls=json.load(open('cls.json'))
def W(f): return {x['board']:x['weight'] for x in json.load(open(f))['panel']}
wA0,wB0=W('panel_A.json'),W('panel_B.json'); wX,wY=W('c60/data/ft60/panels/panel_bal_A72.json'),W('c60/data/ft60/panels/panel_bal_B72.json')
def L(*fs):
    v={}
    for f in fs: v.update(json.load(gzip.open(f,'rt')))
    return v
A=L('v60/s4_t01_A.json.gz'); B=L('v60/s4_t01_B.json.gz')
X=L('bal/X36.json.gz','bal/Xt1.json.gz','bal/Xt2.json.gz'); Y=L('bal/Y1.json.gz','bal/Y2.json.gz','bal/Y3.json.gz')
print('boards A,B,X,Y',len(A),len(B),len(X),len(Y))
def V(vals,w,seat):
    bs=[b for b in vals if b in w]; ws=np.array([w[b] for b in bs])
    return (ws[:,None]*np.array([vals[b]['players'][seat] for b in bs])).sum(0)/ws.sum()
seats=list(next(iter(A.values()))['players'])
grp={'전체 169':cls,'작은 페어 22~66':['22','33','44','55','66'],'A2s~A9s':['A%ds'%i for i in range(2,10)],'AK·AQ·KQ':['AKs','AKo','AQs','AQo','KQs','KQo'],'오프수트 잡패':['72o','83o','94o','T2o','J3o','Q4o','K5o']}
res={}
for s in seats:
    dO=V(A,wA0,s)-V(B,wB0,s); dN=V(X,wX,s)-V(Y,wY,s)
    res[s]={'old':dO,'new':dN,'A':V(A,wA0,s),'B':V(B,wB0,s),'X':V(X,wX,s),'Y':V(Y,wY,s)}
    print('seat',s)
    for g,hs in grp.items():
        ix=[cls.index(h) for h in hs]
        print('  %-14s 예전 A-B %.2f   균형 X-Y %.2f'%(g,np.abs(dO[ix]).mean(),np.abs(dN[ix]).mean()))
    i=cls.index('72o'); print('  72o: A %.2f B %.2f | X %.2f Y %.2f'%(res[s]['A'][i],res[s]['B'][i],res[s]['X'][i],res[s]['Y'][i]))
np.savez('balcmp.npz',**{'%s_%s'%(s,k):v for s in res for k,v in res[s].items()})
