#!/usr/bin/env python3
"""Small read-only query helper for the canonical 9-max GTO knowledge DB."""
import argparse, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data/gto_db"

def rows(path):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stack",type=float)
    ap.add_argument("--scenario")
    ap.add_argument("--hero")
    ap.add_argument("--villain")
    ap.add_argument("--hand")
    ap.add_argument("--ante-model")
    ap.add_argument("--limit",type=int,default=20)
    a=ap.parse_args()

    files=sorted(DB.glob("*.jsonl"))
    found=[]
    for path in files:
        for r in rows(path):
            if int(r.get("game",{}).get("table_players",0) or 0)!=9:
                continue
            c=r.get("conditions",{})
            s=c.get("prehand_stack_bb",c.get("effective_stack_bb"))
            if a.stack is not None and (s is None or abs(float(s)-a.stack)>1e-9):
                continue
            if a.scenario and c.get("scenario")!=a.scenario:
                continue
            if a.hero and c.get("hero_position")!=a.hero:
                continue
            villain=c.get("shover_position") or c.get("opener_position")
            if a.villain and villain!=a.villain:
                continue
            if a.ante_model and (c.get("ante") or {}).get("model")!=a.ante_model:
                continue
            rec={
              "dataset":path.name,
              "spot_id":r.get("spot_id"),
              "stack_bb":s,
              "scenario":c.get("scenario"),
              "hero_position":c.get("hero_position"),
              "villain_position":villain,
              "ante":c.get("ante"),
              "quality":r.get("quality"),
            }
            if a.hand:
                rec["hand"]=a.hand
                rec["strategy"]=(r.get("strategy",{}).get("hands",{}).get(a.hand))
            found.append(rec)

    for r in found[:a.limit]:
        print(json.dumps(r,ensure_ascii=False,sort_keys=True))
    print(json.dumps({"matches":len(found),"shown":min(len(found),a.limit)},sort_keys=True))

if __name__=="__main__":
    main()
