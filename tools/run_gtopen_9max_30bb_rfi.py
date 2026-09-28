#!/usr/bin/env python3
import json, os, time, urllib.request, urllib.error

BASE="http://127.0.0.1:3737"
POSITIONS=["UTG","UTG+1","UTG+2","LJ","HJ","CO","BTN","SB","BB"]
PUBLIC_RFI={
  "UTG":0.165,"UTG+1":0.186,"UTG+2":0.217,"LJ":0.257,
  "HJ":0.299,"CO":0.375,"BTN":0.487,"SB":0.894
}
COMBO_W=[6 if i//13==i%13 else (12 if i//13<i%13 else 4) for i in range(169)]
assert sum(COMBO_W)==1326

def req(method,path,obj=None):
    data=None if obj is None else json.dumps(obj).encode()
    r=urllib.request.Request(BASE+path,data=data,method=method,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=900) as resp:
        return json.load(resp)

cfg={
  "positions":POSITIONS,
  "stack":30.0,
  "posts":[0,0,0,0,0,0,0,0.5,1.0],
  # Near-BBA approximation: same total dead money (1bb), but distributed evenly.
  "ante":1.0/9.0,
  "limp":False,
  "open_raises":[2.0],
  "raise_mults":[3.0],
  "max_raises":2,
  "add_allin":True,
  "allin_threshold":0.85,
  "rake_pct":0.0,
  "rake_cap":0.0,
  "no_flop_no_drop":True,
  "realization":"static",
  "call_only_seats":[],
  "open_raises_by_seat":[[2.0],[2.0],[2.0],[2.0],[2.0],[2.0],[2.0],[2.0],[]],
  "raise_mults_by_seat":[[3.0],[3.0],[3.0],[3.0],[3.0],[3.0],[3.0],[3.5],[3.5]],
  "fourbet_mults":[2.2],
  "fourbet_mults_by_seat":[[2.2],[2.2],[2.2],[2.2],[2.2],[2.2],[2.2],[2.35],[2.35]]
}
print("BUILD",json.dumps(req("POST","/api/preflop/spot",cfg),sort_keys=True))
solve_req={
  "iterations":int(os.getenv("GTOPEN_ITERS","150")),
  "check_every":int(os.getenv("GTOPEN_CHECK","25")),
  "target_gap":float(os.getenv("GTOPEN_TARGET","0.15"))
}
print("SOLVE_START",json.dumps(req("POST","/api/preflop/solve",solve_req),sort_keys=True))
for _ in range(1200):
    st=req("GET","/api/preflop/status")
    if st.get("state")!="running":
        print("STATUS",json.dumps(st,sort_keys=True))
        break
    time.sleep(1)
else:
    raise SystemExit("solve did not finish")

path=[]
records={}
def node():
    return req("POST","/api/preflop/node",{"path":path})
def choose(n,kind,to=None):
    for i,a in enumerate(n["actions"]):
        if a.get("kind")!=kind: continue
        if to is not None and abs(float(a.get("to",0))-to)>1e-6: continue
        return i
    raise RuntimeError("action not found "+json.dumps({"actor":n.get("actor_pos"),"actions":n.get("actions"),"kind":kind,"to":to}))

for pos in POSITIONS[:-1]:
    n=node()
    assert n["actor_pos"]==pos,(pos,n["actor_pos"])
    acts=n["actions"]; strat=n["strategy"]
    open_idxs=[i for i,a in enumerate(acts) if a.get("kind") in ("raise","allin")]
    fold_idx=choose(n,"fold")
    hand_rows=[]
    weighted=0.0
    for h in range(169):
        af=[]
        op=0.0
        for ai,a in enumerate(acts):
            fr=float(strat[ai*169+h])
            if fr>1e-8:
                af.append({"kind":a.get("kind"),"to":a.get("to"),"freq":fr})
            if ai in open_idxs: op+=fr
        weighted+=COMBO_W[h]*op
        hand_rows.append({"index":h,"combo_weight":COMBO_W[h],"open_freq":op,"actions":af})
    rate=weighted/1326.0
    records[pos]={
      "actor":pos,"aggregate_open_rate":rate,
      "public_crosscheck_rate":PUBLIC_RFI[pos],
      "rate_error":rate-PUBLIC_RFI[pos],
      "actions":acts,"hands":hand_rows
    }
    path.append(fold_idx)

mae=sum(abs(x["rate_error"]) for x in records.values())/len(records)
out={
 "schema_version":"gto_solve_audit_v1",
 "spot":"9max MTT 30bb RFI pilot",
 "quality":"near/limited",
 "assumptions":{
   "table_players":9,"stack_bb":30,"sb_bb":0.5,"bb_bb":1.0,
   "ante_model":"uniform 1/9bb per player approximating total 1bb BBA dead money",
   "target_t2_ante":"1bb big-blind ante",
   "open_size_bb":2.0,"sb_open_size_note":"pilot uses 2bb; do not validate SB against public 3.5bb reference",
   "limp":False,"max_raises":2,"add_allin":True,
   "threebet_mult_ip":3.0,"threebet_mult_blinds":3.5,
   "rake":0.0,"icm":False,"realization":"static"
 },
 "solver":{
   "name":"GTOpen vendored snapshot",
   "iterations_requested":solve_req["iterations"],
   "target_gap":solve_req["target_gap"],
   "iteration":st.get("iteration"),
   "gap_total":st.get("gap_total"),
   "publication":st.get("publication"),
   "multiway_equity_model":st.get("multiway_equity_model")
 },
 "external_validation":{
   "source":"PreflopRanges public 9-max MTT 30bb aggregate opening page",
   "usage":"manual aggregate cross-check only; no chart extraction",
   "non_sb_mae":sum(abs(records[p]["rate_error"]) for p in POSITIONS[:-2])/7.0,
   "all_positions_mae_including_mismatched_sb":mae
 },
 "positions":records
}
os.makedirs("data/gto_db/solver",exist_ok=True)
with open("data/gto_db/solver/gtopen_9max_30bb_rfi_pilot.json","w") as f:
    json.dump(out,f,indent=2,sort_keys=True)
print("RESULT",json.dumps({
 "iteration":out["solver"]["iteration"],
 "gap_total":out["solver"]["gap_total"],
 "non_sb_mae":out["external_validation"]["non_sb_mae"],
 "rates":{p:round(records[p]["aggregate_open_rate"],4) for p in records},
 "errors":{p:round(records[p]["rate_error"],4) for p in records}
},sort_keys=True))
