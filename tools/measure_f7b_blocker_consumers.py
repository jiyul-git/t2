#!/usr/bin/env python3
"""F7-B1C3 blocker consumer decomposition.

Diagnostic only. Production behavior is returned unchanged.

Source contract says:
- blocker_score: approximate fallback when bet size is unknown.
- blocker_effect: more exact call-vs-fold effect when size is known.

make_plan currently knows a nominal street size and consumes BOTH:
  (0.5 + 1.8*blocker_score) * (1 + 4*blocker_effect...)

This tool isolates the duplicate strategy contribution without inventing a new
coefficient:
- production: score + effect
- effect_only: blocker_score forced to 0, preserving the formula's existing
  baseline factor 0.5 and leaving blocker_effect untouched
- score_only: blocker_effect forced to 0, leaving blocker_score untouched
- neither: both forced to 0

Only multiway make_plan calls are replayed. All variants receive identical
inputs and seed. Production result is always returned.
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
        if not p: continue
        if '-' in p:
            a,b=p.split('-',1)
            out.extend(range(int(a),int(b)+1))
        else:
            out.append(int(p))
    return out


def run(seeds,hands):
    original=PL.make_plan
    sig=inspect.signature(original)
    rows=[]
    counts={
        'make_plan_calls_total':0,
        'multiway_calls':0,
        'effect_only_plan_changes':0,
        'effect_only_to_bluff':0,
        'effect_only_from_bluff':0,
        'score_only_plan_changes':0,
        'score_only_to_bluff':0,
        'score_only_from_bluff':0,
        'neither_plan_changes':0,
        'neither_to_bluff':0,
        'neither_from_bluff':0,
    }

    def variant(args,kwargs,score_zero=False,effect_zero=False):
        real_s=R.blocker_score
        real_e=R.blocker_effect
        try:
            if score_zero:
                R.blocker_score=lambda *a,**k: 0.0
            if effect_zero:
                R.blocker_effect=lambda *a,**k: 0.0
            return original(*args,**kwargs)
        finally:
            R.blocker_score=real_s
            R.blocker_effect=real_e

    def changed(prod,alt,prefix):
        pc=(prod.get('plan')!=alt.get('plan'))
        if pc:
            counts[prefix+'_plan_changes']+=1
            if prod.get('plan')!='bluff_2street' and alt.get('plan')=='bluff_2street':
                counts[prefix+'_to_bluff']+=1
            if prod.get('plan')=='bluff_2street' and alt.get('plan')!='bluff_2street':
                counts[prefix+'_from_bluff']+=1
        return pc

    def wrapped(*args,**kwargs):
        counts['make_plan_calls_total']+=1
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        prod=original(*args,**kwargs)
        if n<=1:
            return prod

        counts['multiway_calls']+=1
        eff=variant(args,kwargs,score_zero=True,effect_zero=False)
        sco=variant(args,kwargs,score_zero=False,effect_zero=True)
        none=variant(args,kwargs,score_zero=True,effect_zero=True)

        ce=changed(prod,eff,'effect_only')
        cs=changed(prod,sco,'score_only')
        cn=changed(prod,none,'neither')

        if ce or cs or cn or abs(float(prod.get('blocker_net') or 0))>=.08:
            rows.append({
                'street':b.get('street'),
                'n_opp':n,
                'prod_plan':prod.get('plan'),
                'effect_only_plan':eff.get('plan'),
                'score_only_plan':sco.get('plan'),
                'neither_plan':none.get('plan'),
                'prod_blocker':prod.get('blocker'),
                'prod_blocker_net':prod.get('blocker_net'),
                'effect_only_blocker':eff.get('blocker'),
                'effect_only_blocker_net':eff.get('blocker_net'),
                'score_only_blocker':sco.get('blocker'),
                'score_only_blocker_net':sco.get('blocker_net'),
                'prod_rel':prod.get('rel'),
                'prod_eq':prod.get('eq'),
                'prod_made':prod.get('made'),
                'effect_only_changed':ce,
                'score_only_changed':cs,
                'neither_changed':cn,
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
        'counts':counts,
        'difference_rows':rows,
    }


def source_check():
    src=inspect.getsource(R.blocker_score)
    eff=inspect.getsource(R.blocker_effect)
    mp=inspect.getsource(PL.make_plan)
    assert '근사값이다' in src
    assert '폴백' in src
    assert '순 효과' in eff
    assert '(0.5 + 1.8*blk)' in mp
    assert '1.0 + 4.0*blk_net' in mp
    return {
        'score_declared_approx_fallback':True,
        'effect_declared_call_fold_net':True,
        'make_plan_consumes_both':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    a=ap.parse_args()

    print('PASS F7-B1C3 blocker duplicate-consumer source check',source_check())
    print(json.dumps(run(_parse_seeds(a.seeds),a.hands),indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C3 blocker consumer decomposition completed')
    print('NOTE: production make_plan result is always returned.')


if __name__=='__main__':
    main()
