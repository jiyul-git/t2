#!/usr/bin/env python3
import json, os, sys, tempfile, copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ["T2_LIVE_STATE"]=str(Path(tempfile.mkdtemp(prefix="t2_t3_pf_"))/"state.json")
os.environ["T2_BOT_LOG"]="2"

import live2 as L
import persona as PS
import preflop as PF
import runner as RU

SEED=202609271937
TARGETS={
 # Table 3
 ("UTG",("Td","9d")),
 ("UTG+1",("2d","Jd")),
 ("LJ",("4d","6c")),
 ("HJ",("9c","Js")),
 ("CO",("As","9h")),
 ("BTN",("9s","Jc")),
 ("SB",("2h","6s")),
 ("BB",("3d","Ac")),
 # Table 4
 ("UTG",("2s","7d")),
 ("UTG+1",("4c","8h")),
 ("LJ",("6h","8d")),
 ("HJ",("Ac","Th")),
 ("CO",("9c","Ah")),
 ("BTN",("Kh","9s")),
 ("SB",("Ks","Kd")),
 ("BB",("4d","Jh")),
}
records=[]

def norm_hand(hand):
    return tuple(hand)

orig_open=PF.open_decision
def wrap_open(prof,pos,bb,hand,rng,*args,**kwargs):
    out=orig_open(prof,pos,bb,hand,rng,*args,**kwargs)
    key=(pos,norm_hand(hand))
    if key in TARGETS:
        mo=kwargs.get("money_open")
        base=PF._open(prof,pos,kwargs.get("seats",8),bb,kwargs.get("ante",True))
        pressure=PF.table_pressure(kwargs.get("behind_reads"))
        hot=PF.hotzone_pressure(prof,pos,bb,kwargs.get("behind_stacks") or [])
        rec={
          "kind":"open","pos":pos,"hand":list(hand),"bb":bb,
          "hand_pct":PF.pct(hand),"base_open":base,
          "table_pressure":pressure,"hotzone_pressure":hot,
          "money_open":copy.deepcopy(mo),
          "result":list(out) if isinstance(out,tuple) else out,
          "seats":kwargs.get("seats",8),"ante":kwargs.get("ante",True),
          "behind_stacks":kwargs.get("behind_stacks"),
        }
        if isinstance(mo,dict):
            rec["threshold"]=mo.get("money_threshold",mo.get("base_threshold"))
        else:
            rec["threshold"]=base*pressure*hot
        records.append(rec)
    return out
PF.open_decision=wrap_open

orig_def=PF.defend_decision
def wrap_def(prof,def_pos,opener_pos,hand,bb,open_bb,n_callers,rng,*args,**kwargs):
    lik=PF.defend_action_likelihoods(
        prof,def_pos,opener_pos,hand,bb,open_bb,n_callers,
        raise_level=kwargs.get("raise_level",1),
        stack_bb=kwargs.get("stack_bb"),
        exploit=kwargs.get("exploit"),
        bf=kwargs.get("bf",1.0),
        seats=kwargs.get("seats",8),
        ante=kwargs.get("ante",True),
        opener_allin=kwargs.get("opener_allin",False),
        can_raise=kwargs.get("can_raise",True),
        pot_bb=kwargs.get("pot_bb"),
        to_call_bb=kwargs.get("to_call_bb"))
    out=orig_def(prof,def_pos,opener_pos,hand,bb,open_bb,n_callers,rng,*args,**kwargs)
    key=(def_pos,norm_hand(hand))
    if key in TARGETS:
        records.append({
          "kind":"defend","pos":def_pos,"hand":list(hand),
          "opener_pos":opener_pos,"bb":bb,"open_bb":open_bb,
          "n_callers":n_callers,"likelihoods":lik,
          "result":list(out) if isinstance(out,tuple) else out,
          "stack_bb":kwargs.get("stack_bb"),
          "seats":kwargs.get("seats",8),"ante":kwargs.get("ante",True),
          "pot_bb":kwargs.get("pot_bb"),"to_call_bb":kwargs.get("to_call_bb"),
          "exploit":copy.deepcopy(kwargs.get("exploit")),
        })
    return out
PF.defend_decision=wrap_def

def force_profiles():
    st=L.load()
    for pv in (st.get("field",{}).get("players",{}) or {}).values():
        prof=pv.get("prof") or {}
        prof["concepts"]={k:10.0 for k in PS.ALL_CONCEPTS}
        prof["latent"]={"study":10.0,"aggro":5.0,"exp":10.0}
        prof["temper"]={
          "aggression":5.0,"looseness":5.0,"gamble":5.0,
          "tilt_prone":0.0,"tilt_recovery":10.0,"discipline":10.0,
          "adaptability":10.0,"consistency":10.0,"attention":10.0,
          "slowplay_taste":5.0,"tilt_swing":5.0,"tilt_stack":0.0}
        prof.update(PS.derive(prof)); pv["prof"]=prof
    st["field"]["tilt"]={}; st["book"]={}; st["field"]["book"]={}; L.save(st)

L.new_game(entries=100,start_stack=30000,seed=SEED,hands_per_level=12,fmt="standard")
force_profiles()
RU.shape_size=lambda amount,ptype,rng,pot=None:int(round(float(amount)))
out=L.step(defer_others=True)
out=L.step("fold",0,defer_others=True)
st=L.load()
if st.get("others_pending"): L.resume_others(st,None)

order={"UTG":0,"UTG+1":1,"LJ":2,"HJ":3,"CO":4,"BTN":5,"SB":6,"BB":7}
records.sort(key=lambda x:order.get(x["pos"],99))
print("=== T3_T4_PREFLOP_RUNTIME ===")
print(json.dumps(records,ensure_ascii=False,sort_keys=True))

# trigger 1
