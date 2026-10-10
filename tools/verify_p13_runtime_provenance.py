#!/usr/bin/env python3
"""Runtime P13/P8/P9 integration: verify actual session plan seed provenance.

Monkeypatch *only* the entry wrapper to observe the decision contract in real
Field -> HandRun -> preflop_plan calls. Original strategy and RNG unchanged.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fieldsim as FS
import plan as PL

def run(cond_enabled):
    original = PL.preflop_plan
    records = []
    def wrapper(ax, pos, hand, bbs, rng, **kw):
        fr = sys._getframe(1)
        h = fr.f_locals['h']
        seat = fr.f_locals['s']
        provenance = h.bf_details(seat)
        assert kw['bf'] == provenance['value']
        result = original(ax, pos, hand, bbs, rng, **kw)
        records.append((h,seat,result[2],provenance))
        return result

    PL.preflop_plan = wrapper
    if cond_enabled:
        os.environ['T2_RANGE_CONDITIONAL_V1']='1'
    else:
        os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
    try:
        f = FS.Field(entries=8,start_stack=30000,hero_pid=-1,
                     seed=47811,hands_per_level=12)
        for tb in list(f.tables.values()):
            if tb.n() >= 2:
                f._play_table(tb)
    finally:
        PL.preflop_plan = original
        os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
    assert records, 'no bot plans observed'
    methods={}
    for h,seat,returned,provenance in records:
        saved=(h.pf_seed or {}).get(seat) or {}
        assert saved['pf_bf_provenance'] == provenance, (
            'provenance lost in final pf seed',seat,saved)
        assert provenance['bf_kind'] == 'generic_default_risk_not_spot_call_prize_ev'
        assert provenance['price_specific'] is False
        assert provenance['is_exact'] == (provenance['method']=='exact_full_field_icm')
        assert saved.get('pf_opp_range_meta') is not None or 'pf_opp_range_meta' not in saved
        methods[provenance['method']]=methods.get(provenance['method'],0)+1
    return {'conditional_model_on':cond_enabled,'plans':len(records),
            'bf_methods':methods,'field_count':8}

def main():
    off=run(False)
    on=run(True)
    print(json.dumps({'OFF':off,'ON':on},sort_keys=True))
    print('PASS real session -> P5 scalar BF + pf_bf_provenance ON/OFF')

if __name__=='__main__':
    main()
