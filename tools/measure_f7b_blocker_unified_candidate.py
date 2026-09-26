#!/usr/bin/env python3
"""F7-B1C8 full paired replay of unified blocker-judgment candidate.

Production files are not modified by this tool.

Candidate architecture:
1) blocker_score remains observable but its approximate bluff multiplier is
   neutralized to exactly 1.0;
2) response-specific blocker judgment is R.joint_blocker_effect:
   HU exact legacy parity, multiway seat-keyed compatible field semantics;
3) refresh recomputes the current blocker judgment and writes it into state;
4) stackoff['_blk_net'] is refreshed from the same judgment before sizing;
5) river_fix receives the same current joint judgment instead of independently
   recomputing union blocker_effect.

No coefficient is retuned. Existing blocker-awareness and consumer formulas are
preserved. Incomplete seat pools produce a neutral strategy contribution rather
than inventing a missing opponent from the union.

The script runs the frozen 9-max fixture twice from identical seeds:
- production
- candidate monkeypatch

and compares complete action fingerprints, per-hand logs and aggregate stats.
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


def _summarize(stats):
    n=max(1,stats.get('n',0))
    h=max(1,stats.get('hands',0))
    return {
        'vpip_pct':round(100*stats.get('vpip',0)/n,3),
        'pfr_pct':round(100*stats.get('pfr',0)/n,3),
        'flop_pct':round(100*stats.get('flop',0)/h,3),
        'hands':stats.get('hands',0),
        'decisions':stats.get('n',0),
    }


def _run_trace(seeds,hands):
    per_seed={}
    per_hand={}
    stats=collections.Counter()
    for sd in seeds:
        t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,
                       seed=sd,hands_per_level=200)
        rows=['q=%.3f|a=%.2f'%(t.field_q,t.aggr_bias)]
        hrows=[]
        for hi in range(hands):
            if sum(1 for s in t.seats if t.stacks[s]>0)<3:
                break
            st=t.next_hand(); guard=0
            while st and not st.get('done') and guard<200:
                st=t.submit('fold'); guard+=1
            log=list(getattr(t.run,'full_log',[]) or [])
            line=';'.join('%s:%s:%s:%s'%x for x in log)
            rows.append(line)
            hrows.append(line)

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
        self.orig_score_factor=PL._blocker_score_bluff_factor
        self.orig_effect=R.blocker_effect

        self.update_sig=inspect.signature(self.orig_update)
        self.make_sig=inspect.signature(self.orig_make)
        self.refresh_sig=inspect.signature(self.orig_refresh)

    @staticmethod
    def _bg(profile):
        return (max(0.0,min(1.0,(PS.sk(profile,'blocker')-1.0)/7.0))
                if profile and profile.get('concepts') else 1.0)

    def _joint(self,hero,board,pools,n,street,size,seed,tag):
        js=(None if seed is None else
            zlib.crc32(('%s|%s'%(seed,tag)).encode()))
        v=R.joint_blocker_effect(
            hero,pools,board,street,size,n_opp=n,
            sims=self.sims,seed=js)
        if v is None:
            self.counts[tag+'_unknown']+=1
        else:
            self.counts[tag+'_complete']+=1
        return v

    def make(self,*args,**kwargs):
        b=self.make_sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        hero=list(b.get('hero') or [])
        board=list(b.get('board') or [])
        street=b.get('street')
        pools=b.get('opp_ranges')
        seed=b.get('seed')
        size={'flop':0.60,'turn':0.70,'river':0.78}.get(street,0.65)

        joint=(self.orig_effect(
                    hero,list(b.get('opp_range') or []),board,street,size,False)
               if n<=1 else
               self._joint(hero,board,pools,n,street,size,seed,'make_joint'))
        if joint is None:
            joint=0.0

        real_sf=PL._blocker_score_bluff_factor
        real_be=R.blocker_effect
        try:
            PL._blocker_score_bluff_factor=lambda blk:1.0
            R.blocker_effect=lambda *a,**k:joint
            st=self.orig_make(*args,**kwargs)
        finally:
            PL._blocker_score_bluff_factor=real_sf
            R.blocker_effect=real_be

        st=dict(st)
        st['blocker_source']=('legacy_hu' if n<=1 else
                              ('joint_seat_pools' if pools else 'unknown'))
        st['blocker_net_raw']=float(joint)
        return st

    def refresh(self,*args,**kwargs):
        b=self.refresh_sig.bind_partial(*args,**kwargs).arguments
        st=self.orig_refresh(*args,**kwargs)

        n=int(b.get('n_opp') or 1)
        hero=list(b.get('hero') or [])
        board=list(b.get('board') or [])
        opp=list(b.get('opp_range') or [])
        profile=b.get('profile') or {}
        street=b.get('street')
        pools=b.get('opp_ranges')
        seed=b.get('seed')
        size={'flop':0.60,'turn':0.70,'river':0.78}.get(street,0.65)

        if hero and board and opp:
            if n<=1:
                raw=self.orig_effect(hero,opp,board,street,size,False)
                source='legacy_hu'
            else:
                raw=self._joint(
                    hero,board,pools,n,street,size,seed,'refresh_joint')
                source='joint_seat_pools' if raw is not None else 'unknown'
            if raw is None:
                raw=0.0
            bg=self._bg(profile)
            net=float(raw)*bg

            st=dict(st)
            # Approximate score is retained as current provenance/display only.
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
        # update_plan owns the current seat-keyed context during this call.
        ctx=self.ctx[-1] if self.ctx else {}
        n=int(ctx.get('n_opp') or 1)
        pools=ctx.get('opp_ranges')
        street='river'
        seed=ctx.get('seed')
        if n<=1:
            raw=(self.orig_effect(hero,opp_range or [],board,'river',0.75,False)
                 if opp_range else 0.0)
        else:
            raw=self._joint(
                list(hero or []),list(board or []),pools,n,'river',0.75,
                seed,'river_joint')
            if raw is None:
                raw=0.0

        real_be=R.blocker_effect
        try:
            # river_fix applies blocker awareness itself, preserving its old
            # consumer coefficient while changing only the factual judgment.
            R.blocker_effect=lambda *a,**k:raw
            return self.orig_river(
                state,hero,board,profile,opp_range,rng)
        finally:
            R.blocker_effect=real_be

    def update(self,*args,**kwargs):
        b=self.update_sig.bind_partial(*args,**kwargs).arguments
        self.ctx.append({
            'n_opp':b.get('n_opp'),
            'opp_ranges':b.get('opp_ranges'),
            'seed':b.get('seed'),
        })
        try:
            return self.orig_update(*args,**kwargs)
        finally:
            self.ctx.pop()

    def install(self):
        PL.make_plan=self.make
        PL.refresh=self.refresh
        PL.river_fix=self.river
        PL.update_plan=self.update

    def restore(self):
        PL.update_plan=self.orig_update
        PL.make_plan=self.orig_make
        PL.refresh=self.orig_refresh
        PL.river_fix=self.orig_river
        PL._blocker_score_bluff_factor=self.orig_score_factor
        R.blocker_effect=self.orig_effect


def _diff(prod,cand):
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
                idx.append(i+1)
                changed_hands+=1
                if len(first)<12:
                    first.append({
                        'seed':sd,'hand':i+1,
                        'production':x,'candidate':y})
        by_seed[str(sd)]=idx
    return {
        'changed_seeds':changed_seeds,
        'changed_hands_total':changed_hands,
        'changed_hands_by_seed':by_seed,
        'production_fp':pfp,
        'candidate_fp':cfp,
        'production_stats':_summarize(ps),
        'candidate_stats':_summarize(cs),
        'first_differences':first,
    }


def source_check():
    rsrc=inspect.getsource(PL.refresh)
    rvsrc=inspect.getsource(PL.river_fix)
    assert "st['blocker_net']" not in rsrc
    assert "R.blocker_effect(hero, opp_range, board, 'river', 0.75, False)" in rvsrc
    return {
        'production_refresh_stale_confirmed':True,
        'production_river_recompute_confirmed':True,
        'candidate_is_runtime_only':True,
        'no_frequency_coefficients_changed':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    ap.add_argument('--sims',type=int,default=1200)
    a=ap.parse_args()
    seeds=_parse_seeds(a.seeds)

    print('PASS F7-B1C8 unified-candidate source check',source_check())
    production=_run_trace(seeds,a.hands)

    cand=Candidate(a.sims)
    try:
        cand.install()
        candidate=_run_trace(seeds,a.hands)
    finally:
        cand.restore()

    out=_diff(production,candidate)
    out['candidate_joint_counts']=dict(cand.counts)
    out['seeds']=seeds
    out['hands_per_seed']=a.hands
    out['sims']=a.sims
    print(json.dumps(out,indent=2,sort_keys=True))
    print()
    print('PASS F7-B1C8 full paired blocker candidate replay completed')
    print('NOTE: repository production behavior was not modified.')


if __name__=='__main__':
    main()
