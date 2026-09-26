#!/usr/bin/env python3
"""F7-B1C6: same-scale joint multiway blocker-effect shadow.

Production behavior is unchanged.

Unlike the earlier direct field fold-probability delta, R.joint_blocker_effect
uses the SAME normalized semantic unit as legacy R.blocker_effect:

    blocked continuation rate - blocked all-fold rate

where "rate" is measured over compatible joint opponent configurations.

Therefore:
- heads-up parity is exact;
- multiway card collisions are respected;
- missing seat pools return None rather than inventing a union;
- the result remains in [-1, 1] and can be compared to the current consumer
  without inventing a new scaling coefficient.

Candidate strategy shadow:
- neutralize the approximate blocker_score bluff factor to exactly 1.0;
- replace the union blocker_effect with joint_blocker_effect;
- leave every existing coefficient, awareness multiplier, RNG seed and other
  judgment unchanged.

Production make_plan output is always returned.
"""
import argparse
import inspect
import json
import os
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


def _summary(xs):
    xs=[float(x) for x in xs]
    if not xs:
        return {'n':0}
    ys=sorted(xs)
    def q(p):
        return ys[min(len(ys)-1, int(round((len(ys)-1)*p)))]
    return {
        'n':len(xs),
        'mean':round(statistics.mean(xs),6),
        'p50':round(q(.50),6),
        'p90':round(q(.90),6),
        'max':round(max(xs),6),
    }


def fixed_checks():
    hero=['As','Kd']
    board=['2c','7d','Jh']
    dead=set(board)

    # Board-only pool deliberately retains hero-overlap combos.
    pool=[c for c in bot._ALLCOMBOS
          if c[0] not in dead and c[1] not in dead][:420]

    legacy=R.blocker_effect(hero,pool,board,'flop',0.60,False)
    hu=R.joint_blocker_effect(
        hero,{2:pool},board,'flop',0.60,n_opp=1,sims=10,seed=1)
    assert abs(legacy-hu)<1e-12,(legacy,hu)

    inv=R.blocker_effect(hero,pool,board,'flop',0.60,True)
    hu_inv=R.joint_blocker_effect(
        hero,{2:pool},board,'flop',0.60,n_opp=1,sims=10,seed=1,
        for_value=True)
    assert abs(inv-hu_inv)<1e-12,(inv,hu_inv)

    missing=R.joint_blocker_effect(
        hero,{2:pool,3:[]},board,'flop',0.60,n_opp=2,sims=100,seed=1)
    assert missing is None,missing

    return {
        'heads_up_bluff_parity':True,
        'heads_up_value_parity':True,
        'missing_pool_unknown':True,
        'same_scale':True,
    }


def run(seeds,hands,sims):
    original=PL.make_plan
    sig=inspect.signature(original)
    real_score_factor=PL._blocker_score_bluff_factor
    real_effect=R.blocker_effect

    counts={
        'make_plan_calls_total':0,
        'multiway_calls':0,
        'complete_joint':0,
        'unknown_joint':0,
        'union_vs_joint_sign_flip':0,
        'candidate_plan_changes':0,
        'candidate_to_bluff':0,
        'candidate_from_bluff':0,
        'candidate_bluff_mode_changes':0,
    }
    rows=[]
    absdiff=[]

    def wrapped(*args,**kwargs):
        counts['make_plan_calls_total']+=1
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        prod=original(*args,**kwargs)
        if n<=1:
            return prod

        counts['multiway_calls']+=1
        hero=list(b.get('hero') or [])
        board=list(b.get('board') or [])
        street=b.get('street')
        pools=b.get('opp_ranges')
        union=list(b.get('opp_range') or [])
        size={'flop':0.60,'turn':0.70,'river':0.78}.get(street,0.65)
        sd=b.get('seed')
        js=(None if sd is None else
            zlib.crc32(('%s|f7b_joint_blocker'%sd).encode()))
        joint=R.joint_blocker_effect(
            hero,pools,board,street,size,n_opp=n,sims=sims,seed=js)
        if joint is None:
            counts['unknown_joint']+=1
            return prod

        counts['complete_joint']+=1
        union_eff=real_effect(hero,union,board,street,size,False) if union else 0.0
        absdiff.append(abs(union_eff-joint))
        if (union_eff<0<joint) or (joint<0<union_eff):
            counts['union_vs_joint_sign_flip']+=1

        try:
            PL._blocker_score_bluff_factor=lambda blk:1.0
            R.blocker_effect=lambda *a,**k: joint
            alt=original(*args,**kwargs)
        finally:
            PL._blocker_score_bluff_factor=real_score_factor
            R.blocker_effect=real_effect

        pc=(prod.get('plan')!=alt.get('plan'))
        mc=(prod.get('bluff_mode')!=alt.get('bluff_mode')
            or prod.get('bluff_mul')!=alt.get('bluff_mul'))
        if pc:
            counts['candidate_plan_changes']+=1
            if prod.get('plan')!='bluff_2street' and alt.get('plan')=='bluff_2street':
                counts['candidate_to_bluff']+=1
            if prod.get('plan')=='bluff_2street' and alt.get('plan')!='bluff_2street':
                counts['candidate_from_bluff']+=1
        if mc:
            counts['candidate_bluff_mode_changes']+=1

        if pc or mc or abs(union_eff-joint)>=0.10:
            rows.append({
                'street':street,
                'n_opp':n,
                'pool_sizes':[len(v or []) for _,v in
                              sorted((pools or {}).items(),key=lambda kv:str(kv[0]))],
                'prod_plan':prod.get('plan'),
                'candidate_plan':alt.get('plan'),
                'prod_bluff_mode':prod.get('bluff_mode'),
                'candidate_bluff_mode':alt.get('bluff_mode'),
                'prod_blocker':prod.get('blocker'),
                'prod_blocker_net':prod.get('blocker_net'),
                'union_effect_raw':union_eff,
                'joint_effect_raw':joint,
                'abs_diff':abs(union_eff-joint),
                'prod_eq':prod.get('eq'),
                'prod_rel':prod.get('rel'),
                'prod_made':prod.get('made'),
                'plan_changed':pc,
                'mode_changed':mc,
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
        PL._blocker_score_bluff_factor=real_score_factor
        R.blocker_effect=real_effect

    rows=sorted(rows,key=lambda r:r['abs_diff'],reverse=True)
    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'sims':sims,
        'counts':counts,
        'union_joint_abs_diff':_summary(absdiff),
        'difference_rows':rows[:30],
    }


def source_check():
    src=inspect.getsource(R.joint_blocker_effect)
    assert 'return blocker_effect(' in src
    assert 'blocked_continue / float(continue_n)' in src
    assert 'blocked_fold / float(fold_n)' in src
    assert 'return None' in src
    return {
        'hu_delegates_to_legacy':True,
        'joint_continue_vs_all_fold':True,
        'missing_is_unknown':True,
        'production_consumer_unchanged':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=1200)
    a=ap.parse_args()

    print('PASS F7-B1C6 joint blocker fixed semantics',fixed_checks())
    print('PASS F7-B1C6 joint blocker source contract',source_check())
    print(json.dumps(
        run(_parse_seeds(a.seeds),a.hands,a.sims),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C6 joint blocker shadow completed')
    print('NOTE: production blocker strategy remains unchanged.')


if __name__=='__main__':
    main()
