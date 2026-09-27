#!/usr/bin/env python3
import json, os, tempfile, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["T2_LIVE_STATE"] = str(Path(tempfile.mkdtemp(prefix="t2_jj_solver_")) / "state.json")
os.environ["T2_BOT_LOG"] = "2"

import live2 as L
import persona as PS
import runner as RU
import plan as PL
import ranges as R

SEED=202609271937
capture={}
orig=PL.update_plan

def ser_range(r):
    items=R.range_items(r)
    if not items:
        return ""
    mx=max(w for _,w in items) or 1.0
    parts=[]
    for (a,b),w in items:
        wn=float(w)/mx
        if abs(wn-1.0)<1e-12:
            parts.append(a+b)
        else:
            parts.append(f"{a}{b}:{wn:.8f}")
    return ",".join(parts)

def wrapped(state, hero, board, my_range, opp_range, profile, pot, stack,
            street, seed, n_opp, behind, prev_board, oop, initiative, *args, **kwargs):
    if (not capture and street=="flop" and list(hero)==["Jc","Jd"]
            and list(board)==["Td","Jh","6c"]):
        capture.update({
            "hero": list(hero), "board": list(board),
            "pot": float(pot), "stack": float(stack),
            "my_n": len(my_range), "opp_n": len(opp_range),
            "ip_range": ser_range(my_range),
            "oop_range": ser_range(opp_range),
        })
    return orig(state, hero, board, my_range, opp_range, profile, pot, stack,
                street, seed, n_opp, behind, prev_board, oop, initiative, *args, **kwargs)

PL.update_plan=wrapped
RU.shape_size=lambda amount, ptype, rng, pot=None: int(round(float(amount)))

L.new_game(entries=100,start_stack=30000,seed=SEED,hands_per_level=12,fmt="standard")
st=L.load()
for pv in (st.get("field",{}).get("players",{}) or {}).values():
    prof=pv.get("prof") or {}
    prof["concepts"]={k:10.0 for k in PS.ALL_CONCEPTS}
    prof["latent"]={"study":10.0,"aggro":5.0,"exp":10.0}
    prof["temper"]={
        "aggression":5.0,"looseness":5.0,"gamble":5.0,
        "tilt_prone":0.0,"tilt_recovery":10.0,"discipline":10.0,
        "adaptability":10.0,"consistency":10.0,"attention":10.0,
        "slowplay_taste":5.0,"tilt_swing":5.0,"tilt_stack":0.0,
    }
    prof.update(PS.derive(prof))
    pv["prof"]=prof
st["field"]["tilt"]={}
st["book"]={}
L.save(st)

out=L.step(defer_others=True)
if out.get("done"):
    raise SystemExit("unexpected hero state")
out=L.step("fold",0,defer_others=True)
st=L.load()
if st.get("others_pending"):
    L.resume_others(st,None)
if not capture:
    raise SystemExit("T2 JJ flop range capture failed")

# convert chips to BB using the known live hand's bb from the reconstructed field
st=L.load()
f=L._load_field(st["field"])
bb=float(f.bb)
capture["bb"]=bb
capture["pot_bb"]=capture["pot"]/bb
capture["stack_bb"]=capture["stack"]/bb

Path("/tmp/t2_jj_ranges.json").write_text(json.dumps(capture,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in capture.items() if not k.endswith("_range")},ensure_ascii=False,indent=2))
