#!/usr/bin/env python3
"""Manual one-hand runner for ChatGPT-driven hero decisions.

Reads tools/manual_hand_actions.json. Replays one fixed 100-player tournament
hand from scratch each run. If the supplied hero action list is exhausted,
prints the next hero decision state and stops. If the hand ends, settles every
other table in the same tournament round and prints a compact all-table audit.
"""
import json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STATE_DIR = Path(tempfile.mkdtemp(prefix="t2_manual_hand_"))
os.environ["T2_LIVE_STATE"] = str(STATE_DIR / "state.json")
os.environ["T2_BOT_LOG"] = "2"

import live2 as L
import persona as PS
import storage_paths as SP
import telemetry_sync as TM

ACTIONS_PATH = ROOT / "tools" / "manual_hand_actions.json"
SEED = 202609271937
ENTRIES = 100
START_STACK = 30000


def compact_raw(raw):
    if not isinstance(raw, dict):
        return raw
    keep = (
        "stage","pos","hole","board","pot","pot_total","tocall","stack",
        "min_raise","can_raise","log","live","allin","contrib","hash",
        "error","done"
    )
    return {k: raw.get(k) for k in keep if k in raw}


def main():
    actions = json.loads(ACTIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(actions, list):
        raise SystemExit("manual_hand_actions.json must be a list")

    L.new_game(
        entries=ENTRIES, start_stack=START_STACK, seed=SEED,
        hands_per_level=12, fmt="standard")

    out = L.step(defer_others=True)
    used = 0
    for item in actions:
        if out.get("done"):
            break
        if not isinstance(item, list) or len(item) != 2:
            raise SystemExit("action must be [action, amount]")
        act, amt = item
        out = L.step(str(act), int(amt), defer_others=True)
        used += 1

    if not out.get("done"):
        print("=== NEXT_HERO_DECISION ===")
        print(json.dumps(compact_raw(out.get("raw")), ensure_ascii=False, sort_keys=True))
        print("ACTIONS_USED", used)
        return

    print("=== HERO_HAND_DONE ===")
    print(json.dumps({
        "done": True,
        "result": out.get("result"),
        "view": out.get("view"),
        "status": out.get("status"),
    }, ensure_ascii=False, default=str))

    st = L.load()
    if st.get("others_pending"):
        how = L.resume_others(st, None)
        print("OTHER_TABLES_SETTLED", how)

    st = L.load()
    f = L._load_field(st["field"])
    print("=== ROUND_STATUS ===")
    print(json.dumps(f.status(), ensure_ascii=False, sort_keys=True, default=str))

    bot_path = SP.sidecar_path("bot_log")
    rows = TM.read_bot_round(bot_path, f.hand_no)
    print("BOT_TABLE_HANDS", len(rows))

    # Compact audit: preserve every table's hole cards/actions/results plus
    # internal plans/reads/fallback alarms, but avoid dumping huge profiles.
    compact = []
    for h in rows:
        profile_summary = {}
        for seat, pid in (h.get("pids") or {}).items():
            p = (f.players.get(int(pid)) or {}).get("prof") or {}
            tm = p.get("temper") or {}
            cc = p.get("concepts") or {}
            profile_summary[str(seat)] = {
                "pid": int(pid),
                "type": p.get("type"),
                "overall_skill": PS.overall_skill(p) if p else None,
                "tier": PS.tier(p)[0] if p else None,
                "aggression": tm.get("aggression"),
                "looseness": tm.get("looseness"),
                "discipline": tm.get("discipline"),
                "adaptability": tm.get("adaptability"),
                "attention": tm.get("attention"),
                "pf_defend": cc.get("pf_defend"),
                "pf_range": cc.get("pf_range"),
                "reraise": cc.get("reraise"),
                "range_read": cc.get("range_read"),
                "potodds": cc.get("potodds"),
                "bluffcatch_early": cc.get("bluffcatch_early"),
                "bluffcatch_river": cc.get("bluffcatch_river"),
            }
        compact.append({
            "table": h.get("table"),
            "pids": h.get("pids"),
            "profile_summary": profile_summary,
            "pos": h.get("pos"),
            "hole": h.get("hole"),
            "board": h.get("board"),
            "full_log": h.get("full_log"),
            "result": h.get("result"),
            "reads": h.get("reads"),
            "range_fallback_audit": h.get("range_fallback_audit"),
            "intents": h.get("intents"),
            "plans": {
                str(k): {
                    "type": v.get("type"),
                    "plan": v.get("plan"),
                    "plan_goal": v.get("plan_goal"),
                    "why": v.get("why"),
                    "trace": v.get("trace"),
                    "opp_est": v.get("opp_est"),
                    "rel": v.get("rel"),
                    "eq": v.get("eq"),
                    "pf_act": v.get("pf_act"),
                    "pf_role": v.get("pf_role"),
                }
                for k, v in (h.get("plans") or {}).items()
            },
            "tilt_before": h.get("tilt_before"),
            "tilt_after": h.get("tilt_after"),
        })
    print("=== OTHER_TABLE_AUDIT ===")
    print(json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
