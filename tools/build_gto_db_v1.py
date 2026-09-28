#!/usr/bin/env python3
import json, collections, hashlib
from pathlib import Path

ROOT=Path(".")
SRC=ROOT/"data/gto_public/8max_mtt_matthiola.jsonl"
OUT=ROOT/"data/gto_db"
OUT.mkdir(parents=True,exist_ok=True)

SOURCE_META={
  "id":"matthiola0_poker_hand_review_mtt8_v1",
  "name":"matthiola0/poker-hand-review 8-max MTT preflop charts",
  "repo":"https://github.com/matthiola0/poker-hand-review",
  "commit":"9ef33a4d70b48c4ec8aea6093562e38ef46feb24",
  "license":"MIT",
  "source_type":"public_chart",
}

VS_RFI={
  "EP-vs-MP":("LJ","CO"),
  "EP-vs-BTN":("LJ","BTN"),
  "EP-vs-SB":("LJ","SB"),
  "EP-vs-BB":("LJ","BB"),
  "MP-vs-BTN":("CO","BTN"),
  "MP-vs-SB":("CO","SB"),
  "MP-vs-BB":("CO","BB"),
  "BTN-vs-SB":("BTN","SB"),
  "BTN-vs-BB":("BTN","BB"),
  "SB-vs-BB":("SB","BB"),
}
RFI_POS={"UTG":"UTG","UTG1":"UTG+1","LJ":"LJ","HJ":"HJ","CO":"CO","BTN":"BTN","SB":"SB"}

def q(v):
    if v is None: return 0.0
    return round(float(v),8)

groups=collections.defaultdict(dict)
raw_keys=set()
for line in SRC.open():
    x=json.loads(line)
    raw_keys.update(x.keys())
    key=(int(x["stack_bb"]),str(x["scenario"]),str(x["node"]))
    hand=str(x["hand"])
    groups[key][hand]={
      "fold":q(x.get("fold")),
      "call":q(x.get("call")),
      "raise":q(x.get("raise")),
      "allin":q(x.get("allin")),
    }

records=[]
for (stack,scenario,node), hands in sorted(groups.items()):
    if scenario=="rfi":
        hero=RFI_POS.get(node,node)
        opener=None
        history={"type":"unopened","opener":None}
        allowed=["fold","raise","allin"]
    elif scenario=="vs-open":
        opener,hero=VS_RFI.get(node,(None,None))
        history={"type":"face_open","opener":opener}
        allowed=["fold","call","raise","allin"]
    else:
        hero=opener=None
        history={"type":scenario}
        allowed=["fold","call","raise","allin"]

    spot_id=f"mtt8_ante_{stack}bb_{scenario}_{node}".lower().replace("+","p").replace(" ","_")
    rec={
      "schema_version":"gto_spot_v1",
      "spot_id":spot_id,
      "game":{
        "variant":"NLHE",
        "format":"MTT",
        "table_players":8,
        "street":"preflop",
      },
      "conditions":{
        "effective_stack_bb":stack,
        "ante":{
          "present":True,
          "amount_bb":None,
          "kind":"source_unspecified_mtt_ante",
        },
        "scenario":scenario,
        "hero_position":hero,
        "opener_position":opener,
        "source_node":node,
        "history_template":history,
        "allowed_actions":allowed,
        "rake":"source_unspecified",
      },
      "strategy":{
        "hand_class_count":len(hands),
        "hands":dict(sorted(hands.items())),
      },
      "source":dict(SOURCE_META),
      "quality":{
        "status":"exact_source_chart",
        "frequency_fidelity":"lossless_from_source",
        "condition_precision":{
          "players":"exact",
          "stack_bb":"exact",
          "positions":"exact_or_source_bucket",
          "ante_presence":"exact",
          "ante_amount":"unknown",
          "rake":"unknown",
        },
        "use":"GTO learned-prior reference; not an unconditional production action target",
      },
      "tags":["public","preflop","8max","mtt","ante"],
    }
    raw=json.dumps(rec,sort_keys=True,separators=(",",":")).encode()
    rec["sha256"]=hashlib.sha256(raw).hexdigest()
    records.append(rec)

db=OUT/"preflop_spots_v1.jsonl"
with db.open("w") as f:
    for r in records:
        f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n")

by_scenario=collections.Counter(r["conditions"]["scenario"] for r in records)
by_stack=collections.Counter(r["conditions"]["effective_stack_bb"] for r in records)
index={
  "schema_version":"gto_db_index_v1",
  "spot_count":len(records),
  "hand_frequency_rows":sum(r["strategy"]["hand_class_count"] for r in records),
  "source_ids":sorted({r["source"]["id"] for r in records}),
  "scenarios":dict(sorted(by_scenario.items())),
  "stacks_bb":dict(sorted(by_stack.items())),
  "raw_input_keys":sorted(raw_keys),
  "database_file":"preflop_spots_v1.jsonl",
  "known_gaps":[
    "source ante amount is not encoded",
    "source rake model is not encoded",
    "8-max only",
    "preflop only",
    "vs-open source uses EP/MP buckets rather than every exact opener position",
    "no source rows for many re-raise/cold-facing nodes"
  ]
}
(OUT/"index_v1.json").write_text(json.dumps(index,ensure_ascii=False,indent=2,sort_keys=True)+"\n")

schema={
  "schema_version":"gto_spot_v1",
  "required_top_level":["schema_version","spot_id","game","conditions","strategy","source","quality","tags","sha256"],
  "action_frequency_keys":["fold","call","raise","allin"],
  "frequency_semantics":"probability within the source hand class; action frequencies should sum to approximately 1",
  "design_rule":"TRUE/reference GTO knowledge is stored separately from PLAYER_GTO_MEMORY. Runtime persona/reasoning must not mutate this database."
}
(OUT/"schema_v1.json").write_text(json.dumps(schema,ensure_ascii=False,indent=2,sort_keys=True)+"\n")

readme="""# GTO Knowledge DB

This directory is the canonical reference knowledge layer, not the runtime human player's memory.

## Separation

1. GTO Knowledge DB — best available source/solver reference.
2. PLAYER_GTO_MEMORY — which spots a player studied, recall precision, and interpolation confidence.
3. Human reasoning/read/exploit — current-table inference that may intentionally deviate from the learned prior.

A mismatch with this DB is not automatically a bug. Classify it as:
- reasoning error,
- human approximation / bounded knowledge,
- intentional exploit / adaptation.

## v1 contents

preflop_spots_v1.jsonl converts the MIT-licensed public 8-max MTT source into one record per chart/spot.

Each record stores:
- exact stack and table size available from source,
- source scenario/node and normalized positions where semantics are known,
- all 169 hand-class action frequencies,
- provenance and license,
- explicit condition precision/gaps,
- a content fingerprint.

The source only says MTT ante; the exact ante amount and rake model are unknown. Those fields remain unknown instead of being invented.

## Lookup direction

Future lookup should match exact conditions first, then return nearby spots with a distance/confidence score. Interpolation belongs in the learned-memory/reasoning layer; it must not silently rewrite reference rows.

## Next ingestion priorities

1. public 100bb 8-max no-ante cross-check/reference where redistributable values are available,
2. validated mini-CFR solver outputs with full solve metadata,
3. additional vs-open / vs-3bet / cold-facing preflop nodes,
4. postflop solved review spots,
5. broader postflop abstractions only after source/tree semantics are explicit.
"""
(OUT/"README.md").write_text(readme)

print(json.dumps(index,sort_keys=True))
