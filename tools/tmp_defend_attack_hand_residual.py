#!/usr/bin/env python3
import json, pathlib, collections, bisect
import preflop

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=pathlib.Path("/tmp/8max_mtt_matthiola.jsonl")
PCT=json.loads((ROOT/"pf_rank.json").read_text())
TRAIN={10,20,50}; HOLD={15,30,100}
DIRECT={
 "EP-vs-MP":(["UTG","UTG+1","LJ"],"CO"),
 "EP-vs-BTN":(["UTG","UTG+1","LJ"],"BTN"),
 "EP-vs-SB":(["UTG","UTG+1","LJ"],"SB"),
 "EP-vs-BB":(["UTG","UTG+1","LJ"],"BB"),
 "MP-vs-BTN":(["HJ","CO"],"BTN"),
 "MP-vs-SB":(["HJ","CO"],"SB"),
 "MP-vs-BB":(["HJ","CO"],"BB"),
 "BTN-vs-SB":(["BTN"],"SB"),
 "BTN-vs-BB":(["BTN"],"BB"),
 "SB-vs-BB":(["SB"],"BB"),
}
PROF={"concepts":{"pf_defend":10.0},
      "temper":{"looseness":5.0,"aggression":5.0,"slowplay_taste":5.0},
      "type":"GTO_ISH"}

def combos(h): return 6 if len(h)==2 else (4 if h.endswith("s") else 12)
def cards(h):
    if len(h)==2:return [h[0]+"s",h[1]+"h"]
    return [h[0]+"s",h[1]+("s" if h[2]=="s" else "h")]
def targ(r):
    a=float(r.get("raise",0))+float(r.get("allin",0))
    c=float(r.get("call",0));f=float(r.get("fold",0))
    return a,c,f,a+c

def pava(points):
    points=sorted(points)
    blocks=[]
    for x,y,w in points:
        blocks.append({"xmin":x,"xmax":x,"w":w,"wy":w*y,"mean":y})
        while len(blocks)>=2 and blocks[-2]["mean"] < blocks[-1]["mean"]-1e-15:
            b=blocks.pop();a=blocks.pop();w2=a["w"]+b["w"]
            blocks.append({"xmin":a["xmin"],"xmax":b["xmax"],"w":w2,"wy":a["wy"]+b["wy"],"mean":(a["wy"]+b["wy"])/w2})
    bounds=[(a["xmax"]+b["xmin"])/2 for a,b in zip(blocks,blocks[1:])]
    return {"bounds":bounds,"means":[b["mean"] for b in blocks]}

def pred(m,x): return m["means"][bisect.bisect_right(m["bounds"],x)]

rows=[json.loads(x) for x in DATA.read_text().splitlines() if x.strip()]
groups=collections.defaultdict(list)
for r in rows:
    if r.get("scenario")=="vs-open" and r.get("node") in DIRECT:
        groups[(int(r["stack_bb"]),r["node"])].append(r)

items=[]
for (stack,node),rs in sorted(groups.items()):
    ops,hero=DIRECT[node];open_bb=3.0 if node=="SB-vs-BB" else 2.5
    for r in rs:
        h=r["hand"];ta,tc,tf,tcont=targ(r);vals=[]
        for op in ops:
            vals.append(preflop.defend_action_likelihoods(PROF,hero,op,cards(h),stack,open_bb,0,
              raise_level=1,stack_bb=stack,exploit=None,bf=1.0,seats=8,ante=True,
              opener_allin=False,can_raise=True))
        tp=sum(v["tp"] for v in vals)/len(vals);tot=sum(v["tot"] for v in vals)/len(vals)
        ca=sum(v["attack"] for v in vals)/len(vals);cc=sum(v["call"] for v in vals)/len(vals);cf=sum(v["fold"] for v in vals)/len(vals)
        items.append({"stack":stack,"node":node,"hero":hero,"hand":h,"w":combos(h),"r":PCT[h],
          "za":PCT[h]/max(tp,1e-9),"zc":PCT[h]/max(tot,1e-9),
          "ta":ta,"tc":tc,"tf":tf,"tcont":tcont,"ca":ca,"cc":cc,"cf":cf})

# Defender-specific monotone base, trained only on TRAIN.
models={}
for hero in sorted(set(x["hero"] for x in items)):
    sub=[x for x in items if x["stack"] in TRAIN and x["hero"]==hero]
    models[hero]={"a":pava([(x["za"],x["ta"],x["w"]) for x in sub]),
                  "c":pava([(x["zc"],x["tcont"],x["w"]) for x in sub])}

def base_pred(x):
    cont=pred(models[x["hero"]]["c"],x["zc"])
    a=min(pred(models[x["hero"]]["a"],x["za"]),cont)
    return a,cont

# Fit additive attack residual by hand, global and defender-specific.
res_global=collections.defaultdict(lambda:[0.0,0.0])
res_def=collections.defaultdict(lambda:[0.0,0.0])
for x in items:
    if x["stack"] not in TRAIN:continue
    a,cont=base_pred(x);w=x["w"]
    d=x["ta"]-a
    res_global[x["hand"]][0]+=w*d;res_global[x["hand"]][1]+=w
    k=(x["hero"],x["hand"]);res_def[k][0]+=w*d;res_def[k][1]+=w
res_global={h:s/w for h,(s,w) in res_global.items()}
res_def={k:s/w for k,(s,w) in res_def.items()}

def score(kind,shrink,stacks):
    sw=ss=amae=cmae=0.0
    hand_err=collections.defaultdict(lambda:[0.0,0.0])
    for x in items:
        if x["stack"] not in stacks:continue
        a,cont=base_pred(x)
        if kind=="global":d=res_global.get(x["hand"],0.0)
        elif kind=="defender":d=res_def.get((x["hero"],x["hand"]),0.0)
        else:d=0.0
        a=max(0.0,min(cont,a+shrink*d))
        c=max(0.0,cont-a);f=max(0.0,1-cont)
        w=x["w"];sw+=w
        e=((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3
        ss+=w*e;amae+=w*abs(a-x["ta"]);cmae+=w*abs(cont-x["tcont"])
        hand_err[x["hand"]][0]+=w*abs(a-x["ta"]);hand_err[x["hand"]][1]+=w
    worst=sorted(((s/w,h) for h,(s,w) in hand_err.items()),reverse=True)[:20]
    return {"action_brier":ss/sw,"attack_mae":amae/sw,"continue_mae":cmae/sw,
            "worst_attack_hands":[{"hand":h,"mae":e} for e,h in worst]}

candidates=[]
for kind in ["none","global","defender"]:
    shrinks=[0.0] if kind=="none" else [0.25,0.5,0.75,1.0]
    best=None
    for sh in shrinks:
        tr=score(kind,sh,TRAIN)
        key=(tr["action_brier"],tr["attack_mae"],sh)
        if best is None or key<best[0]:best=(key,sh,tr)
    sh=best[1]
    candidates.append({"kind":kind,"shrink":sh,"train":best[2],"holdout":score(kind,sh,HOLD),"all":score(kind,sh,TRAIN|HOLD)})

# Stability of global residual sign/magnitude by training stack.
stack_res={}
for s in sorted(TRAIN):
    dd=collections.defaultdict(lambda:[0.0,0.0])
    for x in items:
        if x["stack"]!=s:continue
        a,_=base_pred(x);w=x["w"];dd[x["hand"]][0]+=w*(x["ta"]-a);dd[x["hand"]][1]+=w
    stack_res[str(s)]={h:v[0]/v[1] for h,v in dd.items()}
stability=[]
for h in sorted(res_global):
    vals=[stack_res[str(s)][h] for s in sorted(TRAIN)]
    same=(all(v>=0 for v in vals) or all(v<=0 for v in vals))
    stability.append({"hand":h,"global_residual":res_global[h],"train_stack_residuals":vals,"same_sign":same})
stability.sort(key=lambda x:abs(x["global_residual"]),reverse=True)

out={"scope":"shadow only: cross-validated additive attack residual by starting-hand class on top of defender-specific normalized isotonic base",
     "train_stacks":sorted(TRAIN),"holdout_stacks":sorted(HOLD),
     "candidates":candidates,
     "top_residual_stability":stability[:50],
     "same_sign_fraction_top50":sum(x["same_sign"] for x in stability[:50])/50.0}
dst=ROOT/"data"/"gto_public";dst.mkdir(parents=True,exist_ok=True)
(dst/"defend_attack_hand_residual_shadow_20260928.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
md=["# Defense attack hand-residual shadow","",
"| model | shrink | train Brier | holdout Brier | holdout attack MAE |",
"|---|---:|---:|---:|---:|"]
for x in candidates:
    md.append(f"| {x['kind']} | {x['shrink']:.2f} | {x['train']['action_brier']:.5f} | {x['holdout']['action_brier']:.5f} | {x['holdout']['attack_mae']:.5f} |")
md+=["",f"- same-sign residual across 10/20/50bb among top-50 residual hands: {out['same_sign_fraction_top50']:.1%}",
"","No production behavior changed."]
(dst/"defend_attack_hand_residual_shadow_20260928.md").write_text("\n".join(md)+"\n")
print("CANDIDATES",json.dumps(candidates,sort_keys=True))
print("STABILITY",json.dumps(out["top_residual_stability"][:30],sort_keys=True))
