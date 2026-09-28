#!/usr/bin/env python3
import json, pathlib, collections, math
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

def combos(h): return 6 if len(h)==2 else (4 if h.endswith("s") else 12)
def cards(h):
    if len(h)==2:return [h[0]+"s",h[1]+"h"]
    return [h[0]+"s",h[1]+("s" if h[2]=="s" else "h")]
def target(r):
    attack=float(r.get("raise",0))+float(r.get("allin",0))
    call=float(r.get("call",0)); fold=float(r.get("fold",0))
    return attack, call, fold, attack+call

def isotonic_decreasing(points):
    # points sorted by current pf_rank ascending: stronger -> weaker.
    blocks=[]
    for i,(x,y,w,h) in enumerate(points):
        blocks.append({"start":i,"end":i,"w":w,"wy":w*y,"mean":y})
        # enforce non-increasing y as rank gets weaker
        while len(blocks)>=2 and blocks[-2]["mean"] < blocks[-1]["mean"]-1e-15:
            b=blocks.pop(); a=blocks.pop()
            w2=a["w"]+b["w"]; wy=a["wy"]+b["wy"]
            blocks.append({"start":a["start"],"end":b["end"],"w":w2,"wy":wy,"mean":wy/w2})
    pred=[0.0]*len(points)
    for b in blocks:
        for i in range(b["start"],b["end"]+1): pred[i]=b["mean"]
    return pred,blocks

def best_cutoff(points):
    vals=[0.0]+sorted(set(x for x,_,_,_ in points))+[1.0]
    best=None
    tw=sum(w for _,_,w,_ in points)
    for t in vals:
        sq=0.0
        for x,y,w,h in points:
            p=1.0 if x<=t else 0.0
            sq+=w*(p-y)**2
        b=sq/tw
        if best is None or (b,t)<(best[0],best[1]): best=(b,t)
    return {"brier":best[0],"threshold":best[1]}

rows=[json.loads(x) for x in DATA.read_text().splitlines() if x.strip()]
groups=collections.defaultdict(list)
for r in rows:
    if r.get("scenario")=="vs-open" and r.get("node") in DIRECT:
        groups[(int(r["stack_bb"]),r["node"])].append(r)

hand_resid_attack=collections.defaultdict(lambda:[0.0,0.0,0])
hand_resid_continue=collections.defaultdict(lambda:[0.0,0.0,0])
charts=[]

for (stack,node),rs in sorted(groups.items()):
    ops,hero=DIRECT[node]
    open_bb=3.0 if node=="SB-vs-BB" else 2.5
    pts_attack=[];pts_continue=[]
    actual=[]
    for r in rs:
        h=r["hand"];w=combos(h); ta,tc,tf,tcont=target(r)
        vals=[]
        for op in ops:
            lik=preflop.defend_action_likelihoods(
                PROF,hero,op,cards(h),stack,open_bb,0,
                raise_level=1,stack_bb=stack,exploit=None,bf=1.0,
                seats=8,ante=True,opener_allin=False,can_raise=True)
            vals.append((float(lik["attack"]),float(lik["call"]),float(lik["fold"])))
        pa=sum(v[0] for v in vals)/len(vals)
        pc=sum(v[1] for v in vals)/len(vals)
        actual.append((h,w,ta,tcont,pa,pa+pc))
        pts_attack.append((PCT[h],ta,w,h))
        pts_continue.append((PCT[h],tcont,w,h))

    pts_attack.sort();pts_continue.sort()
    ipa,ba=isotonic_decreasing(pts_attack)
    ipc,bc=isotonic_decreasing(pts_continue)
    tw=sum(x[2] for x in pts_attack)
    iso_a=sum(w*(p-y)**2 for p,(_,y,w,h) in zip(ipa,pts_attack))/tw
    iso_c=sum(w*(p-y)**2 for p,(_,y,w,h) in zip(ipc,pts_continue))/tw
    hard_a=best_cutoff(pts_attack); hard_c=best_cutoff(pts_continue)

    amap={h:p for p,(_,y,w,h) in zip(ipa,pts_attack)}
    cmap={h:p for p,(_,y,w,h) in zip(ipc,pts_continue)}
    act_a=sum(w*(pa-ta)**2 for h,w,ta,tcont,pa,pcont in actual)/tw
    act_c=sum(w*(pcont-tcont)**2 for h,w,ta,tcont,pa,pcont in actual)/tw

    # Weighted inversion mass: weaker hand attacks/continues materially more than stronger hand.
    # This quantifies how incompatible the target is with a single strength ordering.
    inv_a_num=inv_c_num=inv_den=0.0
    ordered=sorted([(PCT[h],h,w,ta,tcont) for h,w,ta,tcont,pa,pcont in actual])
    for i in range(len(ordered)):
        xi,hi,wi,ai,ci=ordered[i]
        for j in range(i+1,len(ordered)):
            xj,hj,wj,aj,cj=ordered[j]
            ww=wi*wj;inv_den+=ww
            inv_a_num+=ww*max(0.0,aj-ai)
            inv_c_num+=ww*max(0.0,cj-ci)

    for h,w,ta,tcont,pa,pcont in actual:
        ea=(amap[h]-ta)**2
        ec=(cmap[h]-tcont)**2
        hand_resid_attack[h][0]+=w*ea;hand_resid_attack[h][1]+=w;hand_resid_attack[h][2]+=1
        hand_resid_continue[h][0]+=w*ec;hand_resid_continue[h][1]+=w;hand_resid_continue[h][2]+=1

    charts.append({
      "stack_bb":stack,"node":node,"defender":hero,
      "actual_attack_brier":act_a,"actual_continue_brier":act_c,
      "best_monotone_attack_brier":iso_a,"best_monotone_continue_brier":iso_c,
      "best_hard_attack":hard_a,"best_hard_continue":hard_c,
      "attack_inversion_mass":inv_a_num/max(inv_den,1e-9),
      "continue_inversion_mass":inv_c_num/max(inv_den,1e-9),
      "attack_isotonic_blocks":len(ba),"continue_isotonic_blocks":len(bc)
    })

def avg(key,subset=None):
    xs=[c[key] for c in charts if subset is None or c["stack_bb"] in subset]
    return sum(xs)/len(xs)

def worst(d):
    xs=[]
    for h,(se,sw,n) in d.items():
        xs.append((se/max(sw,1e-9),h,n,PCT[h]))
    xs.sort(reverse=True)
    return [{"hand":h,"residual_mse":e,"charts":n,"pct":pct} for e,h,n,pct in xs[:30]]

summary={
 "charts":len(charts),
 "actual_attack_brier_mean":avg("actual_attack_brier"),
 "actual_continue_brier_mean":avg("actual_continue_brier"),
 "best_monotone_attack_brier_mean":avg("best_monotone_attack_brier"),
 "best_monotone_continue_brier_mean":avg("best_monotone_continue_brier"),
 "best_hard_attack_brier_mean":avg("best_hard_attack","__never__") if False else sum(c["best_hard_attack"]["brier"] for c in charts)/len(charts),
 "best_hard_continue_brier_mean":sum(c["best_hard_continue"]["brier"] for c in charts)/len(charts),
 "attack_inversion_mass_mean":avg("attack_inversion_mass"),
 "continue_inversion_mass_mean":avg("continue_inversion_mass"),
 "holdout_15_30_100":{
   "actual_attack_brier":avg("actual_attack_brier",{15,30,100}),
   "actual_continue_brier":avg("actual_continue_brier",{15,30,100}),
   "best_monotone_attack_brier":avg("best_monotone_attack_brier",{15,30,100}),
   "best_monotone_continue_brier":avg("best_monotone_continue_brier",{15,30,100}),
 },
 "worst_attack_monotone_residual_hands":worst(hand_resid_attack),
 "worst_continue_monotone_residual_hands":worst(hand_resid_continue),
 "interpretation":{
   "attack_monotone_gap":"If large, no monotone function of current pf_rank can represent solver 3bet frequencies; blocker/polar structure is structurally missing.",
   "continue_monotone_gap":"Residual after best monotone fit indicates current pf_rank ordering mismatch/noise for total defend decisions.",
   "actual_to_monotone_gap":"How much current mixed-policy mapping could improve without changing hand ordering."
 }
}

# Node families make the polarized attack problem easier to localize.
summary["by_node"]={}
for node in DIRECT:
    cs=[c for c in charts if c["node"]==node]
    summary["by_node"][node]={
      "n":len(cs),
      "actual_attack_brier":sum(c["actual_attack_brier"] for c in cs)/len(cs),
      "monotone_attack_brier":sum(c["best_monotone_attack_brier"] for c in cs)/len(cs),
      "attack_inversion_mass":sum(c["attack_inversion_mass"] for c in cs)/len(cs),
      "actual_continue_brier":sum(c["actual_continue_brier"] for c in cs)/len(cs),
      "monotone_continue_brier":sum(c["best_monotone_continue_brier"] for c in cs)/len(cs),
      "continue_inversion_mass":sum(c["continue_inversion_mass"] for c in cs)/len(cs),
    }

dst=ROOT/"data"/"gto_public";dst.mkdir(parents=True,exist_ok=True)
(dst/"defend_policy_shape_audit_20260928.json").write_text(json.dumps({"summary":summary,"charts":charts},indent=2,sort_keys=True)+"\n")
md=["# Defense policy-shape audit","",
"| metric | current policy | best monotone pf_rank | best hard cutoff |",
"|---|---:|---:|---:|",
f"| attack/3bet Brier | {summary['actual_attack_brier_mean']:.5f} | {summary['best_monotone_attack_brier_mean']:.5f} | {summary['best_hard_attack_brier_mean']:.5f} |",
f"| continue Brier | {summary['actual_continue_brier_mean']:.5f} | {summary['best_monotone_continue_brier_mean']:.5f} | {summary['best_hard_continue_brier_mean']:.5f} |",
"",
f"- attack inversion mass: {summary['attack_inversion_mass_mean']:.5f}",
f"- continue inversion mass: {summary['continue_inversion_mass_mean']:.5f}",
"",
"Large attack residual/inversion means 3bet strategy cannot be repaired by a single scalar threshold/share on current hand-strength rank."]
(dst/"defend_policy_shape_audit_20260928.md").write_text("\n".join(md)+"\n")
print("SUMMARY",json.dumps(summary,sort_keys=True))
