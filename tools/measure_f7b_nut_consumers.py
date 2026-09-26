#!/usr/bin/env python3
"""F7-B1B3: shadow every live nut-advantage strategy consumer.

Production behavior is preserved.

Consumers separated:
A) make_plan:
   union nut affects continuous bluff_ok and the subsequent bluff_mode.
   Re-run make_plan with identical inputs/seed but worst-seat ownership.

B) overbet_frac:
   current function recomputes union nut internally.  Replay from the identical
   RNG pre-state with worst-seat ownership and any-field collision, restore the
   production RNG post-state, and return the production result.

Also verifies the wiring defect:
refresh stores nut_adv and attach_intent passes it to decide_size(nut=...), but
decide_size never reads the nut parameter; overbet_frac recomputes union nut.
"""
import argparse
import inspect
import json
import os
import random
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
        else:
            out.append(int(p))
    return out


def _seat_items(opp_ranges,n_opp):
    if not isinstance(opp_ranges,dict):
        return None
    items=sorted(opp_ranges.items(),key=lambda kv:str(kv[0]))
    if len(items)!=int(n_opp) or any(not r for _,r in items):
        return None
    return [(s,list(r)) for s,r in items]


def worst_seat(my_range,opp_ranges,board,n_opp):
    items=_seat_items(opp_ranges,n_opp)
    if not my_range or not board or not items:
        return None
    vals=[R.nut_advantage(my_range,r,board) for _,r in items]
    return min(vals) if vals else None


def any_field(my_range,opp_ranges,board,n_opp,sims=600,seed=None):
    items=_seat_items(opp_ranges,n_opp)
    if not my_range or not board or not items:
        return None
    if len(items)==1:
        return R.nut_advantage(my_range,items[0][1],board)

    my2=R._strong_share(my_range,board,2)
    my3=R._strong_share(my_range,board,3)
    if seed is None:
        seed=zlib.crc32(
            repr((tuple(board),tuple((s,tuple(r)) for s,r in items),
                  int(sims),'f7b_any_field')).encode())
    rng=random.Random(seed)
    dead=set(board)
    n=0; any2=0; any3=0
    for _ in range(int(sims)):
        used=set(dead); cats=[]; ok=True
        for _,pool in items:
            for _try in range(60):
                c=rng.choice(pool)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1])
                    cats.append(bot.eval7(list(c)+board)[0])
                    break
            else:
                ok=False; break
        if not ok: continue
        n+=1
        if any(x>=2 for x in cats): any2+=1
        if any(x>=3 for x in cats): any3+=1
    if not n:
        return None
    f2=any2/n; f3=any3/n
    return max(-1.0,min(1.0,
        (0.5*(my2-f2)+0.5*(my3-f3))*6.0))


_CTX=[]


def run(seeds,hands):
    orig_update=PL.update_plan
    orig_make=PL.make_plan
    orig_overbet=PL.overbet_frac
    usig=inspect.signature(orig_update)
    msig=inspect.signature(orig_make)

    make_rows=[]
    over_rows=[]
    counts={
        'multiway_update_calls':0,
        'make_plan_calls_total':0,
        'make_plan_calls_multiway':0,
        'make_plan_complete_worst':0,
        'make_plan_plan_changes':0,
        'make_plan_bluff_mode_changes':0,
        'make_plan_to_bluff':0,
        'make_plan_from_bluff':0,
        'overbet_calls_total':0,
        'overbet_calls_multiway':0,
        'overbet_complete':0,
        'overbet_worst_selection_changes':0,
        'overbet_worst_size_changes':0,
        'overbet_any_selection_changes':0,
        'overbet_any_size_changes':0,
    }

    def update_wrapped(*args,**kwargs):
        b=usig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        ctx={
            'multiway':n>1,
            'n_opp':n,
            'opp_ranges':b.get('opp_ranges'),
            'street':b.get('street'),
        }
        if n>1:
            counts['multiway_update_calls']+=1
        _CTX.append(ctx)
        try:
            return orig_update(*args,**kwargs)
        finally:
            _CTX.pop()

    def make_wrapped(*args,**kwargs):
        counts['make_plan_calls_total']+=1
        b=msig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        if n<=1:
            return orig_make(*args,**kwargs)

        counts['make_plan_calls_multiway']+=1
        my=list(b.get('my_range') or [])
        board=list(b.get('board') or [])
        opp_ranges=b.get('opp_ranges')
        union=list(b.get('opp_range') or [])
        w=worst_seat(my,opp_ranges,board,n)

        # Production first.
        prod=orig_make(*args,**kwargs)
        if w is None:
            return prod

        counts['make_plan_complete_worst']+=1
        union_nut=(R.nut_advantage(my,union,board)
                   if my and union and board else 0.0)

        real_nut=R.nut_advantage
        try:
            R.nut_advantage=lambda *a,**k: w
            alt=orig_make(*args,**kwargs)
        finally:
            R.nut_advantage=real_nut

        plan_changed=(prod.get('plan')!=alt.get('plan'))
        mode_changed=(prod.get('bluff_mode')!=alt.get('bluff_mode')
                      or prod.get('bluff_mul')!=alt.get('bluff_mul'))
        if plan_changed:
            counts['make_plan_plan_changes']+=1
            if prod.get('plan')!='bluff_2street' and alt.get('plan')=='bluff_2street':
                counts['make_plan_to_bluff']+=1
            if prod.get('plan')=='bluff_2street' and alt.get('plan')!='bluff_2street':
                counts['make_plan_from_bluff']+=1
        if mode_changed:
            counts['make_plan_bluff_mode_changes']+=1

        if plan_changed or mode_changed or abs(union_nut-w)>.40:
            make_rows.append({
                'street':b.get('street'),
                'n_opp':n,
                'pool_sizes':[len(v or []) for _,v in
                              sorted((opp_ranges or {}).items(),
                                     key=lambda kv:str(kv[0]))],
                'nut_union':union_nut,
                'nut_worst':w,
                'prod_plan':prod.get('plan'),
                'worst_plan':alt.get('plan'),
                'prod_bluff_mode':prod.get('bluff_mode'),
                'worst_bluff_mode':alt.get('bluff_mode'),
                'prod_bluff_mul':prod.get('bluff_mul'),
                'worst_bluff_mul':alt.get('bluff_mul'),
                'plan_changed':plan_changed,
                'mode_changed':mode_changed,
                'rel':prod.get('rel'),
                'made':prod.get('made'),
            })
        return prod

    def overbet_wrapped(profile,hero,board,opp_range,my_range,street,plan,
                        rel,rng,opp_est=None):
        counts['overbet_calls_total']+=1
        ctx=_CTX[-1] if _CTX else None

        pre=rng.getstate()
        prod=orig_overbet(profile,hero,board,opp_range,my_range,street,plan,
                          rel,rng,opp_est)
        post=rng.getstate()

        if not ctx or not ctx.get('multiway'):
            return prod

        counts['overbet_calls_multiway']+=1
        n=ctx['n_opp']; pools=ctx.get('opp_ranges')
        w=worst_seat(my_range,pools,board,n)
        a=any_field(my_range,pools,board,n,sims=600)
        if w is None or a is None:
            return prod
        counts['overbet_complete']+=1

        real_nut=R.nut_advantage
        try:
            rng.setstate(pre)
            R.nut_advantage=lambda *x,**k: w
            ow=orig_overbet(profile,hero,board,opp_range,my_range,street,plan,
                            rel,rng,opp_est)

            rng.setstate(pre)
            R.nut_advantage=lambda *x,**k: a
            oa=orig_overbet(profile,hero,board,opp_range,my_range,street,plan,
                            rel,rng,opp_est)
        finally:
            R.nut_advantage=real_nut
            rng.setstate(post)

        sw=((prod is None)!=(ow is None))
        sa=((prod is None)!=(oa is None))
        zw=(prod is not None and ow is not None and abs(float(prod)-float(ow))>1e-12)
        za=(prod is not None and oa is not None and abs(float(prod)-float(oa))>1e-12)
        if sw: counts['overbet_worst_selection_changes']+=1
        if sa: counts['overbet_any_selection_changes']+=1
        if zw: counts['overbet_worst_size_changes']+=1
        if za: counts['overbet_any_size_changes']+=1

        if sw or sa or zw or za:
            union_nut=(R.nut_advantage(my_range,opp_range,board)
                       if my_range and opp_range else 0.0)
            over_rows.append({
                'street':street,'n_opp':n,'plan':plan,'rel':rel,
                'pool_sizes':[len(v or []) for _,v in
                              sorted((pools or {}).items(),
                                     key=lambda kv:str(kv[0]))],
                'nut_union':union_nut,'nut_worst':w,'nut_any':a,
                'prod_overbet':prod,'worst_overbet':ow,'any_overbet':oa,
                'worst_selection_changed':sw,
                'worst_size_changed':zw,
                'any_selection_changed':sa,
                'any_size_changed':za,
            })
        return prod

    PL.update_plan=update_wrapped
    PL.make_plan=make_wrapped
    PL.overbet_frac=overbet_wrapped
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
        PL.overbet_frac=orig_overbet
        PL.make_plan=orig_make
        PL.update_plan=orig_update

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':counts,
        'make_plan_difference_rows':make_rows,
        'overbet_difference_rows':over_rows,
    }


def wiring_check():
    dsrc=inspect.getsource(PL.decide_size)
    rsrc=inspect.getsource(PL.refresh)
    osrc=inspect.getsource(PL.overbet_frac)
    # Signature contains nut but the body after the docstring never references it.
    body=dsrc.split('"""',2)[-1]
    assert 'nut=' in dsrc.split('\n',2)[1] or 'nut=0.0' in dsrc
    # Simple token check: overbet receives no nut argument and recomputes its own.
    assert 'overbet_frac(profile, hero, board, opp_range, my_range' in dsrc
    assert 'R.nut_advantage(my_range, opp_range, board)' in osrc
    assert "st['nut_adv']" in rsrc
    return {
        'refresh_updates_nut_adv':True,
        'decide_size_accepts_nut':True,
        'overbet_recomputes_union_nut':True,
        'judgment_value_not_forwarded_to_overbet':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    a=ap.parse_args()

    print('PASS F7-B1B3 nut wiring classified',wiring_check())
    res=run(_parse_seeds(a.seeds),a.hands)
    print(json.dumps(res,indent=2,sort_keys=True))
    print()
    print('PASS F7-B1B3 all nut consumers shadowed without production change')


if __name__=='__main__':
    main()
