import json,gzip,glob,itertools,collections,math,numpy as np
R='AKQJT98765432'; RK={r:i for i,r in enumerate(R)}
cls=json.load(open('cls.json'))
PA=json.load(open('panel_A.json')); PB=json.load(open('panel_B.json'))
# classify all flops
def strat(cards):
    rs=[c[0] for c in cards]; ss=[c[1] for c in cards]
    ns=len(set(ss)); nr=len(set(rs))
    tex='paired' if nr<3 else ('monotone' if ns==1 else 'rainbow' if ns==3 else 'twotone')
    hi=min(RK[r] for r in rs); hc='A' if hi==0 else 'KQ' if hi<=2 else 'J_or_lower'
    return tex+'/'+hc
deck=[r+s for r in R for s in 'cdhs']
true=collections.defaultdict(lambda: np.zeros(13)); cnt=collections.Counter()
for f in itertools.combinations(deck,3):
    st=strat(f); cnt[st]+=1
    for c in f: true[st][RK[c[0]]]+=1
for st,v in PA['strata'].items(): assert cnt[st]==v['raw_flops'],(st,cnt[st],v)
Pst={st:v['probability'] for st,v in PA['strata'].items()}
truerank=sum(Pst[st]*true[st]/cnt[st] for st in Pst)  # expected rank count per flop
def rake(panel,iters=500):
    w=np.array([x['weight'] for x in panel]); S=[x['stratum'] for x in panel]
    M=np.array([[sum(1 for c in x['board'][0::2] if c==r) for r in R] for x in panel],float)
    for _ in range(iters):
        cur=w@M; f=truerank/np.maximum(cur,1e-12); w=w*np.exp((M*np.log(f)).sum(1)/np.maximum(M.sum(1),1))
        for st in Pst:
            idx=[i for i,s in enumerate(S) if s==st]; w[idx]*=Pst[st]/w[idx].sum()
    return w, (w@M)/truerank
for P,n in [(PA,'A'),(PB,'B')]:
    w,ratio=rake(P['panel']); w0=np.array([x['weight'] for x in P['panel']])
    print(n,'rank ratio after rake',' '.join('%s:%.2f'%(r,x) for r,x in zip(R,ratio)),' max/min weight ratio vs orig %.2f/%.2f'%((w/w0).max(),(w/w0).min()))
    P['w_rake']={x['board']:wi for x,wi in zip(P['panel'],w)}
    P['w0']={x['board']:x['weight'] for x in P['panel']}
json.dump({'A':PA['w_rake'],'B':PB['w_rake']},open('rake_w.json','w'))
# values per terminal: V_panel(class) = sum_w * v / sum_w (over boards present)
def V(vals,wmap,seat):
    num=np.zeros(169); den=0
    for b,d in vals.items():
        if b not in wmap: continue
        num+=wmap[b]*np.array(d['players'][seat]); den+=wmap[b]
    return num/den
rows=[]
for fa in sorted(glob.glob('v60/*_A.json.gz')):
    fb=fa.replace('_A.','_B.'); t=fa.split('/')[-1][:6]
    try: va=json.load(gzip.open(fa)); vb=json.load(gzip.open(fb))
    except Exception: continue
    if len(va)<72 or len(vb)<72: continue
    for seat in next(iter(va.values()))['players']:
        d0=V(va,PA['w0'],seat)-V(vb,PB['w0'],seat)
        d1=V(va,PA['w_rake'],seat)-V(vb,PB['w_rake'],seat)
        rows.append((t,seat,d0,d1))
D0=np.array([r[2] for r in rows]); D1=np.array([r[3] for r in rows])
print('terminal-seats',len(rows))
print('A-B 차이 |평균| (bb): 원래 %.4f  숫자보정후 %.4f'%(np.abs(D0).mean(),np.abs(D1).mean()))
print('A-B 차이 RMS: 원래 %.4f  보정후 %.4f'%(np.sqrt((D0**2).mean()),np.sqrt((D1**2).mean())))
grp={'작은페어 22-66':['22','33','44','55','66'],'Axs 작은':['A2s','A3s','A4s','A5s','A6s','A7s','A8s','A9s'],'큰카드 AK/AQ/KQ':['AKs','AKo','AQs','AQo','KQs','KQo'],'오프수트 잡패':['72o','83o','94o','T2o','J3o','Q4o','K5o']}
for g,hs in grp.items():
    ix=[cls.index(h) for h in hs]
    print('%-14s 원래 %.4f  보정후 %.4f'%(g,np.abs(D0[:,ix]).mean(),np.abs(D1[:,ix]).mean()))
