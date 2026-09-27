#!/usr/bin/env python3
"""F7-B1D6 stochastic preflop posterior representation audit.

Diagnostic only. Production behavior is unchanged.

B1D3 showed that live HU empty opponent ranges are born in preflop_range and
are reconstructed as 3bet ranges. B1D4's percentile-bin overlap fallback can
make those ranges non-empty, but B1D5 proved that doing so directly changes
strategy on identical pre-hand states.

The deeper semantic question is whether the observed 3bet can be represented
by the current unweighted unique-combo list at all.

For each live HU empty-seat update this tool:
- recovers the exact preflop_range inputs used by the observer model;
- computes the observer-model probability of the 3bet-category action for each
  legal starting-hand class under the SAME mixed-policy equations used by
  preflop.defend_decision, but with the information available to
  preflop_range (no private actor read/exploit state);
- converts those likelihoods into posterior combo mass under a uniform legal
  combo prior;
- measures how much posterior mass the B1D4 percentile-overlap fallback would
  retain;
- reports whether a unique unweighted combo list could exactly represent the
  posterior (only possible when all nonzero combo likelihoods are equal).

No production consumer is changed. No support/mass cutoff is invented.
"""
import argparse
import collections
import inspect
import json
import math
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
import preflop as PF
import ranges as R
import runner as RU
import tourney as T


def parse_seeds(s):
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


_vals=sorted(set(float(v) for v in PF.PCT.values()))
BINS={v:((_vals[i-1] if i else 0.0),v) for i,v in enumerate(_vals)}


def overlaps(lo,hi,a,b):
    return hi>lo and b>lo and a<hi


def overlap_support(prof,pos,bb,dead,n_callers,opener_pos,open_bb,
                    seats,ante,polar,raise_level):
    tp,tot=PF.defend_thresholds(
        prof,pos,opener_pos,bb,open_bb,n_callers,raise_level,seats,ante)
    if polar>0.02:
        vh=tp*(1-0.55*polar)
        bl=min(0.90,tp+0.10+0.25*polar)
        bh=min(0.95,bl+(tp-vh)*2.2)
        ints=[(0.0,vh),(bl,bh)]
    else:
        ints=[(0.0,tp)]
    out=[]
    for c in R._SORTED:
        if c[0] in dead or c[1] in dead:
            continue
        e=float(PF.PCT[PF.cls(list(c))])
        a,b=BINS[e]
        if any(overlaps(lo,hi,a,b) for lo,hi in ints):
            out.append(c)
    return out


def _logit(x,center,width):
    return 1.0/(1.0+math.exp((x-center)/max(1e-6,width)))


def observer_attack_probability(prof,pos,bb,n_callers,opener_pos,open_bb,
                                seats,ante,raise_level,r):
    """P(3bet-category | class) for the observer-visible baseline model.

    Mirrors defend_decision's mixed policy with exploit=None, can_raise=True,
    opener_allin=False. raise_form does not need to be expanded because both
    of its outputs (3bet or shove) are reconstructed downstream as the same
    '3bet' range role.

    The hot-zone reshove branch is included exactly at the category level:
      P(attack) = p_hot + (1-p_hot)*p_mixed.
    """
    tp,tot=PF.defend_thresholds(
        prof,pos,opener_pos,bb,open_bb,n_callers,raise_level,seats,ante)

    p_hot=0.0
    if PF.in_hotzone(bb) and raise_level==1:
        rs=PF.reshove_range(prof,pos,opener_pos,bb,open_bb,n_callers)
        if r<=rs:
            depth=1.0-(r/max(1e-6,rs))
            p_hot=max(0.0,min(1.0,0.30+0.60*depth))

    a=PF.prof_aggr(prof)
    w_raise=_logit(r,tp,max(0.015,tp*0.35))
    w_raise *= (0.35+0.65*max(0.0,1.0-r/max(1e-6,tp)))
    w_raise *= (0.55+0.085*a)

    pf_slow=0.0
    if isinstance(prof,dict) and prof.get('concepts'):
        taste=PF.PS.temper(prof,'slowplay_taste',5.0)/10.0
        passive=max(0.0,min(1.0,(5.0-a)/5.0))
        premium=max(0.0,min(1.0,(0.10-r)/0.10))
        pf_slow=passive*(0.35+0.65*taste)*premium
    elif isinstance(prof,dict):
        typ=prof.get('type')
        if PF.A.ARCHETYPES.get(typ,(0,)*7+('reg',))[6]=='fish':
            pf_slow=max(0.0,min(1.0,(0.10-r)/0.10))*0.55

    w_raise *= max(0.30,1.0-0.70*pf_slow)
    w_cont=_logit(r,tot,max(0.02,(tot-tp)*0.35))
    w_call=max(0.0,w_cont-w_raise*0.6)*(1.5-0.055*a)
    w_call *= 1.0+0.90*pf_slow
    w_fold=max(0.0,1.0-w_cont)

    if r<=0.03:
        w_fold=0.0
    if r<=0.015:
        w_call*=0.16
    elif r<=0.04:
        w_call*=0.35

    slow=0.04+0.012*(10-a)
    if w_raise>0 and w_call>=0:
        w_call=max(w_call,w_raise*slow)
    if r>tot*1.35:
        w_raise=0.0
    if r>tot:
        w_call*=0.15

    total=w_raise+w_call+w_fold
    p_mix=(w_raise/total) if total>0 else 0.0
    return max(0.0,min(1.0,p_hot+(1.0-p_hot)*p_mix))


def posterior_summary(prof,pos,bb,dead,n_callers,opener_pos,open_bb,
                      seats,ante,polar,raise_level):
    legal=[c for c in R._SORTED
           if c[0] not in dead and c[1] not in dead]
    by_class=collections.defaultdict(list)
    for c in legal:
        by_class[PF.cls(list(c))].append(c)

    class_rows=[]
    combo_q={}
    for cl,combos in by_class.items():
        r=float(PF.PCT[cl])
        q=observer_attack_probability(
            prof,pos,bb,n_callers,opener_pos,open_bb,
            seats,ante,raise_level,r)
        mass=len(combos)*q
        class_rows.append({
            'class':cl,'pct':r,'legal_combos':len(combos),
            'attack_likelihood':q,'raw_mass':mass,
        })
        for c in combos:
            combo_q[c]=q

    total=sum(x['raw_mass'] for x in class_rows)
    if total<=0:
        return {
            'posterior_mass_positive':False,
            'total_raw_mass':0.0,
            'support_classes':0,
            'support_combos':0,
        }

    for x in class_rows:
        x['posterior_mass']=x['raw_mass']/total
    class_rows.sort(key=lambda x:(-x['posterior_mass'],x['pct'],x['class']))

    support=[x for x in class_rows if x['attack_likelihood']>1e-15]
    support_q=[x['attack_likelihood'] for x in support]
    support_combos=sum(x['legal_combos'] for x in support)

    ov=set(overlap_support(
        prof,pos,bb,dead,n_callers,opener_pos,open_bb,
        seats,ante,polar,raise_level))
    ov_mass=sum(combo_q.get(c,0.0) for c in ov)/total

    def n_for_mass(target):
        s=0.0
        for i,x in enumerate(class_rows,1):
            s+=x['posterior_mass']
            if s>=target:
                return i
        return len(class_rows)

    qmin=min(support_q) if support_q else 0.0
    qmax=max(support_q) if support_q else 0.0
    uniform=(bool(support_q) and (qmax-qmin)<=1e-12)
    exact_support={c for c,q in combo_q.items() if q>1e-15}

    return {
        'posterior_mass_positive':True,
        'total_raw_mass':total,
        'support_classes':len(support),
        'support_combos':support_combos,
        'classes_for_50pct_mass':n_for_mass(0.50),
        'classes_for_90pct_mass':n_for_mass(0.90),
        'classes_for_95pct_mass':n_for_mass(0.95),
        'overlap_candidate_combos':len(ov),
        'overlap_candidate_mass':ov_mass,
        'mass_outside_overlap':1.0-ov_mass,
        'likelihood_min_nonzero':qmin,
        'likelihood_max':qmax,
        'likelihood_ratio_max_min':(qmax/qmin if qmin>0 else None),
        'unique_unweighted_exact_possible':uniform,
        'overlap_is_exact_posterior_representation':(
            uniform and ov==exact_support),
        'top_classes':[{
            'class':x['class'],
            'pct':round(x['pct'],6),
            'legal_combos':x['legal_combos'],
            'attack_likelihood':round(x['attack_likelihood'],8),
            'posterior_mass':round(x['posterior_mass'],6),
        } for x in class_rows[:12]],
    }


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
        rec={
            'profile':prof_type,
            'pos':pos,'action':action,'bb':float(bb),
            'dead':set(dead or []),
            'n_callers':int(n_callers or 0),
            'opener_pos':opener_pos,'open_bb':float(open_bb),
            'seats':int(seats),'ante':bool(ante),'polar':float(polar or 0.0),
            'raise_level':int(raise_level or 1),
            'preflop_n':len(out or []),
            'perceived_out_n':None,'history_out_n':None,
        }
        if action=='3bet' and opener_pos and not out:
            rec['posterior']=posterior_summary(
                prof_type,pos,float(bb),set(dead or []),int(n_callers or 0),
                opener_pos,float(open_bb),int(seats),bool(ante),
                float(polar or 0.0),int(raise_level or 1))
        pipelines.append(rec)
        current[0]=rec
        return out

    def per_wrap(base,board,acts,profile=None,actor_read=None):
        out=orig_per(base,board,acts,profile,actor_read)
        if current[0] is not None:
            current[0]['perceived_out_n']=len(out or [])
        return out

    def hist_wrap(base_range,dyn,pid,board,dead=None):
        out,note=orig_hist(base_range,dyn,pid,board,dead=dead)
        if current[0] is not None:
            current[0]['history_out_n']=len(out or [])
        return out,note

    def upd_wrap(*args,**kwargs):
        b=upd_sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        pools=b.get('opp_ranges')
        if n==1 and isinstance(pools,dict) and len(pools)==1:
            only=list(pools.values())[0] or []
            if not only:
                counts['hu_empty_updates']+=1
                rec=next((x for x in reversed(pipelines)
                          if x.get('history_out_n') is not None),None)
                if rec is None:
                    counts['pipeline_missing']+=1
                elif rec.get('action')!='3bet' or rec.get('posterior') is None:
                    counts['posterior_scope_miss']+=1
                else:
                    p=rec['posterior']
                    counts['posterior_evaluated']+=1
                    if p.get('posterior_mass_positive'):
                        counts['posterior_positive']+=1
                    if p.get('unique_unweighted_exact_possible'):
                        counts['unweighted_exact_possible']+=1
                    else:
                        counts['unweighted_exact_impossible']+=1
                    if p.get('overlap_is_exact_posterior_representation'):
                        counts['overlap_exact']+=1
                    else:
                        counts['overlap_not_exact']+=1
                    if len(examples)<40:
                        examples.append({
                            'street':b.get('street'),
                            'first':bool(b.get('first')),
                            'pos':rec['pos'],
                            'bb':rec['bb'],
                            'n_callers':rec['n_callers'],
                            'opener_pos':rec['opener_pos'],
                            'open_bb':rec['open_bb'],
                            'raise_level':rec['raise_level'],
                            'polar':rec['polar'],
                            'preflop_n':rec['preflop_n'],
                            'perceived_out_n':rec['perceived_out_n'],
                            'history_out_n':rec['history_out_n'],
                            'posterior':p,
                        })
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

    masses=[x['posterior']['overlap_candidate_mass'] for x in examples
            if x.get('posterior',{}).get('posterior_mass_positive')]
    outside=[x['posterior']['mass_outside_overlap'] for x in examples
             if x.get('posterior',{}).get('posterior_mass_positive')]
    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':dict(counts),
        'overlap_mass_min':min(masses) if masses else None,
        'overlap_mass_max':max(masses) if masses else None,
        'mass_outside_overlap_min':min(outside) if outside else None,
        'mass_outside_overlap_max':max(outside) if outside else None,
        'examples':examples,
    }


def source_check():
    dsrc=inspect.getsource(PF.defend_decision)
    rsrc=inspect.getsource(R.preflop_range)
    for needle in (
        'w_raise = logit',
        'w_call = max(0.0, w_cont - w_raise*0.6)',
        'if r > tot*1.35: w_raise = 0.0',
        'if r > tot:     w_call *= 0.15',
        'if rng.random() < p_shove',
    ):
        assert needle in dsrc, needle
    assert 'lo < pf.PCT[pf.cls(list(c))] <= hi' in rsrc
    return {
        'mirrors_current_mixed_defend_policy':True,
        'observer_model_exploit':None,
        'observer_model_can_raise':True,
        'observer_model_opener_allin':False,
        'production_behavior_changed':False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3011')
    ap.add_argument('--hands',type=int,default=50)
    a=ap.parse_args()

    print('PASS F7-B1D6 posterior source check',source_check())
    print(json.dumps(
        run(parse_seeds(a.seeds),a.hands),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1D6 stochastic posterior representation audit completed')
    print('NOTE: no posterior support/mass cutoff is selected in this step.')
    print('NOTE: production behavior unchanged.')


if __name__=='__main__':
    main()
