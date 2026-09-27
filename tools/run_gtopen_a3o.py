#!/usr/bin/env python3
import json, time, urllib.request, urllib.error, os

BASE="http://127.0.0.1:3737"

def req(method,path,obj=None):
    data=None if obj is None else json.dumps(obj).encode()
    r=urllib.request.Request(BASE+path,data=data,method=method,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=600) as resp:
        return json.load(resp)

cfg={
  "positions":["UTG","UTG+1","LJ","HJ","CO","BTN","SB","BB"],
  "stack":150.0,
  "posts":[0,0,0,0,0,0,0.5,1.0],
  "ante":0.0,
  "limp":False,
  "open_raises":[2.5],
  "raise_mults":[3.0],
  "max_raises":int(os.getenv("GTOPEN_MAX_RAISES","3")),
  "add_allin":os.getenv("GTOPEN_ADD_ALLIN","1")!="0",
  "allin_threshold":0.85,
  "rake_pct":0.0,
  "rake_cap":0.0,
  "no_flop_no_drop":True,
  "realization":"static",
  "call_only_seats":[],
  "open_raises_by_seat":[[],[],[],[],[2.5],[],[],[]],
  "raise_mults_by_seat":[[3.0],[3.0],[3.0],[3.0],[3.0],[3.0],[3.7],[3.7]],
  "fourbet_mults":[2.2],
  "fourbet_mults_by_seat":[[2.15],[2.15],[2.15],[2.15],[2.15],[2.15],[2.35],[2.35]]
}

print("BUILD",json.dumps(req("POST","/api/preflop/spot",cfg),sort_keys=True))
print("SOLVE_START",json.dumps(req("POST","/api/preflop/solve",{
  "iterations":int(os.getenv("GTOPEN_ITERS","300")),"check_every":int(os.getenv("GTOPEN_CHECK","25")),"target_gap":float(os.getenv("GTOPEN_TARGET","0.01"))
}),sort_keys=True))

for _ in range(1200):
    st=req("GET","/api/preflop/status")
    if st.get("state")!="running":
        print("STATUS",json.dumps(st,sort_keys=True))
        break
    time.sleep(1)
else:
    raise SystemExit("solve did not finish")

path=[]
def node():
    return req("POST","/api/preflop/node",{"path":[{"type":"action","index":i} for i in path]})

def choose(n, kind=None, to=None):
    for i,a in enumerate(n["actions"]):
        if kind is not None and a.get("kind")!=kind: continue
        if to is not None and abs(float(a.get("to",0))-to)>1e-6: continue
        return i
    raise RuntimeError("action not found: "+json.dumps({"actor":n.get("actor_pos"),"actions":n.get("actions"),"kind":kind,"to":to}))

for pos in ["UTG","UTG+1","LJ","HJ"]:
    n=node()
    assert n["actor_pos"]==pos,(pos,n["actor_pos"])
    path.append(choose(n,kind="fold"))

n=node(); assert n["actor_pos"]=="CO",n["actor_pos"]
path.append(choose(n,kind="raise",to=2.5))
for pos in ["BTN","SB"]:
    n=node(); assert n["actor_pos"]==pos,(pos,n["actor_pos"])
    path.append(choose(n,kind="fold"))

n=node()
assert n["actor_pos"]=="BB",n["actor_pos"]
idx=25  # A3o: low-rank 3 index 1 * 13 + Ace index 12
strat=n["strategy"]
acts=n["actions"]
freqs=[]
for a,meta in enumerate(acts):
    freqs.append({
      "label":meta["label"],"kind":meta["kind"],"to":meta["to"],
      "freq":strat[a*169+idx]
    })
out={
 "spot":"8max 150bb no-ante CO 2.5bb vs BB A3o",
 "path":path,
 "actor":n["actor_pos"],
 "A3o_index":idx,
 "A3o_reach":n["reach"][idx] if n.get("reach") else None,
 "actions":freqs,
 "strategy_note":n.get("strategy_note"),
 "publication":st.get("publication"),
 "gap_total":st.get("gap_total"),
 "iteration":st.get("iteration"),
 "solver_model":st.get("multiway_equity_model")
}
print("A3O_RESULT",json.dumps(out,sort_keys=True))
