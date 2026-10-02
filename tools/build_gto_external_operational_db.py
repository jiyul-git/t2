#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "gto_external"
OUT = ROOT / "data" / "gto_db"

JENS_DIR = EXT / "jensbaagaard_9max_mtt"
RMH_FILE = EXT / "rangemyhand_pushfold_9max" / "push-fold-ranges.json"

STACKS = [5, 10, 20, 40, 100]
RANKS = "AKQJT98765432"

def canonical_hands():
    out = []
    for i, a in enumerate(RANKS):
        for j, b in enumerate(RANKS):
            if i == j:
                out.append(a + b)
            elif i < j:
                out.append(a + b + "s")
            else:
                out.append(b + a + "o")
    if len(out) != 169 or len(set(out)) != 169:
        raise RuntimeError("failed to build canonical 169-hand universe")
    return out

HANDS_169 = canonical_hands()

PREFIXES = [
    ("call_vs_5bet", "Call 5Bet"),
    ("call_vs_4bet", "Call 4Bet"),
    ("call_vs_3bet", "Call 3Bet"),
    ("three_bet", "3Bet"),
    ("four_bet", "4Bet"),
    ("five_bet", "5Bet"),
    ("call_vs_open", "Call"),
    ("open", "Open"),
    ("limp", "Limp"),
]

def hand_shape(hand):
    if len(hand) == 2 and hand[0] == hand[1]:
        return "pair"
    if hand.endswith("s"):
        return "suited"
    if hand.endswith("o"):
        return "offsuit"
    raise ValueError(f"unexpected hand class: {hand}")

def parse_jens_key(key):
    for family, prefix in PREFIXES:
        if key.startswith(prefix):
            rest = key[len(prefix):]
            parts = rest.split("vs", 1)
            hero = parts[0] or None
            villain = parts[1] if len(parts) > 1 else None
            return family, hero, villain
    return None, None, None

def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

def build_jens():
    rows = []
    per_stack = {}
    for stack in STACKS:
        path = JENS_DIR / f"MTT_{stack}_GTO.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        if len(raw) != 271:
            raise SystemExit(f"{path}: expected 271 scenario keys, got {len(raw)}")
        count = 0
        for key, hand_map in raw.items():
            family, hero, villain = parse_jens_key(key)
            if family is None:
                continue
            unknown = set(hand_map) - set(HANDS_169)
            if unknown:
                raise SystemExit(f"{path}:{key}: unknown hand classes {sorted(unknown)}")
            for hand in HANDS_169:
                v = float(hand_map.get(hand, 0.0))
                if not (0.0 <= v <= 1.0):
                    raise SystemExit(f"{path}:{key}:{hand}: invalid frequency {v}")
                rows.append({
                    "table_players": 9,
                    "format": "MTT",
                    "objective": "ChipEV",
                    "ante_model": "upstream_unspecified",
                    "stack_bb": stack,
                    "stack_model": "symmetric_nominal",
                    "action_history_key": key,
                    "action_family": family,
                    "hero_position": hero,
                    "villain_position": villain,
                    "hand_class": hand,
                    "hand_shape": hand_shape(hand),
                    "frequency": v,
                    "frequency_semantics": "conditional frequency for action represented by action_history_key",
                    "value_status": "exact",
                })
                count += 1
        per_stack[str(stack)] = count
    expected = 1345 * 169
    if len(rows) != expected:
        raise SystemExit(f"Jens rows: expected {expected}, got {len(rows)}")
    return rows, per_stack

def build_rmh():
    raw = json.loads(RMH_FILE.read_text(encoding="utf-8"))
    hands = raw["hands"]
    if len(hands) != 169:
        raise SystemExit(f"RangeMyHand: expected 169 hands, got {len(hands)}")
    rows = []
    spots = 0
    per_stack = {}
    for spot in raw["spots"]:
        if spot.get("table") != "9max":
            continue
        freq = spot["pushFreq"]
        if len(freq) != 169:
            raise SystemExit(f"RangeMyHand {spot['seat']} {spot['stackBB']}bb: bad pushFreq len {len(freq)}")
        stack = int(spot["stackBB"])
        spots += 1
        per_stack[str(stack)] = per_stack.get(str(stack), 0) + 1
        for hand, p in zip(hands, freq):
            v = float(p)
            if not (0.0 <= v <= 1.0):
                raise SystemExit(f"RangeMyHand {spot['seat']} {stack}bb {hand}: invalid frequency {v}")
            rows.append({
                "table_players": 9,
                "format": "MTT",
                "objective": "ChipEV",
                "ante_model": "none",
                "stack_bb": stack,
                "stack_model": "symmetric",
                "action_history_key": "unopened",
                "action_family": "open_shove",
                "hero_position": spot["seat"],
                "players_behind": int(spot["playersBehind"]),
                "hand_class": hand,
                "hand_shape": hand_shape(hand),
                "frequency": v,
                "frequency_semantics": "first-in shove frequency",
                "value_status": "exact",
            })
    if spots != 125:
        raise SystemExit(f"RangeMyHand spots: expected 125, got {spots}")
    if len(rows) != 125 * 169:
        raise SystemExit(f"RangeMyHand rows: expected {125*169}, got {len(rows)}")
    return rows, spots, per_stack

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    jens_rows, jens_by_stack = build_jens()
    rmh_rows, rmh_spots, rmh_by_stack = build_rmh()

    jens_out = OUT / "preflop_9max_fulltree_external_v1.jsonl"
    rmh_out = OUT / "preflop_9max_pushfold_1to25_v1.jsonl"
    write_jsonl(jens_out, jens_rows)
    write_jsonl(rmh_out, rmh_rows)

    index = {
        "schema": "t2_gto_operational_frequency_rows_v1",
        "table_players": 9,
        "format": "MTT",
        "provenance_fields_in_operational_rows": False,
        "datasets": {
            jens_out.name: {
                "rows": len(jens_rows),
                "stacks_bb": STACKS,
                "scenario_tables": 1345,
                "hand_classes_per_table": 169,
                "rows_by_stack": jens_by_stack,
                "families": [x[0] for x in PREFIXES],
            },
            rmh_out.name: {
                "rows": len(rmh_rows),
                "stacks_bb": list(range(1, 26)),
                "scenario_tables": rmh_spots,
                "hand_classes_per_table": 169,
                "scenario": "first_in_open_shove",
                "ante_model": "none",
                "spots_by_stack": rmh_by_stack,
            },
        },
        "total_rows": len(jens_rows) + len(rmh_rows),
    }
    (OUT / "index_9max_external_v1.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(index, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
