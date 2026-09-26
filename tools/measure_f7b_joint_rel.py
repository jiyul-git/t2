#!/usr/bin/env python3
"""F7-B1A: measure a joint-seat extension of relative_strength.

Diagnostic only.  Current production continues to use union relative_strength.

For a multiway state, the candidate metric is:
    P(hero current hand is not strictly behind ANY active opponent)
under one compatible combo sampled from each seat-specific perceived range.

This preserves the heads-up meaning of plan.relative_strength:
ties are "not beaten" and therefore count as 1 for this metric.
A separate current-board pot-share statistic is reported alongside it.
"""
import argparse
import inspect
import json
import math
import os
import random
import statistics
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot
import plan as PL
import tourney as T


def _parse_seeds(s):
    out=[]
    for p in str(s).split(','):
        p=p.strip()
        if not p: continue
        if '-' in p:
            a,b=p.split('-',1); out.extend(range(int(a),int(b)+1))
        else:
            out.append(int(p))
    return out


def _q(xs,p):
    ys=sorted(float(x) for x in xs)
    if not ys: return None
    if len(ys)==1: return ys[0]
    pos=(len(ys)-1)*p
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return ys[lo]
    w=pos-lo
    return ys[lo]*(1-w)+ys[hi]*w


def _summary(xs):
    xs=[float(x) for x in xs]
    if not xs: return {'n':0}
    return {
        'n':len(xs),
        'mean':round(statistics.mean(xs),6),
        'p50':round(_q(xs,.50),6),
        'p90':round(_q(xs,.90),6),
        'p99':round(_q(xs,.99),6),
        'max':round(max(xs),6),
    }


def joint_current_metrics(hero, board, opp_ranges, n_opp, sims=600, seed=None):
    if len(board) < 3 or not isinstance(opp_ranges, dict):
        return None
    items=[(k, list(v or [])) for k,v in
           sorted(opp_ranges.items(), key=lambda kv:str(kv[0]))]
    if len(items) != int(n_opp) or any(not r for _,r in items):
        return None

    dead=set(hero)|set(board)
    pools=[]
    for k,r in items:
        rr=sorted(c for c in r if c[0] not in dead and c[1] not in dead)
        if not rr:
            return None
        pools.append((k,rr))

    if len(pools)==1:
        # Exact parity with the existing heads-up definition.
        exact=PL.relative_strength(hero, board, pools[0][1])
        hs=bot.eval7(hero+board)
        tie_share=0.0; n=0
        for c in pools[0][1]:
            if set(c)&dead: continue
            n+=1
            tie_share += bot._showdown_share(
                hs, [bot.eval7(list(c)+board)])
        share=tie_share/max(1,n)
        return {
            'not_behind': exact,
            'current_share': share,
            'run': n,
        }

    if seed is None:
        seed=zlib.crc32(repr((sorted(hero),tuple(board),pools,sims)).encode())
    rng=random.Random(seed)
    hs=bot.eval7(hero+board)
    not_behind=0.0; share=0.0; run=0
    for _ in range(int(sims)):
        used=set(dead); scores=[]; ok=True
        for _,pool in pools:
            for _try in range(60):
                c=rng.choice(pool)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1])
                    scores.append(bot.eval7(list(c)+board))
                    break
            else:
                ok=False; break
        if not ok: continue
        run+=1
        best=max(scores)
        if hs >= best:
            not_behind += 1.0
        share += bot._showdown_share(hs, scores)
    if not run: return None
    return {
        'not_behind': not_behind/run,
        'current_share': share/run,
        'run': run,
    }


def fixed_fixture():
    board=['2c','7d','Jh','4s','3c']
    hero=['As','Ad']
    dead=set(board)|set(hero)
    tight=[('Js','Jd')]
    used=dead|{'Js','Jd'}
    mine=bot.eval7(hero+board)
    weak=[]
    for c in bot._ALLCOMBOS:
        if set(c)&used: continue
        if bot.eval7(list(c)+board) < mine:
            weak.append(c)
        if len(weak)>=40: break
    union=sorted(set(tight+weak))

    u=PL.relative_strength(hero,board,union)
    j=joint_current_metrics(hero,board,{2:tight,3:weak},2,sims=300,seed=17)
    assert u > .90, u
    assert j['not_behind'] == 0.0, j
    assert j['current_share'] == 0.0, j

    # Heads-up definition parity.
    hu_union=PL.relative_strength(hero,board,weak)
    hu_joint=joint_current_metrics(hero,board,{3:weak},1,sims=10,seed=1)
    assert abs(hu_union-hu_joint['not_behind']) < 1e-12, (hu_union,hu_joint)

    return {
        'union_rel':round(u,6),
        'joint_not_behind':round(j['not_behind'],6),
        'joint_current_share':round(j['current_share'],6),
        'heads_up_parity':True,
    }


def run(seeds,hands,sims):
    original=PL.update_plan
    sig=inspect.signature(original)
    rows=[]
    counts={'multiway_seen':0,'joint_complete':0,'joint_unknown':0,
            'union_joint_band_crossings':0}
    bands=(0.12,0.30,0.42,0.45,0.48,0.50,0.62,0.65,0.80,0.85,0.92)

    def wrapped(*args,**kwargs):
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        if n>1 and len(b.get('board') or [])>=3:
            counts['multiway_seen']+=1
            hero=b.get('hero'); board=list(b.get('board') or [])
            union=list(b.get('opp_range') or [])
            opp_ranges=b.get('opp_ranges')
            j=joint_current_metrics(
                hero,board,opp_ranges,n,sims=sims,
                seed=(None if b.get('seed') is None
                      else zlib.crc32(('%s|f7b_joint_rel' % int(b.get('seed'))).encode())))
            if j is None:
                counts['joint_unknown']+=1
            elif union:
                counts['joint_complete']+=1
                u=PL.relative_strength(hero,board,union)
                d=abs(u-j['not_behind'])
                crossed=[x for x in bands
                         if (u < x <= j['not_behind']) or
                            (j['not_behind'] < x <= u)]
                if crossed:
                    counts['union_joint_band_crossings']+=1
                rows.append({
                    'street':b.get('street'),
                    'n_opp':n,
                    'union_rel':u,
                    'joint_not_behind':j['not_behind'],
                    'joint_current_share':j['current_share'],
                    'abs_delta':d,
                    'crossed_bands':crossed,
                    'pool_sizes':[len(v or []) for _,v in
                                  sorted((opp_ranges or {}).items(),
                                         key=lambda kv:str(kv[0]))],
                })
        return original(*args,**kwargs)

    PL.update_plan=wrapped
    try:
        for sd in seeds:
            t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,
                           seed=sd,hands_per_level=200)
            for _ in range(hands):
                if sum(1 for s in t.seats if t.stacks[s]>0)<3: break
                st=t.next_hand(); guard=0
                while st and not st.get('done') and guard<200:
                    st=t.submit('fold'); guard+=1
                t.finish_hand()
    finally:
        PL.update_plan=original

    top=sorted(rows,key=lambda r:r['abs_delta'],reverse=True)[:10]
    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'sims':sims,
        'counts':counts,
        'abs_delta':_summary([r['abs_delta'] for r in rows]),
        'union_rel':_summary([r['union_rel'] for r in rows]),
        'joint_not_behind':_summary([r['joint_not_behind'] for r in rows]),
        'joint_current_share':_summary([r['joint_current_share'] for r in rows]),
        'top_examples':top,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=600)
    a=ap.parse_args()

    fx=fixed_fixture()
    print('PASS F7-B1A fixed fixture: joint metric preserves opponent identity',fx)
    res=run(_parse_seeds(a.seeds),a.hands,a.sims)
    print(json.dumps(res,indent=2,sort_keys=True))
    print()
    print('PASS F7-B1A joint-relative shadow measurement completed')
    print('NOTE: production still consumes union relative_strength.')


if __name__=='__main__':
    main()
