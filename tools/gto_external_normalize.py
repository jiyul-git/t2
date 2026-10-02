#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

PREFIXES=[
 ("call_vs_5bet","Call 5Bet"),("call_vs_4bet","Call 4Bet"),
 ("call_vs_3bet","Call 3Bet"),("three_bet","3Bet"),
 ("four_bet","4Bet"),("five_bet","5Bet"),
 ("call_vs_open","Call"),("open","Open"),("limp","Limp"),
]

def shape(h):
    if len(h)==2 and h[0]==h[1]: return "pair"
    if h.endswith("s"): return "suited"
    if h.endswith("o"): return "offsuit"
    return "other"

def parse_key(k):
    for family,prefix in PREFIXES:
        if k.startswith(prefix):
            rest=k[len(prefix):]
            p=rest.split("vs",1)
            return family, p[0] or None, p[1] if len(p)>1 else None
    return "utility",None,None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--stack",type=float,required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    d=json.load(open(a.input))
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    n=0
    with out.open("w") as f:
        for key,hm in d.items():
            family,hero,villain=parse_key(key)
            if family=="utility": continue
            for hand,v in hm.items():
                v=float(v)
                row={
                  "table_players":9,"format":"MTT",
                  "nominal_stack_bb":a.stack,"stack_model":"symmetric_nominal",
                  "range_key":key,"action_family":family,
                  "hero_position":hero,"villain_position":villain,
                  "hand_class":hand,"hand_shape":shape(hand),
                  "frequency":v,
                  "frequency_semantics":"upstream conditional frequency for this range key",
                  "value_status":"exact"
                }
                f.write(json.dumps(row,separators=(",",":"))+"\n"); n+=1
    print(n)

if __name__=="__main__": main()
