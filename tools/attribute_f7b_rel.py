#!/usr/bin/env python3
"""Attribute post-F7-B1A regression movement to the joint-rel consumer only.

Requires tools/baseline_9max_post_f8.json generated at the post-F8 checkpoint.

Runs the same six-seed/30-hand regression twice:
  current : joint multiway relative strength enabled
  union   : only _decision_relative_strength is forced back to legacy union

All other F7/F8 code remains identical.
"""
import json
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
from tools import regress as RG


def _forced_union(hero, board, opp_range, n_opp=1,
                  opp_ranges=None, sims=600, seed=None):
    legacy=PL.relative_strength(hero,board,opp_range) if board else 0.5
    return legacy, {
        'source':'attribution_forced_union',
        'union':legacy,
        'joint':None,
        'complete':False,
    }


def main():
    path=RG.BASELINES['current'][0]
    if not os.path.exists(path):
        raise SystemExit(
            'post-F8 baseline missing: %s\n'
            'run tools/regress.py save --baseline current first' % path)

    base=json.load(open(path))
    expected={int(k):v for k,v in base['fp'].items()}

    current,_=RG.fingerprint()

    original=PL._decision_relative_strength
    PL._decision_relative_strength=_forced_union
    try:
        union,_=RG.fingerprint()
    finally:
        PL._decision_relative_strength=original

    changed=sorted(s for s in current if current[s] != expected.get(s))
    union_bad=sorted(s for s in union if union[s] != expected.get(s))

    print('post-F8 baseline rev',base.get('rev'))
    print('changed seeds with B1-A',changed)
    print('current fingerprints',{s:current[s] for s in changed})
    print('baseline fingerprints',{s:expected.get(s) for s in changed})
    print('forced-union mismatches',union_bad)

    assert not union_bad, (
        'forcing only B1-A relative-strength consumer off did not restore baseline',
        union_bad)

    if changed:
        print('PASS disabling only F7-B1A restores every frozen post-F8 fingerprint')
    else:
        print('PASS F7-B1A did not move the six-seed frozen fixture')
    print('1/1 F7-B1A attribution check passed')


if __name__=='__main__':
    main()
