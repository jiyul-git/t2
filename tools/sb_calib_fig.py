import os, sys, math, collections
D='/home/user/t2'; sys.path.insert(0,D); sys.path.insert(0,os.path.join(D,'tools'))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus']=False
import persona as PS
from sb_calib import load, branch_of, p_formula, river_odds

rows = load([os.path.join(D,'collected.jsonl')])
for i in rows:
    i['_branch']=branch_of(i); i['_sk']=PS.sk(i['_prof'],'semibluff')/3.33
mp=[i for i in rows if i['_branch']]
below=[i for i in mp if i['_branch']!='above']
rolled=[i for i in below if i['outs']>=8 and i.get('behind',0)<=1 and i['_sk']>=0.4]
def cond(i): return i['outs']>=8 and i.get('behind',0)<=1 and i['_sk']>=0.4
allg=[i for i in mp if cond(i)]

FG='#1b1b1b'; GR='#8a8a8a'
BLUE='#2f6fb5'; RED='#c1453c'; GREY='#b9b9b9'; GREEN='#3f8f5e'
fig=plt.figure(figsize=(13.5,9.6), dpi=150, facecolor='white')
gs=fig.add_gridspec(2,2, hspace=0.46, wspace=0.26,
                    left=0.075, right=0.975, top=0.855, bottom=0.075)

fig.suptitle('세미블러프 확률식  p = min(0.95, 0.25 + 0.24 × 개념)  실측 calibration',
             fontsize=15, color=FG, y=0.975)
fig.text(0.5,0.936,'봇 대전 1,000핸드 · make_plan 분기 1,463건 · 주사위가 실제로 굴려진 68건',
         ha='center',fontsize=10,color=GR)

# --- (1) 두 축의 눈금 ---
ax=fig.add_subplot(gs[0,0])
sk=[x/100 for x in range(40,301)]
ax.plot(sk,[p_formula(s) for s in sk],color=BLUE,lw=2.4,label='식이 반응하는 축: 개념')
ax.axhline(0.610,color=GREEN,ls='--',lw=1.2)
ax.text(3.02,0.610,'표본 평균 p\n0.610',fontsize=8,color=GREEN,va='center')
# 드로우 축 (플랍 완성확률을 같은 y 범위로 겹쳐 그린다)
o=[8,9,11,13]
ro=[river_odds(x,'flop') for x in o]
ax2=ax.twiny()
ax2.plot(o,ro,color=RED,lw=2.4,marker='o',ms=6,label='식이 무시하는 축: 드로우')
ax2.set_xlim(7.5,13.5); ax2.set_xlabel('물리 아웃츠 (플랍)',color=RED,fontsize=10)
ax2.tick_params(axis='x',colors=RED,labelsize=9)
for x,y in zip(o,ro): ax2.annotate('%d아웃 %.0f%%'%(x,y*100),(x,y),textcoords='offset points',
                                   xytext=(0,-16),ha='center',fontsize=8,color=RED)
ax.set_xlim(0.3,3.05); ax.set_ylim(0.15,1.0)
ax.set_xlabel('semibluff 개념 sk (0~3 스케일)',color=BLUE,fontsize=10)
ax.tick_params(axis='x',colors=BLUE,labelsize=9)
ax.set_ylabel('확률',fontsize=10)
ax.text(0.02,0.97,'① 개념 축은 2.75배로 움직이고\n    드로우 축(1.53배)은 0배로 들어간다',
        transform=ax.transAxes,va='top',ha='left',fontsize=11,color=FG,
        bbox=dict(fc='white',ec='none',alpha=0.85,pad=2))
ax.grid(alpha=0.25,lw=0.6)
h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
ax.legend(h1+h2,l1+l2,fontsize=8.5,loc='lower right',framealpha=0.95)

# --- (2) 예측 vs 실측 (sk 구간) ---
ax=fig.add_subplot(gs[0,1])
bins=[(0.4,1.0),(1.0,1.5),(1.5,2.0),(2.0,3.01)]
lab=[];pe=[];po=[];ns=[]
for a,b in bins:
    s=[i for i in rolled if a<=i['_sk']<b]
    if not s: continue
    lab.append('%.1f~%.1f'%(a,min(b,3.0))); ns.append(len(s))
    pe.append(sum(p_formula(i['_sk']) for i in s)/len(s))
    po.append(sum(1 for i in s if i['_branch']=='semibluff')/len(s))
x=range(len(lab)); w=0.36
ax.bar([i-w/2 for i in x],pe,w,color=BLUE,label='식이 예측한 p')
ax.bar([i+w/2 for i in x],po,w,color=GREY,edgecolor=FG,lw=0.7,label='실측 채택률')
for i,(a,b,n) in enumerate(zip(pe,po,ns)):
    ax.text(i,max(a,b)+0.03,'n=%d'%n,ha='center',fontsize=8.5,color=GR)
ax.set_xticks(list(x)); ax.set_xticklabels(lab,fontsize=9)
ax.set_ylim(0,1.0); ax.set_xlabel('semibluff 개념 sk',fontsize=10); ax.set_ylabel('확률',fontsize=10)
ax.set_title('② 식은 의도대로 굴러간다\n    전체 예측 41.5건 vs 실측 35건 (z = -1.64, 유의하지 않음)',
             fontsize=11,color=FG,loc='left')
ax.legend(fontsize=8.5); ax.grid(axis='y',alpha=0.25,lw=0.6)

# --- (3) 드로우 강도별 — 평평해야 정상 ---
ax=fig.add_subplot(gs[1,0])
for st,col,mk in (('flop',BLUE,'o'),('turn',RED,'s')):
    sub=[i for i in rolled if i['street']==st]
    os_=sorted(set(i['outs_true'] for i in sub if i['outs_true']>=8))
    xs=[];ys=[];nn=[]
    for oo in os_:
        s2=[i for i in sub if i['outs_true']==oo]
        xs.append(oo); ys.append(sum(p_formula(i['_sk']) for i in s2)/len(s2)); nn.append(len(s2))
    ax.plot(xs,ys,color=col,marker=mk,lw=2.2,ms=7,label='%s 예측 p (n=%d)'%(st,len(sub)))
    for a,b,n in zip(xs,ys,nn):
        ax.annotate('n=%d'%n,(a,b),textcoords='offset points',xytext=(0,9 if st=='flop' else -17),ha='center',fontsize=8,color=col)
ax.set_xlim(7.4,13.6); ax.set_ylim(0.40,0.80)
ax.set_xticks([8,9,11,13])
ax.set_xlabel('물리 아웃츠 outs_true  (draw_strength 는 8·9·11·13 만 낸다)',fontsize=10)
ax.set_ylabel('식이 배정한 확률 p',fontsize=10)
ax.set_title('③ 8아웃과 13아웃에 같은 확률이 배정된다\n    corr(p, 완성확률) = -0.05',
             fontsize=11,color=FG,loc='left')
ax.legend(fontsize=8.5); ax.grid(alpha=0.25,lw=0.6)

# --- (4) outs>=8 드로우 114건의 행선지 ---
ax=fig.add_subplot(gs[1,1])
c=collections.Counter(i['plan'] for i in allg)
order=[k for k,_ in c.most_common()]
vals=[c[k] for k in order]
cols=[GREEN if k=='semibluff' else (RED if k=='giveup' else GREY) for k in order]
b=ax.barh(range(len(order))[::-1],vals,color=cols,edgecolor=FG,lw=0.7)
for i,(k,v) in enumerate(zip(order,vals)):
    ax.text(v+0.8,len(order)-1-i,'%d  (%.0f%%)'%(v,100*v/len(allg)),va='center',fontsize=9,color=FG)
ax.set_yticks(range(len(order))[::-1]); ax.set_yticklabels(order,fontsize=9.5)
ax.set_xlim(0,42); ax.set_xlabel('건수',fontsize=10)
ax.set_title('④ outs≥8 · behind≤1 · 개념통과 인 드로우 114건의 종착지\n'
             '    giveup 31건 = 선점 폴백 14 + 주사위 기각 17',
             fontsize=11,color=FG,loc='left')
ax.grid(axis='x',alpha=0.25,lw=0.6)

out='/home/user/t2/tools/sb_calib.png'
fig.savefig(out,facecolor='white')
print(out)
