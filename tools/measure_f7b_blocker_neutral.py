#!/usr/bin/env python3
"""F7-B1C4: neutralize blocker_score's multiplicative factor exactly.

Diagnostic only. Production behavior is always returned.

Correction to B1C3:
Setting blocker_score=0 does NOT remove its strategy contribution because
make_plan multiplies bluff_ok by:

    0.5 + 1.8 * blocker_score

At score=0 the factor is 0.5, not the neutral multiplicative value 1.0.

Therefore the algebraic neutral score is:

    (1.0 - 0.5) / 1.8 = 5/18

This tool compares, on identical inputs/seeds for multiway make_plan calls:

- production: current score + current effect
- score_neutral: score factor forced to exactly 1.0, effect unchanged
- effect_zero: score unchanged, blocker_effect forced to 0
- no_blocker: score factor exactly 1.0 AND blocker_effect=0

The 5/18 value is not a proposed poker parameter. It only cancels the existing
formula for attribution.
"""
import argparse
import inspect
import json
import os
import statistics
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
import ranges as R
import tourney as T

NEUTRAL_SCORE=(1.0-0.5)/1.8


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


def _transition(prod,alt,prefix,counts):
    changed=(prod.get('plan')!=alt.get('plan'))
    if changed:
        counts[prefix+'_plan_changes']+=1
        if prod.get('plan')!='bluff_2street' and alt.get('plan')=='bluff_2street':
            counts[prefix+'_to_bluff']+=1
        if prod.get('plan')=='bluff_2street' and alt.get('plan')!='bluff_2street':
            counts[prefix+'_from_bluff']+=1
    mode_changed=(
        prod.get('bluff_mode')!=alt.get('bluff_mode')
        or prod.get('bluff_mul')!=alt.get('bluff_mul'))
    if mode_changed:
        counts[prefix+'_bluff_mode_changes']+=1
    return changed,mode_changed


def run(seeds,hands):
    original=PL.make_plan
    sig=inspect.signature(original)
    rows=[]
    factors=[]
    counts={
        'make_plan_calls_total':0,
        'multiway_calls':0,
        'score_neutral_plan_changes':0,
        'score_neutral_to_bluff':0,
        'score_neutral_from_bluff':0,
        'score_neutral_bluff_mode_changes':0,
        'effect_zero_plan_changes':0,
        'effect_zero_to_bluff':0,
        'effect_zero_from_bluff':0,
        'effect_zero_bluff_mode_changes':0,
        'no_blocker_plan_changes':0,
        'no_blocker_to_bluff':0,
        'no_blocker_from_bluff':0,
        'no_blocker_bluff_mode_changes':0,
    }

    def variant(args,kwargs,neutral_score=False,effect_zero=False):
        real_s=R.blocker_score
        real_e=R.blocker_effect
        try:
            if neutral_score:
                R.blocker_score=lambda *a,**k: NEUTRAL_SCORE
            if effect_zero:
                R.blocker_effect=lambda *a,**k: 0.0
            return original(*args,**kwargs)
        finally:
            R.blocker_score=real_s
            R.blocker_effect=real_e

    def wrapped(*args,**kwargs):
        counts['make_plan_calls_total']+=1
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        prod=original(*args,**kwargs)
        if n<=1:
            return prod

        counts['multiway_calls']+=1
        score=float(prod.get('blocker') or 0.0)
        # st['blocker'] includes concept-awareness scaling.  The raw source factor
        # used inside make_plan is reconstructed only for descriptive context here.
        factors.append(0.5+1.8*score)

        sn=variant(args,kwargs,neutral_score=True,effect_zero=False)
        ez=variant(args,kwargs,neutral_score=False,effect_zero=True)
        nb=variant(args,kwargs,neutral_score=True,effect_zero=True)

        cs,ms=_transition(prod,sn,'score_neutral',counts)
        ce,me=_transition(prod,ez,'effect_zero',counts)
        cn,mn=_transition(prod,nb,'no_blocker',counts)

        if cs or ce or cn or ms or me or mn:
            rows.append({
                'street':b.get('street'),
                'n_opp':n,
                'prod_plan':prod.get('plan'),
                'score_neutral_plan':sn.get('plan'),
                'effect_zero_plan':ez.get('plan'),
                'no_blocker_plan':nb.get('plan'),
                'prod_bluff_mode':prod.get('bluff_mode'),
                'score_neutral_bluff_mode':sn.get('bluff_mode'),
                'effect_zero_bluff_mode':ez.get('bluff_mode'),
                'no_blocker_bluff_mode':nb.get('bluff_mode'),
                'prod_blocker':prod.get('blocker'),
                'prod_blocker_net':prod.get('blocker_net'),
                'prod_eq':prod.get('eq'),
                'prod_rel':prod.get('rel'),
                'prod_made':prod.get('made'),
                'score_neutral_changed':cs,
                'effect_zero_changed':ce,
                'no_blocker_changed':cn,
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
        PL.make_plan=original

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'neutral_score_exact':NEUTRAL_SCORE,
        'counts':counts,
        'observed_display_score_factor':{
            'n':len(factors),
            'min':round(min(factors),6) if factors else None,
            'mean':round(statistics.mean(factors),6) if factors else None,
            'max':round(max(factors),6) if factors else None,
        },
        'difference_rows':rows,
    }


def source_check():
    src=inspect.getsource(PL.make_plan)
    assert '(0.5 + 1.8*blk)' in src
    assert abs((0.5+1.8*NEUTRAL_SCORE)-1.0)<1e-12
    return {
        'current_formula':'0.5 + 1.8*blk',
        'score_zero_factor':0.5,
        'neutral_factor':1.0,
        'neutral_score_exact':NEUTRAL_SCORE,
        'neutral_is_algebraic_not_tuning':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    a=ap.parse_args()

    print('PASS F7-B1C4 exact blocker-score neutralization',source_check())
    print(json.dumps(run(_parse_seeds(a.seeds),a.hands),indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C4 blocker neutral-factor attribution completed')
    print('NOTE: production make_plan result is always returned.')


if __name__=='__main__':
    main()
