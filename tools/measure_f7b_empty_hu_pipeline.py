#!/usr/bin/env python3
"""F7-B1D3 trace HU empty opponent range to its construction stage.

Diagnostic only. Production behavior is returned unchanged.

B1D2 confirmed:
- every live incomplete pool is heads-up;
- for every HU empty-seat call, downstream opp_range == my_range.

Source inspection shows perceived_range and history adjustment do not turn a
non-empty base range into empty. This tool instruments the three-stage opponent
pipeline:
    preflop_range -> perceived_range -> adjust_range_by_history
and, for each HU empty-seat update_plan call, reports the most recent completed
opponent pipeline with its preflop inputs and output sizes.

For call/3bet roles with opener_pos, it also records defend_thresholds so an
empty interval (tp == total or otherwise degenerate) is explicit.
"""
import argparse
import collections
import inspect
import json
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
import ranges as R
import runner as RU
import preflop as PF
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


def _short(v,n=120):
    s=repr(v)
    return s if len(s)<=n else s[:n-3]+'...'


def run(seeds,hands):
    orig_pre=R.preflop_range
    orig_per=R.perceived_range
    orig_hist=RU.adjust_range_by_history
    orig_upd=PL.update_plan
    upd_sig=inspect.signature(orig_upd)

    pipelines=[]
    current=[None]
    counts=collections.Counter()
    examples=[]

    def pre_wrap(prof_type,pos,action,bb,dead,n_callers=0,
                 opener_pos=None,open_bb=2.5,seats=8,ante=True,polar=0.0,
                 raise_level=1):
        out=orig_pre(
            prof_type,pos,action,bb,dead,n_callers=n_callers,
            opener_pos=opener_pos,open_bb=open_bb,seats=seats,ante=ante,
            polar=polar,raise_level=raise_level)
        thr=None
        if action in ('call','3bet') and opener_pos:
            try:
                tp,tot=PF.defend_thresholds(
                    prof_type,pos,opener_pos,bb,open_bb,n_callers,
                    raise_level,seats,ante)
                thr={'threebet_top':tp,'defend_total':tot,
                     'interval_width':tot-tp}
            except Exception as e:
                thr={'error':repr(e)}
        rec={
            'profile':_short(prof_type),
            'pos':pos,
            'action':action,
            'bb':bb,
            'dead_n':len(dead or []),
            'n_callers':n_callers,
            'opener_pos':opener_pos,
            'open_bb':open_bb,
            'seats':seats,
            'ante':bool(ante),
            'polar':polar,
            'raise_level':raise_level,
            'thresholds':thr,
            'preflop_n':len(out or []),
            'perceived_in_n':None,
            'perceived_out_n':None,
            'history_in_n':None,
            'history_out_n':None,
            'history_note':None,
        }
        pipelines.append(rec)
        current[0]=rec
        return out

    def per_wrap(base,board,acts,profile=None,actor_read=None):
        out=orig_per(base,board,acts,profile,actor_read)
        rec=current[0]
        if rec is not None:
            rec['perceived_in_n']=len(base or [])
            rec['perceived_out_n']=len(out or [])
            rec['acts']=[list(x) for x in (acts or [])]
        return out

    def hist_wrap(base_range,dyn,pid,board,dead=None):
        out,note=orig_hist(base_range,dyn,pid,board,dead=dead)
        rec=current[0]
        if rec is not None:
            rec['history_in_n']=len(base_range or [])
            rec['history_out_n']=len(out or [])
            rec['history_note']=note
            rec['pid']=str(pid)
        return out,note

    def upd_wrap(*args,**kwargs):
        b=upd_sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        pools=b.get('opp_ranges')
        if n==1 and isinstance(pools,dict) and len(pools)==1:
            only=list(pools.values())[0] or []
            if not only:
                counts['hu_empty_updates']+=1
                street=b.get('street')
                counts['street_'+str(street)]+=1
                counts['first_'+str(bool(b.get('first'))).lower()]+=1

                rec=next(
                    (x for x in reversed(pipelines)
                     if x.get('history_out_n') is not None),
                    None)
                if rec is None:
                    counts['pipeline_missing']+=1
                else:
                    counts['preflop_zero' if rec['preflop_n']==0 else 'preflop_nonzero']+=1
                    if rec.get('perceived_out_n')==0:
                        counts['perceived_zero']+=1
                    if rec.get('history_out_n')==0:
                        counts['history_zero']+=1
                    counts['action_'+str(rec.get('action'))]+=1
                    counts['pos_'+str(rec.get('pos'))]+=1
                    th=rec.get('thresholds') or {}
                    if isinstance(th,dict) and th.get('interval_width') is not None:
                        if abs(float(th['interval_width']))<1e-12:
                            counts['defend_interval_zero']+=1
                        elif float(th['interval_width'])<0:
                            counts['defend_interval_negative']+=1
                        else:
                            counts['defend_interval_positive']+=1

                    if len(examples)<40:
                        ex=dict(rec)
                        ex.update({
                            'street':street,
                            'first':bool(b.get('first')),
                            'my_range_n':len(b.get('my_range') or []),
                            'opp_range_n':len(b.get('opp_range') or []),
                            'opp_equals_my':(
                                sorted(set(b.get('opp_range') or []))
                                == sorted(set(b.get('my_range') or []))),
                        })
                        examples.append(ex)
        return orig_upd(*args,**kwargs)

    R.preflop_range=pre_wrap
    R.perceived_range=per_wrap
    RU.adjust_range_by_history=hist_wrap
    PL.update_plan=upd_wrap
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
        R.preflop_range=orig_pre
        R.perceived_range=orig_per
        RU.adjust_range_by_history=orig_hist
        PL.update_plan=orig_upd

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':dict(counts),
        'examples':examples,
    }


def source_check():
    psrc=inspect.getsource(R.perceived_range)
    nsrc=inspect.getsource(R.narrow_by_actions)
    hsrc=inspect.getsource(RU.adjust_range_by_history)
    assert 'return full + rest[:n_extra]' in psrc
    assert 'return r if r else list(base)' in nsrc
    assert 'if not base_range: return base_range, None' in hsrc
    return {
        'perceived_range_preserves_nonempty_base':True,
        'narrowing_has_nonempty_fallback':True,
        'history_preserves_empty_input':True,
        'diagnostic_only':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3011')
    ap.add_argument('--hands',type=int,default=50)
    a=ap.parse_args()
    print('PASS F7-B1D3 range-pipeline source check',source_check())
    print(json.dumps(
        run(_parse_seeds(a.seeds),a.hands),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1D3 HU empty range pipeline audit completed')
    print('NOTE: production behavior unchanged.')


if __name__=='__main__':
    main()
