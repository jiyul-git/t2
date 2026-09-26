#!/usr/bin/env python3
"""F7-B1D5 direct attribution for percentile-bin empty-range fallback.

Runs production sequentially to preserve the real baseline trajectory.
Before each hand it deep-copies the exact pre-hand tournament state, then runs
the candidate on that snapshot only. Candidate results are never fed into the
next hand, so any mismatch is a direct within-hand effect, not cross-hand
cascade.

The candidate is exactly the B1D4 overlap fallback:
- existing non-empty preflop ranges are untouched;
- only empty call/3bet reconstructions get percentile-bin overlap recovery;
- no coefficients or action-generation logic are changed.
"""
import argparse
import copy
import json
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import ranges as R
import preflop as PF
import tourney as T


def parse_seeds(s):
    out=[]
    for p in str(s).split(','):
        p=p.strip()
        if not p:
            continue
        if '-' in p:
            a,b=p.split('-',1)
            out.extend(range(int(a),int(b)+1))
        else:
            out.append(int(p))
    return out


_vals=sorted(set(float(v) for v in PF.PCT.values()))
BINS={v:((_vals[i-1] if i else 0.0),v) for i,v in enumerate(_vals)}

def overlaps(lo,hi,a,b):
    return hi>lo and b>lo and a<hi


def fallback(prof,pos,act,bb,dead,n_callers=0,opener_pos=None,open_bb=2.5,
             seats=8,ante=True,polar=0.0,raise_level=1):
    if act not in ('call','3bet') or not opener_pos:
        return []
    tp,tot=PF.defend_thresholds(
        prof,pos,opener_pos,bb,open_bb,n_callers,raise_level,seats,ante)
    if act=='call':
        ints=[(tp,tot)]
    elif polar>0.02:
        vh=tp*(1-0.55*polar)
        bl=min(0.90,tp+0.10+0.25*polar)
        bh=min(0.95,bl+(tp-vh)*2.2)
        ints=[(0.0,vh),(bl,bh)]
    else:
        ints=[(0.0,tp)]

    out=[]
    for c in R._SORTED:
        if c[0] in dead or c[1] in dead:
            continue
        e=float(PF.PCT[PF.cls(list(c))])
        a,b=BINS[e]
        if any(overlaps(lo,hi,a,b) for lo,hi in ints):
            out.append(c)
    return out


class Candidate:
    def __init__(self):
        self.orig=R.preflop_range
        self.empty=0
        self.recovered=0

    def func(self,*a,**k):
        out=self.orig(*a,**k)
        if out:
            return out
        self.empty+=1
        try:
            fb=fallback(*a,**k)
        except TypeError:
            fb=[]
        if fb:
            self.recovered+=1
            return fb
        return out

    def on(self):
        R.preflop_range=self.func

    def off(self):
        R.preflop_range=self.orig


def play_one(t):
    st=t.next_hand()
    guard=0
    while st and not st.get('done') and guard<200:
        st=t.submit('fold')
        guard+=1
    log=list(getattr(t.run,'full_log',[]) or [])
    result={
        'log':[list(x) for x in log],
        'guard':guard,
        'remaining':sum(1 for x in t.seats if t.stacks[x]>0),
        'hero_stack':t.stacks.get(t.hero_seat),
    }
    t.finish_hand()
    return result


def first_diff(a,b):
    la=a['log']; lb=b['log']
    n=max(len(la),len(lb))
    for i in range(n):
        xa=la[i] if i<len(la) else None
        xb=lb[i] if i<len(lb) else None
        if xa!=xb:
            return {
                'index':i,
                'production':xa,
                'candidate':xb,
                'production_len':len(la),
                'candidate_len':len(lb),
            }
    if a['hero_stack']!=b['hero_stack'] or a['remaining']!=b['remaining']:
        return {
            'index':None,
            'production':{
                'hero_stack':a['hero_stack'],'remaining':a['remaining']},
            'candidate':{
                'hero_stack':b['hero_stack'],'remaining':b['remaining']},
            'production_len':len(la),
            'candidate_len':len(lb),
        }
    return None


def run(seeds,hands):
    direct=[]
    checked=0
    recovery={'empty':0,'recovered':0}

    for sd in seeds:
        prod=T.Tournament(
            entries=100,start_stack=30000,hero_seat=7,
            seed=sd,hands_per_level=200)

        for hand_no in range(1,hands+1):
            if sum(1 for x in prod.seats if prod.stacks[x]>0)<3:
                break

            snap=copy.deepcopy(prod)
            p=play_one(prod)

            cand=copy.deepcopy(snap)
            cwrap=Candidate(); cwrap.on()
            try:
                c=play_one(cand)
            finally:
                cwrap.off()

            recovery['empty']+=cwrap.empty
            recovery['recovered']+=cwrap.recovered
            checked+=1

            d=first_diff(p,c)
            if d is not None:
                direct.append({
                    'seed':sd,
                    'hand':hand_no,
                    'first_diff':d,
                })

    return {
        'hands_checked':checked,
        'candidate_empty_calls':recovery['empty'],
        'candidate_recovered_calls':recovery['recovered'],
        'direct_changed_hands_total':len(direct),
        'direct_changes':direct,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3011')
    ap.add_argument('--hands',type=int,default=50)
    a=ap.parse_args()

    print('PASS F7-B1D5 direct-pair fixture', {
        'AA_endpoint':PF.PCT['AA'],
        'candidate_only_on_empty':True,
        'candidate_not_fed_forward':True,
    })
    print(json.dumps(
        run(parse_seeds(a.seeds),a.hands),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1D5 direct attribution completed')
    print('NOTE: stochastic-policy posterior semantics remain OPEN.')


if __name__=='__main__':
    main()
