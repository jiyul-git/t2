# 손패(169)별 플랍 맞음 특징의 '정답'(전체 22100 플랍) 계산 → proxy_truth.npz
import itertools, numpy as np, json
R='AKQJT98765432'; RV={r:14-i for i,r in enumerate(R)}
cls=json.load(open('cls.json'))
deck=[(RV[r],s) for r in R for s in range(4)]
flops=list(itertools.combinations(range(52),3))
def reps(c):
    if len(c)==2: a=RV[c[0]]; return [((a,0),(a,1)),((a,0),(a,2)),((a,0),(a,3)),((a,1),(a,2)),((a,1),(a,3)),((a,2),(a,3))]
    a,b=RV[c[0]],RV[c[1]]
    if c[2]=='s': return [((a,s),(b,s)) for s in range(4)]
    return [((a,s),(b,t)) for s in range(4) for t in range(4) if s!=t]
NF=8
def feats(h,f):
    cards=list(h)+f; rk=[c[0] for c in cards]; br=[c[0] for c in f]; hr=[h[0][0],h[1][0]]
    cnt={r:rk.count(r) for r in set(rk)}; bc={r:br.count(r) for r in set(br)}
    v=np.zeros(NF)
    hp= hr[0]==hr[1]
    # made category using hole involvement
    trips= any(cnt[r]>=3 and (r in hr) for r in cnt)
    twop= (not hp) and all(r in bc for r in hr)
    top=max(br)
    if trips: v[0]=1
    elif twop: v[1]=1
    elif hp and hr[0]>top: v[2]=1          # overpair
    elif any(r in bc for r in hr):
        r=[x for x in hr if x in bc][0]
        v[3 if r==top else 4]=1               # top pair / weaker pair
    su=[c[1] for c in cards]; fsuit=max(set(su),key=su.count); nfs=su.count(fsuit)
    hole_in=[c[1]==fsuit for c in h]
    if nfs>=5 and any(hole_in): v[5]=1
    elif nfs==4 and any(hole_in): v[6]=1      # flush draw
    s=set(rk); s|={1} if 14 in s else set()
    best=max(sum(1 for x in range(lo,lo+5) if x in s) for lo in range(1,11))
    if best>=4 and any((x in [c[0] for c in h]) for x in rk): v[7]=1  # straight or draw (rough)
    return v
T=np.zeros((169,22100,NF),np.float32)
for ci,c in enumerate(cls):
    hs=reps(c)
    for fi,f in enumerate(flops):
        fc=[deck[i] for i in f]; acc=np.zeros(NF); n=0
        for h in hs:
            if h[0] in fc or h[1] in fc: continue
            acc+=feats(h,fc); n+=1
        T[ci,fi]=acc/n
    if ci%20==0: print(ci,flush=True)
names=[''.join([R[14-deck[i][0]],'cdhs'[deck[i][1]]]) for i in range(52)]
np.savez_compressed('proxy_truth.npz',T=T,flops=np.array([''.join(names[i] for i in f) for f in flops]))
