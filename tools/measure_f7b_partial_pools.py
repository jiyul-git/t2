#!/usr/bin/env python3
"""F7-B1D partial opponent-pool reachability audit.

Diagnostic only. Production behavior is always returned unchanged.

Current _normalize_opp_pools can silently invent missing opponents:
- partial seat-keyed pools are padded with opp_range / last known pool;
- union-only multiway input is duplicated n_opp times.

This tool records every live call site and classifies the input BEFORE current
normalization. It answers whether incomplete/union-only multiway inputs are
actually reached by:
- _eq_current (record-only current-board equity)
- _eq_vs (planning equity)
- act_with_plan (call/response equity)

A fixed fixture proves the current padding behavior. Live tournament state
always follows production.
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


def _shape(opp_range,n_opp,opp_ranges):
    n=max(1,int(n_opp or 1))
    if isinstance(opp_ranges,dict):
        vals=[opp_ranges[k] for k in sorted(opp_ranges,key=lambda x:str(x))]
        total=len(vals); nonempty=sum(1 for r in vals if r)
        if total==n and nonempty==n:
            kind='seat_complete'
        elif total or nonempty:
            kind='seat_partial'
        else:
            kind='seat_empty'
        return {
            'kind':kind,'n_opp':n,'entries':total,'nonempty':nonempty,
            'union_n':len(opp_range or []),
        }
    if isinstance(opp_ranges,(list,tuple)):
        total=len(opp_ranges); nonempty=sum(1 for r in opp_ranges if r)
        if total==n and nonempty==n:
            kind='list_complete'
        elif total or nonempty:
            kind='list_partial'
        else:
            kind='list_empty'
        return {
            'kind':kind,'n_opp':n,'entries':total,'nonempty':nonempty,
            'union_n':len(opp_range or []),
        }
    if n>1 and opp_range:
        kind='union_only_multiway'
    elif n==1 and opp_range:
        kind='legacy_hu'
    else:
        kind='no_range'
    return {
        'kind':kind,'n_opp':n,'entries':0,'nonempty':0,
        'union_n':len(opp_range or []),
    }


def fixed_fixture():
    union=[('As','Kd'),('Qc','Jh')]
    partial={2:[('As','Kd')],3:[]}
    out=PL._normalize_opp_pools(union,2,partial)
    assert len(out)==2,out
    assert out[0]==[('As','Kd')],out
    assert out[1]==union,out

    union_only=PL._normalize_opp_pools(union,3,None)
    assert len(union_only)==3
    assert all(p==union for p in union_only)

    return {
        'partial_seat_is_padded':True,
        'partial_missing_pool_equals_union':True,
        'union_only_is_duplicated_per_opponent':True,
    }


def run(seeds,hands):
    original=PL._normalize_opp_pools
    counts=collections.Counter()
    examples=[]

    def wrapped(opp_range,n_opp,opp_ranges=None):
        caller=inspect.currentframe().f_back.f_code.co_name
        sh=_shape(opp_range,n_opp,opp_ranges)
        kind=sh['kind']
        counts['calls_total']+=1
        counts['caller_'+caller]+=1
        counts['kind_'+kind]+=1
        counts['caller_'+caller+'__'+kind]+=1
        if int(n_opp or 1)>1:
            counts['multiway_calls']+=1
        if kind in ('seat_partial','list_partial','seat_empty','list_empty',
                    'union_only_multiway','no_range'):
            counts['noncomplete_calls']+=1
            if caller in ('_eq_vs','act_with_plan'):
                counts['strategy_noncomplete_calls']+=1
            if len(examples)<30:
                ex=dict(sh)
                ex['caller']=caller
                examples.append(ex)
        return original(opp_range,n_opp,opp_ranges)

    PL._normalize_opp_pools=wrapped
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
        PL._normalize_opp_pools=original

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':dict(counts),
        'noncomplete_examples':examples,
    }


def source_check():
    src=inspect.getsource(PL._normalize_opp_pools)
    assert 'while len(pools) < max(1, n_opp)' in src
    assert 'pools.append(fallback)' in src
    assert 'return [list(opp_range)] * max(1, n_opp)' in src
    return {
        'partial_padding_present':True,
        'union_duplication_present':True,
        'diagnostic_only':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3011')
    ap.add_argument('--hands',type=int,default=50)
    a=ap.parse_args()
    print('PASS F7-B1D partial-pool fixed fixture',fixed_fixture())
    print('PASS F7-B1D source check',source_check())
    print(json.dumps(run(_parse_seeds(a.seeds),a.hands),indent=2,sort_keys=True))
    print()
    print('PASS F7-B1D partial opponent-pool reachability audit completed')
    print('NOTE: production behavior unchanged.')


if __name__=='__main__':
    main()
