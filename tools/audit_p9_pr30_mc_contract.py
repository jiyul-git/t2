#!/usr/bin/env python3
"""P9 read-only independent audit of exact PR #30 producer/consumer SHA.

No strategy modifications or fitted constants. Prints reproducible observations
and fails if an unavailable/missing known-pool source is treated as documented
computed evidence in postflop consumer logs.
"""
import json
import random
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot
import plan

P={'type':'reg','aggr':5,'bluff':5,'concepts':{}}
H=['3c','4d']
B=['As','Ks','Qs','Js','9s']
POOL=[('Ts','2h')]
CTX={'facing_seat':1,'facing_contrib':100,'facing_stack':1000,'facing_target':100}
GAPS=[]
REPORT=[]

def note(case, **fields):
    r={'case':case, **fields}
    REPORT.append(r)
    print('AUDIT '+json.dumps(r,ensure_ascii=False,sort_keys=True,default=str),flush=True)

def gap(case, detail):
    GAPS.append({'case':case,'detail':detail})
    note(case, result='CONTRACT_GAP', detail=detail)

def mc_producer():
    global_rng=random.getstate()
    hero=['Ac','Kh']; board=['2c','7d','9h']
    singleton=[('Qs','Jd')]
    a={}
    v=bot.equity_vs_combos(hero,board,[singleton,singleton],sims=37,seed=31,audit=a)
    assert v is None and (a['requested'],a['accepted'],a['rejected'])==(37,0,37)
    assert a['complete'] is False and a['reason']=='no_valid_mc_samples'
    note('zero_valid_cross_opponent_overlap',equity=v,audit=a)

    # Independent synthetic 1 accepted, 1 rejected (second opponent's pool
    # overlaps first opponent in the first draw only).
    one=[('2c','3c')]; bad=[('2c','4c')]; good=[('4c','5c')]
    counter={'trial':0}
    def choose(rng,pool):
        if pool==one:
            counter['trial']+=1
            return one[0]
        return bad[0] if counter['trial']==1 else good[0]
    a={}
    with patch.object(bot,'_sample_pool_combo',side_effect=choose):
        v=bot.equity_vs_pools(['Ah','Ad'],['Ks','Qs','Js','Ts','9s'],
                              [one,bad],sims=2,seed=7,audit=a)
    assert v is None and (a['requested'],a['accepted'],a['rejected'])==(2,1,1)
    assert a['complete'] is False and a['reason']=='insufficient_valid_samples'
    assert a['mean_share']==1/3 and a['split_pot_draws']==1
    note('partial_valid_1_of_2',equity=v,audit=a)

    a={}
    v=bot.equity_vs_combos(H,B,[POOL],sims=19,seed=7,audit=a)
    assert v==0.0 and a['complete'] and a['accepted']==a['requested']==19
    assert a['reason']=='computed' and a['sample_variance']==0.0
    note('real_equity_zero_19_of_19',equity=v,audit=a)
    a={}
    v=bot.equity_vs_combos(['2c','3d'],['As','Ks','Qs','Js','Ts'],
                             [[('4c','5d')]],sims=9,seed=7,audit=a)
    assert v==0.5 and a['split_pot_draws']==9 and a['complete']
    note('genuine_tie_9_of_9',equity=v,audit=a)
    a={}
    v=bot.equity_vs_combos(H,B,[[]],sims=3,seed=7,audit=a)
    assert v is None and a['reason']=='missing_opponent_range'
    note('missing_opponent_producer',equity=v,audit=a)

    state0=random.getstate()
    aud={}
    v1=bot.equity_vs_combos(['Ac','Kh'],['2c','7d','9h'],
                              [[('Qs','Jd')]],sims=41,seed=71)
    v2=bot.equity_vs_combos(['Ac','Kh'],['2c','7d','9h'],
                              [[('Qs','Jd')]],sims=41,seed=71,audit=aud)
    assert v1==v2 and random.getstate()==state0==global_rng
    note('global_rng_and_audit_parity',same_value=v1==v2,global_state_unchanged=True,
         sample_count=aud['accepted'])

def safe_consumers():
    hero=['Ac','Kh']; board=['2c','7d','9h']; singleton=[('Qs','Jd')]
    st={'plan':'value_2street','eq':.65,'rel':.8,'outs':0,'made':1}
    act,eq,need=plan.act_with_plan(hero,board,P,st,300,100,1000,'flop',
         opp_range=singleton,opp_ranges={1:singleton,2:singleton},
         n_opp=2,response_context=CTX,response_kind='face_bet',seed=11)
    rec=st['response_plans']['flop'][-1]
    assert act==('fold',0) and eq is None and need is None
    assert not st['_last_response_boundary']['mathematically_justified']
    assert rec['equity_status']=='unavailable_not_negative_ev'
    assert rec['equity_unavailable']['accepted']==0
    note('postflop_missing_mc_safe_fold',action=act,reason=rec['equity_unavailable'].get('reason'),
         accepted=rec['equity_unavailable'].get('accepted'),justified=False)

    def fail(*args,**kwargs):
        au=kwargs.get('audit')
        if au is not None: au.update(requested=kwargs.get('sims'),accepted=3,
                    rejected=kwargs.get('sims',0)-3,complete=False,
                    reason='insufficient_valid_samples',seed=91)
        return None
    with patch.object(plan.R,'perceived_continue_range',lambda *a,**kw: POOL):
        with patch.object(bot,'equity_vs_combos',side_effect=fail):
            gate=plan._nonvalue_raise_ev_gate(P,H,B,'river',POOL,{1:POOL},
                        1,300,100,1000,0,CTX,mult=1.0)
            v_audit={}
            ok,eqc,fair=plan.value_raise_qualification(
                H,B,'river',.7,1,POOL,CTX,0,1000,300,100,1.0,P,audit=v_audit)
    assert not gate['allow'] and not gate['known'] and gate['ev'] is None
    assert gate['mc_audit']['accepted']==3 and gate['mc_audit']['reason']=='insufficient_valid_samples'
    assert not ok and eqc is None and v_audit['mc_audit']['accepted']==3
    st={'_last_nonvalue_raise_gate':gate,
        '_last_value_raise_gate':{'ok':False,'continue_eq':None,
          'continue_eq_status':v_audit['status'],'continue_mc_audit':v_audit['mc_audit']}}
    plan.record_response_plan(st,'river',{'act':'fold','source':'generic_response'})
    rec=st['response_plans']['river'][-1]
    assert rec['nonvalue_raise_gate']['mc_audit']['accepted']==3
    assert rec['value_raise_gate']['continue_mc_audit']['accepted']==3
    note('partial_continue_mc_gate_and_log',nonvalue=rec['nonvalue_raise_gate'],
         value=rec['value_raise_gate'])

    state={'plan':'showdown','rel':.5,'eq':.7,'outs':0,'made':0}
    with patch.object(bot,'equity_vs_combos',side_effect=fail):
        act,eq,need=plan.act_with_plan(H,B,P,state,300,100,1000,'river',
                opp_range=POOL,opp_ranges={1:POOL},
                response_context=CTX,response_kind='face_bet',seed=11)
    rec=state['response_plans']['river'][-1]
    assert act==('fold',0) and eq is None and rec['equity_unavailable']['accepted']==3
    note('partial_response_mc_safe_fold',action=act,
          reason=rec['equity_unavailable']['reason'],accepted=3)

def audit_missing_seat_disclosure():
    # A known missing seat cannot be confused with a wholly observed
    # multiway pool when evaluating a decision; distinguish source/proxy.
    missing={1:POOL}
    a={}
    eq=plan.response_equity(H,B,P,POOL,missing,2,None,
              300,100,'river',CTX,11,audit=a)
    note('response_missing_seat',numeric=eq is not None,audit=a,
         identified_missing=('missing' in str(a).lower()),
         neutral_model_declared=('fallback' in str(a).lower() or 'neutral' in str(a).lower()))
    if eq is not None and not any(key in a for key in (
            'missing_opponents','range_provenance','missing_ranges','field_fallback',
            'imputed_seats')):
        gap('response_missing_seat_provenance',
            'seat 2 absent but completed response audit has no missing-seat or field-proxy marker')

    cur_a={}
    curr=plan._eq_current(H,B,POOL,2,sims=8,seed=21,
                         opp_ranges=missing,audit=cur_a)
    note('current_missing_seat',numeric=curr is not None,audit=cur_a)
    if curr is not None and not any(key in cur_a for key in (
             'missing_opponents','range_provenance','missing_ranges','field_fallback',
             'imputed_seats')):
        gap('current_missing_seat_provenance',
            'same-board MC returned a numeric equity but did not record missing seat 2')

def audit_original_failure_fallback_provenance():
    hero=['Ac','Kh']; board=['2c','7d','9h']; r=[('Qs','Jd')]
    primary={}
    direct=plan._eq_vs(hero,board,r,2,sims=33,seed=29,
                       opp_ranges={1:r,2:r},audit=primary)
    assert direct is None and primary['accepted']==0
    aud={}
    estimate,used=plan._plan_eq(hero,board,r,2,sims=33,seed=29,
                                opp_ranges={1:r,2:r},audit=aud)
    note('plan_primary_conflicting_fallback',original=primary,
         final_equity=estimate,fallback=used,passed_audit=aud)
    if estimate is not None and used and not aud:
        gap('plan_fallback_failure_reason_lost',
            'original no_valid_mc_samples (accepted=0) replaced by field equity; caller audit empty')

def audit_missing_facing_seat_nonvalue_gate():
    # If facing seat has an explicitly empty range, a different union range
    # is not evidence of that seat's fold/call behavior.
    meta={}
    def optimistic(*args,**kwargs):
        a=kwargs.get('audit')
        if a is not None:
            a.update(complete=True,requested=kwargs.get('sims'),
                     accepted=kwargs.get('sims'),reason='computed')
        return .95
    with patch.object(plan.R,'perceived_continue_range',lambda *a,**kw: POOL):
        with patch.object(bot,'equity_vs_combos',side_effect=optimistic):
            g=plan._nonvalue_raise_ev_gate(P,H,B,'river',POOL,{1:[]},
                                1,300,100,1000,0,CTX,mult=1.0)
    note('nonvalue_facing_seat_missing',gate=g)
    if g.get('allow') and g.get('known') and not g.get('equity_status'):
        gap('nonvalue_raise_on_missing_facing_seat',
            'explicitly empty facing-seat pool replaced by union pool, gate marks positive EV known and allows raise')

def main():
    before=random.getstate()
    mc_producer()
    safe_consumers()
    audit_missing_seat_disclosure()
    audit_original_failure_fallback_provenance()
    audit_missing_facing_seat_nonvalue_gate()
    assert random.getstate()==before, 'global RNG state altered'
    print('INDEPENDENT_SUMMARY '+json.dumps({'gaps':GAPS,'n_cases':len(REPORT)},
          ensure_ascii=False,sort_keys=True),flush=True)
    if GAPS:
        raise SystemExit('BLOCK: '+str(len(GAPS))+' producer-to-consumer provenance/raise contract gaps')
    print('APPROVE: no contract gaps found')

if __name__=='__main__':
    main()
