#!/usr/bin/env python3
import json, pathlib, collections, bisect, math
import preflop
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=pathlib.Path("/tmp/8max_mtt_matthiola.jsonl")
PCT=json.loads((ROOT/"pf_rank.json").read_text())
TRAIN={10,20,50};HOLD={15,30,100}
EDGES=[0.0,0.45,0.70,0.90,1.05,1.25,1.55,2.20,float("inf")]
DIRECT={
 "EP-vs-MP":(["UTG","UTG+1","LJ"],"CO"),"EP-vs-BTN":(["UTG","UTG+1","LJ"],"BTN"),
 "EP-vs-SB":(["UTG","UTG+1","LJ"],"SB"),"EP-vs-BB":(["UTG","UTG+1","LJ"],"BB"),
 "MP-vs-BTN":(["HJ","CO"],"BTN"),"MP-vs-SB":(["HJ","CO"],"SB"),"MP-vs-BB":(["HJ","CO"],"BB"),
 "BTN-vs-SB":(["BTN"],"SB"),"BTN-vs-BB":(["BTN"],"BB"),"SB-vs-BB":(["SB"],"BB")}
PROF={"concepts":{"pf_defend":10.0},"temper":{"looseness":5.0,"aggression":5.0,"slowplay_taste":5.0},"type":"GTO_ISH"}
RV={r:i+2 for i,r in enumerate("23456789TJQKA")}

def combos(h):return 6 if len(h)==2 else (4 if h.endswith("s") else 12)
def cards(h):
    if len(h)==2:return [h[0]+"s",h[1]+"h"]
    return [h[0]+"s",h[1]+("s" if h[2]=="s" else "h")]
def targ(r):
    a=float(r.get("raise",0))+float(r.get("allin",0));c=float(r.get("call",0));f=float(r.get("fold",0))
    return a,c,f,a+c
rows=[json.loads(x) for x in DATA.read_text().splitlines() if x.strip()]
groups=collections.defaultdict(list)
for r in rows:
    if r.get("scenario")=="vs-open" and r.get("node") in DIRECT:groups[(int(r["stack_bb"]),r["node"])].append(r)
items=[]
for (stack,node),rs in sorted(groups.items()):
    ops,hero=DIRECT[node];ob=3.0 if node=="SB-vs-BB" else 2.5
    for r in rs:
        h=r["hand"];ta,tc,tf,tcont=targ(r);vs=[]
        for op in ops:
            vs.append(preflop.defend_action_likelihoods(PROF,hero,op,cards(h),stack,ob,0,raise_level=1,stack_bb=stack,exploit=None,bf=1.0,seats=8,ante=True,opener_allin=False,can_raise=True))
        tp=sum(v["tp"] for v in vs)/len(vs);tot=sum(v["tot"] for v in vs)/len(vs)
        items.append({"stack":stack,"hero":hero,"hand":h,"w":combos(h),"za":PCT[h]/max(tp,1e-9),"zc":PCT[h]/max(tot,1e-9),"ta":ta,"tc":tc,"tf":tf,"tcont":tcont})

def pava(sy,sw):
    vals=[sy[i]/sw[i] if sw[i] else 0 for i in range(len(sw))];blocks=[]
    for i,(y,w) in enumerate(zip(vals,sw)):
        if w==0:w=1e-6
        blocks.append([i,i,w,w*y,w*y/w])
        while len(blocks)>=2 and blocks[-2][4]<blocks[-1][4]-1e-15:
            b=blocks.pop();a=blocks.pop();w=a[2]+b[2];wy=a[3]+b[3];blocks.append([a[0],b[1],w,wy,wy/w])
    out=[0]*len(sw)
    for b in blocks:
        for i in range(b[0],b[1]+1):out[i]=b[4]
    return out
def fit_base(stacks):
    m={};nb=len(EDGES)-1
    for hero in sorted(set(x["hero"] for x in items)):
        sub=[x for x in items if x["stack"] in stacks and x["hero"]==hero];q={}
        for key,ykey in [("a","ta"),("c","tcont")]:
            sy=[0.0]*nb;sw=[0.0]*nb;zk="za" if key=="a" else "zc"
            for x in sub:
                i=max(0,min(nb-1,bisect.bisect_right(EDGES,x[zk])-1));sy[i]+=x["w"]*x[ykey];sw[i]+=x["w"]
            q[key]=pava(sy,sw)
        m[hero]=q
    return m
def bp(m,x):
    nb=len(EDGES)-1
    ia=max(0,min(nb-1,bisect.bisect_right(EDGES,x["za"])-1));ic=max(0,min(nb-1,bisect.bisect_right(EDGES,x["zc"])-1))
    cont=m[x["hero"]]["c"][ic];a=min(m[x["hero"]]["a"][ia],cont);return a,cont

def allfeat(h):
    pair=len(h)==2;suited=len(h)==3 and h[2]=="s";off=len(h)==3 and h[2]=="o";a=RV[h[0]];b=RV[h[1]];hi=max(a,b);lo=min(a,b);gap=abs(a-b)
    ace=hi==14;king=hi==13;broad=hi>=10 and lo>=10
    return {
      "bias":1.0,"ace":float(ace),"ace_offsuit":float(ace and off),"ace_suited":float(ace and suited),
      "wheel_ace_suited":float(ace and suited and lo<=5),"broadway":float(broad),
      "broadway_suited":float(broad and suited),"king_suited":float(king and suited),
      "pair":float(pair),"small_pair":float(pair and hi<=6),"mid_pair":float(pair and 7<=hi<=11),
      "suited_connector":float(suited and gap==1),"low_suited_connector":float(suited and gap==1 and hi<=9),
      "gap":min(gap,12)/12,"lo_rank":(lo-2)/12,
    }
SETS={
 "core6":["bias","ace_offsuit","wheel_ace_suited","broadway_suited","small_pair","suited_connector"],
 "core9":["bias","ace","ace_offsuit","wheel_ace_suited","broadway","broadway_suited","king_suited","small_pair","suited_connector"],
 "core12":["bias","ace","ace_offsuit","ace_suited","wheel_ace_suited","broadway","broadway_suited","king_suited","pair","small_pair","suited_connector","gap"],
 "core15":["bias","ace","ace_offsuit","ace_suited","wheel_ace_suited","broadway","broadway_suited","king_suited","pair","small_pair","mid_pair","suited_connector","low_suited_connector","gap","lo_rank"],
}
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
            for j in range(col,n+1):M[i][j]-=q*M[col][j]
    return [M[i][n] for i in range(n)]
def fit(base,stacks,names,lam):
    p=len(names);A=[[0.0]*p for _ in range(p)];b=[0.0]*p
    for x in items:
        if x["stack"] not in stacks:continue
        ba,_=bp(base,x);fd=allfeat(x["hand"]);v=[fd[n] for n in names];y=x["ta"]-ba;w=x["w"]
        for i in range(p):
            b[i]+=w*v[i]*y
            for j in range(p):A[i][j]+=w*v[i]*v[j]
    for i,n in enumerate(names):A[i][i]+=0 if n=="bias" else lam
    return solve(A,b)
def score(base,names,beta,stacks):
    sw=ss=am=cm=0
    for x in items:
        if x["stack"] not in stacks:continue
        a,cont=bp(base,x)
        if beta is not None:
            fd=allfeat(x["hand"]);a=max(0,min(cont,a+sum(q*fd[n] for q,n in zip(beta,names))))
        c=cont-a;f=1-cont;w=x["w"];sw+=w
        ss+=w*((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3;am+=w*abs(a-x["ta"]);cm+=w*abs(cont-x["tcont"])
    return {"action_brier":ss/sw,"attack_mae":am/sw,"continue_mae":cm/sw}
base=fit_base(TRAIN)
res=[]
for label,names in SETS.items():
    cv=[]
    for lam in [100,300,1000,3000,10000]:
        qq=[]
        for hs in TRAIN:
            tr=TRAIN-{hs};bb=fit_base(tr);be=fit(bb,tr,names,lam);qq.append(score(bb,names,be,{hs}))
        cv.append((sum(x["action_brier"] for x in qq)/len(qq),sum(x["attack_mae"] for x in qq)/len(qq),lam))
    cv.sort();lam=cv[0][2];beta=fit(base,TRAIN,names,lam)
    res.append({"set":label,"features":names,"lambda":lam,"train":score(base,names,beta,TRAIN),"holdout":score(base,names,beta,HOLD),"coefficients":dict(zip(names,beta))})
out={"scope":"shadow: reduced semantic attack feature sets on 8-bin defender policy","edges":EDGES[:-1]+[None],"base_holdout":score(base,[],None,HOLD),"results":res}
dst=ROOT/"data"/"gto_public";dst.mkdir(parents=True,exist_ok=True)
(dst/"defend_attack_reduced_features_20260928.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
(dst/"defend_attack_reduced_features_20260928.md").write_text("\n".join(["# Reduced defense attack features",""]+[f"- {x['set']}: holdout Brier {x['holdout']['action_brier']:.5f}, attack MAE {x['holdout']['attack_mae']:.5f}, lambda {x['lambda']}" for x in res])+ "\n")
print("RESULT",json.dumps(out,sort_keys=True))
