#!/usr/bin/env python3
"""Semantic attribution for the opponent application weight and READ_RECENCY_V3.

Stage 9 B5: EXPLOIT_WEIGHT_V3 and the legacy ``exploit_weight()`` entry were
retired; the audit now checks the single application weight.  READ_RECENCY_V3
is still tested at the API it controls.
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
    # Stage 9 B5: EXPLOIT_WEIGHT_V3 and the legacy exploit_weight entry were
    # retired.  The only application weight is _exploit_base_weight, consumed
    # through read_opponent (and the trap read in plan, B3).
    p=prof(att=2,adp=9,rr=2,st=7)
    conf=.8; n=24
    shared=PS._exploit_base_weight(p,conf,n)
    rd=PS.read_opponent(p,{'confidence':conf,'n':n,'ftb':.70,'bluff':6.0,'aggr':6.0})
    return {'shared_base':shared,'read_w':rd.get('w'),
            'legacy_entry_retired':not hasattr(PS,'exploit_weight'),
            'read_matches_shared':rd.get('w')==shared}


def recency_probe():
    # Stage 9 closeout A1: READ_RECENCY_V3 retired; the window is the only path.
    # The lifetime view is reproduced as a reference via an identity window.
    b=RD.Book()
    for x in [0]*80+[1]*20:
        b.observe_preflop(['obs'],'vill',bool(x),bool(x),limp=False,limp_chance=True,rfi_exp=.25)
    p=prof(att=2,adp=2)
    on=RD.estimate(b,'obs','vill',p,random.Random(12345))
    _recent=RD._recent_record
    try:
        RD._recent_record=lambda r, m: r
        off=RD.estimate(b,'obs','vill',p,random.Random(12345))
    finally:
        RD._recent_record=_recent
    return {'off':off,'on':on,'semantic_changed':off!=on,
            'n_off':off.get('n'),'n_on':on.get('n'),
            'vpip_off':off.get('vpip'),'vpip_on':on.get('vpip')}


def main():
    e=exploit_probe(); r=recency_probe()
    checks={'exploit_single_weight':e['legacy_entry_retired'] and e['read_matches_shared'],
            'recency_semantic_live':r['semantic_changed']}
    out={'pass':all(checks.values()),'checks':checks,'exploit':e,'recency':r,
         'interpretation':(
           'EXPLOIT_WEIGHT_V3 was retired in stage9 B5 (single application weight). '
           'READ_RECENCY_V3 was retired in the stage9 closeout (recent window is '
           'the only path); the recency check compares it with a lifetime reference.')}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__': main()
