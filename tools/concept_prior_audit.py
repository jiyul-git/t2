#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only audit of realized concept priors/population shape."""

import argparse
import math
import random
import statistics
import sys
import os

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import persona as PS


def q(xs,p):
    ys=sorted(float(x) for x in xs)
    if not ys: return 0.0
    return ys[min(len(ys)-1,int((len(ys)-1)*p))]


def corr(xs,ys):
    if len(xs)!=len(ys) or len(xs)<2:
        return 0.0
    mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
    dx=[x-mx for x in xs]; dy=[y-my for y in ys]
    vx=sum(x*x for x in dx); vy=sum(y*y for y in dy)
    if vx<=1e-12 or vy<=1e-12:
        return 0.0
    return sum(a*b for a,b in zip(dx,dy))/math.sqrt(vx*vy)


def fmt(v):
    return '%.3f'%float(v)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--n',type=int,default=3000)
    ap.add_argument('--seed',type=int,default=20260926)
    ap.add_argument('--q',default='0.40,0.60,0.78,1.00,1.20')
    args=ap.parse_args()

    qs=[float(x.strip()) for x in args.q.split(',') if x.strip()]
    if 0.78 not in qs:
        raise SystemExit('q grid must include 0.78 for reference output')

    samples={}
    for qi,fq in enumerate(qs):
        rr=random.Random(args.seed + qi*1000003)
        ps=[]
        for i in range(args.n):
            p=PS.make_player(rr,fq,pid=qi*args.n+i)
            ps.append(p)
        samples[fq]=ps

    print('# concept prior / population audit')
    print('seed=%d n_per_q=%d q_grid=%s provisional=%s'
          %(args.seed,args.n,','.join('%.2f'%x for x in qs),
            getattr(PS,'LOADING_PROVISIONAL',None)))

    print()
    print('## overall skill by field quality')
    for fq in qs:
        xs=[PS.overall_skill(p) for p in samples[fq]]
        print('  q=%.2f n=%d q10=%.2f med=%.2f q90=%.2f min=%.2f max=%.2f'
              %(fq,len(xs),q(xs,.10),q(xs,.50),q(xs,.90),min(xs),max(xs)))

    ref=samples[0.78]
    lows=samples[min(qs)]
    highs=samples[max(qs)]

    rows=[]
    for c in PS.ALL_CONCEPTS:
        refv=[p['concepts'][c] for p in ref]
        lov=[p['concepts'][c] for p in lows]
        hiv=[p['concepts'][c] for p in highs]
        st=[p['latent']['study'] for p in ref]
        ag=[p['latent']['aggro'] for p in ref]
        ex=[p['latent']['exp'] for p in ref]
        osk=[PS.overall_skill(p) for p in ref]

        if c in PS.LOADING:
            ws,wa,we,base=PS.LOADING[c]
            spread=PS.SPREAD.get(c,PS.DEFAULT_SPREAD)
        else:
            ws,wa,we,base=(None,None,None,None)
            spread=None

        row={
            'concept':c,
            'group':('EXEC' if c in PS.EXEC else
                     'CALC' if c in PS.CALC else 'PERCEPTION'),
            'base':base,'spread':spread,
            'q10':q(refv,.10),'med':q(refv,.50),'q90':q(refv,.90),
            'floor':sum(1 for x in refv if x<=0.0)/len(refv),
            'ceil':sum(1 for x in refv if x>=10.0)/len(refv),
            'lowmed':q(lov,.50),'highmed':q(hiv,.50),
            'shift':q(hiv,.50)-q(lov,.50),
            'cstudy':corr(refv,st),'caggro':corr(refv,ag),
            'cexp':corr(refv,ex),'coverall':corr(refv,osk),
        }
        rows.append(row)

    print()
    print('## q=0.78 realized concept shape')
    print('%-20s %-10s %5s %6s %5s %5s %5s %6s %6s %6s %6s %6s %6s %6s'
          %('concept','group','base','spread','q10','med','q90','floor%','ceil%',
            'q40','q120','shift','rStudy','rExp'))
    print('-'*150)
    for r in rows:
        print('%-20s %-10s %5s %6s %5.1f %5.1f %5.1f %6.1f %6.1f %6.1f %6.1f %+6.1f %+6.2f %+6.2f'
              %(r['concept'],r['group'],
                ('%.1f'%r['base'] if r['base'] is not None else '-'),
                ('%.2f'%r['spread'] if r['spread'] is not None else '-'),
                r['q10'],r['med'],r['q90'],100*r['floor'],100*r['ceil'],
                r['lowmed'],r['highmed'],r['shift'],r['cstudy'],r['cexp']))

    print()
    print('## realized difficulty order at q=0.78 (hardest median first)')
    for i,r in enumerate(sorted(rows,key=lambda z:(z['med'],z['q90'],z['concept'])),1):
        print('  %2d. %-20s med=%.1f q10=%.1f q90=%.1f'
              %(i,r['concept'],r['med'],r['q10'],r['q90']))

    nom=[r for r in rows if r['base'] is not None]
    nom_order={r['concept']:i for i,r in enumerate(sorted(nom,key=lambda z:(z['base'],z['concept'])),1)}
    real_order={r['concept']:i for i,r in enumerate(sorted(nom,key=lambda z:(z['med'],z['concept'])),1)}

    inv=[]
    for r in nom:
        d=real_order[r['concept']]-nom_order[r['concept']]
        inv.append((abs(d),d,r))
    inv.sort(reverse=True,key=lambda x:(x[0],x[1]))

    print()
    print('## largest nominal-base vs realized-median rank shifts')
    for _,d,r in inv[:15]:
        print('  %-20s nominal_rank=%2d realized_rank=%2d delta=%+3d base=%.1f med=%.1f'
              %(r['concept'],nom_order[r['concept']],real_order[r['concept']],d,
                r['base'],r['med']))

    print()
    print('## saturation flags (>5% at 0 or 10)')
    flagged=[r for r in rows if r['floor']>0.05 or r['ceil']>0.05]
    if not flagged:
        print('  (none)')
    else:
        for r in sorted(flagged,key=lambda z:max(z['floor'],z['ceil']),reverse=True):
            print('  %-20s floor=%.1f%% ceil=%.1f%% med=%.1f'
                  %(r['concept'],100*r['floor'],100*r['ceil'],r['med']))

    print()
    print('## strongest latent correlations at q=0.78')
    for key,label in [('cstudy','study'),('caggro','aggro'),('cexp','exp'),('coverall','overall')]:
        print('  [%s]'%label)
        for r in sorted(rows,key=lambda z:abs(z[key]),reverse=True)[:10]:
            print('    %-20s r=%+.3f'%(r['concept'],r[key]))

    print()
    print('No generator parameters were changed by this audit.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
