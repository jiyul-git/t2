#!/usr/bin/env python3
import json, pathlib, collections, math, bisect
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
SCHEMES={
 "6bin":[0.0,0.60,0.85,1.05,1.35,2.0,float("inf")],
 "8bin":[0.0,0.45,0.70,0.90,1.05,1.25,1.55,2.20,float("inf")],
 "10bin":[0.0,0.35,0.55,0.75,0.90,1.00,1.15,1.35,1.65,2.20,float("inf")],
}

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
    ops,hero=DIRECT[node]; ob=3.0 if node=="SB-vs-BB" else 2.5
    for r in rs:
        h=r["hand"];ta,tc,tf,tcont=targ(r); vals=[]
        for op in ops:
            vals.append(preflop.defend_action_likelihoods(
                PROF,hero,op,cards(h),stack,ob,0,raise_level=1,
                stack_bb=stack,exploit=None,bf=1.0,seats=8,ante=True,
                opener_allin=False,can_raise=True))
        tp=sum(float(v["tp"]) for v in vals)/len(vals)
        tot=sum(float(v["tot"]) for v in vals)/len(vals)
        ca=sum(float(v["attack"]) for v in vals)/len(vals)
        cc=sum(float(v["call"]) for v in vals)/len(vals)
        cf=sum(float(v["fold"]) for v in vals)/len(vals)
        items.append({"stack":stack,"node":node,"hero":hero,"hand":h,"w":combos(h),
          "r":PCT[h],"za":PCT[h]/max(tp,1e-9),"zc":PCT[h]/max(tot,1e-9),
          "ta":ta,"tc":tc,"tf":tf,"tcont":tcont,"ca":ca,"cc":cc,"cf":cf})

def pava_bins(sumy,sumw):
    # Fill empty bins by nearest populated bin before monotone pooling.
    n=len(sumw); vals=[None]*n
    for i in range(n):
        if sumw[i]>0: vals[i]=sumy[i]/sumw[i]
    for i in range(n):
        if vals[i] is None:
            nearest=min((j for j in range(n) if vals[j] is not None),key=lambda j:abs(j-i))
            vals[i]=vals[nearest]
            sumw[i]=1e-6;sumy[i]=vals[i]*1e-6
    blocks=[]
    for i in range(n):
        blocks.append({"lo":i,"hi":i,"w":sumw[i],"wy":sumy[i],"mean":sumy[i]/sumw[i]})
        while len(blocks)>=2 and blocks[-2]["mean"] < blocks[-1]["mean"]-1e-15:
            b=blocks.pop();a=blocks.pop();w=a["w"]+b["w"]
            blocks.append({"lo":a["lo"],"hi":b["hi"],"w":w,"wy":a["wy"]+b["wy"],"mean":(a["wy"]+b["wy"])/w})
    out=[0.0]*n
    for b in blocks:
        for i in range(b["lo"],b["hi"]+1):out[i]=b["mean"]
    return out

def fit_bins(edges,train_stacks):
    models={}
    nb=len(edges)-1
    for hero in sorted(set(x["hero"] for x in items)):
        sub=[x for x in items if x["stack"] in train_stacks and x["hero"]==hero]
        model={}
        for axis,ykey in [("attack","ta"),("continue","tcont")]:
            sy=[0.0]*nb;sw=[0.0]*nb
            zkey="za" if axis=="attack" else "zc"
            for x in sub:
                i=max(0,min(nb-1,bisect.bisect_right(edges,x[zkey])-1))
                sy[i]+=x["w"]*x[ykey];sw[i]+=x["w"]
            model[axis]=pava_bins(sy,sw)
        models[hero]=model
    return models

def bpred(models,edges,x):
    nb=len(edges)-1
    ia=max(0,min(nb-1,bisect.bisect_right(edges,x["za"])-1))
    ic=max(0,min(nb-1,bisect.bisect_right(edges,x["zc"])-1))
    cont=models[x["hero"]]["continue"][ic]
    a=min(models[x["hero"]]["attack"][ia],cont)
    return a,cont

def feats(h):
    pair=len(h)==2; suited=(len(h)==3 and h[2]=="s"); off=(len(h)==3 and h[2]=="o")
    r1=RV[h[0]];r2=RV[h[1]]; hi=max(r1,r2);lo=min(r1,r2);gap=abs(r1-r2)
    ace=hi==14;king=hi==13;queen=hi==12;broad=hi>=10 and lo>=10
    return [
      1.0,float(pair),float(pair)*(hi-2)/12,float(suited),float(off),float(ace),
      float(ace and suited),float(ace and off),float(suited and ace and lo<=5),
      float(king),float(king and suited),float(queen),float(broad),float(broad and suited),
      float(suited and gap==1),float(suited and gap==2),float(suited and gap==1 and hi<=9),
      float(pair and hi<=6),float(pair and 7<=hi<=11),float(pair and hi>=12),
      (hi-2)/12,(lo-2)/12,min(gap,12)/12
    ]
FN=["bias","pair","pair_rank","suited","offsuit","ace","ace_suited","ace_offsuit",
    "wheel_ace_suited","king","king_suited","queen_high","broadway","broadway_suited",
    "suited_connector","suited_onegap","low_suited_connector","small_pair","mid_pair",
    "premium_pair","hi_rank","lo_rank","gap"]

def solve(A,b):
    n=len(b);M=[A[i][:]+[b[i]] for i in range(n)]
    for col in range(n):
        piv=max(range(col,n),key=lambda i:abs(M[i][col]))
        if abs(M[piv][col])<1e-12:continue
        M[col],M[piv]=M[piv],M[col];q=M[col][col]
        for j in range(col,n+1):M[col][j]/=q
        for i in range(n):
            if i==col:continue
            q=M[i][col]
            if abs(q)<1e-15:continue
            for j in range(col,n+1):M[i][j]-=q*M[col][j]
    return [M[i][n] for i in range(n)]

def fit_ridge(models,edges,train_stacks,lam):
    p=len(FN);A=[[0.0]*p for _ in range(p)];b=[0.0]*p
    for x in items:
        if x["stack"] not in train_stacks:continue
        ba,_=bpred(models,edges,x);v=feats(x["hand"]);y=x["ta"]-ba;w=x["w"]
        for i in range(p):
            b[i]+=w*v[i]*y
            for j in range(p):A[i][j]+=w*v[i]*v[j]
    for i,n in enumerate(FN):A[i][i]+=0.0 if n=="bias" else lam
    return solve(A,b)

def score(models,edges,beta,stacks):
    sw=ss=amae=cmae=0.0
    by=collections.defaultdict(lambda:[0.0,0.0,0.0,0.0])
    for x in items:
        if x["stack"] not in stacks:continue
        a,cont=bpred(models,edges,x)
        if beta is not None:
            a=max(0.0,min(cont,a+sum(q*v for q,v in zip(beta,feats(x["hand"])))))
        c=max(0.0,cont-a);f=max(0.0,1.0-cont);w=x["w"];sw+=w
        e=((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3
        ss+=w*e;amae+=w*abs(a-x["ta"]);cmae+=w*abs(cont-x["tcont"])
        q=by[x["node"]];q[0]+=w*e;q[1]+=w*abs(a-x["ta"]);q[2]+=w*abs(cont-x["tcont"]);q[3]+=w
    return {"action_brier":ss/sw,"attack_mae":amae/sw,"continue_mae":cmae/sw,
      "by_node":{k:{"action_brier":v[0]/v[3],"attack_mae":v[1]/v[3],"continue_mae":v[2]/v[3]} for k,v in sorted(by.items())}}

def current(stacks):
    sw=ss=amae=cmae=0.0
    for x in items:
        if x["stack"] not in stacks:continue
        w=x["w"];sw+=w
        ss+=w*((x["ca"]-x["ta"])**2+(x["cc"]-x["tc"])**2+(x["cf"]-x["tf"])**2)/3
        amae+=w*abs(x["ca"]-x["ta"]);cmae+=w*abs((x["ca"]+x["cc"])-x["tcont"])
    return {"action_brier":ss/sw,"attack_mae":amae/sw,"continue_mae":cmae/sw}

results=[]
for name,edges in SCHEMES.items():
    models=fit_bins(edges,TRAIN)
    base_train=score(models,edges,None,TRAIN);base_hold=score(models,edges,None,HOLD)
    cv=[]
    for lam in [100.0,300.0,1000.0,3000.0,10000.0]:
        folds=[]
        for hs in sorted(TRAIN):
            tr=TRAIN-{hs};fm=fit_bins(edges,tr);beta=fit_ridge(fm,edges,tr,lam)
            folds.append(score(fm,edges,beta,{hs}))
        cv.append({"lambda":lam,
                   "brier":sum(x["action_brier"] for x in folds)/len(folds),
                   "attack_mae":sum(x["attack_mae"] for x in folds)/len(folds)})
    best=min(cv,key=lambda x:(x["brier"],x["attack_mae"]))
    beta=fit_ridge(models,edges,TRAIN,best["lambda"])
    sem_train=score(models,edges,beta,TRAIN);sem_hold=score(models,edges,beta,HOLD)
    results.append({
      "scheme":name,"edges":[None if math.isinf(x) else x for x in edges],
      "curves":models,"base_train":base_train,"base_holdout":base_hold,
      "cv":cv,"lambda":best["lambda"],"semantic_train":sem_train,"semantic_holdout":sem_hold,
      "semantic_coefficients":[{"feature":n,"coef":v} for n,v in zip(FN,beta)]
    })

winner=min(results,key=lambda x:(x["semantic_holdout"]["action_brier"],x["semantic_holdout"]["attack_mae"]))
out={"scope":"shadow only: compact defender-specific normalized bins + semantic attack residual",
     "train_stacks":sorted(TRAIN),"holdout_stacks":sorted(HOLD),
     "current_train":current(TRAIN),"current_holdout":current(HOLD),
     "results":results,"winner":winner}
dst=ROOT/"data"/"gto_public";dst.mkdir(parents=True,exist_ok=True)
(dst/"defend_policy_compact_semantic_20260928.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
md=["# Defense compact semantic policy shadow","",
"| model | holdout Brier | holdout attack MAE | holdout continue MAE |",
"|---|---:|---:|---:|",
f"| current | {out['current_holdout']['action_brier']:.5f} | {out['current_holdout']['attack_mae']:.5f} | {out['current_holdout']['continue_mae']:.5f} |"]
for x in results:
    md.append(f"| {x['scheme']} base | {x['base_holdout']['action_brier']:.5f} | {x['base_holdout']['attack_mae']:.5f} | {x['base_holdout']['continue_mae']:.5f} |")
    md.append(f"| {x['scheme']} + semantic | {x['semantic_holdout']['action_brier']:.5f} | {x['semantic_holdout']['attack_mae']:.5f} | {x['semantic_holdout']['continue_mae']:.5f} |")
md+=["",f"Winner: **{winner['scheme']} + semantic**, lambda={winner['lambda']}.",
"No production changes."]
(dst/"defend_policy_compact_semantic_20260928.md").write_text("\n".join(md)+"\n")
print("SUMMARY",json.dumps({"current":out["current_holdout"],"results":[{"scheme":x["scheme"],"base":x["base_holdout"],"semantic":x["semantic_holdout"],"lambda":x["lambda"]} for x in results]},sort_keys=True))
print("WINNER",json.dumps({"scheme":winner["scheme"],"edges":winner["edges"],"curves":winner["curves"],"lambda":winner["lambda"],"coefs":winner["semantic_coefficients"]},sort_keys=True))
