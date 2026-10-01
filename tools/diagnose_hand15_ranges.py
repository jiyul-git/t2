#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tools"))

import ranges as R
import bot
import manual_one_hand as M

TARGET=["Td","2h","9h"]
orig=R.perceived_range
rows=[]

def shape(rng, board):
    mass=max(1e-12,R.range_mass(rng))
    cats={str(i):0.0 for i in range(9)}
    draws={"8plus":0.0,"4plus":0.0,"none":0.0}
    top=[]
    for c,w in R.range_items(rng):
        cat=bot.eval7(list(c)+list(board))[0]
        cats[str(cat)]+=float(w)
        outs=bot.draw_strength(list(c),list(board))
        if outs>=8: draws["8plus"]+=float(w)
        elif outs>=4: draws["4plus"]+=float(w)
        else: draws["none"]+=float(w)
        top.append((float(w),list(c),cat,outs))
    top=sorted(top,reverse=True)[:20]
    return {
      "n":len(R.range_support(rng)),"mass":round(mass,4),
      "cat_share":{k:round(v/mass,4) for k,v in cats.items() if v>0},
      "draw_share":{k:round(v/mass,4) for k,v in draws.items() if v>0},
      "top_mass_combos":[{"c":c,"cat":cat,"outs":outs,"w":round(w,4)}
                         for w,c,cat,outs in top],
    }

def wrapped(base, board, acts, profile=None, actor_read=None):
    out=orig(base,board,acts,profile=profile,actor_read=actor_read)
    if list(board or [])==TARGET:
        ev=[]
        for x in acts or []:
            if isinstance(x,dict):
                ev.append({k:x.get(k) for k in (
                    "seat","action_kind","size_frac","facing_kind",
                    "facing_size_frac","facing_price_frac",
                    "raise_depth_full_after")})
            else:
                ev.append(x)
        if any(isinstance(x,dict) and x.get("action_kind")=="raise" for x in acts or []):
            rec={"acts":ev,"shape":shape(out,board)}
            rows.append(rec)
            print("=== HAND15_RANGE_DIAG ===")
            print(json.dumps(rec,sort_keys=True))
    return out

R.perceived_range=wrapped
M.main()
print("=== HAND15_RANGE_DIAG_COUNT ===")
print(len(rows))
