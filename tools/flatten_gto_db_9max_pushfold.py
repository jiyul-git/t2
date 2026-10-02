#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data" / "gto_db" / "preflop_9max_pushfold_v1.jsonl"
OUT = ROOT / "data" / "gto_db" / "preflop_9max_pushfold_holdemmath_flat_v1.jsonl"
IDX = ROOT / "data" / "gto_db" / "index_9max_pushfold_holdemmath_flat_v1.json"
MASTER = ROOT / "data" / "gto_db" / "index_9max_operational_v1.json"

def shape(hand):
    if len(hand) == 2 and hand[0] == hand[1]:
        return "pair"
    if hand.endswith("s"):
        return "suited"
    if hand.endswith("o"):
        return "offsuit"
    raise ValueError(hand)

rows = 0
spots = 0
by_variant = {}
by_depth = {}
with IN.open(encoding="utf-8") as src, OUT.open("w", encoding="utf-8") as dst:
    for line in src:
        rec = json.loads(line)
        spots += 1
        c = rec["conditions"]
        st = rec["strategy"]
        hands = st["hands"]
        if st["hand_class_count"] != 169 or len(hands) != 169:
            raise SystemExit(f"{rec['spot_id']}: expected 169 hands")
        scenario = c["scenario"]
        active_action = "jam" if scenario == "first_in_shove" else "call"
        if scenario not in {"first_in_shove", "call_vs_shove"}:
            raise SystemExit(f"unexpected scenario {scenario}")
        ante = c["ante"]
        ante_model = ante["model"]
        variant = "no_ante" if ante_model == "none" else "ante_0p1_each"
        by_variant[variant] = by_variant.get(variant, 0) + 1
        depth = int(c["prehand_stack_bb"])
        by_depth[str(depth)] = by_depth.get(str(depth), 0) + 1

        for hand, strat in hands.items():
            freq = float(strat[active_action])
            if not (0.0 <= freq <= 1.0):
                raise SystemExit(f"{rec['spot_id']} {hand}: bad frequency {freq}")
            row = {
                "table_players": 9,
                "format": "MTT",
                "objective": "ChipEV",
                "stack_bb": depth,
                "stack_model": "symmetric",
                "ante_model": ante_model,
                "ante_per_player_bb": float(ante.get("per_player_bb", 0.0)),
                "ante_total_9max_bb": float(ante.get("total_at_9max_bb", 0.0)),
                "action_history_key": "unopened" if scenario == "first_in_shove" else f"face_shove:{c['shover_position']}",
                "action_family": "open_shove" if scenario == "first_in_shove" else "call_vs_shove",
                "action": active_action,
                "hero_position": c["hero_position"],
                "shover_position": c.get("shover_position"),
                "hand_class": hand,
                "hand_shape": shape(hand),
                "frequency": freq,
                "frequency_semantics": f"conditional {active_action} frequency",
                "value_status": "exact",
            }
            if "action_ev_bb" in strat:
                row["action_ev_bb"] = float(strat["action_ev_bb"])
            dst.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            rows += 1

if spots != 616:
    raise SystemExit(f"expected 616 spots, got {spots}")
if rows != 616 * 169:
    raise SystemExit(f"expected {616*169} rows, got {rows}")

index = {
    "schema": "t2_gto_operational_frequency_rows_v1",
    "table_players": 9,
    "format": "MTT",
    "provenance_fields_in_operational_rows": False,
    "dataset": OUT.name,
    "spot_count": spots,
    "hand_classes_per_spot": 169,
    "rows": rows,
    "stacks_bb": [4, 6, 8, 10, 12, 15, 20],
    "spots_by_variant": by_variant,
    "spots_by_depth": by_depth,
    "action_families": ["open_shove", "call_vs_shove"],
}
IDX.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")

external = json.loads((ROOT / "data" / "gto_db" / "index_9max_external_v1.json").read_text(encoding="utf-8"))
master = {
    "schema": "t2_gto_operational_index_v1",
    "table_players": 9,
    "format": "MTT",
    "provenance_fields_in_runtime_rows": False,
    "datasets": {
        **external["datasets"],
        OUT.name: {
            "rows": rows,
            "spot_count": spots,
            "stacks_bb": [4, 6, 8, 10, 12, 15, 20],
            "action_families": ["open_shove", "call_vs_shove"],
            "ante_models": ["none", "per_player"],
        },
    },
    "total_rows": int(external["total_rows"]) + rows,
}
MASTER.write_text(json.dumps(master, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(master, sort_keys=True))
