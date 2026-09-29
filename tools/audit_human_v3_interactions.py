#!/usr/bin/env python3
"""Pairwise interaction audit for Human Model V3 flags on canonical 9-max fixture.

Measurement only. Detects non-additive feature interactions by comparing OFF,
single-feature and pair-feature fingerprints/stats on the same deterministic seed.
"""
import itertools, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import verify_human_model_v3_integration as V

SEED=5150

def delta(a,b,k):
    return int(b.get('stats',{}).get(k,0))-int(a.get('stats',{}).get(k,0))

def main():
    off=V.run(SEED,set())
    singles={f:V.run(SEED,{f}) for f in V.FLAGS}
    pairs={}
    for a,b in itertools.combinations(V.FLAGS,2):
        x=V.run(SEED,{a,b})
        expected={k:delta(off,singles[a],k)+delta(off,singles[b],k) for k in ('vpip','pfr','flop')}
        actual={k:delta(off,x,k) for k in ('vpip','pfr','flop')}
        pairs[a+'+'+b]={
            'changed_vs_off':x['fingerprint']!=off['fingerprint'],
            'same_as_a':x['fingerprint']==singles[a]['fingerprint'],
            'same_as_b':x['fingerprint']==singles[b]['fingerprint'],
            'expected_additive_delta':expected,
            'actual_delta':actual,
            'nonadditive_delta':{k:actual[k]-expected[k] for k in actual},
            'errors':x['errors'],
            'hands':x['hands'],
        }
    checks={
        'all_singles_live':all(x['fingerprint']!=off['fingerprint'] for x in singles.values()),
        'all_pairs_complete':all(x['hands']==V.HANDS and not x['errors'] for x in pairs.values()),
    }
    out={'pass':all(checks.values()),'checks':checks,'seed':SEED,'pairs':pairs,
         'note':'Non-additivity is reported, not failed: interactions are expected; pathological interactions require follow-up attribution.'}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__': main()
