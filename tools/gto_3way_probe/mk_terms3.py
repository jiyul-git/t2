import json,gzip,numpy as np
POS=['UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB']
nodes={}
for l in gzip.open('d60.jsonl.gz','rt'):
    d=json.loads(l); nodes['|'.join(d['line'])]=d
cls=json.load(open('cls.json'))
TOP=['BTN:Raise 2.5|SB:Call 2.5|BB:Call 2.5','CO:Raise 2.5|SB:Call 2.5|BB:Call 2.5','HJ:Raise 2.5|SB:Call 2.5|BB:Call 2.5',
'LJ:Raise 2.5|SB:Call 2.5|BB:Call 2.5','UTG+2:Raise 2.5|SB:Call 2.5|BB:Call 2.5','UTG+1:Raise 2.5|SB:Call 2.5|BB:Call 2.5',
'UTG:Raise 2.5|SB:Call 2.5|BB:Call 2.5','UTG:Raise 2.5|BTN:Call 2.5|BB:Call 2.5','UTG+2:Raise 2.5|BTN:Call 2.5|BB:Call 2.5','UTG+1:Raise 2.5|BTN:Call 2.5|BB:Call 2.5']
ANTE=1/9
for j,short in enumerate(TOP):
    act=dict(x.split(':',1) for x in short.split('|'))
    full='|'.join('%s:%s'%(p,act.get(p,'Fold')) for p in POS)
    keep={}; acts=full.split('|')
    for i,a in enumerate(acts):
        p,ac=a.split(':',1); d=nodes['|'.join(acts[:i])]; assert d['actor']==p
        keep[p]=keep.get(p,np.ones(169))*np.array(d['sigma'][d['actions'].index(ac)])
    live=list(act); order=[p for p in ['SB','BB']+POS[:7] if p in live]
    pot=sum(2.5 for p in live)+1.0+(0.5 if 'SB' not in live else 0)
    t={'schema':'spot_terminal_3way_v1','line':full,'path_spec':full,'postflop_order':order,'pot_bb':pot,'effective_behind_bb':60-2.5-ANTE,
       'class_labels':cls,'source':'ft60 step4 dump: product of own sigma along line (checked on term01: diff 1e-7)',
       'players':[{'position':p,'seat':POS.index(p),'class_keep_fraction':list(map(float,keep[p])),'invested_bb':2.5+ANTE} for p in order]}
    json.dump(t,open('terms3/t%02d.json'%j,'w'))
    print(j,order,pot,{p:round(float(keep[p].sum()),1) for p in order})
