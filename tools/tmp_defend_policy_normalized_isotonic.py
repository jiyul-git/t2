#!/usr/bin/env python3
import json, pathlib, collections, bisect
import preflop

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=pathlib.Path("/tmp/8max_mtt_matthiola.jsonl")
PCT=json.loads((ROOT/"pf_rank.json").read_text())
TRAIN={10,20,50}
HOLD={15,30,100}
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

rows=[json.loads(x) for x in DATA.read_text().splitlines() if x.strip()]
groups=collections.defaultdict(list)
for r in rows:
    if r.get("scenario")=="vs-open" and r.get("node") in DIRECT:
        groups[(int(r["stack_bb"]),r["node"])].append(r)

items=[]
for (stack,node),rs in sorted(groups.items()):
    ops,hero=DIRECT[node]; open_bb=3.0 if node=="SB-vs-BB" else 2.5
    for r in rs:
        h=r["hand"];ta,tc,tf,tcont=targ(r); vals=[]
        for op in ops:
            vals.append(preflop.defend_action_likelihoods(
              PROF,hero,op,cards(h),stack,open_bb,0,raise_level=1,
              stack_bb=stack,exploit=None,bf=1.0,seats=8,ante=True,
              opener_allin=False,can_raise=True))
        tp=sum(v["tp"] for v in vals)/len(vals)
        tot=sum(v["tot"] for v in vals)/len(vals)
        ca=sum(v["attack"] for v in vals)/len(vals)
        cc=sum(v["call"] for v in vals)/len(vals)
        cf=sum(v["fold"] for v in vals)/len(vals)
        items.append({"stack":stack,"node":node,"hero":hero,"hand":h,"w":combos(h),
          "r":PCT[h],"tp":tp,"tot":tot,
          "za":PCT[h]/max(tp,1e-9),"zc":PCT[h]/max(tot,1e-9),
          "ta":ta,"tc":tc,"tf":tf,"tcont":tcont,
          "ca":ca,"cc":cc,"cf":cf})

def pava(points):
    # points: (x,y,w), fit non-increasing y vs x
    points=sorted(points)
    blocks=[]
    for x,y,w in points:
        b={"xmin":x,"xmax":x,"w":w,"wy":w*y,"mean":y}
        blocks.append(b)
        while len(blocks)>=2 and blocks[-2]["mean"] < blocks[-1]["mean"]-1e-15:
            q=blocks.pop(); p=blocks.pop()
            w2=p["w"]+q["w"]
            blocks.append({"xmin":p["xmin"],"xmax":q["xmax"],"w":w2,
                           "wy":p["wy"]+q["wy"],"mean":(p["wy"]+q["wy"])/w2})
    bounds=[]
    for a,b in zip(blocks,blocks[1:]):
        bounds.append((a["xmax"]+b["xmin"])/2.0)
    means=[b["mean"] for b in blocks]
    return {"blocks":blocks,"bounds":bounds,"means":means}

def pred(fit,x):
    return fit["means"][bisect.bisect_right(fit["bounds"],x)]

def fit_model(by_defender):
    train=[x for x in items if x["stack"] in TRAIN]
    models={}
    keys=sorted(set(x["hero"] for x in train)) if by_defender else ["GLOBAL"]
    for key in keys:
        sub=[x for x in train if (x["hero"]==key if by_defender else True)]
        models[key]={
          "attack":pava([(x["za"],x["ta"],x["w"]) for x in sub]),
          "continue":pava([(x["zc"],x["tcont"],x["w"]) for x in sub]),
        }
    return models

def predict(models,x,by_defender):
    key=x["hero"] if by_defender else "GLOBAL"
    a=pred(models[key]["attack"],x["za"])
    cont=pred(models[key]["continue"],x["zc"])
    a=min(a,cont);c=max(0.0,cont-a);f=max(0.0,1-cont)
    z=a+c+f
    return a/z,c/z,f/z

def score_current(stacks):
    sw=ss=amae=cmae=0.0
    for x in items:
        if x["stack"] not in stacks:continue
        w=x["w"];sw+=w
        ss+=w*((x["ca"]-x["ta"])**2+(x["cc"]-x["tc"])**2+(x["cf"]-x["tf"])**2)/3
        amae+=w*abs(x["ca"]-x["ta"])
        cmae+=w*abs((x["ca"]+x["cc"])-x["tcont"])
    return {"action_brier":ss/sw,"attack_mae":amae/sw,"continue_mae":cmae/sw}

def score_model(models,by_defender,stacks):
    sw=ss=amae=cmae=0.0
    by=collections.defaultdict(lambda:[0.0,0.0,0.0,0.0])
    for x in items:
        if x["stack"] not in stacks:continue
        a,c,f=predict(models,x,by_defender);w=x["w"];sw+=w
        e=((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3
        ss+=w*e; amae+=w*abs(a-x["ta"]);cmae+=w*abs((a+c)-x["tcont"])
        b=by[x["node"]];b[0]+=w*e;b[1]+=w*abs(a-x["ta"]);b[2]+=w*abs((a+c)-x["tcont"]);b[3]+=w
    return {"action_brier":ss/sw,"attack_mae":amae/sw,"continue_mae":cmae/sw,
      "by_node":{k:{"action_brier":v[0]/v[3],"attack_mae":v[1]/v[3],"continue_mae":v[2]/v[3]} for k,v in sorted(by.items())}}

def compact(fit):
    # Store just step thresholds and means; enough to reproduce.
    return [{"through":fit["bounds"][i] if i<len(fit["bounds"]) else None,"p":p}
            for i,p in enumerate(fit["means"])]

out={"scope":"shadow only: empirical monotone link of normalized hand percentile to calibrated tp/tot",
     "train_stacks":sorted(TRAIN),"holdout_stacks":sorted(HOLD),
     "current_train":score_current(TRAIN),"current_holdout":score_current(HOLD)}
for label,bydef in [("global",False),("by_defender",True)]:
    models=fit_model(bydef)
    out[label]={
      "train":score_model(models,bydef,TRAIN),
      "holdout":score_model(models,bydef,HOLD),
      "models":{k:{"attack":compact(v["attack"]),"continue":compact(v["continue"]),
                    "attack_blocks":len(v["attack"]["means"]),"continue_blocks":len(v["continue"]["means"])}
                for k,v in models.items()}
    }

dst=ROOT/"data"/"gto_public";dst.mkdir(parents=True,exist_ok=True)
(dst/"defend_policy_normalized_isotonic_20260928.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
md=["# Defense normalized-isotonic shadow","",
"| model | train Brier | holdout Brier | holdout attack MAE | holdout continue MAE |",
"|---|---:|---:|---:|---:|",
f"| current | {out['current_train']['action_brier']:.5f} | {out['current_holdout']['action_brier']:.5f} | {out['current_holdout']['attack_mae']:.5f} | {out['current_holdout']['continue_mae']:.5f} |",
f"| global normalized isotonic | {out['global']['train']['action_brier']:.5f} | {out['global']['holdout']['action_brier']:.5f} | {out['global']['holdout']['attack_mae']:.5f} | {out['global']['holdout']['continue_mae']:.5f} |",
f"| defender-specific normalized isotonic | {out['by_defender']['train']['action_brier']:.5f} | {out['by_defender']['holdout']['action_brier']:.5f} | {out['by_defender']['holdout']['attack_mae']:.5f} | {out['by_defender']['holdout']['continue_mae']:.5f} |",
"",
"Normalized axes: attack uses hand_pct/tp, continue uses hand_pct/tot. Train 10/20/50bb; holdout 15/30/100bb. No production changes."]
(dst/"defend_policy_normalized_isotonic_20260928.md").write_text("\n".join(md)+"\n")
print("SUMMARY",json.dumps({k:out[k] for k in ["current_train","current_holdout"]},sort_keys=True))
for k in ["global","by_defender"]:
    print(k.upper(),json.dumps({"train":out[k]["train"],"holdout":out[k]["holdout"],
      "blocks":{q:{"a":v["attack_blocks"],"c":v["continue_blocks"]} for q,v in out[k]["models"].items()}},sort_keys=True))
