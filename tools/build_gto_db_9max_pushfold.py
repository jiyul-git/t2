#!/usr/bin/env python3
import argparse, json, hashlib
from pathlib import Path

SOURCE_REPO="Julian-cloud-max/holdemmath-data"
SOURCE_COMMIT="7c72b1261f08c63cf8366120dc531631935c21cd"

def sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--license",required=True)
    ap.add_argument("--out-dir",default="data/gto_db")
    a=ap.parse_args()

    raw=json.load(open(a.source))
    order=list(raw["order"])
    if len(order)!=169:
        raise SystemExit(f"expected 169 hand classes, got {len(order)}")
    depths=[int(x) for x in raw["depths"]]
    expected=[4,6,8,10,12,15,20]
    if depths!=expected:
        raise SystemExit(f"unexpected depths {depths}")

    out=Path(a.out_dir)
    (out/"licenses").mkdir(parents=True,exist_ok=True)
    lic_text=Path(a.license).read_text()
    (out/"licenses"/"HoldemMath-CC-BY-4.0.txt").write_text(lic_text)

    source={
      "id":"holdemmath_pushfold_9max_v1",
      "repo":f"https://github.com/{SOURCE_REPO}",
      "commit":SOURCE_COMMIT,
      "source_path":"pushfold/pushfold_charts.json",
      "license":"CC BY 4.0",
      "attribution":"HoldemMath (holdemmath.com)",
      "model":"multiway first-in push/fold; single-caller approximation",
    }

    variants=[
      ("no_ante","data",0.0),
      ("ante_0p1_each","dataAnte10",0.1),
    ]
    records=[]
    counts={}
    for variant_name, field, ante_each in variants:
        data=raw[field]["max9"]
        vcount=0
        for depth in depths:
            seats=data[str(depth)]
            for node,pf in sorted(seats.items()):
                selected=set(int(i) for i in pf["s"])
                ev=list(pf.get("e") or [])
                if ev and len(ev)!=169:
                    raise SystemExit(f"{field}/max9/{depth}/{node}: EV len {len(ev)}")
                if "|" in node:
                    hero,shover=node.split("|",1)
                    scenario="call_vs_shove"
                    actions=["fold","call"]
                    active="call"
                    history={"type":"face_shove","shover_position":shover}
                else:
                    hero=node
                    shover=None
                    scenario="first_in_shove"
                    actions=["fold","jam"]
                    active="jam"
                    history={"type":"unopened"}

                hands={}
                for i,h in enumerate(order):
                    take=1.0 if i in selected else 0.0
                    row={"fold":round(1.0-take,8),active:take}
                    if ev:
                        row["action_ev_bb"]=float(ev[i])
                    hands[h]=row

                rec={
                  "schema_version":"gto_spot_v1",
                  "spot_id":f"hm_9max_{variant_name}_{depth}bb_{node}".lower().replace("|","_vs_"),
                  "game":{"variant":"NLHE","format":"MTT","table_players":9,"street":"preflop"},
                  "conditions":{
                    "prehand_stack_bb":depth,
                    "scenario":scenario,
                    "hero_position":hero,
                    "shover_position":shover,
                    "history_template":history,
                    "allowed_actions":actions,
                    "blinds_bb":{"sb":0.5,"bb":1.0},
                    "ante":{
                      "model":"none" if ante_each==0 else "per_player",
                      "per_player_bb":ante_each,
                      "total_at_9max_bb":round(ante_each*9,3),
                    },
                    "rake":0.0,
                    "icm":False,
                    "limps":False,
                  },
                  "strategy":{
                    "hand_class_count":169,
                    "coverage_pct":float(pf["p"]),
                    "hands":hands,
                  },
                  "source":source,
                  "quality":{
                    "status":"near_t2_bba",
                    "source_quality":"near-exact HU; multiway single-caller approximation",
                    "t2_mismatch":[
                      "T2 ante phase uses 1BB big-blind ante, not per-player ante",
                      "source push/fold tree does not model non-all-in opens",
                      "source has no ICM",
                    ],
                    "use":"short-stack GTO learned-prior reference; do not substitute for normal raise-tree strategy",
                  },
                  "tags":["9max","mtt","preflop","pushfold","public","redistributable"],
                }
                rec["sha256"]=sha(rec)
                records.append(rec);vcount+=1
        counts[variant_name]=vcount

    path=out/"preflop_9max_pushfold_v1.jsonl"
    with path.open("w") as f:
        for r in records:
            f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n")

    index={
      "schema_version":"gto_db_index_v1",
      "canonical_table_players":9,
      "target_format":"MTT",
      "target_ante_model":"1BB big-blind ante",
      "dataset":"preflop_9max_pushfold_v1.jsonl",
      "record_count":len(records),
      "records_by_variant":counts,
      "depths_bb":depths,
      "hand_classes":169,
      "source":source,
      "status":"auxiliary-near for T2 BBA; canonical short-stack reference only within source model",
    }
    (out/"index_9max_v1.json").write_text(json.dumps(index,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print(json.dumps(index,sort_keys=True))

if __name__=="__main__":
    main()
