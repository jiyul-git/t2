#!/usr/bin/env python3
"""Verify Human Model v3 concept-specific calc error semantics.

Stage 9 B4: the V3 semantics are the only production path (flag retired).  The
legacy formula is kept here only as a reference implementation, so the evidence
comparing the two (C5) stays reproducible.
"""

import json, math, pathlib, random, statistics, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS


def prof(concept, skill):
    c={k:5.0 for k in PS.ALL_CONCEPTS}
    c[concept]=float(skill)
    return {'concepts':c,'temper':{k:5.0 for k in PS.TEMPER},
            'aggr':5.0,'gamble':5.0,'icm':5.0,'type':'X'}


def samples(concept, skill, enabled, n=16000, base=7300000):
    if enabled:
        p=prof(concept,skill)
        return [PS.calc_noise(p,concept,random.Random(base+i)) for i in range(n)]
    return [legacy_expected(concept,skill,base+i) for i in range(n)]


def legacy_expected(concept, skill, seed):
    p=prof(concept,skill)
    s=PS.sk(p,concept)
    sigma=max(0.02,0.70*(1-s/10.0)**1.1)
    bias=1.0+0.30*(1-s/10.0)
    return max(0.20,min(3.0,random.Random(seed).gauss(bias,sigma)))


def main():
    checks={}

    # C1: outs keeps the historical formula bit-for-bit (directional overcount).
    exact=True
    mismatches=[]
    for skill in (0,2,5,8,10):
        p=prof('outs',skill)
        for seed in range(101,181):
            got=PS.calc_noise(p,'outs',random.Random(seed))
            exp=legacy_expected('outs',skill,seed)
            if got != exp:
                exact=False
                mismatches.append(('outs',skill,seed,got,exp))
                break
    checks['C1_outs_legacy_bit_exact']={
        'pass':exact,'mismatches':mismatches[:3]}

    # C2: outs is intentionally unchanged by V3.
    outs_same=True
    for skill in (0,2,5,8,10):
        a=samples('outs',skill,False,n=1200,base=7400000+skill*10000)
        b=samples('outs',skill,True,n=1200,base=7400000+skill*10000)
        outs_same &= (a==b)
    checks['C2_outs_semantics_preserved']={'pass':bool(outs_same)}

    # C3/C4: arithmetic concepts are centered on 1 and variance shrinks with skill.
    means={}; sds={}
    centered=True; monotone=True
    for concept in ('potodds','spr'):
        means[concept]={}; sds[concept]={}
        prev=None
        for skill in (0,2,5,8,10):
            xs=samples(concept,skill,True,n=16000,
                       base=7500000+(0 if concept=='potodds' else 100000)+skill*20000)
            m=statistics.fmean(xs); sd=statistics.pstdev(xs)
            means[concept][str(skill)]=round(m,5)
            sds[concept][str(skill)]=round(sd,5)
            centered &= abs(m-1.0) < 0.012
            if prev is not None:
                monotone &= sd < prev
            prev=sd
    checks['C3_arithmetic_zero_mean']={'pass':bool(centered),'means':means}
    checks['C4_error_shrinks_with_skill']={'pass':bool(monotone),'sd':sds}

    # C5: at equal distance around a pot-odds boundary, V3 must not impose a
    # systematic overfold direction.  need=.33; .35 and .31 are symmetric in
    # multiplier space around 1 by +/- .060606...
    xs=samples('potodds',0,True,n=30000,base=7800000)
    need=.33
    hi=.35/need
    lo=.31/need
    wrong_overfold=sum(z>hi for z in xs)/len(xs)
    wrong_loosecall=sum(z<=lo for z in xs)/len(xs)
    balanced=abs(wrong_overfold-wrong_loosecall)<0.02

    legacy=samples('potodds',0,False,n=30000,base=7800000)
    legacy_over=sum(max(.65,min(1.55,z))>hi for z in legacy)/len(legacy)
    legacy_loose=sum(max(.65,min(1.55,z))<=lo for z in legacy)/len(legacy)
    checks['C5_potodds_no_directional_overfold']={
        'pass':bool(balanced),
        'v3_wrong_overfold':round(wrong_overfold,4),
        'v3_wrong_loosecall':round(wrong_loosecall,4),
        'legacy_wrong_overfold':round(legacy_over,4),
        'legacy_wrong_loosecall':round(legacy_loose,4)}

    # C6: SPR noise should now coexist with the already-existing "poor skill
    # pulls perceived SPR toward 5" model, rather than cancelling it upward.
    p=prof('spr',5)
    xs=samples('spr',5,True,n=24000,base=7900000)
    sa=max(0.0,min(1.0,(PS.sk(p,'spr')-1.0)/6.0))
    true_spr=8.0
    seen=[true_spr*z*sa + 5.0*(1.0-sa) for z in xs]
    expected=true_spr*sa + 5.0*(1.0-sa)
    m=statistics.fmean(seen)
    checks['C6_spr_neutral_pull_not_cancelled']={
        'pass':abs(m-expected)<0.04,
        'skill':5,'true_spr':true_spr,
        'expected_seen':round(expected,4),'mean_seen':round(m,4)}

    passed=all(v['pass'] for v in checks.values())
    print(json.dumps({'pass':passed,'checks':checks},indent=2,sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':
    main()
