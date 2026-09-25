#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only local sensitivity map for persona LOADING/SPREAD.

Each profile uses its own deterministic RNG seed so one arm's rejection path cannot shift
the random stream of later profiles.
"""

import argparse
import random
import sys
import os

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import persona as PS


def quant(xs,p):
    ys=sorted(float(x) for x in xs)
    if not ys:
        return 0.0
    return ys[min(len(ys)-1,int((len(ys)-1)*p))]


def stats(vals):
    return {
        'q10':quant(vals,.10),
        'med':quant(vals,.50),
        'q90':quant(vals,.90),
        'width':quant(vals,.90)-quant(vals,.10),
        'floor':sum(1 for x in vals if x<=0.0)/float(len(vals) or 1),
        'ceil':sum(1 for x in vals if x>=10.0)/float(len(vals) or 1),
    }


def profile_seed(seed,i):
    return seed + 1000003*i


def sample_concept(concept,n,seed,fq):
    vals=[]
    for i in range(n):
        rr=random.Random(profile_seed(seed,i))
        p=PS.make_player(rr,fq,pid=i)
        vals.append(p['concepts'][concept])
    return stats(vals)


def delta(a,b,k):
    return a[k]-b[k]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--n',type=int,default=3000)
    ap.add_argument('--seed',type=int,default=20260926)
    ap.add_argument('--field-q',type=float,default=0.78)
    ap.add_argument('--base-step',type=float,default=0.25)
    ap.add_argument('--spread-step',type=float,default=0.15)
    args=ap.parse_args()

    concepts=list(PS.LOADING)
    original_loading=dict(PS.LOADING)
    original_spread=dict(PS.SPREAD)

    print('# concept prior local sensitivity')
    print('n=%d seed=%d field_q=%.2f base_step=%.2f spread_step=%.2f'
          %(args.n,args.seed,args.field_q,args.base_step,args.spread_step))
    print('profiles use per-pid deterministic RNG seeds; production files are not modified')
    print()

    base_stats={}
    print('building baseline...',flush=True)
    for j,c in enumerate(concepts,1):
        if j==1:
            # One common baseline population; collect all concepts in one pass.
            vals={k:[] for k in concepts}
            for i in range(args.n):
                rr=random.Random(profile_seed(args.seed,i))
                p=PS.make_player(rr,args.field_q,pid=i)
                for k in concepts:
                    vals[k].append(p['concepts'][k])
            for k in concepts:
                base_stats[k]=stats(vals[k])
        break

    rows=[]
    try:
        for j,c in enumerate(concepts,1):
            ws,wa,we,base=original_loading[c]
            spread=original_spread.get(c,PS.DEFAULT_SPREAD)
            print('[%d/%d] %s'% (j,len(concepts),c),flush=True)

            arms={}
            for label,bval,sval in (
                ('base_minus',base-args.base_step,spread),
                ('base_plus', base+args.base_step,spread),
                ('spread_minus',base,max(0.05,spread-args.spread_step)),
                ('spread_plus',base,spread+args.spread_step),
            ):
                PS.LOADING[c]=(ws,wa,we,bval)
                if c in PS.SPREAD or sval!=PS.DEFAULT_SPREAD:
                    PS.SPREAD[c]=sval
                arms[label]=sample_concept(c,args.n,args.seed,args.field_q)

            # restore before next concept
            PS.LOADING[c]=original_loading[c]
            if c in original_spread:
                PS.SPREAD[c]=original_spread[c]
            elif c in PS.SPREAD:
                del PS.SPREAD[c]

            b=base_stats[c]
            bm=arms['base_minus']; bp=arms['base_plus']
            sm=arms['spread_minus']; sp=arms['spread_plus']
            rows.append({
                'concept':c,'base':base,'spread':spread,'b':b,
                'base_minus':bm,'base_plus':bp,
                'spread_minus':sm,'spread_plus':sp,
            })
    finally:
        PS.LOADING.clear(); PS.LOADING.update(original_loading)
        PS.SPREAD.clear(); PS.SPREAD.update(original_spread)

    print()
    print('## base sensitivity (realized median)')
    print('%-20s %5s %5s  %7s %7s  %7s %7s  %7s'
          %('concept','base','med','med-','med+','d-','d+','asym'))
    print('-'*96)
    for r in rows:
        med=r['b']['med']
        dm=r['base_minus']['med']-med
        dp=r['base_plus']['med']-med
        asym=abs(abs(dm)-abs(dp))
        print('%-20s %5.2f %5.2f  %7.2f %7.2f  %+7.2f %+7.2f  %7.2f'
              %(r['concept'],r['base'],med,
                r['base_minus']['med'],r['base_plus']['med'],dm,dp,asym))

    print()
    print('## spread sensitivity (realized width q90-q10)')
    print('%-20s %6s %6s  %7s %7s  %7s %7s  %7s %7s'
          %('concept','spr','width','wid-','wid+','d-','d+','floor+','ceil+'))
    print('-'*112)
    for r in rows:
        w=r['b']['width']
        dm=r['spread_minus']['width']-w
        dp=r['spread_plus']['width']-w
        print('%-20s %6.2f %6.2f  %7.2f %7.2f  %+7.2f %+7.2f  %6.1f%% %6.1f%%'
              %(r['concept'],r['spread'],w,
                r['spread_minus']['width'],r['spread_plus']['width'],
                dm,dp,100*r['spread_plus']['floor'],100*r['spread_plus']['ceil']))

    print()
    print('## strongest nonlinear / clamp-sensitive concepts')
    scored=[]
    for r in rows:
        med=r['b']['med']
        dm=r['base_minus']['med']-med
        dp=r['base_plus']['med']-med
        asym=abs(abs(dm)-abs(dp))
        clamp=max(r['spread_plus']['floor'],r['spread_plus']['ceil'])
        scored.append((max(asym,clamp),asym,clamp,r))
    for _,asym,clamp,r in sorted(scored,key=lambda x:x[0],reverse=True)[:15]:
        print('  %-20s base_asym=%.2f spread+ clamp=%.1f%% baseline floor/ceil=%.1f/%.1f%%'
              %(r['concept'],asym,100*clamp,
                100*r['b']['floor'],100*r['b']['ceil']))

    print()
    print('No LOADING/SPREAD parameter was persisted or changed.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
