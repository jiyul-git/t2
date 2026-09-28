#!/usr/bin/env python3
import json, os, time, urllib.request

BASE="http://127.0.0.1:3737"
POSITIONS=["UTG","UTG+1","UTG+2","LJ","HJ","CO","BTN","SB","BB"]
RANKS="23456789TJQKA"

def class_names():
    out=[]
    for i,r in enumerate(RANKS):
        for j,c in enumerate(RANKS):
            if i==j: out.append(r+r)
            elif j>i: out.append(c+r+"o")
            else: out.append(r+c+"s")
    assert len(out)==169 and out[25]=="A3o"
    return out
CLASSES=class_names()

def combo_weight(h):
    return 6 if len(h)==2 else (4 if h.endswith("s") else 12)

def req(method,path,obj=None):
    data=None if obj is None else json.dumps(obj).encode()
    r=urllib.request.Request(BASE+path,data=data,method=method,
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=1200) as resp:
        return json.load(resp)

def node(path):
    return req("POST","/api/preflop/node",{"path":path})

def choose(n, kind=None, to=None, nonjam_raise=False):
    for i,a in enumerate(n["actions"]):
        if kind is not None and a.get("kind")!=kind: continue
        if nonjam_raise and a.get("kind")!="raise": continue
        if to is not None and abs(float(a.get("to",0))-float(to))>1e-6: continue
        return i
    raise RuntimeError("action not found "+json.dumps({
      "actor":n.get("actor_pos"),"actions":n.get("actions"),
      "kind":kind,"to":to,"nonjam_raise":nonjam_raise}))

def extract(n, path, spot_type, **meta):
    strat=n["strategy"]; acts=n["actions"]
    hands={}
    for hi,h in enumerate(CLASSES):
        row={}
        for ai,a in enumerate(acts):
            key=a["kind"]
            if key in ("raise","jam"):
                key=f'{key}_to_{float(a.get("to",0)):g}'
            row[key]=float(strat[ai*169+hi])
        hands[h]=row
    out={
      "spot_type":spot_type,
      "actor":n["actor_pos"],
      "path":list(path),
      "actions":acts,
      "hands":hands,
      "strategy_note":n.get("strategy_note"),
    }
    out.update(meta)
    return out

def aggregate_aggression(spot):
    num=den=0.0
    for h,row in spot["hands"].items():
        w=combo_weight(h); den+=w
        num += w*sum(v for k,v in row.items() if k.startswith("raise_") or k.startswith("jam_"))
    return num/den

def path_to_rfi(pos):
    p=[]
    while True:
        n=node(p)
        if n["actor_pos"]==pos: return p,n
        p.append(choose(n,kind="fold"))

def face_open(opener, hero):
    p,n=path_to_rfi(opener)
    open_to=2.5 if opener=="SB" else 2.0
    p.append(choose(n,kind="raise",to=open_to))
    for _ in range(20):
        n=node(p)
        if n["actor_pos"]==hero:
            return p,n
        p.append(choose(n,kind="fold"))
    raise RuntimeError("hero not reached")

def opener_vs_3bet(opener, threebettor):
    p,n=path_to_rfi(opener)
    open_to=2.5 if opener=="SB" else 2.0
    p.append(choose(n,kind="raise",to=open_to))
    # everyone before chosen 3bettor folds
    for _ in range(20):
        n=node(p)
        if n["actor_pos"]==threebettor: break
        p.append(choose(n,kind="fold"))
    else: raise RuntimeError("3bettor not reached")
    p.append(choose(n,nonjam_raise=True))
    # fold every other reopened seat until original opener
    for _ in range(30):
        n=node(p)
        if n["actor_pos"]==opener:
            return p,n
        p.append(choose(n,kind="fold"))
    raise RuntimeError("opener not reached after 3bet")

def main():
    stack=float(os.getenv("GT9_STACK","30"))
    iterations=int(os.getenv("GT9_ITERS","120"))
    target=float(os.getenv("GT9_TARGET","0.15"))
    max_raises=int(os.getenv("GT9_MAX_RAISES","2"))
    # GTOpen's legacy ante is uniform and outside the live stack cap.
    # 1/9 bb each gives the same 1bb dead-money total as T2 BBA but is NOT exact BBA.
    ante=1.0/9.0
    per_open=[[2.0] for _ in POSITIONS]
    per_open[7]=[2.5]  # SB
    per_raise=[[3.0] for _ in POSITIONS]
    per_raise[7]=[4.0]; per_raise[8]=[4.0]
    cfg={
      "positions":POSITIONS,
      "stack":stack,
      "posts":[0,0,0,0,0,0,0,0.5,1.0],
      "ante":ante,
      "limp":False,
      "open_raises":[2.0],
      "raise_mults":[3.0],
      "max_raises":max_raises,
      "add_allin":True,
      "allin_threshold":0.85,
      "rake_pct":0.0,"rake_cap":0.0,"no_flop_no_drop":True,
      "realization":"static",
      "call_only_seats":[],
      "open_raises_by_seat":per_open,
      "raise_mults_by_seat":per_raise,
      "fourbet_mults":[2.2],
      "fourbet_mults_by_seat":[[2.2] for _ in POSITIONS],
    }
    print("BUILD",json.dumps(req("POST","/api/preflop/spot",cfg),sort_keys=True))
    print("SOLVE_START",json.dumps(req("POST","/api/preflop/solve",{
      "iterations":iterations,"check_every":20,"target_gap":target
    }),sort_keys=True))
    st=None
    for _ in range(1800):
        st=req("GET","/api/preflop/status")
        if st.get("state")!="running": break
        time.sleep(1)
    if not st or st.get("state")=="running":
        raise SystemExit("solve timeout")
    print("STATUS",json.dumps(st,sort_keys=True))

    spots=[]
    rfi_summary={}
    for pos in POSITIONS[:-1]:
        p,n=path_to_rfi(pos)
        s=extract(n,p,"rfi",position=pos)
        spots.append(s); rfi_summary[pos]=aggregate_aggression(s)

    # All clean single-open defense nodes, no callers.
    for oi,opener in enumerate(POSITIONS[:-1]):
        for hero in POSITIONS[oi+1:]:
            p,n=face_open(opener,hero)
            spots.append(extract(n,p,"face_open",opener=opener,defender=hero))

    # Common opener-facing-3bet response nodes in restricted open+3bet tree.
    pairs=[("HJ","BTN"),("CO","BTN"),("CO","SB"),("CO","BB"),
           ("BTN","SB"),("BTN","BB")]
    for opener,threebettor in pairs:
        try:
            p,n=opener_vs_3bet(opener,threebettor)
            spots.append(extract(n,p,"opener_faces_3bet",
                opener=opener,threebettor=threebettor))
        except Exception as e:
            spots.append({"spot_type":"opener_faces_3bet","opener":opener,
                          "threebettor":threebettor,"error":str(e)})

    out={
      "schema_version":"gto_9max_solver_pilot_v1",
      "table_players":9,
      "stack_bb":stack,
      "target_model":"T2 1BB BBA",
      "solver_ante_model":{
        "kind":"uniform_per_player_same_total_dead_money",
        "per_player_bb":ante,
        "total_bb":1.0,
        "exact_bba":False,
        "limitation":"BB live stack is not reduced by the full 1BB BBA; treat as near/limited, especially for BB defense."
      },
      "config":cfg,
      "solver":{
        "iterations_requested":iterations,
        "target_gap":target,
        "status":st,
        "multiway_equity_model":st.get("multiway_equity_model"),
        "publication":st.get("publication"),
      },
      "rfi_combo_weighted":rfi_summary,
      "spots":spots,
    }
    path=f"data/gto_9max_solver_pilot_{int(stack)}bb.json"
    os.makedirs("data",exist_ok=True)
    with open(path,"w") as f:json.dump(out,f,indent=2,sort_keys=True)
    print("PILOT_SUMMARY",json.dumps({
      "stack":stack,"rfi":rfi_summary,"spot_count":len(spots),
      "gap_total":st.get("gap_total"),"iteration":st.get("iteration"),
      "output":path},sort_keys=True))

if __name__=="__main__":
    main()
