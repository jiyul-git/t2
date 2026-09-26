#!/usr/bin/env python3
"""Attribute F7-B1B range-advantage behavior against frozen post-B1A baseline.

Runs canonical regression twice:
  current : joint multiway range advantage enabled
  union   : only _decision_range_advantage forced to legacy union

All B1-A/F8 behavior remains enabled in both runs.
"""
import json
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
import ranges as R
from tools import regress as RG

BASE=os.path.join(ROOT,'tools','baseline_9max_post_b1a.json')


def _forced_union(my_range, board, opp_range, n_opp=1,
                  opp_ranges=None, sims=600, seed=None, joint_seed=None):
    if not my_range or not opp_range or not board:
        legacy=0.0
    else:
        legacy=R.range_advantage(
            my_range,opp_range,board,sims=sims,seed=seed)
    return legacy,{
        'source':'attribution_forced_union',
        'union':legacy,
        'joint':None,
        'complete':False,
    }


def main():
    if not os.path.exists(BASE):
        raise SystemExit('post-B1A baseline missing: %s' % BASE)

    base=json.load(open(BASE))
    expected={int(k):v for k,v in base['fp'].items()}

    current,_=RG.fingerprint()

    original=PL._decision_range_advantage
    PL._decision_range_advantage=_forced_union
    try:
        union,_=RG.fingerprint()
    finally:
        PL._decision_range_advantage=original

    changed=sorted(s for s in current if current[s]!=expected.get(s))
    union_bad=sorted(s for s in union if union[s]!=expected.get(s))

    print('post-B1A baseline rev',base.get('rev'))
    print('changed seeds with B1-B range advantage',changed)
    print('current fingerprints',{s:current[s] for s in changed})
    print('baseline fingerprints',{s:expected.get(s) for s in changed})
    print('forced-union mismatches',union_bad)

    assert not union_bad, (
        'forcing only B1-B range-advantage consumer off did not restore post-B1A baseline',
        union_bad)

    if changed:
        print('PASS disabling only F7-B1B range advantage restores every post-B1A fingerprint')
    else:
        print('PASS F7-B1B range advantage did not move the six-seed fixture')
    print('1/1 F7-B1B attribution check passed')


if __name__=='__main__':
    main()
