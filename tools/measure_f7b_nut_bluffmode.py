#!/usr/bin/env python3
"""F7-B1B2: shadow the *actual bluff_mode consumer* with worst-seat nut ownership.

Production behavior is preserved exactly:
- update_plan wrapper derives worst-seat ownership from the current seat pools;
- bluff_mode wrapper runs production union input first and returns that result;
- it then replays the same bluff_mode call from the identical RNG pre-state with
  worst-seat ownership;
- after the shadow replay it restores the RNG post-state produced by production.

Thus shadow computation consumes no extra production randomness.
"""
import argparse
import inspect
import json
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

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


def _worst_seat(my_range,opp_ranges,board,n_opp):
    if not my_range or not board or not isinstance(opp_ranges,dict):
        return None
    items=sorted(opp_ranges.items(),key=lambda kv:str(kv[0]))
    if len(items)!=int(n_opp) or any(not r for _,r in items):
        return None
    vals=[R.nut_advantage(my_range,list(r),board) for _,r in items]
    return min(vals) if vals else None


_CTX=[]


def run(seeds,hands):
    original_update=PL.update_plan
    original_bluff=PL.bluff_mode
    usig=inspect.signature(original_update)

    rows=[]
    counts={
        'multiway_update_calls':0,
        'multiway_complete_worst':0,
        'bluff_mode_calls_total':0,
        'bluff_mode_calls_multiway':0,
        'bluff_mode_calls_multiway_complete':0,
        'nut_055_crossings_at_bluff_mode':0,
        'mode_changes':0,
        'to_polarized':0,
        'from_polarized':0,
    }

    def update_wrapped(*args,**kwargs):
        b=usig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        ctx={
            'multiway':n>1,
            'n_opp':n,
            'street':b.get('street'),
            'worst':None,
            'union':None,
            'pool_sizes':None,
        }
        if n>1:
            counts['multiway_update_calls']+=1
            my=list(b.get('my_range') or [])
            board=list(b.get('board') or [])
            pools=b.get('opp_ranges')
            union=list(b.get('opp_range') or [])
            ctx['worst']=_worst_seat(my,pools,board,n)
            ctx['union']=(R.nut_advantage(my,union,board)
                          if my and union and board else None)
            if isinstance(pools,dict):
                ctx['pool_sizes']=[
                    len(v or []) for _,v in
                    sorted(pools.items(),key=lambda kv:str(kv[0]))]
            if ctx['worst'] is not None:
                counts['multiway_complete_worst']+=1
        _CTX.append(ctx)
        try:
            return original_update(*args,**kwargs)
        finally:
            _CTX.pop()

    def bluff_wrapped(profile,rel,danger,nut_adv,opp_est,street,s,rng):
        counts['bluff_mode_calls_total']+=1
        ctx=_CTX[-1] if _CTX else None

        pre=rng.getstate()
        out_union=original_bluff(
            profile,rel,danger,nut_adv,opp_est,street,s,rng)
        post=rng.getstate()

        if ctx and ctx.get('multiway'):
            counts['bluff_mode_calls_multiway']+=1
            worst=ctx.get('worst')
            if worst is not None:
                counts['bluff_mode_calls_multiway_complete']+=1
                rng.setstate(pre)
                out_worst=original_bluff(
                    profile,rel,danger,worst,opp_est,street,s,rng)
                rng.setstate(post)

                cross=((nut_adv<.55<=worst) or
                       (worst<.55<=nut_adv))
                if cross:
                    counts['nut_055_crossings_at_bluff_mode']+=1
                changed=(out_union != out_worst)
                if changed:
                    counts['mode_changes']+=1
                    if out_union[0] != 'polarized' and out_worst[0] == 'polarized':
                        counts['to_polarized']+=1
                    if out_union[0] == 'polarized' and out_worst[0] != 'polarized':
                        counts['from_polarized']+=1

                rows.append({
                    'street':street,
                    'n_opp':ctx.get('n_opp'),
                    'pool_sizes':ctx.get('pool_sizes'),
                    'nut_union_arg':nut_adv,
                    'nut_union_recomputed':ctx.get('union'),
                    'nut_worst':worst,
                    'cross_055':cross,
                    'union_mode':out_union[0],
                    'worst_mode':out_worst[0],
                    'union_mul':out_union[1],
                    'worst_mul':out_worst[1],
                    'mode_changed':changed,
                    'rel':rel,
                    'danger':danger,
                    'spr':s,
                })

        return out_union

    PL.update_plan=update_wrapped
    PL.bluff_mode=bluff_wrapped
    try:
        for sd in seeds:
            t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,
                           seed=sd,hands_per_level=200)
            for _ in range(hands):
                if sum(1 for x in t.seats if t.stacks[x]>0)<3:
                    break
                st=t.next_hand(); guard=0
                while st and not st.get('done') and guard<200:
                    st=t.submit('fold'); guard+=1
                t.finish_hand()
    finally:
        PL.bluff_mode=original_bluff
        PL.update_plan=original_update

    changed=[r for r in rows if r['mode_changed']]
    crossings=[r for r in rows if r['cross_055']]
    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':counts,
        'mode_change_rows':changed,
        'threshold_crossing_rows':crossings,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    a=ap.parse_args()

    res=run(_parse_seeds(a.seeds),a.hands)
    print(json.dumps(res,indent=2,sort_keys=True))
    print()
    print('PASS F7-B1B2 actual bluff_mode consumer shadow completed')
    print('NOTE: production returned union results; RNG post-state preserved.')


if __name__=='__main__':
    main()
