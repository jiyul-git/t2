import os, sys, glob, collections
D='/home/user/t2'; sys.path.insert(0,D); sys.path.insert(0,os.path.join(D,'tools'))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='WenQuanYi Zen Hei'; plt.rcParams['axes.unicode_minus']=False
import persona as PS
from sb_calib import load, branch_of
from sb_114 import thresholds
from init_gate import fired, block_fired, block_p, _street_why

def arm(paths):
    rows=load(paths)
    for i in rows:
        i['_branch']=branch_of(i); i['_v3'],i['_v2'],i['_pcz']=thresholds(i)
    mp=[i for i in rows if i['_branch']]
    pop=[i for i in mp if (not i.get('init')) and i['rel']>=0.5 and i.get('made',0)==0]
    inpcz=[i for i in pop if i['_branch']=='above']
    hit=[i for i in pop if i['plan'] in ('giveup','showdown') and (i.get('tocall') or 0)==0]
    src=collections.Counter()
    for i in hit:
        w=_street_why(i)
        if any(x.startswith('중간강도이나') for x in w): src['402 폴백\n(eq>=pcz 안)']+=1
        elif any(x.startswith('쇼다운 가치 있음') for x in w): src['최종 else\n쇼다운 가치 있음']+=1
        elif any(x.startswith('쇼다운 가치 없고') for x in w): src['최종 else\n포기']+=1
        else: src['기타/revise']+=1
    sup=collections.Counter()
    for i in inpcz:
        f=fired(i)
        if block_fired(i) and f is None: sup['block 생존']+=1
        elif f=='pot_control': sup['pot_control']+=1
        elif f=='thin_value': sup['얇은 밸류']+=1
        else: sup['공급 실패']+=1
    return dict(n_pop=len(pop), n_inpcz=len(inpcz), hit=len(hit), src=src, sup=sup)

A=arm(sorted(glob.glob(os.path.join(D,'collected_p*.jsonl'))))
B=arm([os.path.join(D,'ab_B_%d.jsonl'%i) for i in range(4)])

FG,GR='#1b1b1b','#8a8a8a'; BLUE,RED,GREEN,GREY,ORA='#2f6fb5','#c1453c','#3f8f5e','#b9b9b9','#d08a33'
fig=plt.figure(figsize=(13.5,6.4),dpi=150,facecolor='white')
gs=fig.add_gridspec(1,3,wspace=0.32,left=0.06,right=0.98,top=0.78,bottom=0.16)
fig.suptitle('block 복구 후 — initiative=False 공급망을 다시 평가한다', fontsize=15,color=FG,y=0.965)
fig.text(0.5,0.895,'각 6,000핸드 · 모집단 init=False·rel>=0.5·made==0 · 수정 전 %d건 → 수정 후 %d건'
         % (A['n_pop'],B['n_pop']), ha='center',fontsize=10,color=GR)

ax=fig.add_subplot(gs[0,0])
ks=['block 생존','pot_control','얇은 밸류','공급 실패']
a=[A['sup'].get(k,0) for k in ks]; b=[B['sup'].get(k,0) for k in ks]
x=range(len(ks)); w=0.38
ax.bar([v-w/2 for v in x],a,w,color=GREY,edgecolor=FG,lw=0.7,label='수정 전 (n=%d)'%A['n_inpcz'])
ax.bar([v+w/2 for v in x],b,w,color=GREEN,edgecolor=FG,lw=0.7,label='수정 후 (n=%d)'%B['n_inpcz'])
for i,(u,v) in enumerate(zip(a,b)):
    ax.text(i-w/2,u+0.6,'%d'%u,ha='center',fontsize=9.5); ax.text(i+w/2,v+0.6,'%d'%v,ha='center',fontsize=9.5)
ax.set_xticks(list(x)); ax.set_xticklabels(ks,fontsize=9)
ax.set_ylabel('건수 (eq>=pcz 진입분)',fontsize=10)
ax.set_title('① 공급망은 실제로 복구됐다\n    block 0 → 9 · 공급 성공 %d/%d → %d/%d'
             % (A['n_inpcz']-A['sup'].get('공급 실패',0),A['n_inpcz'],
                B['n_inpcz']-B['sup'].get('공급 실패',0),B['n_inpcz']),
             fontsize=11,color=FG,loc='left')
ax.legend(fontsize=8.5); ax.grid(axis='y',alpha=0.25,lw=0.6)

ax=fig.add_subplot(gs[0,1])
ax.bar([0,1],[A['hit'],B['hit']],color=[GREY,RED],edgecolor=FG,lw=0.8,width=0.5)
for i,v in enumerate([A['hit'],B['hit']]): ax.text(i,v+1.2,'%d'%v,ha='center',fontsize=12)
ax.set_xticks([0,1]); ax.set_xticklabels(['수정 전','수정 후'],fontsize=10)
ax.set_ylim(0,max(A['hit'],B['hit'])*1.3); ax.set_ylabel('건수',fontsize=10)
ax.set_title('② 그런데 하드 게이트 인구는 줄지 않았다\n    `if not initiative: return 0.0` · 양쪽 다 전부 체크',
             fontsize=11,color=FG,loc='left')
ax.grid(axis='y',alpha=0.25,lw=0.6)

ax=fig.add_subplot(gs[0,2])
ks2=[k for k,_ in B['src'].most_common()]
a2=[A['src'].get(k,0) for k in ks2]; b2=[B['src'].get(k,0) for k in ks2]
x=range(len(ks2))
ax.bar([v-w/2 for v in x],a2,w,color=GREY,edgecolor=FG,lw=0.7,label='수정 전')
ax.bar([v+w/2 for v in x],b2,w,color=RED,edgecolor=FG,lw=0.7,label='수정 후')
for i,(u,v) in enumerate(zip(a2,b2)):
    ax.text(i-w/2,u+0.8,'%d'%u,ha='center',fontsize=9); ax.text(i+w/2,v+0.8,'%d'%v,ha='center',fontsize=9)
ax.set_xticks(list(x)); ax.set_xticklabels(ks2,fontsize=8.5)
ax.set_ylabel('건수',fontsize=10)
ax.set_title('③ 이유 — 인구의 출처가 다르다\n    block 은 eq>=pcz 안에만 산다',
             fontsize=11,color=FG,loc='left')
ax.legend(fontsize=8.5); ax.grid(axis='y',alpha=0.25,lw=0.6)

out=os.path.join(D,'tools','init_gate_after.png')
fig.savefig(out,facecolor='white'); print(out)
