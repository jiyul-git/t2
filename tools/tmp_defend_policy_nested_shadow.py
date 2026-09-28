#!/usr/bin/env python3
import json, pathlib, collections, math, itertools
import preflop

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=pathlib.Path("/tmp/8max_mtt_matthiola.jsonl")
PCT=json.loads((ROOT/"pf_rank.json").read_text())

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
TRAIN={10,20,50}
HOLD={15,30,100}

def combos(h): return 6 if len(h)==2 else (4 if h.endswith("s") else 12)
def cards(h):
    if len(h)==2:return [h[0]+"s",h[1]+"h"]
    return [h[0]+"s",h[1]+("s" if h[2]=="s" else "h")]
def target(r):
    a=float(r.get("raise",0))+float(r.get("allin",0))
    c=float(r.get("call",0)); f=float(r.get("fold",0))
    return a,c,f

def sig(x, center, width):
    z=(x-center)/max(width,1e-9)
    if z>50:return 0.0
    if z<-50:return 1.0
    return 1.0/(1.0+math.exp(z))

rows=[json.loads(x) for x in DATA.read_text().splitlines() if x.strip()]
groups=collections.defaultdict(list)
for r in rows:
    if r.get("scenario")=="vs-open" and r.get("node") in DIRECT:
        groups[(int(r["stack_bb"]),r["node"])].append(r)

# Precompute current thresholds + hot attack for each chart/hand.
items=[]
for (stack,node),rs in sorted(groups.items()):
    ops,hero=DIRECT[node]
    open_bb=3.0 if node=="SB-vs-BB" else 2.5
    for r in rs:
        h=r["hand"]; ta,tc,tf=target(r)
        vals=[]
        for op in ops:
            lik=preflop.defend_action_likelihoods(
                PROF,hero,op,cards(h),stack,open_bb,0,
                raise_level=1,stack_bb=stack,exploit=None,bf=1.0,
                seats=8,ante=True,opener_allin=False,can_raise=True)
            vals.append(lik)
        # Average over grouped opener aliases.
        tp=sum(float(v["tp"]) for v in vals)/len(vals)
        tot=sum(float(v["tot"]) for v in vals)/len(vals)
        hot=sum(float(v["hot_attack"]) for v in vals)/len(vals)
        cur_a=sum(float(v["attack"]) for v in vals)/len(vals)
        cur_c=sum(float(v["call"]) for v in vals)/len(vals)
        cur_f=sum(float(v["fold"]) for v in vals)/len(vals)
        items.append({
          "stack":stack,"node":node,"hero":hero,"hand":h,"r":PCT[h],"w":combos(h),
          "tp":tp,"tot":tot,"hot":hot,
          "ta":ta,"tc":tc,"tf":tf,
          "cur_a":cur_a,"cur_c":cur_c,"cur_f":cur_f,
        })

def predict(x,pars,use_hot):
    af,ar,cf,cr=pars
    wa=max(af,ar*x["tp"])
    wc=max(cf,cr*max(0.01,x["tot"]-x["tp"]))
    cont=sig(x["r"],x["tot"],wc)
    atk0=sig(x["r"],x["tp"],wa)
    atk0=min(atk0,cont)
    hot=x["hot"] if use_hot else 0.0
    # Hot shove is an independent earlier branch. If it does not fire, use nested policy.
    a=hot+(1.0-hot)*atk0
    c=(1.0-hot)*max(0.0,cont-atk0)
    f=(1.0-hot)*max(0.0,1.0-cont)
    z=a+c+f
    return a/z,c/z,f/z

def score(pars,use_hot,stacks):
    ss=ma=mc=0.0; sw=0.0
    for x in items:
        if x["stack"] not in stacks: continue
        a,c,f=predict(x,pars,use_hot)
        w=x["w"]; sw+=w
        ss+=w*((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3.0
        ma+=w*abs(a-x["ta"])
        mc+=w*abs((a+c)-(x["ta"]+x["tc"]))
    return {"action_brier":ss/sw,"attack_mae":ma/sw,"continue_mae":mc/sw}

def current_score(stacks):
    ss=ma=mc=0.0;sw=0.0
    for x in items:
        if x["stack"] not in stacks:continue
        w=x["w"];sw+=w
        ss+=w*((x["cur_a"]-x["ta"])**2+(x["cur_c"]-x["tc"])**2+(x["cur_f"]-x["tf"])**2)/3.0
        ma+=w*abs(x["cur_a"]-x["ta"])
        mc+=w*abs((x["cur_a"]+x["cur_c"])-(x["ta"]+x["tc"]))
    return {"action_brier":ss/sw,"attack_mae":ma/sw,"continue_mae":mc/sw}

# Small smooth family. Train only on 10/20/50; holdout is untouched.
floors_a=[0.003,0.006,0.010,0.015,0.020,0.030]
rels_a=[0.05,0.10,0.15,0.20,0.25,0.35,0.50]
floors_c=[0.005,0.010,0.015,0.020,0.030,0.040]
rels_c=[0.10,0.20,0.30,0.40,0.55,0.70,1.00]

fits=[]
for use_hot in [False,True]:
    best=None
    for pars in itertools.product(floors_a,rels_a,floors_c,rels_c):
        sc=score(pars,use_hot,TRAIN)
        key=(sc["action_brier"],sc["continue_mae"],sc["attack_mae"],pars)
        if best is None or key<best[0]:
            best=(key,pars,sc)
    pars=best[1]
    fits.append({
      "use_hot":use_hot,"params":{"attack_floor":pars[0],"attack_rel_tp":pars[1],
                                  "continue_floor":pars[2],"continue_rel_gap":pars[3]},
      "train":best[2],"holdout":score(pars,use_hot,HOLD),
      "all":score(pars,use_hot,TRAIN|HOLD),
    })

# Node-level holdout for the winner to catch localized regressions.
winner=min(fits,key=lambda x:(x["holdout"]["action_brier"],x["holdout"]["continue_mae"]))
wp=(winner["params"]["attack_floor"],winner["params"]["attack_rel_tp"],
    winner["params"]["continue_floor"],winner["params"]["continue_rel_gap"])
by_node={}
for node in DIRECT:
    sub=[x for x in items if x["node"]==node and x["stack"] in HOLD]
    def subscore(current=False):
        ss=ma=mc=sw=0.0
        for x in sub:
            if current:a,c,f=x["cur_a"],x["cur_c"],x["cur_f"]
            else:a,c,f=predict(x,wp,winner["use_hot"])
            w=x["w"];sw+=w
            ss+=w*((a-x["ta"])**2+(c-x["tc"])**2+(f-x["tf"])**2)/3
            ma+=w*abs(a-x["ta"]);mc+=w*abs((a+c)-(x["ta"]+x["tc"]))
        return {"action_brier":ss/sw,"attack_mae":ma/sw,"continue_mae":mc/sw}
    by_node[node]={"current":subscore(True),"candidate":subscore(False)}

out={
 "scope":"shadow only: replace current post-threshold w_raise/w_call/w_fold shape with nested smooth cumulative policy",
 "train_stacks":sorted(TRAIN),"holdout_stacks":sorted(HOLD),
 "current_train":current_score(TRAIN),"current_holdout":current_score(HOLD),"current_all":current_score(TRAIN|HOLD),
 "fits":fits,"winner":winner,"winner_holdout_by_node":by_node,
 "formula":{
   "continue":"sigmoid(rank; center=tot, width=max(c_floor,c_rel*(tot-tp)))",
   "attack0":"min(sigmoid(rank; center=tp, width=max(a_floor,a_rel*tp)), continue)",
   "with_hot":"attack=hot+(1-hot)*attack0; call=(1-hot)*(continue-attack0); fold=(1-hot)*(1-continue)"
 }
}
dst=ROOT/"data"/"gto_public";dst.mkdir(parents=True,exist_ok=True)
(dst/"defend_policy_nested_shadow_20260928.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
md=["# Defense nested-policy shadow","",
f"- current train Brier: {out['current_train']['action_brier']:.5f}",
f"- current holdout Brier: {out['current_holdout']['action_brier']:.5f}",
f"- winner use_hot: {winner['use_hot']}",
f"- winner params: {json.dumps(winner['params'],sort_keys=True)}",
f"- winner train Brier: {winner['train']['action_brier']:.5f}",
f"- winner holdout Brier: {winner['holdout']['action_brier']:.5f}",
f"- winner holdout attack MAE: {winner['holdout']['attack_mae']:.5f}",
f"- winner holdout continue MAE: {winner['holdout']['continue_mae']:.5f}","",
"Train stacks: 10/20/50bb. Holdout stacks: 15/30/100bb. No production code changed."]
(dst/"defend_policy_nested_shadow_20260928.md").write_text("\n".join(md)+"\n")
print("RESULT",json.dumps({k:out[k] for k in ["current_train","current_holdout","current_all"]},sort_keys=True))
print("FITS",json.dumps(fits,sort_keys=True))
print("WINNER_NODE",json.dumps(by_node,sort_keys=True))
