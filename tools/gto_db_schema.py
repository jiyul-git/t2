#!/usr/bin/env python3
"""Canonical T2 GTO spot schema.

The spot address is derived from T2's semantic state, never from file order/path.
Solver/source details live in solutions and therefore do not change spot_key.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

POSITIONS=["UTG","UTG+1","UTG+2","LJ","HJ","CO","BTN","SB","BB"]
RANKS="23456789TJQKA"

def class_names():
    out=[]
    for i,r in enumerate(RANKS):
        for j,c in enumerate(RANKS):
            if i==j: out.append(r+r)
            elif j>i: out.append(c+r+"o")
            else: out.append(r+c+"s")
    assert len(out)==169
    return out
CLASSES=class_names()

def _num(x):
    x=float(x)
    return int(x) if x.is_integer() else round(x,6)

def canonical_json(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def spot_key(state):
    return hashlib.sha256(canonical_json(state).encode()).hexdigest()

def base_state(stack_bb, scenario, hero, history):
    return {
      "schema":"t2_gto_state_v1",
      "game":{"variant":"NLHE","format":"MTT","table_players":9,"street":"preflop"},
      "stack":{"prehand_bb":_num(stack_bb)},
      "blinds":{"sb_bb":0.5,"bb_bb":1.0,"ante":{"model":"big_blind_ante","total_bb":1.0}},
      "scenario":scenario,
      "hero_position":hero,
      "history":history,
      "icm":False,
      "rake_pct":0.0,
    }

def rfi_state(stack_bb, hero):
    i=POSITIONS.index(hero)
    hist=[{"actor":p,"kind":"fold"} for p in POSITIONS[:i]]
    return base_state(stack_bb,"P1_unopened",hero,hist)

def face_open_state(stack_bb, opener, hero, open_to_bb=None):
    oi,hi=POSITIONS.index(opener),POSITIONS.index(hero)
    if hi<=oi:
        raise ValueError("hero must act after opener in clean single-open spot")
    if open_to_bb is None:
        open_to_bb=2.5 if opener=="SB" else 2.0
    hist=[{"actor":p,"kind":"fold"} for p in POSITIONS[:oi]]
    hist.append({"actor":opener,"kind":"raise","to_bb":_num(open_to_bb),"raise_level":1})
    hist.extend({"actor":p,"kind":"fold"} for p in POSITIONS[oi+1:hi])
    return base_state(stack_bb,"P3_face_first_open",hero,hist)

def action_obj(a):
    kind=a.get("kind")
    if kind=="allin": kind="jam"
    out={"kind":kind}
    if kind in ("raise","jam") and a.get("to") is not None:
        out["to_bb"]=_num(a["to"])
    return out

def policy_from_node(node):
    acts=[action_obj(a) for a in node["actions"]]
    raw=node["strategy"]
    if len(raw)!=len(acts)*169:
        raise ValueError(f"strategy len {len(raw)} != {len(acts)}*169")
    hands={}
    for hi,h in enumerate(CLASSES):
        hands[h]=[float(raw[ai*169+hi]) for ai in range(len(acts))]
    return {"actions":acts,"hand_class_order":CLASSES,"hands":hands}

def solution_id(spot, solver_meta):
    return hashlib.sha256((spot+canonical_json(solver_meta)).encode()).hexdigest()

def spot_path(root, key):
    return Path(root)/"data/gto_db/spots"/key[:2]/(key+".json")

def load_spot(path):
    return json.loads(Path(path).read_text())

def write_spot(root, state, solution):
    key=spot_key(state)
    p=spot_path(root,key)
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        doc=load_spot(p)
        if doc.get("spot_key")!=key or doc.get("state")!=state:
            raise RuntimeError(f"spot collision/schema mismatch: {p}")
        ids={x.get("solution_id") for x in doc.get("solutions",[])}
        if solution["solution_id"] not in ids:
            doc.setdefault("solutions",[]).append(solution)
    else:
        doc={"schema":"t2_gto_spot_v2","spot_key":key,"state":state,"solutions":[solution]}
    tmp=p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    tmp.replace(p)
    return key,p
