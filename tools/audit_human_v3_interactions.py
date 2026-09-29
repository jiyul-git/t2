#!/usr/bin/env python3
"""Pairwise endpoint-interaction audit for Human Model V3 on canonical 9-max.

This audit asks whether flag combinations execute cleanly and reports action-level
non-additivity. A single flag is NOT required to flip a 24-hand fingerprint:
EXPLOIT_WEIGHT is a compatibility-path unification and READ_RECENCY needs enough
opponent evidence. Semantic liveness for those mechanisms is verified separately
by audit_human_v3_live_attribution.py.
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
            'errors':x['errors'],'hands':x['hands'],
        }
    single_endpoint_live={f:x['fingerprint']!=off['fingerprint'] for f,x in singles.items()}
    checks={
        'off_complete':off['hands']==V.HANDS and not off['errors'],
        'all_singles_complete':all(x['hands']==V.HANDS and not x['errors'] for x in singles.values()),
        'all_pairs_complete':all(x['hands']==V.HANDS and not x['errors'] for x in pairs.values()),
    }
    out={'pass':all(checks.values()),'checks':checks,'seed':SEED,
         'single_endpoint_live':single_endpoint_live,'pairs':pairs,
         'note':'Non-additivity and endpoint-inert singles are diagnostics, not failures. Semantic liveness is a separate audit.'}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__': main()
