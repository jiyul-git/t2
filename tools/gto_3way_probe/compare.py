import json,numpy as np,itertools
t=json.load(open('term3_btn_sb_bb.json')); lab=t['class_labels']
cnt=np.array([6 if len(l)==2 else (4 if l.endswith('s') else 12) for l in lab])
W={p['position']:np.array(p['class_keep_fraction'])*cnt for p in t['players']}
def load(n):
    d=json.load(open('p3/%s.json'%n)); return {d['positions'][p['player']]:np.array(p['class_gross']) for p in d['final']['players']}, d['final']['exploitability_pct_pot']
def diff(a,b):
    out={}
    for p in a:
        w=W[p]/W[p].sum(); m=W[p]>0.05*W[p].max()/1  # 의미 있는 클래스
        dd=np.abs(a[p]-b[p]); out[p]=(float((w*dd).sum()), float(dd[m].max()))
    return out
for board,sizes in [('Kc7d4h',[4,8,12]),('9h8h3c',[4,8,16])]:
    R={n:load('%s_balanced0_%dx%d'%(board,n,n)) for n in sizes}
    print('==',board,{n:round(R[n][1],3) for n in sizes},'(expl %pot)')
    big=sizes[-1]
    for n in sizes[:-1]:
        print(' balanced %d vs %d:'%(n,big),{p:tuple(round(x,2) for x in v) for p,v in diff(R[n][0],R[big][0]).items()})
    if board=='Kc7d4h':
        rr=[load('Kc7d4h_random%d_8x8'%s)[0] for s in (1,2,3)]
        for i,r in enumerate(rr): print(' random%d 8 vs bal12:'%(i+1),{p:tuple(round(x,2) for x in v) for p,v in diff(r,R[12][0]).items()})
        for i,j in itertools.combinations(range(3),2): print(' random%d vs random%d:'%(i+1,j+1),{p:tuple(round(x,2) for x in v) for p,v in diff(rr[i],rr[j]).items()})
    print(' pot 8.5bb; range value per player (bal %d):'%big, {p:round(float((W[p]/W[p].sum()*R[big][0][p]).sum()),2) for p in W})
