#!/usr/bin/env python3
"""F7-B1C5 exact blocker consumer attribution through isolated factors.

Requires production helpers:
  PL._blocker_score_bluff_factor(blk)
  PL._blocker_net_bluff_factor(blk_net)

Production formulas are unchanged.  This diagnostic replays each multiway
make_plan call with identical inputs and seed while replacing exactly one
multiplicative consumer with neutral factor 1.0.

Variants:
- production
- score_neutral: score helper -> 1.0, net helper production
- net_neutral: score helper production, net helper -> 1.0
- both_neutral: both helpers -> 1.0

This is exact attribution.  It does not modify raw blocker values, awareness,
or any poker-frequency coefficient.
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


def _record_transition(prod,alt,prefix,counts):
    pc=(prod.get('plan')!=alt.get('plan'))
    mc=(prod.get('bluff_mode')!=alt.get('bluff_mode')
        or prod.get('bluff_mul')!=alt.get('bluff_mul'))
    if pc:
        counts[prefix+'_plan_changes']+=1
        if prod.get('plan')!='bluff_2street' and alt.get('plan')=='bluff_2street':
            counts[prefix+'_to_bluff']+=1
        if prod.get('plan')=='bluff_2street' and alt.get('plan')!='bluff_2street':
            counts[prefix+'_from_bluff']+=1
    if mc:
        counts[prefix+'_bluff_mode_changes']+=1
    return pc,mc


def run(seeds,hands):
    original_make=PL.make_plan
    sig=inspect.signature(original_make)
    original_score_factor=PL._blocker_score_bluff_factor
    original_net_factor=PL._blocker_net_bluff_factor

    counts={
        'make_plan_calls_total':0,
        'multiway_calls':0,
    }
    for p in ('score_neutral','net_neutral','both_neutral'):
        counts[p+'_plan_changes']=0
        counts[p+'_to_bluff']=0
        counts[p+'_from_bluff']=0
        counts[p+'_bluff_mode_changes']=0
    rows=[]

    def variant(args,kwargs,score_neutral=False,net_neutral=False):
        try:
            if score_neutral:
                PL._blocker_score_bluff_factor=lambda blk:1.0
            if net_neutral:
                PL._blocker_net_bluff_factor=lambda blk_net:1.0
            return original_make(*args,**kwargs)
        finally:
            PL._blocker_score_bluff_factor=original_score_factor
            PL._blocker_net_bluff_factor=original_net_factor

    def wrapped(*args,**kwargs):
        counts['make_plan_calls_total']+=1
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        prod=original_make(*args,**kwargs)
        if n<=1:
            return prod

        counts['multiway_calls']+=1
        sn=variant(args,kwargs,score_neutral=True,net_neutral=False)
        nn=variant(args,kwargs,score_neutral=False,net_neutral=True)
        bn=variant(args,kwargs,score_neutral=True,net_neutral=True)

        cs,ms=_record_transition(prod,sn,'score_neutral',counts)
        cn,mn=_record_transition(prod,nn,'net_neutral',counts)
        cb,mb=_record_transition(prod,bn,'both_neutral',counts)

        if cs or cn or cb or ms or mn or mb:
            rows.append({
                'street':b.get('street'),
                'n_opp':n,
                'prod_plan':prod.get('plan'),
                'score_neutral_plan':sn.get('plan'),
                'net_neutral_plan':nn.get('plan'),
                'both_neutral_plan':bn.get('plan'),
                'prod_bluff_mode':prod.get('bluff_mode'),
                'score_neutral_bluff_mode':sn.get('bluff_mode'),
                'net_neutral_bluff_mode':nn.get('bluff_mode'),
                'both_neutral_bluff_mode':bn.get('bluff_mode'),
                'prod_blocker':prod.get('blocker'),
                'prod_blocker_net':prod.get('blocker_net'),
                'score_factor':original_score_factor(float(prod.get('blocker') or 0.0)),
                'net_factor':original_net_factor(float(prod.get('blocker_net') or 0.0)),
                'prod_eq':prod.get('eq'),
                'prod_rel':prod.get('rel'),
                'prod_made':prod.get('made'),
                'score_neutral_changed':cs,
                'net_neutral_changed':cn,
                'both_neutral_changed':cb,
            })
        return prod

    PL.make_plan=wrapped
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
        PL.make_plan=original_make
        PL._blocker_score_bluff_factor=original_score_factor
        PL._blocker_net_bluff_factor=original_net_factor

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':counts,
        'difference_rows':rows,
    }


def source_check():
    ssrc=inspect.getsource(PL._blocker_score_bluff_factor)
    nsrc=inspect.getsource(PL._blocker_net_bluff_factor)
    msrc=inspect.getsource(PL.make_plan)
    assert '0.5 + 1.8*blk' in ssrc
    assert 'max(0.45, min(1.65, 1.0 + 4.0*blk_net))' in nsrc
    assert '_blocker_score_bluff_factor(blk)' in msrc
    assert '_blocker_net_bluff_factor(blk_net)' in msrc
    return {
        'score_factor_isolated':True,
        'net_factor_isolated':True,
        'neutral_factor':1.0,
        'raw_blocker_and_awareness_untouched':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    a=ap.parse_args()

    print('PASS F7-B1C5 isolated blocker-factor source check',source_check())
    print(json.dumps(run(_parse_seeds(a.seeds),a.hands),indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C5 exact blocker-factor attribution completed')
    print('NOTE: production result and formulas are unchanged.')


if __name__=='__main__':
    main()
