#!/usr/bin/env python3
"""Pure calloff isolation: production cannot query wrong vs-open prior.

Covers exact evidence and missing evidence, actor vs observer contract,
preservation of shared RNG, and general non-all-in defend path ownership.
No poker strategy constants are introduced.
"""
import os
import sys
import random
from unittest.mock import patch

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import preflop as PF
import plan as PL
import ranges as R
import gto as G
from tools.verify_hand130_b37_replay import original

def main():
    case=original()
    seed=case['actor_pf_seed']
    args=dict(
        aggressor_pos='BB', open_bb=seed['pf_open_bb'],
        raise_level=2, prior_pf={'pf_act':'raise','pf_role':'open'},
        can_raise=False, opener_allin=True,
        pot_bb=seed['pf_pot_bb'], to_call_bb=seed['pf_to_call_bb'],
        seats=8, ante=True, bf=case['actor_pf_seed']['pf_calloff_consumer']['objective_bubble_factor'],
        bb_chips=10000, calloff_decision_seed=3365551903,
        cold_context=seed['pf_cold_context'])
    def forbidden(*args, **kwargs):
        raise AssertionError('vs-open prior touched by pure calloff strategy')
    saved=seed['pf_call_ev_shadow']
    rng=random.Random(171)
    initial=rng.getstate()
    with patch.object(PF,'calloff_cap',forbidden),\
         patch.object(PF,'defend_thresholds',forbidden),\
         patch.object(PF,'defend_decision',forbidden),\
         patch.object(G,'defend_pct',forbidden):
        action, size, provenance=PL.preflop_plan(
            case['actor_profile'],'LJ',['Kh','Ac'],seed['pf_stack_bb'],
            rng,call_ev_shadow=saved, **args)
    assert (action,size)==('call',seed['pf_to_call_bb'])
    assert rng.getstate()==initial
    trace=provenance['pf_calloff_consumer']
    assert trace['legacy_evaluated'] is False
    assert trace['gate_pass'] is False
    assert provenance['pf_calloff_compare'] is None

    missing=dict(saved, complete=False, missing_equity_layers=[1])
    with patch.object(PF,'calloff_cap',forbidden),\
         patch.object(PF,'defend_thresholds',forbidden),\
         patch.object(PF,'defend_decision',forbidden),\
         patch.object(G,'defend_pct',forbidden):
        act2,_,info=PL.preflop_plan(
            case['actor_profile'],'LJ',['Kh','Ac'],seed['pf_stack_bb'],
            rng,call_ev_shadow=missing, **args)
    assert act2=='fold'
    assert info['pf_calloff_consumer']['mathematically_justified'] is False
    assert info['pf_calloff_consumer']['missing_equity_layers']==[1]
    assert rng.getstate()==initial

    # Ordinary 3bet/4bet defense still owns vs-open behavior; the independent
    # observer reconstruction is unchanged by this actor routing change.
    called=[]
    def normal(*args,**kwargs):
        called.append((args,kwargs))
        return ('fold',0)
    with patch.object(PF,'defend_decision',normal):
        a,_,_ = PL.preflop_plan(
            case['actor_profile'],'LJ',['Kh','Ac'],seed['pf_stack_bb'],
            random.Random(17),aggressor_pos='BB',open_bb=2,
            can_raise=True,opener_allin=False,raise_level=2,
            prior_pf={'pf_act':'raise','pf_role':'open'})
    assert a=='fold' and len(called)==1
    # Check P8 producer explicitly remains available to weighted posterior.
    prior=R.preflop_range('TAG','BB','3bet',6.3442,{'Ac','Kh'},
        n_callers=0,opener_pos='LJ',open_bb=2.0,seats=8,ante=True,raise_level=1)
    assert prior and R.range_mass(prior)>0
    print('PASS all-in complete/incomplete bypass vs-open prior and shared RNG')
    print('PASS ordinary defend still separate; observer weighted prior available')
    print('observer TAG BB-vs-LJ proxy: combinations=%d mass=%.9f'%(
        len(prior),R.range_mass(prior)))

if __name__=='__main__':
    main()
