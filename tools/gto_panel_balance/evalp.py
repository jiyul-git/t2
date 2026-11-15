import numpy as np, json, random
from design import by, ST, Pst, norm, rnd_panel
z=np.load('proxy_truth.npz'); T=z['T']; FL=list(z['flops']); IX={f:i for i,f in enumerate(FL)}
cls=json.load(open('cls.json'))
truth=np.nanmean(T,axis=1)                       # (169,8) 전체 플랍 균등 = 실제
def est(panel,wmap=None):
    if wmap is None:
        return sum(Pst[s]*np.nanmean(T[:,[IX[norm(f)] for f in panel[s]],:],axis=1) for s in ST)
    tot=0; acc=0
    for s in ST:
        for f in panel[s]: acc=acc+wmap[f]*np.nan_to_num(T[:,IX[norm(f)],:]); tot+=wmap[f]
    return acc/tot
def err(e):
    d=(e-truth); return np.sqrt((d**2).mean())*100, np.abs(d).max()*100
PA=json.load(open('panel_A.json')); PB=json.load(open('panel_B.json')); RW=json.load(open('rake_w.json')); BAL=json.load(open('bal_panels.json'))
old={n:{s:[x['board'] for x in P['panel'] if x['stratum']==s] for s in ST} for n,P in [('A',PA),('B',PB)]}
rows=[('기존 A',est(old['A'])),('기존 B',est(old['B'])),('기존 A+B 평균',(est(old['A'])+est(old['B']))/2),
      ('숫자보정 A',est(old['A'],RW['A'])),('숫자보정 B',est(old['B'],RW['B'])),
      ('균형 A',est(BAL['BAL_A'])),('균형 B',est(BAL['BAL_B'])),('균형 A+B 평균',(est(BAL['BAL_A'])+est(BAL['BAL_B']))/2)]
for n,e in rows: print('%-14s RMS %.2f%%p  최대 %.2f%%p'%(n,*err(e)))
r=[err(est(rnd_panel(1000+s)))[0] for s in range(30)]
print('무작위 패널 30개 RMS 중앙 %.2f, 범위 %.2f~%.2f'%(np.median(r),min(r),max(r)))
names=['셋/트립스','투페어','오버페어','탑페어','약한페어','플러시','플러시드로우','스트레이트/드로우']
for n,e in [('기존 B',est(old['B'])),('균형 B',est(BAL['BAL_B']))]:
    for h in ['22','33','72o']:
        k=cls.index(h); print(n,h,' '.join('%s %.1f/%.1f'%(names[j],100*e[k,j],100*truth[k,j]) for j in range(5)))
