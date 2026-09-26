#!/usr/bin/env python3
"""F7-B1B shadow measurement for multiway range/nut advantage.

No production strategy is changed.

Candidate semantics:
- range advantage: current-board joint showdown share of a random hero-range
  combo versus one compatible combo from every seat-specific opponent range,
  normalized around the fair multiway share 1/(N+1).  This reduces exactly to
  the existing heads-up 2*equity-1 scale.
- nut advantage: preserve the existing hero strong-share definition, but compare
  it with the probability that at least one opponent seat occupies the same
  strong region.  This reduces to the existing heads-up definition.
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
        if not p: continue
        if '-' in p:
            a,b=p.split('-',1); out.extend(range(int(a),int(b)+1))
        else: out.append(int(p))
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
    xs=[float(x) for x in xs if x is not None]
    if not xs: return {'n':0}
    return {
        'n':len(xs),
        'mean':round(statistics.mean(xs),6),
        'p50':round(_q(xs,.50),6),
        'p90':round(_q(xs,.90),6),
        'p99':round(_q(xs,.99),6),
        'max':round(max(xs),6),
    }


def _clean_pools(board, opp_ranges, n_opp):
    if not isinstance(opp_ranges,dict):
        return None
    items=sorted(opp_ranges.items(),key=lambda kv:str(kv[0]))
    if len(items)!=int(n_opp):
        return None
    dead=set(board)
    pools=[]
    for seat,r in items:
        rr=sorted(c for c in (r or [])
                  if c[0] not in dead and c[1] not in dead)
        if not rr:
            return None
        pools.append((seat,rr))
    return pools


def joint_range_advantage(my_range, opp_ranges, board, n_opp,
                          sims=600, seed=None):
    """-1..1, centered at fair multiway current-board share."""
    if not my_range or len(board)<3:
        return None
    pools=_clean_pools(board,opp_ranges,n_opp)
    if not pools:
        return None
    if len(pools)==1:
        return R.range_advantage(
            my_range,pools[0][1],board,sims=sims,seed=seed)

    dead=set(board)
    my=sorted(c for c in my_range
              if c[0] not in dead and c[1] not in dead)
    if not my:
        return None
    if seed is None:
        seed=zlib.crc32(repr((tuple(my),tuple(board),pools,sims)).encode())
    rng=random.Random(seed)
    share=0.0; run=0
    for _ in range(int(sims)):
        used=set(dead)
        # hero-range combo is sampled first because it also blocks every seat.
        for _try in range(60):
            h=rng.choice(my)
            if h[0] not in used and h[1] not in used:
                used.add(h[0]); used.add(h[1]); break
        else:
            continue
        hs=bot.eval7(list(h)+board)
        scores=[]; ok=True
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
        share += bot._showdown_share(hs,scores)
    if not run:
        return None
    e=share/run
    fair=1.0/(len(pools)+1.0)
    if e>=fair:
        out=(e-fair)/max(1e-12,1.0-fair)
    else:
        out=(e-fair)/max(1e-12,fair)
    return max(-1.0,min(1.0,out))


def joint_nut_advantage(my_range, opp_ranges, board, n_opp,
                        sims=600, seed=None):
    """Existing strong-share idea versus 'any opponent strong' occupancy."""
    if not my_range or len(board)<3:
        return None
    pools=_clean_pools(board,opp_ranges,n_opp)
    if not pools:
        return None
    if len(pools)==1:
        return R.nut_advantage(my_range,pools[0][1],board)

    # Preserve existing hero-side definition exactly.
    my2=R._strong_share(my_range,board,2)
    my3=R._strong_share(my_range,board,3)

    if seed is None:
        seed=zlib.crc32(repr((tuple(board),pools,sims,'nut')).encode())
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
                ok=False; break
        if not ok: continue
        run+=1
        if any(x>=2 for x in cats): any2+=1
        if any(x>=3 for x in cats): any3+=1
    if not run:
        return None
    field2=any2/run; field3=any3/run
    return max(-1.0,min(1.0,
        (0.5*(my2-field2)+0.5*(my3-field3))*6.0))


def fixed_checks():
    board=['2c','7d','Jh','4s','3c']
    my=[('As','Ad')]
    tight=[('Js','Jd')]
    weak=[]
    dead=set(board)|set(my[0])|set(tight[0])
    mine=bot.eval7(list(my[0])+board)
    for c in bot._ALLCOMBOS:
        if set(c)&dead: continue
        if bot.eval7(list(c)+board)<mine:
            weak.append(c)
        if len(weak)>=40: break
    union=sorted(set(tight+weak))

    ua=R.range_advantage(my,union,board,sims=1200,seed=1)
    ja=joint_range_advantage(
        my,{2:tight,3:weak},board,2,sims=500,seed=1)
    assert ua>0.80,ua
    assert ja==-1.0,ja

    # Heads-up parity is exact by definition/fallback.
    hua=joint_range_advantage(my,{3:weak},board,1,sims=400,seed=9)
    hua0=R.range_advantage(my,weak,board,sims=400,seed=9)
    hun=joint_nut_advantage(my,{3:weak},board,1,sims=400,seed=9)
    hun0=R.nut_advantage(my,weak,board)
    assert abs(hua-hua0)<1e-12,(hua,hua0)
    assert abs(hun-hun0)<1e-12,(hun,hun0)

    missing_a=joint_range_advantage(
        my,{2:tight,3:[]},board,2,sims=50,seed=2)
    missing_n=joint_nut_advantage(
        my,{2:tight,3:[]},board,2,sims=50,seed=2)
    assert missing_a is None and missing_n is None

    return {
        'union_range_adv':round(ua,6),
        'joint_range_adv':round(ja,6),
        'heads_up_range_parity':True,
        'heads_up_nut_parity':True,
        'missing_pool_unknown':True,
    }


def run(seeds,hands,sims):
    original=PL.update_plan
    sig=inspect.signature(original)
    rows=[]
    counts={
        'multiway_seen':0,'complete':0,'unknown':0,
        'range_adv_sign_flips':0,
        'nut_adv_sign_flips':0,
        'nut_055_crossings':0,
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
            sa=(None if seed is None else
                zlib.crc32(('%s|f7b_range_adv' % int(seed)).encode()))
            sn=(None if seed is None else
                zlib.crc32(('%s|f7b_nut_adv' % int(seed)).encode()))
            ja=joint_range_advantage(my,pools,board,n,sims=sims,seed=sa)
            jn=joint_nut_advantage(my,pools,board,n,sims=sims,seed=sn)
            if ja is None or jn is None or not union or not my:
                counts['unknown']+=1
            else:
                counts['complete']+=1
                ua=R.range_advantage(my,union,board,sims=sims,seed=sa)
                un=R.nut_advantage(my,union,board)
                if (ua<0<ja) or (ja<0<ua):
                    counts['range_adv_sign_flips']+=1
                if (un<0<jn) or (jn<0<un):
                    counts['nut_adv_sign_flips']+=1
                if (un<.55<=jn) or (jn<.55<=un):
                    counts['nut_055_crossings']+=1
                rows.append({
                    'street':b.get('street'),'n_opp':n,
                    'pool_sizes':[len(v or []) for _,v in
                                  sorted((pools or {}).items(),key=lambda kv:str(kv[0]))],
                    'range_union':ua,'range_joint':ja,
                    'range_abs_delta':abs(ua-ja),
                    'nut_union':un,'nut_joint':jn,
                    'nut_abs_delta':abs(un-jn),
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

    top_r=sorted(rows,key=lambda x:x['range_abs_delta'],reverse=True)[:10]
    top_n=sorted(rows,key=lambda x:x['nut_abs_delta'],reverse=True)[:10]
    return {
        'seeds':seeds,'hands_per_seed':hands,'sims':sims,'counts':counts,
        'range_abs_delta':_summary([x['range_abs_delta'] for x in rows]),
        'nut_abs_delta':_summary([x['nut_abs_delta'] for x in rows]),
        'top_range_examples':top_r,
        'top_nut_examples':top_n,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=600)
    a=ap.parse_args()

    fx=fixed_checks()
    print('PASS F7-B1B fixed semantics',fx)
    res=run(_parse_seeds(a.seeds),a.hands,a.sims)
    print(json.dumps(res,indent=2,sort_keys=True))
    print()
    print('PASS F7-B1B range/nut shadow measurement completed')
    print('NOTE: no production consumer changed.')


if __name__=='__main__':
    main()
