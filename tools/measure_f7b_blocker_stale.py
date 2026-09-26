#!/usr/bin/env python3
"""F7-B1C7 stale blocker judgment audit.

Diagnostic only. Production behavior is unchanged.

Current architecture:
- make_plan computes blocker/blocker_net once and stores them;
- refresh updates rel/eq/outs/nut/range_adv but NOT blocker metrics;
- decide_size later consumes stackoff['_blk_net'], copied from make_plan;
- river_fix independently recomputes UNION blocker_effect on the river.

This tool measures, at every multiway refresh:
1. stored blocker/blocker_net vs current-board UNION recomputation;
2. stored stackoff['_blk_net'] vs current-board UNION recomputation;
3. stored/current UNION vs same-scale JOINT blocker_effect;
4. implied value-sizing multiplier drift from stale stackoff blocker;
5. river semibluff states where river_fix's current union blocker disagrees
   with the joint field-semantic blocker.

No strategy outputs are changed.
"""
import argparse
import inspect
import json
import math
import os
import statistics
import sys
import zlib

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
import ranges as R
import persona as PS
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
    xs=[float(x) for x in xs if x is not None]
    if not xs:
        return {'n':0}
    ys=sorted(xs)
    def q(p):
        if len(ys)==1:
            return ys[0]
        pos=(len(ys)-1)*p
        lo=int(math.floor(pos)); hi=int(math.ceil(pos))
        if lo==hi:
            return ys[lo]
        w=pos-lo
        return ys[lo]*(1-w)+ys[hi]*w
    return {
        'n':len(xs),
        'mean':round(statistics.mean(xs),6),
        'p50':round(q(.50),6),
        'p90':round(q(.90),6),
        'max':round(max(xs),6),
    }


def _sign_flip(a,b,eps=1e-12):
    return (a < -eps and b > eps) or (a > eps and b < -eps)


def _value_size_factor(net):
    return max(0.75,min(1.25,1.0-2.0*float(net or 0.0)))


def run(seeds,hands,sims):
    orig_refresh=PL.refresh
    sig=inspect.signature(orig_refresh)

    counts={
        'refresh_calls_total':0,
        'refresh_calls_multiway':0,
        'refresh_complete_joint':0,
        'refresh_unknown_joint':0,
        'stored_net_vs_current_union_changed':0,
        'stored_net_vs_current_union_sign_flip':0,
        'stored_net_vs_joint_sign_flip':0,
        'stackoff_net_vs_current_union_changed':0,
        'value_size_factor_changed_ge_002':0,
        'river_refresh_states':0,
        'river_semibluff_refresh_states':0,
        'river_union_vs_joint_sign_flip':0,
    }
    rows=[]
    stale_abs=[]
    joint_abs=[]
    size_abs=[]

    def wrapped(*args,**kwargs):
        counts['refresh_calls_total']+=1
        b=sig.bind_partial(*args,**kwargs).arguments
        state=b.get('state') or {}
        n=int(b.get('n_opp') or 1)
        hero=list(b.get('hero') or [])
        board=list(b.get('board') or [])
        opp_range=list(b.get('opp_range') or [])
        profile=b.get('profile') or {}
        street=b.get('street')
        pools=b.get('opp_ranges')
        seed=b.get('seed')

        if n>1 and board and opp_range:
            counts['refresh_calls_multiway']+=1
            typ={'flop':0.60,'turn':0.70,'river':0.78}.get(street,0.65)
            bg=(max(0.0,min(1.0,(PS.sk(profile,'blocker')-1.0)/7.0))
                if profile.get('concepts') else 1.0)

            current_union_raw=R.blocker_effect(
                hero,opp_range,board,street,typ,False)
            current_union=current_union_raw*bg
            current_score=R.blocker_score(hero,opp_range,board)*bg

            js=(None if seed is None else
                zlib.crc32(('%s|f7b_blocker_refresh'%seed).encode()))
            joint_raw=R.joint_blocker_effect(
                hero,pools,board,street,typ,n_opp=n,sims=sims,seed=js)
            joint=(None if joint_raw is None else joint_raw*bg)

            stored=float(state.get('blocker_net') or 0.0)
            stored_score=float(state.get('blocker') or 0.0)
            so=state.get('stackoff') or {}
            stackoff_net=(float(so.get('_blk_net') or 0.0)
                          if isinstance(so,dict) else 0.0)

            d=abs(stored-current_union)
            stale_abs.append(d)
            if d>1e-9:
                counts['stored_net_vs_current_union_changed']+=1
            if _sign_flip(stored,current_union):
                counts['stored_net_vs_current_union_sign_flip']+=1

            ds=abs(stackoff_net-current_union)
            if ds>1e-9:
                counts['stackoff_net_vs_current_union_changed']+=1

            old_sf=_value_size_factor(stackoff_net)
            cur_sf=_value_size_factor(current_union)
            sdf=abs(old_sf-cur_sf)
            size_abs.append(sdf)
            if sdf>=0.02:
                counts['value_size_factor_changed_ge_002']+=1

            if joint is None:
                counts['refresh_unknown_joint']+=1
            else:
                counts['refresh_complete_joint']+=1
                joint_abs.append(abs(current_union-joint))
                if _sign_flip(stored,joint):
                    counts['stored_net_vs_joint_sign_flip']+=1
                if street=='river' and _sign_flip(current_union,joint):
                    counts['river_union_vs_joint_sign_flip']+=1

            if street=='river':
                counts['river_refresh_states']+=1
                if state.get('plan')=='semibluff':
                    counts['river_semibluff_refresh_states']+=1

            if (d>=0.03 or sdf>=0.03
                    or (joint is not None and abs(current_union-joint)>=0.08)
                    or _sign_flip(stored,current_union)
                    or (joint is not None and _sign_flip(current_union,joint))):
                rows.append({
                    'street':street,
                    'n_opp':n,
                    'plan':state.get('plan'),
                    'pool_sizes':[len(v or []) for _,v in
                                  sorted((pools or {}).items(),
                                         key=lambda kv:str(kv[0]))],
                    'stored_blocker':stored_score,
                    'current_score':current_score,
                    'stored_blocker_net':stored,
                    'stackoff_blocker_net':stackoff_net,
                    'current_union_net':current_union,
                    'current_joint_net':joint,
                    'stale_abs':d,
                    'union_joint_abs':(
                        None if joint is None else abs(current_union-joint)),
                    'stored_value_size_factor':old_sf,
                    'current_union_value_size_factor':cur_sf,
                    'value_size_factor_abs':sdf,
                })

        return orig_refresh(*args,**kwargs)

    PL.refresh=wrapped
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
        PL.refresh=orig_refresh

    rows=sorted(
        rows,
        key=lambda r:max(
            r.get('stale_abs') or 0.0,
            r.get('union_joint_abs') or 0.0,
            r.get('value_size_factor_abs') or 0.0),
        reverse=True)

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'sims':sims,
        'counts':counts,
        'stored_vs_current_union_abs':_summary(stale_abs),
        'current_union_vs_joint_abs':_summary(joint_abs),
        'value_size_factor_abs':_summary(size_abs),
        'largest_rows':rows[:30],
    }


def source_check():
    rsrc=inspect.getsource(PL.refresh)
    dsrc=inspect.getsource(PL.decide_size)
    rvsrc=inspect.getsource(PL.river_fix)

    assert "st['blocker_net']" not in rsrc
    assert "st['blocker']" not in rsrc
    assert "(stackoff or {}).get('_blk_net')" in dsrc
    assert "R.blocker_effect(hero, opp_range, board, 'river', 0.75, False)" in rvsrc

    return {
        'refresh_does_not_update_blocker':True,
        'value_sizing_reads_make_plan_stackoff_copy':True,
        'river_fix_recomputes_union_separately':True,
        'three_blocker_paths_confirmed':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=1000)
    a=ap.parse_args()

    print('PASS F7-B1C7 blocker stale-path source check',source_check())
    print(json.dumps(
        run(_parse_seeds(a.seeds),a.hands,a.sims),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C7 blocker stale judgment audit completed')
    print('NOTE: production behavior unchanged.')


if __name__=='__main__':
    main()
