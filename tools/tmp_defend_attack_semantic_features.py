#!/usr/bin/env python3
import json, pathlib, collections, bisect, math
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
RV={r:i+2 for i,r in enumerate("23456789TJQKA")}
DEFENDERS=["BB","SB","BTN","CO"]

def combos(h): return 6 if len(h)==2 else (4 if h.endswith("s") else 12)
def cards(h):
    if len(h)==2:return [h[0]+"s",h[1]+"h"]
    return [h[0]+"s",h[1]+("s" if h[2]=="s" else "h")]
def targ(r):
    a=float(r.get("raise",0))+float(r.get("allin",0));c=float(r.get("call",0));f=float(r.get("fold",0))
    return a,c,f,a+c

def pava(points):
    points=sorted(points);blocks=[]
    for x,y,w in points:
        blocks.append({"xmin":x,"xmax":x,"w":w,"wy":w*y,"mean":y})
        while len(blocks)>=2 and blocks[-2]["mean"] < blocks[-1]["mean"]-1e-15:
            b=blocks.pop();a=blocks.pop();w2=a["w"]+b["w"]
            blocks.append({"xmin":a["xmin"],"xmax":b["xmax"],"w":w2,"wy":a["wy"]+b["wy"],"mean":(a["wy"]+b["wy"])/w2})
    return {"bounds":[(a["xmax"]+b["xmin"])/2 for a,b in zip(blocks,blocks[1:])],
            "means":[b["mean"] for b in blocks]}
def ipred(m,x): return m["means"][bisect.bisect_right(m["bounds"],x)]

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
        items.append({"stack":stack,"node":node,"hero":hero,"hand":h,"w":combos(h),"r":PCT[h],
          "za":PCT[h]/max(tp,1e-9),"zc":PCT[h]/max(tot,1e-9),
          "ta":ta,"tc":tc,"tf":tf,"tcont":tcont})

# Base normalized isotonic is defender-specific and re-fit inside each training split.
def fit_base(train_stacks):
    models={}
    for hero in DEFENDERS:
        sub=[x for x in items if x["stack"] in train_stacks and x["hero"]==hero]
        models[hero]={"a":pava([(x["za"],x["ta"],x["w"]) for x in sub]),
                      "c":pava([(x["zc"],x["tcont"],x["w"]) for x in sub])}
    return models
def base_pred(models,x):
    cont=ipred(models[x["hero"]]["c"],x["zc"])
    a=min(ipred(models[x["hero"]]["a"],x["za"]),cont)
    return a,cont

def hand_features(h,hero,extended):
    pair=len(h)==2
    suited=(len(h)==3 and h[2]=="s")
    off=(len(h)==3 and h[2]=="o")
    r1=RV[h[0]];r2=RV[h[1]]
    hi=max(r1,r2);lo=min(r1,r2);gap=abs(r1-r2)
    ace=(hi==14); king=(hi==13); queen=(hi==12)
    broad=(hi>=10 and lo>=10)
    conn=(not pair and gap==1); onegap=(not pair and gap==2)
    wheel_as=suited and hi==14 and lo<=5
    names=[
      "bias","pair","pair_rank","suited","offsuit","ace","ace_suited","ace_offsuit",
      "wheel_ace_suited","king","king_suited","queen_high","broadway","broadway_suited",
      "suited_connector","suited_onegap","low_suited_connector","small_pair","mid_pair",
      "premium_pair","hi_rank","lo_rank","gap"
    ]
    vals=[
      1.0,float(pair),float(pair)*(hi-2)/12,float(suited),float(off),float(ace),
      float(ace and suited),float(ace and off),float(wheel_as),float(king),
      float(king and suited),float(queen),float(broad),float(broad and suited),
      float(suited and conn),float(suited and onegap),float(suited and conn and hi<=9),
      float(pair and hi<=6),float(pair and 7<=hi<=11),float(pair and hi>=12),
      (hi-2)/12,(lo-2)/12,min(gap,12)/12
    ]
    if extended:
        # defender intercepts and interactions with the most interpretable polar features.
        core={"ace_offsuit":float(ace and off),"wheel_ace_suited":float(wheel_as),
              "pair":float(pair),"broadway_suited":float(broad and suited),
              "suited_connector":float(suited and conn)}
        for d in DEFENDERS:
            names.append(f"def_{d}");vals.append(float(hero==d))
        for d in DEFENDERS:
            for k,v in core.items():
                names.append(f"{d}*{k}");vals.append(float(hero==d)*v)
    return names,vals

def solve(A,b):
    n=len(b);M=[list(A[i])+[b[i]] for i in range(n)]
    for col in range(n):
        piv=max(range(col,n),key=lambda i:abs(M[i][col]))
        if abs(M[piv][col])<1e-12:continue
        M[col],M[piv]=M[piv],M[col]
        q=M[col][col]
        for j in range(col,n+1):M[col][j]/=q
        for i in range(n):
            if i==col:continue
            q=M[i][col]
            if abs(q)<1e-15:continue
            for j in range(col,n+1):M[i][j]-=q*M[col][j]
    return [M[i][n] for i in range(n)]

def fit_ridge(train_stacks,extended,lam):
    bm=fit_base(train_stacks)
    # residual target is attack - base attack
    name0,x0=hand_features("AA","BB",extended);p=len(x0)
    A=[[0.0]*p for _ in range(p)];b=[0.0]*p
    for x in items:
        if x["stack"] not in train_stacks:continue
        ba,_=base_pred(bm,x);names,v=hand_features(x["hand"],x["hero"],extended)
        y=x["ta"]-ba;w=x["w"]
        for i in range(p):
            b[i]+=w*v[i]*y
            for j in range(p):A[i][j]+=w*v[i]*v[j]
    # Don't penalize bias; lightly exempt defender intercepts.
    for i,n in enumerate(name0):
        penalty=0.0 if n=="bias" or n.startswith("def_") else lam
        A[i][i]+=penalty
    beta=solve(A,b)
    return bm,name0,beta

def predict(model,x):
    bm,names,beta=model;ba,cont=base_pred(bm,x)
    _,v=hand_features(x["hand"],x["hero"],len(names)>23)
    d=sum(a*b for a,b in zip(beta,v))
    a=max(0.0,min(cont,ba+d))
    return a,cont

def score(model,stacks):
    sw=ss=amae=cmae=0.0
    for x in items:
        if x["stack"] not in stacks:continue
        a,cont=predict(model,x);c=max(0,cont-a);f=max(0,1-cont);w=x["w"];sw+=w
        ss+=w*((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3
        amae+=w*abs(a-x["ta"]);cmae+=w*abs(cont-x["tcont"])
    return {"action_brier":ss/sw,"attack_mae":amae/sw,"continue_mae":cmae/sw}

lams=[0.01,0.1,1.0,10.0,100.0,1000.0]
results=[]
for extended in [False,True]:
    cv=[]
    for lam in lams:
        scores=[]
        for hs in sorted(TRAIN):
            tr=TRAIN-{hs};m=fit_ridge(tr,extended,lam);scores.append(score(m,{hs}))
        cvb=sum(s["action_brier"] for s in scores)/len(scores)
        cva=sum(s["attack_mae"] for s in scores)/len(scores)
        cv.append((cvb,cva,lam))
    cv.sort();lam=cv[0][2]
    model=fit_ridge(TRAIN,extended,lam)
    train_sc=score(model,TRAIN);hold_sc=score(model,HOLD)
    names=model[1];beta=model[2]
    coefs=sorted(({"feature":n,"coef":v} for n,v in zip(names,beta)),key=lambda x:abs(x["coef"]),reverse=True)
    results.append({"variant":"extended" if extended else "semantic","lambda":lam,
                    "cv_candidates":[{"lambda":x[2],"brier":x[0],"attack_mae":x[1]} for x in cv],
                    "train":train_sc,"holdout":hold_sc,"coefficients":coefs})

# baseline defender-isotonic
base=fit_base(TRAIN)
baseline=(base,None,None)
def base_score(stacks):
    sw=ss=amae=cmae=0
    for x in items:
        if x["stack"] not in stacks:continue
        a,cont=base_pred(base,x);c=cont-a;f=1-cont;w=x["w"];sw+=w
        ss+=w*((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3
        amae+=w*abs(a-x["ta"]);cmae+=w*abs(cont-x["tcont"])
    return {"action_brier":ss/sw,"attack_mae":amae/sw,"continue_mae":cmae/sw}

out={"scope":"shadow only: compress cross-stack hand-class attack residual into semantic starting-hand features using weighted ridge",
     "train_stacks":sorted(TRAIN),"holdout_stacks":sorted(HOLD),
     "baseline":{"train":base_score(TRAIN),"holdout":base_score(HOLD)},"results":results}
dst=ROOT/"data"/"gto_public";dst.mkdir(parents=True,exist_ok=True)
(dst/"defend_attack_semantic_features_20260928.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
md=["# Defense attack semantic-feature shadow","",
"| model | lambda | train Brier | holdout Brier | holdout attack MAE |",
"|---|---:|---:|---:|---:|",
f"| defender-isotonic base | - | {out['baseline']['train']['action_brier']:.5f} | {out['baseline']['holdout']['action_brier']:.5f} | {out['baseline']['holdout']['attack_mae']:.5f} |"]
for x in results:
    md.append(f"| {x['variant']} | {x['lambda']} | {x['train']['action_brier']:.5f} | {x['holdout']['action_brier']:.5f} | {x['holdout']['attack_mae']:.5f} |")
md+=["","Top coefficients are stored in the JSON. Features are semantic hand properties, not 169 hand IDs. No production changes."]
(dst/"defend_attack_semantic_features_20260928.md").write_text("\n".join(md)+"\n")
print("SUMMARY",json.dumps({"baseline":out["baseline"],"results":[{k:x[k] for k in ["variant","lambda","train","holdout"]} for x in results]},sort_keys=True))
for x in results:print(x["variant"].upper()+"_COEFS",json.dumps(x["coefficients"][:25],sort_keys=True))
