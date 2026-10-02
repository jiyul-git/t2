#!/usr/bin/env python3
"""Read-only lookup for canonical T2 GTO v2 spot files."""
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from gto_db_schema import CLASSES, face_open_state, rfi_state, spot_key, spot_path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stack",type=float,required=True)
    ap.add_argument("--scenario",choices=["rfi","face_open"],required=True)
    ap.add_argument("--hero",required=True)
    ap.add_argument("--opener")
    ap.add_argument("--hand")
    a=ap.parse_args()
    if a.scenario=="rfi":
        state=rfi_state(a.stack,a.hero)
    else:
        if not a.opener: raise SystemExit("--opener required for face_open")
        state=face_open_state(a.stack,a.opener,a.hero,2.5 if a.opener=="SB" else 2.0)
    key=spot_key(state); path=spot_path(ROOT,key)
    if not path.exists():
        print(json.dumps({"status":"MISS","spot_key":key,"state":state},ensure_ascii=False,sort_keys=True))
        raise SystemExit(2)
    d=json.loads(path.read_text())
    sol=d["solutions"][-1]
    out={"status":"EXACT_SPOT","spot_key":key,"state":state,"quality":sol.get("quality"),"solver":sol.get("solver")}
    if a.hand:
        pol=sol["strategy"]
        if a.hand not in pol["hands"]: raise SystemExit(f"unknown hand class {a.hand}")
        out["hand"]=a.hand
        out["frequencies"]=[{"action":act,"freq":fr} for act,fr in zip(pol["actions"],pol["hands"][a.hand])]
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
