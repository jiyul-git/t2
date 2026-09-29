#!/usr/bin/env python3
"""Attribute why EXPLOIT_WEIGHT_V3 / READ_RECENCY_V3 may be fingerprint-inert.

A tournament fingerprint is an action-level endpoint.  These mechanisms are
state/evidence dependent, so endpoint identity on one short fixture is not by
itself evidence that they are dead.  This audit separates semantic liveness
from endpoint threshold crossing and records the coverage limitation.
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
    p=prof(); opp={'confidence':.8,'n':24,'ftb':.70,'bluff':6.0,'aggr':6.0,'cbet':.7,'barrel':.6}
    old=PS.EXPLOIT_WEIGHT_V3
    try:
        PS.EXPLOIT_WEIGHT_V3=False; a=PS.read_opponent(p,opp)
        PS.EXPLOIT_WEIGHT_V3=True; b=PS.read_opponent(p,opp)
    finally: PS.EXPLOIT_WEIGHT_V3=old
    return {'off':a,'on':b,'semantic_changed':a!=b,
            'w_changed':a.get('w')!=b.get('w')}


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
    checks={'exploit_semantic_live':e['semantic_changed'],
            'recency_semantic_live':r['semantic_changed']}
    out={'pass':all(checks.values()),'checks':checks,'exploit':e,'recency':r,
         'interpretation':(
           'If this passes while the short integration fingerprint is inert, '
           'the integration fixture lacks evidence/threshold coverage; do not '
           'classify the feature as dead or require every single flag to flip '
           'an action fingerprint on that fixture.')}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__': main()
