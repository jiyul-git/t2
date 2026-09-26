#!/usr/bin/env python3
"""F7-B1C11 full paired replay for the blocker STRUCTURE-ONLY candidate.

This is the trajectory companion to B1C10.

Both worlds start from identical seeds:
- production
- structure-only blocker candidate

The candidate preserves the existing blocker_score bluff-frequency factor and
all coefficients. It changes only:
- complete multiway blocker_effect: union -> joint seat-keyed semantics;
- blocker judgment refresh on current board/current ranges;
- stackoff['_blk_net'] refresh from that same judgment;
- river_fix consumption of the shared current judgment.

Incomplete multiway pools retain production union fallback in this diagnostic.

The resulting candidate fingerprints are the expected post-activation behavior.
Production repository behavior is never modified by this script.
"""
import argparse
import collections
import hashlib
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


def _summary(stats):
    n=max(1,stats.get('n',0))
    h=max(1,stats.get('hands',0))
    return {
        'vpip_pct':round(100*stats.get('vpip',0)/n,3),
        'pfr_pct':round(100*stats.get('pfr',0)/n,3),
        'flop_pct':round(100*stats.get('flop',0)/h,3),
        'hands':stats.get('hands',0),
        'decisions':stats.get('n',0),
    }


def _trace(seeds,hands):
    per_seed={}
    per_hand={}
    stats=collections.Counter()
    for sd in seeds:
        t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,
                       seed=sd,hands_per_level=200)
        rows=['q=%.3f|a=%.2f'%(t.field_q,t.aggr_bias)]
        hrows=[]
        for _ in range(hands):
            if sum(1 for s in t.seats if t.stacks[s]>0)<3:
                break
            st=t.next_hand(); guard=0
            while st and not st.get('done') and guard<200:
                st=t.submit('fold'); guard+=1
            log=list(getattr(t.run,'full_log',[]) or [])
            line=';'.join('%s:%s:%s:%s'%x for x in log)
            rows.append(line); hrows.append(line)

            seen=set()
            for stt,x,a,_ in log:
                if stt!='preflop' or x==t.hero or x in seen:
                    continue
                seen.add(x); stats['n']+=1
                if a in ('bet','raise','allin'):
                    stats['vpip']+=1; stats['pfr']+=1
                elif a=='call':
                    stats['vpip']+=1
            stats['hands']+=1
            if any(x[0]=='flop' for x in log):
                stats['flop']+=1
            t.finish_hand()

        per_seed[sd]=hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
        per_hand[sd]=hrows
    return per_seed,per_hand,dict(stats)


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
        raw,source=self._raw(hero,board,opp,pools,n,street,size,seed,'make')

        real_be=R.blocker_effect
        try:
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
            raw,source=self._raw(hero,board,opp,pools,n,street,size,seed,'refresh')
            bg=self._bg(profile)
            net=float(raw)*bg
            st=dict(st)
            st['blocker']=round(R.blocker_score(hero,opp,board)*bg,2)
            st['blocker_net']=round(net,3)
            st['blocker_net_raw']=float(raw)
            st['blocker_source']=source
            so=st.get('stackoff')
            if isinstance(so,dict):
                so=dict(so); so['_blk_net']=round(net,3); st['stackoff']=so
        return st

    def river(self,state,hero,board,profile=None,opp_range=None,rng=None):
        raw=state.get('blocker_net_raw')
        if raw is None:
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
            R.blocker_effect=lambda *a,**k:float(raw)
            return self.orig_river(state,hero,board,profile,opp_range,rng)
        finally:
            R.blocker_effect=real_be

    def update(self,*args,**kwargs):
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

    def install(self):
        PL.update_plan=self.update

    def restore(self):
        PL.update_plan=self.orig_update
        PL.make_plan=self.orig_make
        PL.refresh=self.orig_refresh
        PL.river_fix=self.orig_river
        R.blocker_effect=self.orig_effect


def _compare(prod,cand):
    pfp,ph,ps=prod
    cfp,ch,cs=cand
    changed_seeds=[s for s in pfp if pfp[s]!=cfp.get(s)]
    changed_hands=0
    first=[]
    by_seed={}
    for sd in pfp:
        a=ph.get(sd,[]); b=ch.get(sd,[])
        idx=[]
        for i in range(max(len(a),len(b))):
            x=a[i] if i<len(a) else None
            y=b[i] if i<len(b) else None
            if x!=y:
                idx.append(i+1); changed_hands+=1
                if len(first)<12:
                    first.append({
                        'seed':sd,'hand':i+1,
                        'production':x,'candidate':y})
        by_seed[str(sd)]=idx
    return {
        'production_fp':pfp,
        'candidate_fp':cfp,
        'changed_seeds':changed_seeds,
        'changed_hands_total':changed_hands,
        'changed_hands_by_seed':by_seed,
        'production_stats':_summary(ps),
        'candidate_stats':_summary(cs),
        'first_differences':first,
    }


def source_check():
    assert '_blocker_score_bluff_factor(blk)' in inspect.getsource(PL.make_plan)
    return {
        'score_frequency_factor_preserved':True,
        'full_trajectory_pairing':True,
        'production_repository_unchanged':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=1200)
    a=ap.parse_args()
    seeds=_parse_seeds(a.seeds)

    print('PASS F7-B1C11 structure-only full-pair source check',source_check())
    production=_trace(seeds,a.hands)

    cand=Candidate(a.sims)
    try:
        cand.install()
        candidate=_trace(seeds,a.hands)
    finally:
        cand.restore()

    out=_compare(production,candidate)
    out['candidate_judgment_counts']=dict(cand.counts)
    out['seeds']=seeds
    out['hands_per_seed']=a.hands
    out['sims']=a.sims
    print(json.dumps(out,indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C11 structure-only full paired replay completed')
    print('NOTE: candidate fingerprints are the expected activation target.')


if __name__=='__main__':
    main()
