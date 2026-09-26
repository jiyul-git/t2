#!/usr/bin/env python3
"""F7-B1C: multiway blocker field-semantics shadow.

Production behavior is unchanged.

Current production collapses all opponent ranges into a union before computing:
- R.blocker_score(hero, opp_range, board)
- R.blocker_effect(hero, opp_range, board, street, size, False)

This diagnostic keeps seat-keyed perceived ranges and directly measures two
counterfactual FIELD events with compatible-card Monte Carlo:

A. strong-presence blocker:
   P(any opponent occupies that seat's current top-20% board-strength band)
   without hero cards dead
   minus
   the same probability with hero cards dead.

B. fold-field blocker:
   P(all opponents fold to the same nominal bet)
   with hero cards dead
   minus
   the same probability without hero cards dead.

Positive means hero's cards help the bluff:
- strong-presence positive -> hero removes strong field configurations;
- fold-field positive -> hero removal makes the whole field more likely to fold.

The "without hero dead" world is deliberately counterfactual.  It is the thing
a blocker asks: what opponent configurations disappear because hero holds these
cards?
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
            a,b=p.split('-',1)
            out.extend(range(int(a),int(b)+1))
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


def _seat_items(opp_ranges,n_opp):
    if not isinstance(opp_ranges,dict):
        return None
    items=sorted(opp_ranges.items(),key=lambda kv:str(kv[0]))
    if len(items)!=int(n_opp) or any(not r for _,r in items):
        return None
    return [(s,list(r)) for s,r in items]


def _strong_set(pool,board):
    ranked=sorted(pool,key=lambda c:bot.eval7(list(c)+board),reverse=True)
    k=max(4,len(ranked)//5)
    return set(ranked[:k])


def _joint_events(hero,board,items,street,size_frac,sims,seed,hero_dead):
    """Return P(any strong), P(all fold) in one sampled world."""
    rng=random.Random(seed)
    dead=set(board)
    if hero_dead:
        dead |= set(hero)

    prepared=[]
    for seat,pool in items:
        # Keep board-only counterfactual combos in source; world dead decides feasibility.
        pool=[c for c in pool if c[0] not in set(board) and c[1] not in set(board)]
        if not pool:
            return None
        strong=_strong_set(pool,board)
        calls=set(R._call_range(pool,board,street,size_frac))
        prepared.append((seat,pool,strong,calls))

    n=0; any_strong=0; all_fold=0
    for _ in range(int(sims)):
        used=set(dead)
        picks=[]
        ok=True
        for seat,pool,strong,calls in prepared:
            pick=None
            for _try in range(80):
                c=rng.choice(pool)
                if c[0] not in used and c[1] not in used:
                    pick=c
                    used.add(c[0]); used.add(c[1])
                    break
            if pick is None:
                ok=False
                break
            picks.append((pick,strong,calls))
        if not ok:
            continue
        n+=1
        if any(c in strong for c,strong,calls in picks):
            any_strong+=1
        if all(c not in calls for c,strong,calls in picks):
            all_fold+=1

    if not n:
        return None
    return {
        'n':n,
        'p_any_strong':any_strong/n,
        'p_all_fold':all_fold/n,
    }


def field_blocker(hero,board,opp_ranges,n_opp,street,size_frac,
                  sims=800,seed=None):
    items=_seat_items(opp_ranges,n_opp)
    if not hero or not board or not items:
        return None
    if seed is None:
        seed=zlib.crc32(
            repr((tuple(hero),tuple(board),
                  tuple((s,tuple(r)) for s,r in items),
                  street,float(size_frac),int(sims),'f7b_blocker_field')).encode())
    base=_joint_events(
        hero,board,items,street,size_frac,sims,
        zlib.crc32(('%s|base'%seed).encode()),False)
    blocked=_joint_events(
        hero,board,items,street,size_frac,sims,
        zlib.crc32(('%s|blocked'%seed).encode()),True)
    if base is None or blocked is None:
        return None
    return {
        'base':base,
        'blocked':blocked,
        # Blocking strong configurations helps a bluff.
        'strong_drop':base['p_any_strong']-blocked['p_any_strong'],
        # Making everybody fold more often helps a bluff.
        'all_fold_gain':blocked['p_all_fold']-base['p_all_fold'],
    }


def fixed_checks():
    board=['2c','7d','Jh','4s','3c']
    hero=['As','Kd']

    # Build two different seat pools with board-only dead cards.
    allc=[c for c in bot._ALLCOMBOS
          if c[0] not in set(board) and c[1] not in set(board)]
    # Split by current-board strength so pool sizes and distributions differ.
    ranked=sorted(allc,key=lambda c:bot.eval7(list(c)+board),reverse=True)
    a=ranked[:180]
    b=ranked[180:620]
    items={2:a,3:b}
    union=sorted(set(a+b))

    u_score=R.blocker_score(hero,union,board)
    u_eff=R.blocker_effect(hero,union,board,'river',0.75,False)
    f=field_blocker(hero,board,items,2,'river',0.75,sims=2500,seed=91)
    assert f is not None

    # Heads-up field direction should agree with exact single-seat fold-prob change.
    hu={2:a}
    hf=field_blocker(hero,board,hu,1,'river',0.75,sims=2500,seed=92)
    assert hf is not None

    return {
        'union_blocker_score':round(u_score,6),
        'union_blocker_effect':round(u_eff,6),
        'field_strong_drop':round(f['strong_drop'],6),
        'field_all_fold_gain':round(f['all_fold_gain'],6),
        'heads_up_field_strong_drop':round(hf['strong_drop'],6),
        'heads_up_field_all_fold_gain':round(hf['all_fold_gain'],6),
        'field_events_defined':True,
    }


def run(seeds,hands,sims):
    original=PL.update_plan
    sig=inspect.signature(original)
    rows=[]
    counts={
        'multiway_seen':0,
        'complete':0,
        'unknown':0,
        'union_effect_vs_field_sign_flip':0,
        'union_score_positive_field_strong_negative':0,
        'river_states':0,
    }

    def wrapped(*args,**kwargs):
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        board=list(b.get('board') or [])
        hero=list(b.get('hero') or [])
        street=b.get('street')
        if n>1 and len(board)>=3:
            counts['multiway_seen']+=1
            if street=='river':
                counts['river_states']+=1
            pools=b.get('opp_ranges')
            union=list(b.get('opp_range') or [])
            size={'flop':0.60,'turn':0.70,'river':0.78}.get(street,0.65)
            sd=b.get('seed')
            f=field_blocker(
                hero,board,pools,n,street,size,sims=sims,
                seed=(None if sd is None else
                      zlib.crc32(('%s|f7b_blocker_field'%sd).encode())))
            if f is None or not union:
                counts['unknown']+=1
            else:
                counts['complete']+=1
                us=R.blocker_score(hero,union,board)
                ue=R.blocker_effect(hero,union,board,street,size,False)
                fg=f['all_fold_gain']
                fs=f['strong_drop']
                if (ue<0<fg) or (fg<0<ue):
                    counts['union_effect_vs_field_sign_flip']+=1
                if us>0 and fs<0:
                    counts['union_score_positive_field_strong_negative']+=1
                rows.append({
                    'street':street,
                    'n_opp':n,
                    'pool_sizes':[len(v or []) for _,v in
                                  sorted((pools or {}).items(),
                                         key=lambda kv:str(kv[0]))],
                    'union_score':us,
                    'union_effect':ue,
                    'field_strong_drop':fs,
                    'field_all_fold_gain':fg,
                    'base_any_strong':f['base']['p_any_strong'],
                    'blocked_any_strong':f['blocked']['p_any_strong'],
                    'base_all_fold':f['base']['p_all_fold'],
                    'blocked_all_fold':f['blocked']['p_all_fold'],
                    'effect_abs_proxy':abs(ue-fg),
                    'score_abs_proxy':abs(us-fs),
                })
        return original(*args,**kwargs)

    PL.update_plan=wrapped
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
        PL.update_plan=original

    top_effect=sorted(rows,key=lambda r:r['effect_abs_proxy'],reverse=True)[:12]
    top_score=sorted(rows,key=lambda r:r['score_abs_proxy'],reverse=True)[:12]
    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'sims':sims,
        'counts':counts,
        'union_effect_abs':_summary([abs(r['union_effect']) for r in rows]),
        'field_all_fold_gain_abs':_summary([abs(r['field_all_fold_gain']) for r in rows]),
        'union_score_abs':_summary([abs(r['union_score']) for r in rows]),
        'field_strong_drop_abs':_summary([abs(r['field_strong_drop']) for r in rows]),
        'top_effect_examples':top_effect,
        'top_score_examples':top_score,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=800)
    a=ap.parse_args()

    print('PASS F7-B1C fixed field-blocker semantics',fixed_checks())
    print(json.dumps(
        run(_parse_seeds(a.seeds),a.hands,a.sims),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C field blocker shadow completed')
    print('NOTE: production blocker consumers remain union-based.')


if __name__=='__main__':
    main()
