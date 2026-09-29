#!/usr/bin/env python3
"""Semantic attribution for EXPLOIT_WEIGHT_V3 and READ_RECENCY_V3.

Important: EXPLOIT_WEIGHT_V3 gates the legacy compatibility entry
``exploit_weight()``. ``read_opponent()`` deliberately uses the V3 shared base
unconditionally, so toggling the flag around read_opponent is not a valid A/B.
This audit tests each flag at the API it actually controls.
"""
import json, pathlib, random, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS
import reads as RD


def prof(att=7,adp=7,rr=7,st=7):
    c={k:5.0 for k in PS.ALL_CONCEPTS}; t={k:5.0 for k in PS.TEMPER}
    c['range_read']=rr; c['sizing_tell']=st
    t['attention']=att; t['adaptability']=adp
    return {'id':1,'concepts':c,'temper':t,'type':'X','aggr':5.0,'bluff':5.0}


def exploit_probe():
    # Pick deliberately asymmetric traits so legacy's blended trait differs
    # from V3's adaptability-only common upper bound.
    p=prof(att=2,adp=9,rr=2,st=7)
    conf=.8; n=24
    old=PS.EXPLOIT_WEIGHT_V3
    try:
        PS.EXPLOIT_WEIGHT_V3=False; off=PS.exploit_weight(p,conf,n)
        PS.EXPLOIT_WEIGHT_V3=True; on=PS.exploit_weight(p,conf,n)
        shared=PS._exploit_base_weight(p,conf,n)
        # read_opponent's w is intentionally the same shared V3 base.
        rd=PS.read_opponent(p,{'confidence':conf,'n':n,'ftb':.70,'bluff':6.0,'aggr':6.0})
    finally: PS.EXPLOIT_WEIGHT_V3=old
    return {'off':off,'on':on,'shared_base':shared,'read_w':rd.get('w'),
            'semantic_changed':off!=on,
            'v3_matches_shared':on==shared,
            'read_matches_shared':rd.get('w')==shared}


def recency_probe():
    old=RD.READ_RECENCY_V3
    try:
        RD.READ_RECENCY_V3=True
        b=RD.Book()
        for x in [0]*80+[1]*20:
            b.observe_preflop(['obs'],'vill',bool(x),bool(x),limp=False,limp_chance=True,rfi_exp=.25)
        p=prof(att=2,adp=2)
        on=RD.estimate(b,'obs','vill',p,random.Random(12345))
        RD.READ_RECENCY_V3=False
        off=RD.estimate(b,'obs','vill',p,random.Random(12345))
    finally: RD.READ_RECENCY_V3=old
    return {'off':off,'on':on,'semantic_changed':off!=on,
            'n_off':off.get('n'),'n_on':on.get('n'),
            'vpip_off':off.get('vpip'),'vpip_on':on.get('vpip')}


def main():
    e=exploit_probe(); r=recency_probe()
    checks={'exploit_flag_live':e['semantic_changed'],
            'exploit_v3_unifies_shared_base':e['v3_matches_shared'] and e['read_matches_shared'],
            'recency_semantic_live':r['semantic_changed']}
    out={'pass':all(checks.values()),'checks':checks,'exploit':e,'recency':r,
         'interpretation':(
           'EXPLOIT_WEIGHT_V3 is a compatibility-entry unification flag, not a '
           'read_opponent gate. READ_RECENCY_V3 is evidence-dependent. Therefore '
           'a short tournament fingerprint need not change for either flag alone.')}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__': main()
