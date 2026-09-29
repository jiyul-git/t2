#!/usr/bin/env python3
"""Audit probability-space saturation in Human Model v3 preflop deviation.

Measurement only.  No formula is changed and no public/GTO target is fitted.

We measure the raw temperament-shifted width before the final probability
clamps and count how often real generated personas land on those clamps in
the best-covered studied condition (8-max, ante, 40bb).
"""
import json, pathlib, random, statistics, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS
import preflop as PF
import gto as G
import table as TB


def _clamp(x,a,b): return max(a,min(b,x))


def open_parts(p,pos,seats=8,bb=40.0,ante=True):
    base=G.rfi(pos,seats,bb,ante)
    pos_acc=0.10+0.80*min(1.0,PS.sk(p,'positional')/8.0)
    flat=(1.0-pos_acc)*0.60
    if flat>1e-6:
        base=base*(1-flat)+G.avg_rfi(seats,bb,ante)*flat
    loose=PS.temper(p,'looseness',5.0)
    aggr=PS.temper(p,'aggression',5.0)
    d=_clamp(((.75*loose+.25*aggr)-5.0)/4.0,-1,1)
    # matched studied condition: anchor == target after same flattening.
    raw=PS.preflop_reasoned_width(
        p,'rfi',base,d,pos,seats,bb,ante,
        deviation_scale=.95,anchor=base)
    final=_clamp(raw,0.02,0.92)
    return base,d,raw,final


def defend_parts(p,def_pos,opener,seats=8,bb=40.0,ante=True,open_bb=2.5):
    bt=G.threebet_pct(def_pos,opener,seats,bb,ante,open_bb)
    bo=G.defend_pct(def_pos,opener,seats,bb,ante,open_bb)
    loose=PS.temper(p,'looseness',5.0)
    aggr=PS.temper(p,'aggression',5.0)
    dc=_clamp((loose-5.0)/4.0,-1,1)
    dt=_clamp(((.45*loose+.55*aggr)-5.0)/4.0,-1,1)
    raw_tot=PS.preflop_reasoned_width(
        p,'defend',bo,dc,def_pos,seats,bb,ante,
        opener_pos=opener,open_bb=open_bb,deviation_scale=.95,anchor=bo)
    raw_tp=PS.preflop_reasoned_width(
        p,'defend',bt,dt,def_pos,seats,bb,ante,
        opener_pos=opener,open_bb=open_bb,deviation_scale=1.10,anchor=bt)
    # In this calibrated 8-max + ante audit path _finish_widths is a clamp,
    # not the legacy exp saturation.
    raw_tot=max(raw_tp,raw_tot)
    fin_tot=_clamp(raw_tot,0.0,0.95)
    fin_tp=_clamp(raw_tp,0.0,fin_tot)
    return bo,bt,dc,dt,raw_tot,raw_tp,fin_tot,fin_tp


def make_extreme(skill, temperament):
    c={k:5.0 for k in PS.ALL_CONCEPTS}
    c['pf_range']=c['pf_defend']=float(skill)
    c['positional']=8.0
    c['stack_decay']=c['potodds']=8.0
    t={k:5.0 for k in PS.TEMPER}
    t['looseness']=t['aggression']=float(temperament)
    return {'concepts':c,'temper':t,'type':'X','aggr':temperament,
            'gamble':5.0,'bluff':5.0}


def synthetic_grid():
    _,pre,_=TB.orders(8)
    poss=[p for p in pre if p!='BB']
    rows=[]
    for sk in (0,2,5,8):
        for temp in (1,3,5,7,9):
            p=make_extreme(sk,temp)
            vals={}
            for pos in poss:
                base,d,raw,fin=open_parts(p,pos)
                vals[pos]={'base':round(base,4),'raw':round(raw,4),
                           'final':round(fin,4),'clamped':raw<.02 or raw>.92}
            rows.append({'skill':sk,'temperament':temp,'open':vals})
    return rows


def population(n=5000):
    rng=random.Random(20260929)
    _,pre,_=TB.orders(8)
    poss=[p for p in pre if p!='BB']
    dspots=[('BB','HJ'),('BB','CO'),('BB','BTN'),('BB','SB'),
            ('SB','HJ'),('SB','CO'),('SB','BTN')]
    out={}
    for q in (.40,.80,1.20):
        oc={'n':0,'low':0,'high':0,'overshoot_sum':0.0,'by_pos':{}}
        dc={'n':0,'low':0,'high':0,'by_spot':{}}
        for i in range(n):
            p=PS.make_player(rng,q,pid=int(q*100000)+i)
            for pos in poss:
                _b,_d,raw,fin=open_parts(p,pos)
                oc['n']+=1
                lo=raw<.02; hi=raw>.92
                oc['low']+=lo; oc['high']+=hi
                if lo: oc['overshoot_sum']+=.02-raw
                if hi: oc['overshoot_sum']+=raw-.92
                bp=oc['by_pos'].setdefault(pos,{'n':0,'low':0,'high':0})
                bp['n']+=1; bp['low']+=lo; bp['high']+=hi
            for dp,op in dspots:
                *_,rt,rp,ft,fp=defend_parts(p,dp,op)
                dc['n']+=2
                for raw,lo_cap,hi_cap,tag in ((rt,0,.95,'tot'),(rp,0,.90,'tp')):
                    lo=raw<lo_cap; hi=raw>hi_cap
                    dc['low']+=lo; dc['high']+=hi
                    key=f'{dp}_vs_{op}_{tag}'
                    bs=dc['by_spot'].setdefault(key,{'n':0,'low':0,'high':0})
                    bs['n']+=1; bs['low']+=lo; bs['high']+=hi
        def finish(x):
            z=dict(x)
            z['low_rate']=round(x['low']/max(1,x['n']),6)
            z['high_rate']=round(x['high']/max(1,x['n']),6)
            z['clamp_rate']=round((x['low']+x['high'])/max(1,x['n']),6)
            for k,v in z.get('by_pos',{}).items():
                v['clamp_rate']=round((v['low']+v['high'])/max(1,v['n']),6)
            for k,v in z.get('by_spot',{}).items():
                v['clamp_rate']=round((v['low']+v['high'])/max(1,v['n']),6)
            return z
        out[str(q)]={'open':finish(oc),'defend':finish(dc)}
    return out


def collision_probe():
    """Count adjacent temperament levels that collapse to the same final width."""
    rows=[]
    for sk in (0,2,5,8):
        pvals={}
        for pos in ('UTG','HJ','CO','BTN','SB'):
            vs=[]
            for temp in range(0,11):
                p=make_extreme(sk,temp)
                _,_,raw,fin=open_parts(p,pos)
                vs.append((temp,raw,fin))
            ties=sum(abs(vs[i][2]-vs[i-1][2])<1e-12 for i in range(1,len(vs)))
            pvals[pos]={'adjacent_ties':ties,
                        'values':[round(x[2],4) for x in vs]}
        rows.append({'skill':sk,'positions':pvals})
    return rows


def main():
    old=PS.PREFLOP_REASONING_V3
    PS.PREFLOP_REASONING_V3=True
    try:
        out={'condition':{'seats':8,'bb':40,'ante':True},
             'population':population(),
             'extreme_grid':synthetic_grid(),
             'collision_probe':collision_probe()}
    finally:
        PS.PREFLOP_REASONING_V3=old
    print(json.dumps(out,indent=2,sort_keys=True))


if __name__=='__main__':
    main()
