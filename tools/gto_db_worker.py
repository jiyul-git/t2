#!/usr/bin/env python3
"""Termux GTO DB worker.

- Uses the existing vendored GTOpen server; does NOT implement a new solver.
- Solves only stacks that still have missing planned spots.
- Stores one canonical T2 spot per file; file order is irrelevant.
- Existing v2 spot files are always skipped.
- Qualified existing 9-max pilot rows are normalized first, so they are not recomputed.
"""
from __future__ import annotations
import argparse, glob, hashlib, json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from gto_db_schema import POSITIONS, CLASSES, action_obj, face_open_state, policy_from_node, rfi_state, solution_id, spot_key, spot_path, write_spot

BASE="http://127.0.0.1:3737"

def req(method,path,obj=None,timeout=1200):
    data=None if obj is None else json.dumps(obj).encode()
    r=urllib.request.Request(BASE+path,data=data,method=method,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=timeout) as resp:
        return json.load(resp)

def server_alive():
    try:
        req("GET","/api/preflop/capabilities",timeout=2)
        return True
    except Exception:
        return False

def start_server(threads,eq_samples,seed):
    if server_alive():
        print("SERVER already running")
        return None
    binary=ROOT/"vendor/gtopen/target/release/gto-server"
    if not binary.exists():
        raise SystemExit("missing GTOpen binary; first run: cd vendor/gtopen && cargo build --release -p server")
    env={**os.environ,
         "SOLVER_THREADS":str(threads),
         "PREFLOP_EQ_SAMPLES":str(eq_samples),
         "PREFLOP_EQ_SEED":str(seed),
         "PREFLOP_MULTIWAY_SEED":str(seed)}
    log=open(ROOT/"gto_db_worker_server.log","a")
    p=subprocess.Popen([str(binary)],cwd=ROOT/"vendor/gtopen",env=env,stdout=log,stderr=log)
    for _ in range(120):
        if server_alive():
            print("SERVER started pid",p.pid)
            return p
        if p.poll() is not None:
            raise SystemExit("gto-server exited; see gto_db_worker_server.log")
        time.sleep(1)
    p.terminate()
    raise SystemExit("gto-server start timeout")

def cfg_for(stack):
    # Same 9-max pilot tree profile already used in the repository.
    ante=1.0/9.0
    per_open=[[2.0] for _ in POSITIONS]
    per_open[7]=[2.5]
    per_raise=[[3.0] for _ in POSITIONS]
    per_raise[7]=[4.0]; per_raise[8]=[4.0]
    return {
      "positions":POSITIONS,"stack":float(stack),
      "posts":[0,0,0,0,0,0,0,0.5,1.0],"ante":ante,
      "limp":False,"open_raises":[2.0],"raise_mults":[3.0],"max_raises":2,
      "add_allin":True,"allin_threshold":0.85,
      "rake_pct":0.0,"rake_cap":0.0,"no_flop_no_drop":True,
      "realization":"balanced","call_only_seats":[],
      "open_raises_by_seat":per_open,"raise_mults_by_seat":per_raise,
      "fourbet_mults":[2.2],"fourbet_mults_by_seat":[[2.2] for _ in POSITIONS],
    }

def planned_states(stack):
    out=[]
    for hero in POSITIONS[:-1]:
        out.append(rfi_state(stack,hero))
    for oi,opener in enumerate(POSITIONS[:-1]):
        for hero in POSITIONS[oi+1:]:
            out.append(face_open_state(stack,opener,hero,2.5 if opener=="SB" else 2.0))
    return out

def existing_keys():
    return {p.stem for p in (ROOT/"data/gto_db/spots").glob("*/*.json")} if (ROOT/"data/gto_db/spots").exists() else set()

def _pilot_action_key(a):
    k=a.get("kind")
    if k=="allin": k="jam"
    if k in ("raise","jam"):
        return f'{k}_to_{float(a.get("to",0)):g}'
    return k

def _pilot_policy(s):
    acts=[action_obj(a) for a in s["actions"]]
    hands={}
    for h in CLASSES:
        row=s["hands"][h]
        vals=[]
        for a0,a1 in zip(s["actions"],acts):
            k=a0.get("kind")
            if k=="allin": k="jam"
            oldk=k
            if a0.get("kind") in ("raise","jam","allin"):
                rawkind="jam" if a0.get("kind")=="allin" else a0.get("kind")
                oldk=f'{rawkind}_to_{float(a0.get("to",0)):g}'
            vals.append(float(row.get(oldk,row.get(k,0.0))))
        hands[h]=vals
    return {"actions":acts,"hand_class_order":CLASSES,"hands":hands}

def import_existing_pilots():
    """Normalize already-qualified repo pilot RFI/face-open data. No solver work."""
    made=0
    for fn in sorted(glob.glob(str(ROOT/"data/gto_9max_solver_pilot_*.json"))):
        if fn.endswith("_ensemble.json"): continue
        try: d=json.load(open(fn))
        except Exception: continue
        if not isinstance(d,dict) or not isinstance(d.get("spots"),list): continue
        solver=d.get("solver",{})
        status=solver.get("status",{})
        gap=status.get("gap_total")
        target=solver.get("target_gap")
        if gap is None or target is None or float(gap)>float(target):
            continue
        stack=float(d.get("stack_bb",d.get("config",{}).get("stack",0)))
        for s in d["spots"]:
            typ=s.get("spot_type")
            if typ=="rfi":
                state=rfi_state(stack,s["position"])
            elif typ=="face_open":
                op=s["opener"]; hero=s.get("defender") or s.get("hero")
                state=face_open_state(stack,op,hero,2.5 if op=="SB" else 2.0)
            else:
                continue
            key=spot_key(state)
            if spot_path(ROOT,key).exists(): continue
            meta={
              "source_kind":"existing_solver_pilot",
              "source_file":str(Path(fn).relative_to(ROOT)),
              "solver_name":"GTOpen vendored snapshot",
              "target_model":"T2 1BB BBA",
              "ante_model":{"kind":"uniform_per_player_same_total_dead_money","exact_bba":False},
              "gap_total":float(gap),"target_gap":float(target),
              "iteration":status.get("iteration"),
              "config_sha256":hashlib.sha256(json.dumps(d.get("config",{}),sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            }
            sol={"solution_id":solution_id(key,meta),"quality":{"status":"qualified_near_t2_bba","exact_target_match":False},
                 "solver":meta,"strategy":_pilot_policy(s)}
            write_spot(ROOT,state,sol); made+=1
    if made: print("IMPORTED existing qualified pilot spots:",made)
    return made

def node(path):
    return req("POST","/api/preflop/node",{"path":path})

def choose(n,kind=None,to=None):
    for i,a in enumerate(n["actions"]):
        ak=a.get("kind")
        if kind=="jam" and ak=="allin": ak="jam"
        if kind is not None and ak!=kind: continue
        if to is not None and abs(float(a.get("to",0))-float(to))>1e-6: continue
        return i
    raise RuntimeError("action not found "+json.dumps({"actor":n.get("actor_pos"),"actions":n.get("actions"),"kind":kind,"to":to}))

def path_to_rfi(pos):
    p=[]
    while True:
        n=node(p)
        if n["actor_pos"]==pos: return p,n
        p.append(choose(n,"fold"))

def face_open(opener,hero):
    p,n=path_to_rfi(opener)
    open_to=2.5 if opener=="SB" else 2.0
    p.append(choose(n,"raise",open_to))
    for _ in range(20):
        n=node(p)
        if n["actor_pos"]==hero: return p,n
        p.append(choose(n,"fold"))
    raise RuntimeError("hero not reached")

def make_solution(key,n,stack,status,cfg,seed):
    meta={
      "source_kind":"termux_worker",
      "solver_name":"GTOpen vendored snapshot",
      "target_model":"T2 1BB BBA",
      "ante_model":{
        "kind":"uniform_per_player_same_total_dead_money",
        "per_player_bb":1.0/9.0,"total_bb":1.0,"exact_bba":False,
        "limitation":"same dead money, not exact T2 BBA; especially relevant to BB defense"
      },
      "stack_bb":float(stack),"seed":seed,
      "gap_total":status.get("gap_total"),"iteration":status.get("iteration"),
      "config_sha256":hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
      "git_commit":subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True).stdout.strip(),
    }
    return {"solution_id":solution_id(key,meta),
            "quality":{"status":"qualified_near_t2_bba","exact_target_match":False},
            "solver":meta,"strategy":policy_from_node(n)}

def solve_stack(stack,iters,target,seed):
    cfg=cfg_for(stack)
    print("BUILD",stack)
    req("POST","/api/preflop/spot",cfg)
    print("SOLVE",stack,"iters",iters,"target",target)
    req("POST","/api/preflop/solve",{"iterations":iters,"check_every":20,"target_gap":target})
    st=None
    for _ in range(24*3600):
        st=req("GET","/api/preflop/status")
        if st.get("state")!="running": break
        time.sleep(1)
    if not st or st.get("state")=="running":
        raise RuntimeError("solve timeout")
    gap=st.get("gap_total")
    print("STATUS",stack,"iteration",st.get("iteration"),"gap",gap)
    if gap is None or float(gap)>target:
        print("NOT SAVED: convergence gate missed")
        return 0
    have=existing_keys(); wrote=0
    for hero in POSITIONS[:-1]:
        state=rfi_state(stack,hero); key=spot_key(state)
        if key in have: continue
        _,n=path_to_rfi(hero)
        write_spot(ROOT,state,make_solution(key,n,stack,st,cfg,seed)); have.add(key); wrote+=1
    for oi,opener in enumerate(POSITIONS[:-1]):
        for hero in POSITIONS[oi+1:]:
            state=face_open_state(stack,opener,hero,2.5 if opener=="SB" else 2.0); key=spot_key(state)
            if key in have: continue
            _,n=face_open(opener,hero)
            write_spot(ROOT,state,make_solution(key,n,stack,st,cfg,seed)); have.add(key); wrote+=1
    print("SAVED",wrote,"new canonical spots for",stack,"bb")
    return wrote

def git_push(count):
    if count<=0:
        print("PUSH skipped: no new spot files")
        return
    branch=subprocess.run(["git","branch","--show-current"],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    subprocess.run(["git","add","data/gto_db/spots"],cwd=ROOT,check=True)
    diff=subprocess.run(["git","diff","--cached","--quiet"],cwd=ROOT)
    if diff.returncode==0:
        print("PUSH skipped: nothing staged"); return
    subprocess.run(["git","commit","-m",f"gto-db: add {count} canonical solved spots"],cwd=ROOT,check=True)
    subprocess.run(["git","push","origin",f"HEAD:{branch}"],cwd=ROOT,check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stacks",type=float,nargs="+",default=[30,25,40,20])
    ap.add_argument("--iters",type=int,default=120)
    ap.add_argument("--target-gap",type=float,default=0.15)
    ap.add_argument("--seed",type=int,default=20261003)
    ap.add_argument("--threads",type=int,default=4)
    ap.add_argument("--eq-samples",type=int,default=1200)
    ap.add_argument("--push",action="store_true")
    ap.add_argument("--inventory-only",action="store_true")
    a=ap.parse_args()

    imported=import_existing_pilots()
    have=existing_keys()
    print("INVENTORY canonical v2 spots:",len(have),"imported_now:",imported)
    for s in a.stacks:
        plan=planned_states(s); miss=[x for x in plan if spot_key(x) not in have]
        print(f"PLAN {s:g}bb: total={len(plan)} missing={len(miss)}")
    if a.inventory_only:
        return

    need=[s for s in a.stacks if any(spot_key(x) not in have for x in planned_states(s))]
    if not need:
        print("DONE: all requested spots already exist")
        if a.push: git_push(imported)
        return
    proc=start_server(a.threads,a.eq_samples,a.seed)
    wrote=0
    try:
        for s in a.stacks:
            have=existing_keys()
            miss=sum(1 for x in planned_states(s) if spot_key(x) not in have)
            if not miss:
                print("SKIP",s,"bb: all planned spots already stored")
                continue
            wrote+=solve_stack(s,a.iters,a.target_gap,a.seed)
    finally:
        if proc is not None:
            proc.terminate()
    if a.push:
        git_push(wrote+imported)
    print("DONE new_or_imported",wrote+imported)

if __name__=="__main__":
    main()
