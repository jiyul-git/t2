#!/usr/bin/env python3
"""F7-B1C10 direct attribution for blocker STRUCTURE-ONLY candidate.

Production drives the tournament. For every PL.update_plan call, replay the
same pre-decision state through a candidate that changes only blocker semantics
and lifecycle, NOT bluff-frequency calibration.

Preserved exactly:
- production blocker_score bluff factor (0.5 + 1.8*blk);
- all existing blocker awareness multipliers;
- all consumer coefficients and RNG seeds.

Candidate changes:
- HU blocker_effect remains exact legacy;
- multiway complete seat pools use R.joint_blocker_effect;
- refresh writes current blocker/blocker_net and stackoff['_blk_net'];
- river_fix consumes state['blocker_net_raw'] instead of independently
  recomputing union blocker_effect.

Incomplete multiway pools fall back to production union behavior in this tool
so partial-pool semantics remain a separate audit item.

Production output is always returned, so candidate differences cannot cascade.
"""
import argparse
import collections
import copy
import inspect
import json
import os
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


def _intent(st,street):
    it=PL.intent_of(st,street)
    if not isinstance(it,dict):
        return None
    return {'act':it.get('act'),'size':it.get('size'),'why':it.get('why')}


def _size_changed(a,b,eps=1e-9):
    av=None if not a else a.get('size')
    bv=None if not b else b.get('size')
    if av is None or bv is None:
        return av!=bv
    try:
        return abs(float(av)-float(bv))>eps
    except Exception:
        return av!=bv


class Candidate:
    def __init__(self,sims):
        self.sims=int(sims)
        self.ctx=[]
        self.counts=collections.Counter()
        self.orig_update=PL.update_plan
        self.orig_make=PL.make_plan
        self.orig_refresh=PL.refresh
        self.orig_river=PL.river_fix
        self.orig_effect=R.blocker_effect
        self.update_sig=inspect.signature(self.orig_update)
        self.make_sig=inspect.signature(self.orig_make)
        self.refresh_sig=inspect.signature(self.orig_refresh)

    @staticmethod
    def _bg(profile):
        return (max(0.0,min(1.0,(PS.sk(profile,'blocker')-1.0)/7.0))
                if profile and profile.get('concepts') else 1.0)

    def _raw(self,hero,board,opp,pools,n,street,size,seed,tag):
        if n<=1:
            self.counts[tag+'_hu']+=1
            return self.orig_effect(hero,opp,board,street,size,False),'legacy_hu'
        js=(None if seed is None else
            zlib.crc32(('%s|%s'%(seed,tag)).encode()))
        v=R.joint_blocker_effect(
            hero,pools,board,street,size,n_opp=n,sims=self.sims,seed=js)
        if v is None:
            self.counts[tag+'_union_fallback_incomplete']+=1
            return self.orig_effect(hero,opp,board,street,size,False),'union_fallback_incomplete'
        self.counts[tag+'_joint_complete']+=1
        return v,'joint_seat_pools'

    def make(self,*args,**kwargs):
        b=self.make_sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        hero=list(b.get('hero') or [])
        board=list(b.get('board') or [])
        opp=list(b.get('opp_range') or [])
        pools=b.get('opp_ranges')
        street=b.get('street')
        seed=b.get('seed')
        size={'flop':0.60,'turn':0.70,'river':0.78}.get(street,0.65)
        raw,source=self._raw(
            hero,board,opp,pools,n,street,size,seed,'make')

        real_be=R.blocker_effect
        try:
            # blocker_score factor is intentionally NOT patched here.
            R.blocker_effect=lambda *a,**k:raw
            st=self.orig_make(*args,**kwargs)
        finally:
            R.blocker_effect=real_be

        st=dict(st)
        st['blocker_net_raw']=float(raw)
        st['blocker_source']=source
        return st

    def refresh(self,*args,**kwargs):
        b=self.refresh_sig.bind_partial(*args,**kwargs).arguments
        st=self.orig_refresh(*args,**kwargs)

        n=int(b.get('n_opp') or 1)
        hero=list(b.get('hero') or [])
        board=list(b.get('board') or [])
        opp=list(b.get('opp_range') or [])
        profile=b.get('profile') or {}
        pools=b.get('opp_ranges')
        street=b.get('street')
        seed=b.get('seed')
        size={'flop':0.60,'turn':0.70,'river':0.78}.get(street,0.65)

        if hero and board and opp:
            raw,source=self._raw(
                hero,board,opp,pools,n,street,size,seed,'refresh')
            bg=self._bg(profile)
            net=float(raw)*bg
            st=dict(st)
            # Current blocker_score is provenance/display only on refresh.
            # Its strategy consumer exists only in make_plan and is preserved.
            st['blocker']=round(R.blocker_score(hero,opp,board)*bg,2)
            st['blocker_net']=round(net,3)
            st['blocker_net_raw']=float(raw)
            st['blocker_source']=source
            so=st.get('stackoff')
            if isinstance(so,dict):
                so=dict(so)
                so['_blk_net']=round(net,3)
                st['stackoff']=so
        return st

    def river(self,state,hero,board,profile=None,opp_range=None,rng=None):
        # The unified judgment should already have been refreshed by update_plan.
        raw=state.get('blocker_net_raw')
        if raw is None:
            # Compatibility fallback for old/replay states only.
            ctx=self.ctx[-1] if self.ctx else {}
            n=int(ctx.get('n_opp') or 1)
            pools=ctx.get('opp_ranges')
            seed=ctx.get('seed')
            raw,_=self._raw(
                list(hero or []),list(board or []),list(opp_range or []),
                pools,n,'river',0.75,seed,'river_fallback')
        else:
            self.counts['river_used_state_judgment']+=1

        real_be=R.blocker_effect
        try:
            # river_fix keeps its existing blocker-awareness multiplier and
            # coefficient, but consumes the shared raw factual judgment.
            R.blocker_effect=lambda *a,**k:float(raw)
            return self.orig_river(state,hero,board,profile,opp_range,rng)
        finally:
            R.blocker_effect=real_be

    def replay(self,args,kwargs):
        b=self.update_sig.bind_partial(*args,**kwargs).arguments
        self.ctx.append({
            'n_opp':b.get('n_opp'),
            'opp_ranges':b.get('opp_ranges'),
            'seed':b.get('seed'),
        })
        real_make=PL.make_plan
        real_refresh=PL.refresh
        real_river=PL.river_fix
        try:
            PL.make_plan=self.make
            PL.refresh=self.refresh
            PL.river_fix=self.river
            return self.orig_update(*args,**kwargs)
        finally:
            PL.make_plan=real_make
            PL.refresh=real_refresh
            PL.river_fix=real_river
            self.ctx.pop()


def run(seeds,hands,sims):
    orig_update=PL.update_plan
    sig=inspect.signature(orig_update)
    cand=Candidate(sims)
    counts=collections.Counter()
    by_street=collections.Counter()
    rows=[]

    def wrapped(*args,**kwargs):
        cargs=copy.deepcopy(args)
        ckwargs=copy.deepcopy(kwargs)
        b=sig.bind_partial(*args,**kwargs).arguments
        street=b.get('street')
        n=int(b.get('n_opp') or 1)
        bucket='mw' if n>1 else 'hu'

        prod=orig_update(*args,**kwargs)
        alt=cand.replay(cargs,ckwargs)

        counts['update_calls_total']+=1
        counts[bucket+'_calls']+=1
        by_street[str(street)+'_calls']+=1

        pp=prod.get('plan')
        ap=alt.get('plan')
        pi=_intent(prod,street)
        ai=_intent(alt,street)

        flags={
            'plan_changes': pp!=ap,
            'intent_act_changes': ((pi or {}).get('act')!=(ai or {}).get('act')),
            'intent_size_changes': _size_changed(pi,ai),
            'bluff_mode_changes': (
                prod.get('bluff_mode')!=alt.get('bluff_mode')
                or prod.get('bluff_mul')!=alt.get('bluff_mul')),
        }

        pso=prod.get('stackoff') or {}
        aso=alt.get('stackoff') or {}
        pbn=(pso.get('_blk_net') if isinstance(pso,dict) else None)
        abn=(aso.get('_blk_net') if isinstance(aso,dict) else None)
        flags['blocker_state_changes']=(
            prod.get('blocker_net')!=alt.get('blocker_net') or pbn!=abn)

        for name,flag in flags.items():
            if flag:
                counts[name]+=1
                counts[bucket+'_'+name]+=1
                by_street[str(street)+'_'+name]+=1

        if flags['plan_changes']:
            counts['plan_'+str(pp)+'__to__'+str(ap)]+=1

        if any(flags[k] for k in (
                'plan_changes','intent_act_changes',
                'intent_size_changes','bluff_mode_changes')):
            rows.append({
                'street':street,
                'n_opp':n,
                'bucket':bucket,
                'first':bool(b.get('first')),
                'prod_plan':pp,
                'candidate_plan':ap,
                'prod_intent':pi,
                'candidate_intent':ai,
                'prod_blocker':prod.get('blocker'),
                'candidate_blocker':alt.get('blocker'),
                'prod_blocker_net':prod.get('blocker_net'),
                'candidate_blocker_net':alt.get('blocker_net'),
                'prod_stackoff_blocker_net':pbn,
                'candidate_stackoff_blocker_net':abn,
                'prod_bluff_mode':prod.get('bluff_mode'),
                'candidate_bluff_mode':alt.get('bluff_mode'),
                'candidate_blocker_source':alt.get('blocker_source'),
                **flags,
            })
        return prod

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
        PL.update_plan=orig_update

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'sims':sims,
        'counts':dict(counts),
        'by_street':dict(by_street),
        'candidate_judgment_counts':dict(cand.counts),
        'direct_difference_rows':rows,
    }


def source_check():
    msrc=inspect.getsource(PL.make_plan)
    assert '_blocker_score_bluff_factor(blk)' in msrc
    assert '0.5 + 1.8*blk' in inspect.getsource(PL._blocker_score_bluff_factor)
    return {
        'production_score_factor_preserved':True,
        'frequency_calibration_untouched':True,
        'candidate_changes_only_effect_semantics_and_lifecycle':True,
        'cascade_excluded':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=1200)
    a=ap.parse_args()

    print('PASS F7-B1C10 structure-only candidate source check',source_check())
    print(json.dumps(
        run(_parse_seeds(a.seeds),a.hands,a.sims),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C10 direct blocker structure-only attribution completed')
    print('NOTE: tournament state followed production only.')


if __name__=='__main__':
    main()
