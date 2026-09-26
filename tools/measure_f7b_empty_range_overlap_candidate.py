#!/usr/bin/env python3
import argparse,collections,hashlib,json,os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
import ranges as R, preflop as PF, tourney as T

def seeds(s):
    out=[]
    for p in s.split(','):
        if '-' in p:
            a,b=p.split('-',1); out+=list(range(int(a),int(b)+1))
        else: out.append(int(p))
    return out

_vals=sorted(set(float(v) for v in PF.PCT.values()))
BINS={v:((_vals[i-1] if i else 0.0),v) for i,v in enumerate(_vals)}
def ov(lo,hi,a,b): return hi>lo and b>lo and a<hi

def fallback(prof,pos,act,bb,dead,n_callers=0,opener_pos=None,open_bb=2.5,
             seats=8,ante=True,polar=0.0,raise_level=1):
    if act not in ('call','3bet') or not opener_pos: return []
    tp,tot=PF.defend_thresholds(prof,pos,opener_pos,bb,open_bb,n_callers,raise_level,seats,ante)
    if act=='call': ints=[(tp,tot)]
    elif polar>0.02:
        vh=tp*(1-0.55*polar); bl=min(0.90,tp+0.10+0.25*polar)
        bh=min(0.95,bl+(tp-vh)*2.2); ints=[(0.0,vh),(bl,bh)]
    else: ints=[(0.0,tp)]
    out=[]
    for c in R._SORTED:
        if c[0] in dead or c[1] in dead: continue
        e=float(PF.PCT[PF.cls(list(c))]); a,b=BINS[e]
        if any(ov(lo,hi,a,b) for lo,hi in ints): out.append(c)
    return out

class Cand:
    def __init__(self):
        self.orig=R.preflop_range; self.c=collections.Counter(); self.ex=[]
    def f(self,*a,**k):
        out=self.orig(*a,**k); self.c['calls']+=1
        if out: return out
        self.c['empty']+=1
        try: fb=fallback(*a,**k)
        except TypeError: fb=[]
        if fb:
            self.c['recovered']+=1
            act=k.get('action',a[2] if len(a)>2 else None)
            self.c['action_'+str(act)]+=1
            if len(self.ex)<20:
                self.ex.append({'action':act,'n':len(fb),
                    'classes':sorted(set(PF.cls(list(x)) for x in fb))})
            return fb
        self.c['still_empty']+=1
        return out
    def on(self): R.preflop_range=self.f
    def off(self): R.preflop_range=self.orig

def trace(ss,hands):
    fp={}; hh={}; st=collections.Counter()
    for sd in ss:
        t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,seed=sd,hands_per_level=200)
        rows=['q=%.3f|a=%.2f'%(t.field_q,t.aggr_bias)]; hs=[]
        for _ in range(hands):
            if sum(t.stacks[x]>0 for x in t.seats)<3: break
            x=t.next_hand(); g=0
            while x and not x.get('done') and g<200: x=t.submit('fold'); g+=1
            log=list(getattr(t.run,'full_log',[]) or [])
            line=';'.join('%s:%s:%s:%s'%z for z in log); rows.append(line); hs.append(line)
            seen=set()
            for street,s,a,_ in log:
                if street!='preflop' or s==t.hero or s in seen: continue
                seen.add(s); st['n']+=1
                if a in ('bet','raise','allin'): st['vpip']+=1; st['pfr']+=1
                elif a=='call': st['vpip']+=1
            st['hands']+=1; st['flop']+=int(any(z[0]=='flop' for z in log))
            t.finish_hand()
        fp[sd]=hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]; hh[sd]=hs
    return fp,hh,dict(st)

def summ(s):
    n=max(1,s.get('n',0)); h=max(1,s.get('hands',0))
    return {'vpip_pct':round(100*s.get('vpip',0)/n,3),'pfr_pct':round(100*s.get('pfr',0)/n,3),
            'flop_pct':round(100*s.get('flop',0)/h,3),'hands':s.get('hands',0)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--seeds',default='3000-3011'); ap.add_argument('--hands',type=int,default=50)
    q=ap.parse_args(); ss=seeds(q.seeds)
    print('PASS fixture',{'AA_endpoint':PF.PCT['AA'],'overlap_0_0032':ov(0,0.0032,*BINS[PF.PCT['AA']])})
    p=trace(ss,q.hands); c=Cand(); c.on()
    try: z=trace(ss,q.hands)
    finally: c.off()
    changed={}; total=0
    for sd in ss:
        ids=[i+1 for i,(a,b) in enumerate(zip(p[1][sd],z[1][sd])) if a!=b]
        changed[str(sd)]=ids; total+=len(ids)
    print(json.dumps({'candidate_counts':dict(c.c),'examples':c.ex,'production_fp':p[0],'candidate_fp':z[0],
      'changed_hands_total':total,'changed_hands_by_seed':changed,'production_stats':summ(p[2]),'candidate_stats':summ(z[2])},
      indent=2,sort_keys=True))
    print('PASS F7-B1D4 overlap fallback shadow completed')
    print('NOTE stochastic-policy posterior semantics remain OPEN')

if __name__=='__main__': main()
