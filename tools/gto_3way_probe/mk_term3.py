import json,gzip,sys,numpy as np
nodes={}
for l in gzip.open('d60.jsonl.gz','rt'):
    d=json.loads(l); nodes['|'.join(d['line'])]=d
def keep(line):
    acts=line.split('|'); out={}
    for i,a in enumerate(acts):
        p,act=a.split(':',1)
        d=nodes['|'.join(acts[:i])]; assert d['actor']==p
        out[p]=out.get(p,np.ones(169))*np.array(d['sigma'][d['actions'].index(act)])
    return out
t=json.load(open('c60/data/ft60/step4/terms/term01.json'))
k=keep(t['line'])
for pl in t['players']:
    print(pl['position'],'maxdiff',np.abs(k[pl['position']]-np.array(pl['class_keep_fraction'])).max(), pl['invested_bb'])
# 3-way terminal
POS=['UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB']
line='UTG:Fold|UTG+1:Fold|UTG+2:Fold|LJ:Fold|HJ:Fold|CO:Fold|BTN:Raise 2.5|SB:Call 2.5|BB:Call 2.5'
k=keep(line)
order=['SB','BB','BTN']
out={'schema':'spot_terminal_3way_v1','line':line,'path_spec':line,'postflop_order':order,'pot_bb':8.5,
 'effective_behind_bb':t['effective_behind_bb'],'source':'ft60 step4 dump (d60), product of own sigma along line',
 'class_labels':json.load(open('cls.json')) if False else None,
 'players':[{'position':p,'seat':POS.index(p),'class_keep_fraction':list(map(float,k[p])),'invested_bb':2.5+0.111111111111} for p in order]}
json.dump(out,open('term3_btn_sb_bb.json','w'))
print({p:round(float(k[p].sum()),1) for p in order})
