#!/usr/bin/env python3
"""F7-B1B2 nut-advantage semantics audit.

Shadow only.  No production strategy changes.

Compares three meanings on the same live multiway decisions:

1. union:
   current production behavior; all opponent combos pooled.

2. worst-seat ownership:
   compute existing R.nut_advantage(hero_range, seat_range, board) separately
   for every opponent seat and take the minimum.  This asks whether hero owns
   the top-end versus the strongest individual opponent range, without adding a
   player-count effect and without synthesizing a fake merged opponent.

3. any-field collision:
   probability at least one compatible opponent combo occupies the existing
   strong bands (made category >=2 / >=3), plugged into the existing formula.
   This includes the real "more opponents => more chance someone is strong"
   effect and is therefore a field-collision quantity, not pure ownership.
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

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import bot
import plan as PL
import ranges as R
import tourney as T


def _parse_seeds(s):
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


def _q(xs,p):
    ys=sorted(float(x) for x in xs)
    if not ys:
        return None
    if len(ys)==1:
        return ys[0]
    pos=(len(ys)-1)*p
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:
        return ys[lo]
    w=pos-lo
    return ys[lo]*(1-w)+ys[hi]*w


def _summary(xs):
    xs=[float(x) for x in xs if x is not None]
    if not xs:
        return {'n':0}
    return {
        'n':len(xs),
        'mean':round(statistics.mean(xs),6),
        'p50':round(_q(xs,.50),6),
        'p90':round(_q(xs,.90),6),
        'p99':round(_q(xs,.99),6),
        'max':round(max(xs),6),
    }


def _seat_pools(opp_ranges,n_opp):
    if not isinstance(opp_ranges,dict):
        return None
    items=sorted(opp_ranges.items(),key=lambda kv:str(kv[0]))
    if len(items)!=int(n_opp):
        return None
    out=[]
    for seat,r in items:
        if not r:
            return None
        out.append((seat,list(r)))
    return out


def worst_seat_nut_advantage(my_range,opp_ranges,board,n_opp):
    pools=_seat_pools(opp_ranges,n_opp)
    if not my_range or not board or not pools:
        return None
    vals=[R.nut_advantage(my_range,r,board) for _,r in pools]
    return min(vals) if vals else None


def any_field_nut_advantage(my_range,opp_ranges,board,n_opp,
                            sims=600,seed=None):
    pools=_seat_pools(opp_ranges,n_opp)
    if not my_range or not board or not pools:
        return None
    if len(pools)==1:
        return R.nut_advantage(my_range,pools[0][1],board)

    my2=R._strong_share(my_range,board,2)
    my3=R._strong_share(my_range,board,3)
    if seed is None:
        seed=zlib.crc32(
            repr((tuple(board),tuple((s,tuple(r)) for s,r in pools),
                  int(sims),'f7b_nut_any')).encode())
    rng=random.Random(seed)
    dead=set(board)
    any2=0; any3=0; run=0
    for _ in range(int(sims)):
        used=set(dead); cats=[]; ok=True
        for _,pool in pools:
            for _try in range(60):
                c=rng.choice(pool)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1])
                    cats.append(bot.eval7(list(c)+board)[0])
                    break
            else:
                ok=False
                break
        if not ok:
            continue
        run+=1
        if any(x>=2 for x in cats):
            any2+=1
        if any(x>=3 for x in cats):
            any3+=1
    if not run:
        return None
    f2=any2/run; f3=any3/run
    return max(-1.0,min(1.0,
        (0.5*(my2-f2)+0.5*(my3-f3))*6.0))


def _overbet_nut_factor(nut):
    return 0.25 + 1.9*max(0.0,min(0.5,float(nut)))


def fixed_checks():
    board=['2c','7d','Jh','4s','3c']
    my=[('As','Ad')]
    tight=[('Js','Jd')]
    weak=[]
    dead=set(board)|set(my[0])|set(tight[0])
    mine=bot.eval7(list(my[0])+board)
    for c in bot._ALLCOMBOS:
        if set(c)&dead:
            continue
        if bot.eval7(list(c)+board)<mine:
            weak.append(c)
        if len(weak)>=40:
            break
    union=sorted(set(tight+weak))

    u=R.nut_advantage(my,union,board)
    w=worst_seat_nut_advantage(my,{2:tight,3:weak},board,2)
    a=any_field_nut_advantage(my,{2:tight,3:weak},board,2,
                              sims=500,seed=1)

    hu_w=worst_seat_nut_advantage(my,{3:weak},board,1)
    hu_a=any_field_nut_advantage(my,{3:weak},board,1,
                                 sims=100,seed=1)
    hu=R.nut_advantage(my,weak,board)
    assert abs(hu_w-hu)<1e-12,(hu_w,hu)
    assert abs(hu_a-hu)<1e-12,(hu_a,hu)

    missing_w=worst_seat_nut_advantage(my,{2:tight,3:[]},board,2)
    missing_a=any_field_nut_advantage(my,{2:tight,3:[]},board,2,
                                      sims=100,seed=1)
    assert missing_w is None and missing_a is None

    return {
        'union':round(u,6),
        'worst_seat_ownership':round(w,6),
        'any_field_collision':round(a,6),
        'heads_up_parity':True,
        'missing_pool_unknown':True,
    }


def run(seeds,hands,sims):
    original=PL.update_plan
    sig=inspect.signature(original)
    rows=[]
    counts={
        'multiway_seen':0,
        'complete':0,
        'unknown':0,
        'union_vs_worst_sign_flips':0,
        'union_vs_any_sign_flips':0,
        'union_vs_worst_055_crossings':0,
        'union_vs_any_055_crossings':0,
        'worst_vs_any_055_disagreements':0,
    }

    def wrapped(*args,**kwargs):
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        board=list(b.get('board') or [])
        if n>1 and len(board)>=3:
            counts['multiway_seen']+=1
            my=list(b.get('my_range') or [])
            union=list(b.get('opp_range') or [])
            pools=b.get('opp_ranges')
            seed=b.get('seed')
            w=worst_seat_nut_advantage(my,pools,board,n)
            aseed=(None if seed is None else
                   zlib.crc32(('%s|f7b_nut_any' % int(seed)).encode()))
            a=any_field_nut_advantage(my,pools,board,n,sims=sims,seed=aseed)

            if w is None or a is None or not my or not union:
                counts['unknown']+=1
            else:
                counts['complete']+=1
                u=R.nut_advantage(my,union,board)
                if (u<0<w) or (w<0<u):
                    counts['union_vs_worst_sign_flips']+=1
                if (u<0<a) or (a<0<u):
                    counts['union_vs_any_sign_flips']+=1
                uw=((u<.55<=w) or (w<.55<=u))
                ua=((u<.55<=a) or (a<.55<=u))
                wa=((w<.55<=a) or (a<.55<=w))
                if uw:
                    counts['union_vs_worst_055_crossings']+=1
                if ua:
                    counts['union_vs_any_055_crossings']+=1
                if wa:
                    counts['worst_vs_any_055_disagreements']+=1
                rows.append({
                    'street':b.get('street'),
                    'n_opp':n,
                    'pool_sizes':[len(v or []) for _,v in
                                  sorted((pools or {}).items(),
                                         key=lambda kv:str(kv[0]))],
                    'union':u,
                    'worst_seat':w,
                    'any_field':a,
                    'union_worst_abs':abs(u-w),
                    'union_any_abs':abs(u-a),
                    'worst_any_abs':abs(w-a),
                    'union_overbet_factor':_overbet_nut_factor(u),
                    'worst_overbet_factor':_overbet_nut_factor(w),
                    'any_overbet_factor':_overbet_nut_factor(a),
                    'union_ge_055':u>=.55,
                    'worst_ge_055':w>=.55,
                    'any_ge_055':a>=.55,
                })
        return original(*args,**kwargs)

    PL.update_plan=wrapped
    try:
        for sd in seeds:
            t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,
                           seed=sd,hands_per_level=200)
            for _ in range(hands):
                if sum(1 for s in t.seats if t.stacks[s]>0)<3:
                    break
                st=t.next_hand(); guard=0
                while st and not st.get('done') and guard<200:
                    st=t.submit('fold'); guard+=1
                t.finish_hand()
    finally:
        PL.update_plan=original

    def top(key):
        return sorted(rows,key=lambda x:x[key],reverse=True)[:10]

    by_n={}
    for n in sorted(set(r['n_opp'] for r in rows)):
        rr=[r for r in rows if r['n_opp']==n]
        by_n[str(n)]={
            'n':len(rr),
            'union_worst_abs':_summary([r['union_worst_abs'] for r in rr]),
            'union_any_abs':_summary([r['union_any_abs'] for r in rr]),
            'worst_any_abs':_summary([r['worst_any_abs'] for r in rr]),
            'union_ge_055':sum(r['union_ge_055'] for r in rr),
            'worst_ge_055':sum(r['worst_ge_055'] for r in rr),
            'any_ge_055':sum(r['any_ge_055'] for r in rr),
        }

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'sims':sims,
        'counts':counts,
        'union_worst_abs':_summary([r['union_worst_abs'] for r in rows]),
        'union_any_abs':_summary([r['union_any_abs'] for r in rows]),
        'worst_any_abs':_summary([r['worst_any_abs'] for r in rows]),
        'by_n_opp':by_n,
        'top_union_worst':top('union_worst_abs'),
        'top_worst_any':top('worst_any_abs'),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=600)
    a=ap.parse_args()

    fx=fixed_checks()
    print('PASS F7-B1B2 fixed nut semantics',fx)
    res=run(_parse_seeds(a.seeds),a.hands,a.sims)
    print(json.dumps(res,indent=2,sort_keys=True))
    print()
    print('PASS F7-B1B2 nut ownership/collision measurement completed')
    print('NOTE: production nut_advantage remains union-based.')


if __name__=='__main__':
    main()
