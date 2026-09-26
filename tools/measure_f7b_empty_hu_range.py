#!/usr/bin/env python3
"""F7-B1D2 HU empty-opponent-range provenance audit.

Diagnostic only. Production behavior is always returned unchanged.

B1D found every live incomplete seat pool was heads-up:
  n_opp == 1, exactly one opponent seat entry, entry == [].

Session currently does:
    opp_r = sorted(set(opp_r))
    if not opp_r:
        opp_r = sorted(set(my_r))

This tool records every update_plan call where the single opponent seat range is
empty and checks whether the union/legacy opp_range passed downstream is in fact
the hero's own my_range.

It also separates first-plan vs refresh and street to show whether emptiness is
born on the initial postflop state or later after range narrowing.
"""
import argparse
import collections
import hashlib
import inspect
import json
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
import session as SE
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


def _sig(r):
    if not r:
        return None
    payload='\n'.join(sorted(str(tuple(c)) for c in r))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def run(seeds,hands):
    original=PL.update_plan
    sig=inspect.signature(original)
    counts=collections.Counter()
    examples=[]

    def wrapped(*args,**kwargs):
        b=sig.bind_partial(*args,**kwargs).arguments
        n=int(b.get('n_opp') or 1)
        pools=b.get('opp_ranges')
        my=list(b.get('my_range') or [])
        opp=list(b.get('opp_range') or [])
        street=b.get('street')
        first=bool(b.get('first'))

        counts['update_calls_total']+=1
        if n==1 and isinstance(pools,dict) and len(pools)==1:
            only=list(pools.values())[0] or []
            if not only:
                counts['hu_empty_seat_calls']+=1
                counts['street_'+str(street)]+=1
                counts['first_'+str(first).lower()]+=1
                if opp:
                    counts['opp_union_nonempty']+=1
                else:
                    counts['opp_union_empty']+=1
                if my:
                    counts['my_range_nonempty']+=1
                else:
                    counts['my_range_empty']+=1
                same=(sorted(set(opp))==sorted(set(my)))
                if same:
                    counts['opp_range_equals_my_range']+=1
                else:
                    counts['opp_range_differs_from_my_range']+=1

                if len(examples)<40:
                    examples.append({
                        'street':street,
                        'first':first,
                        'my_range_n':len(my),
                        'opp_range_n':len(opp),
                        'seat_range_n':len(only),
                        'my_sig':_sig(my),
                        'opp_sig':_sig(opp),
                        'opp_equals_my':same,
                        'state_plan':(
                            (b.get('state') or {}).get('plan')
                            if isinstance(b.get('state'),dict) else None),
                    })
        return original(*args,**kwargs)

    PL.update_plan=wrapped
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
        PL.update_plan=original

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':dict(counts),
        'examples':examples,
    }


def source_check():
    src=inspect.getsource(SE.HandRun._run)
    assert 'if not opp_r: opp_r = sorted(set(my_r))' in src
    return {
        'session_self_range_fallback_present':True,
        'diagnostic_only':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3011')
    ap.add_argument('--hands',type=int,default=50)
    a=ap.parse_args()

    print('PASS F7-B1D2 HU empty-range source check',source_check())
    print(json.dumps(
        run(_parse_seeds(a.seeds),a.hands),
        indent=2,sort_keys=True))
    print()
    print('PASS F7-B1D2 HU empty opponent-range provenance audit completed')
    print('NOTE: production behavior unchanged.')


if __name__=='__main__':
    main()
