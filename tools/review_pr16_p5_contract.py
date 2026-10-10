#!/usr/bin/env python3
"""Independent P5 review of P8 PR16, no strategy modifications.

Checks the actual session adapter, confidence metadata survival, and the
zero-accepted-MC boundary. A detected blocker is printed, not presented as
a passing behavior contract. Base PR16 SHA: 54e879863d7d1ef08a14079289f0822e6995b1e2.
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import session as S
import ranges as R
import range_posterior_v1 as RP
import plan as PL
import reads as RD
from tools.verify_hand130_conditioned_posterior import rows

def fixture():
    h = SimpleNamespace(
        bb=10000, pos={3:"LJ",9:"BB"},
        hole={3:["Ac","Kh"]}, hash="6e1ba98ab1a0",
        pf_seed={9:{"pf_stack_bb":6.3442, "pf_act":"shove", "pf_role":"defend", "pf_level":2}},
        _start_stacks={3:231114,9:74692}, book=None,
        bf=lambda s: 1.2, field_q=0.6, payout_flat=0.0,
        reentry=False,progress=0.0,erosion_per_hand=0.0,field_avg_stack=0,
    )
    rnd=SimpleNamespace(action_meta=rows(),order=[3,9],stacks={3:209864,9:0})
    handrun=S.HandRun.__new__(S.HandRun)
    handrun.h=h
    handrun._pid=lambda s:s
    handrun._dseed=lambda *args:111
    return handrun,rnd

def inspect():
    run,rnd=fixture()
    os.environ["T2_RANGE_CONDITIONAL_V1"]="1"
    with patch.object(RD,"perceived_profile",return_value=None):
        # A supported and completely specified all-in event must preserve
        # weighted map + complete=True through session into layer equity.
        posterior,meta=run._preflop_perceived_range(3,9,{"concepts":{}},rnd,9,8,True)
    assert meta["source"]==RP.MODEL and meta["complete"], meta
    assert posterior and isinstance(posterior,dict)
    assert R.range_mass(posterior)>0
    e,err=RP.conditioned_preflop_range(
        RD.range_profile(None), RP.classify_public_action(
            rows(stack=63442),9,10000,"BB"), {"Ac","Kh"},
        observer_context={"opener_pos":"LJ"})
    assert err["complete"] and R.range_signature(posterior)==R.range_signature(e)
    print("PASS public 3bet-shove range -> session adapter keeps exact weighted combos")

    # Missing conditional evidence is correctly refused by the P8 producer,
    # but session retains metadata only when rr is truthy (open problem).
    with patch.object(RD,"perceived_profile",return_value=None),patch.object(
        RP,"conditioned_preflop_range", return_value=(
            None,{"source":RP.MODEL,"kind":"threebet_shove",
                  "complete":False,"missing":["public_actor_stack_bb"]})):
        empty,missing=run._preflop_perceived_range(3,9,{"concepts":{}},rnd,9,8,True)
    assert empty=={} and missing["complete"] is False
    kept={}
    info={}
    if empty:   # actual HandRun._run logic from session.py
        kept[9]=empty
        info[9]=missing
    assert info=={}
    print("BLOCKER incomplete P8 range metadata is DROPPED by HandRun._run if _rr false")

    # Unsupported public action class falls back to a normal legacy range
    # when experiment ON, so the experimental model's 'unsupported' status
    # is not present in the consumer provenance at all.
    with patch.object(RD,"perceived_profile",return_value=None),patch.object(
        RP,"classify_public_action",return_value={"kind":"call_allin"}):
        old_pool,old_meta=run._preflop_perceived_range(
            3,9,{"concepts":{}},rnd,9,8,True)
    assert old_meta.get("source") != RP.MODEL, old_meta
    print("BLOCKER unsupported call_allin transparently consumes legacy range with no explicit model_unavailable metadata")

    # Zero accepted Monte Carlo draws are not a numeric 0% equity.
    # The current layer API incorrectly treats this as complete even
    # with sampling capture revealing the absence of observations.
    layer=[{"level":10000,"amount":30000,"hero_eligible":True,
            "eligible_seats":[3,9]}]
    def none_accepted(*a,**kw):
        kw.get("audit",{}).update({"accepted":0,"requested":800,"rejected":800})
        return 0.0
    with patch.object(S.bot,"equity_vs_combos",side_effect=none_accepted):
        observed=S.layer_equities_by_pot_layer(
            3,["Ac","Kh"],[],layer,{}, {9:{("As","Ad"):1.0}},
            sims=800,seed=7,capture_sampling=True)
    res=S._layer_call_summary(10000,layer,observed)
    assert observed[0]["sampling"]["accepted"]==0
    assert observed[0]["complete"] and res["complete"] and res["effective_equity"]==0
    print("BLOCKER 0 accepted MC draws appear as complete 0.0 equity and can trigger mathematical-looking fold")
    print("PASS P5 PR16 independent review reproduced 3 release-blocking integration risks")

if __name__=="__main__":
    inspect()
