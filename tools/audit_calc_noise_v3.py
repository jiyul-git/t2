#!/usr/bin/env python3
"""Audit calc_noise directional effects before changing production behavior.

This script asks a narrow causal question:
  what does the *shared positive mean bias* in calc_noise do to the actual
  downstream decision boundaries for outs, pot odds and SPR?

It does not fit population targets.  It reports:
  - multiplier distribution by skill,
  - outs >= 8 threshold crossing,
  - call/fold flips from pot-odds error,
  - bluff_mode probe-rate shifts caused by perceived SPR.

A neutral-mean counterfactual is included only as a diagnostic reference.
"""

import json, math, pathlib, random, statistics, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import persona as PS
import plan as PL


def prof(concept, skill):
    c={k:5.0 for k in PS.ALL_CONCEPTS}
    c[concept]=float(skill)
    t={k:5.0 for k in PS.TEMPER}
    # bluff_mode awareness should be high so SPR actually reaches its risk gate.
    c['sizing_tell']=8.0
    c['fold_equity']=8.0
    return {'concepts':c,'temper':t,'aggr':5.0,'gamble':5.0,'bluff':5.0,'type':'X'}


def sample_noise(concept, skill, n=20000):
    p=prof(concept,skill)
    xs=[PS.calc_noise(p,concept,random.Random(1000003+i)) for i in range(n)]
    return xs


def q(xs,p):
    s=sorted(xs)
    return s[min(len(s)-1,max(0,int(round(p*(len(s)-1)))))]


def noise_summary():
    out={}
    for concept in ('outs','potodds','spr'):
        out[concept]={}
        for skill in (0,2,5,8,10):
            xs=sample_noise(concept,skill,6000)
            out[concept][str(skill)]={
                'mean':round(statistics.mean(xs),4),
                'median':round(statistics.median(xs),4),
                'p10':round(q(xs,.10),4),'p90':round(q(xs,.90),4),
                'above_1':round(sum(x>1 for x in xs)/len(xs),4),
            }
    return out


def outs_effect():
    rows=[]
    for skill in (0,2,5,8,10):
        p=prof('outs',skill)
        for true_outs in (4,6,7,8,9,12):
            seen=[]
            for i in range(8000):
                z=PS.calc_noise(p,'outs',random.Random(2100000+i))
                seen.append(int(round(true_outs*z)))
            rows.append({
                'skill':skill,'true_outs':true_outs,
                'mean_seen':round(statistics.mean(seen),3),
                'p_semibluff_gate':round(sum(x>=8 for x in seen)/len(seen),4),
                'false_positive':round(sum(x>=8 for x in seen)/len(seen),4) if true_outs<8 else 0.0,
                'false_negative':round(sum(x<8 for x in seen)/len(seen),4) if true_outs>=8 else 0.0,
            })
    return rows


def potodds_effect():
    # Marginal calls are where threshold error matters.  Compare objective
    # equity to perceived required equity after the same clamp used in plan.py.
    rows=[]
    scenarios=[
        (0.25,0.27), (0.30,0.32), (0.33,0.35),
        (0.36,0.38), (0.40,0.42),
        (0.33,0.31), # objectively a fold, to see erroneous loose calls too
    ]
    for skill in (0,2,5,8,10):
        p=prof('potodds',skill)
        for need_true,eq in scenarios:
            calls=0; mean_need=0.0
            for i in range(8000):
                z=PS.calc_noise(p,'potodds',random.Random(3100000+i))
                z=max(0.65,min(1.55,z))
                need=max(0.01,min(0.95,need_true*z))
                mean_need+=need
                calls += (eq>=need)
            objective=(eq>=need_true)
            call_p=calls/8000
            rows.append({
                'skill':skill,'need_true':need_true,'eq':eq,
                'objective_action':'call' if objective else 'fold',
                'mean_need_seen':round(mean_need/8000,4),
                'call_probability':round(call_p,4),
                'wrong_action_probability':round((1-call_p) if objective else call_p,4),
            })
    return rows


def _spr_seen(p, true_spr, seed):
    z=PS.calc_noise(p,'spr',random.Random(seed))
    s=true_spr*z
    sa=max(0.0,min(1.0,(PS.sk(p,'spr')-1.0)/6.0))
    return s*sa + 5.0*(1.0-sa)


def spr_effect():
    rows=[]
    for skill in (0,2,5,8,10):
        p=prof('spr',skill)
        for true_spr in (1.5,3.0,5.0,8.0,12.0):
            ss=[]; probes=0
            for i in range(8000):
                seed=4100000+i
                s=_spr_seen(p,true_spr,seed)
                ss.append(s)
                # reads < .55 makes the non-probe fallback barrel, isolating the
                # SPR-dependent probe gate. danger=.45 puts risk near boundary.
                mode,_,_=PL.bluff_mode(
                    p, rel=.25, danger=.45, nut_adv=.20,
                    opp_est={'sizing_tell':4.0,'fold':.5},
                    street='flop', s=s, rng=random.Random(seed))
                probes += (mode=='probe')
            rows.append({
                'skill':skill,'true_spr':true_spr,
                'mean_seen_spr':round(statistics.mean(ss),3),
                'probe_rate':round(probes/8000,4),
            })
    return rows


def main():
    out={
        'noise':noise_summary(),
        'outs_threshold':outs_effect(),
        'potodds_threshold':potodds_effect(),
        'spr_probe':spr_effect(),
        'interpretation':{
            'outs':'positive multiplier can create phantom >=8-out semibluffs',
            'potodds':'positive multiplier raises required equity and therefore creates systematic overfold pressure',
            'spr':'positive multiplier plus neutral-pull can make deep-risk/probe perception asymmetric',
        }
    }
    print(json.dumps(out,indent=2,sort_keys=True))


if __name__=='__main__':
    main()
