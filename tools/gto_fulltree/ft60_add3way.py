import json,glob,numpy as np
S='/tmp/claude-0/-home-user-t2/bd21691f-5a05-5554-9137-a4bdcc9bc5c6/scratchpad'
cls=json.load(open(S+'/cls.json'))
pan={x['board']:x['weight'] for x in json.load(open('data/ft60/panels/panel_bal_A72.json'))['panel']}
info=json.load(open(S+'/mw3_nodes.json'))
def combos(c):
    r1,r2=c[0],c[1]; s='cdhs'
    if len(c)==2: return [(r1+a,r1+b) for i,a in enumerate(s) for b in s[i+1:]]
    if c[2]=='s': return [(r1+a,r2+a) for a in s]
    return [(r1+a,r2+b) for a in s for b in s if a!=b]
CB=[combos(c) for c in cls]
man=json.load(open('data/ft60/step5/tables/manifest.json'))
assert not any(t.get('threeway') for t in man['tables'])
for j,e in enumerate(info):
    t=json.load(open(S+'/terms3/t%02d.json'%j))
    seats=[]
    for pos in t['postflop_order']:
        num=np.zeros(169); den=np.zeros(169)
        for f in sorted(glob.glob(S+'/p8/data/gto_3way_panel/t%02d/*.json'%j)):
            b=f.split('/')[-1][:-5]; r=json.load(open(f)); bc={b[i:i+2] for i in (0,2,4)}
            p=[x for x in r['final']['players'] if r['positions'][x['player']]==pos][0]
            avail=np.array([sum(1 for x,y in CB[h] if x not in bc and y not in bc) for h in range(169)],float)
            num+=pan[b]*avail*np.array(p['class_gross']); den+=pan[b]*avail
        g=num/den
        seat=next(s['seat'] for s in e['seats'] if s['position']==pos)
        seats.append({'seat':seat,'position':pos,'gross':[float(x) for x in g]})
    tab={'schema':'t2_hu_continuation_table_v1','node':e['node'],'live':int(e['live']),'pot_bb':float(e['pot_bb']),'value_convention':'gross_share',
         'line':t['line'],'seats':seats,
         'provenance':{'kind':'3-way terminal solved by t2_3way (M2 menu, exact card removal), balanced panel A 72 flops, turn/river 8x8 balanced subset per flop, target 0.3% pot',
                       'alpha':1.0,'note':'first 3-way table: replaces the static coupled-deck pot*equity value (no mixing with static)',
                       'results_branches':'claude/ft3way_p8_%d..%d'%(2*j+1,2*j+2)}}
    fn='node%d.json'%e['node']
    json.dump(tab,open('data/ft60/step5/tables/'+fn,'w'))
    man['tables'].append({'file':fn,'line':t['line'],'alpha':1.0,'threeway':True})
    print(fn,{s['position']:round(float(np.mean(s['gross'])),2) for s in seats})
man['note']+=' + 10 three-way terminal tables (t2_3way, 8x8 runouts, balanced panel A)'
json.dump(man,open('data/ft60/step5/tables/manifest.json','w'),indent=1)
print(len(man['tables']))
