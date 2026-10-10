#!/usr/bin/env python3
"""P10 independent provenance routing: observed/neutral/legacy/empty/MC fallback."""
import random
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot
import plan

P = {'type':'reg', 'aggr':5, 'bluff':5, 'concepts':{}}
H = ['3c','4d']
B = ['As','Ks','Qs','Js','9s']
POOL = [('Ts','2h')]
CTX = {'facing_seat':1,'facing_contrib':100,'facing_stack':1000,'facing_target':100}

def main():
    before=random.getstate()
    # Exact calculated equity 0.0 remains numerical even if one unknown
    # opponent uses a neutral model: audit must not claim fully observed.
    aud={}
    eq=plan.response_equity(H,B,P,POOL,{1:POOL},2,None,
                            300,100,'river',CTX,11,audit=aud)
    assert eq is not None and aud['complete'], aud
    assert aud['accepted']==aud['requested']==600, aud
    assert not aud['observed_input_complete'], aud
    assert len(aud['missing_opponents'])==1, aud
    missing=aud['missing_opponents'][0]
    assert missing['slot']==2 and missing['seat'] is None, aud
    assert missing['source']=='neutral_field_proxy', aud
    assert aud['neutral_model']=='existing_field_range_combos_0.35', aud

    ca={}
    ce=plan._eq_current(H,B,POOL,2,sims=8,seed=21,
                        opp_ranges={1:POOL},audit=ca)
    assert ce is not None and ca['accepted']==8 and ca['complete'], ca
    assert not ca['observed_input_complete'], ca
    assert ca['missing_opponents'][0]['slot']==2, ca

    # Explicitly empty observer range (not only an omitted opponent).
    a={}
    val=plan.response_equity(H,B,P,POOL,{1:[]},1,None,
                             300,100,'river',CTX,11,audit=a)
    assert val is not None and a['missing_opponents'][0]['seat']==1, a
    assert a['missing_opponents'][0]['reason']=='explicit_empty_range', a
    assert a['model_source']=='observed_and_neutral_field_proxy_mc', a

    # True absence of seat-key input retains distinct, documented HU legacy.
    legacy={}
    lv=plan.response_equity(H,B,P,POOL,None,1,None,
                            300,100,'river',CTX,11,audit=legacy)
    assert lv==0.0 and legacy['complete'], legacy
    assert legacy['observed_input_complete'] and not legacy['missing_opponents'], legacy
    assert legacy['input_contract']=='legacy_hu_opp_range', legacy

    # MC producer failures must be retained even when neutral re-estimation succeeds.
    hh=['Ac','Kh']; bb=['2c','7d','9h']; rr=[('Qs','Jd')]
    pa={}
    estimate, fallback=plan._plan_eq(hh,bb,rr,2,sims=33,seed=29,
                                     opp_ranges={1:rr,2:rr},audit=pa)
    assert estimate is not None and fallback, pa
    assert pa['source']=='neutral_field_after_primary_failure', pa
    orig=pa['original']; fb=pa['field_fallback']
    assert orig['accepted']==0 and orig['reason']=='no_valid_mc_samples', orig
    assert orig['requested']==orig['rejected'], orig
    assert fb['accepted']==fb['requested'] and fb['complete'], fb
    assert pa['result_equity']==estimate, pa
    assert fb['observed_input_complete'] is False, fb

    # Missing facing seat may never be replaced with the union in a raise gate.
    hero2=['Jh','Jd']; board2=['As','Ks','Qs','7c','2d']
    union=[('3h','4h')]
    assert bot.equity_vs_combos(hero2,board2,[union],sims=37)==1.0
    with patch.object(plan.R,'perceived_continue_range',lambda *args,**kw: union):
        bad=plan._nonvalue_raise_ev_gate(
            P,hero2,board2,'river',union,{1:[]},1,300,100,1000,0,CTX,mult=1.0)
        missing_seat=plan._nonvalue_raise_ev_gate(
            P,hero2,board2,'river',union,{2:union},1,300,100,1000,0,CTX,mult=1.0)
        legacy_gate=plan._nonvalue_raise_ev_gate(
            P,hero2,board2,'river',union,None,1,300,100,1000,0,CTX,mult=1.0)
        keyed_gate=plan._nonvalue_raise_ev_gate(
            P,hero2,board2,'river',union,{'1':union},1,300,100,1000,0,CTX,mult=1.0)
    for item in (bad, missing_seat):
        assert item['known'] is False and item['allow'] is False and item['ev'] is None,item
        assert item['equity_status']=='unavailable_not_negative_ev',item
    assert bad['range_provenance']['reason']=='explicit_empty_facing_seat_range',bad
    assert missing_seat['range_provenance']['reason']=='facing_seat_not_in_observed_ranges',missing_seat
    assert legacy_gate['known'] and legacy_gate['allow'],legacy_gate
    assert legacy_gate['range_provenance']['source']=='legacy_hu_opp_range',legacy_gate
    assert keyed_gate['known'] and keyed_gate['allow'],keyed_gate
    assert keyed_gate['range_provenance']['source']=='observed_facing_seat',keyed_gate

    # Final decision logging retains *used* model, not just numeric equity.
    st={'plan':'showdown','eq':0.7,'rel':.5,'outs':0,'made':0}
    act, final_eq, need = plan.act_with_plan(
        H,B,P,st,300,100,1000,'river',opp_range=POOL,
        opp_ranges={1:POOL},n_opp=2,response_context=CTX,
        response_kind='face_bet',seed=11)
    assert final_eq is not None, (act,final_eq,need,st)
    final=st['response_plans']['river'][-1]
    ra=final['response_equity_audit']
    assert ra['missing_opponents'][0]['slot']==2,ra
    assert ra['model_source']=='observed_and_neutral_field_proxy_mc',ra
    assert ra['accepted']==ra['requested']==600,ra
    assert not ra['observed_input_complete'],ra

    assert random.getstate()==before,'global RNG state changed'
    print('PASS P10 missing/empty/legacy/neutral, original MC failure, facing-seat gate, final response provenance, shared RNG')

if __name__=='__main__':
    main()
