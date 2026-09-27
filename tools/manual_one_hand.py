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
import preflop as PF
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



def force_max_logic_profiles():
    """Manual audit only: identical maximum-skill profiles, neutral style."""
    st = L.load()
    for pv in (st.get("field", {}).get("players", {}) or {}).values():
        prof = pv.get("prof") or {}

        # All executable/calculation/perception concepts at maximum.
        prof["concepts"] = {k: 10.0 for k in PS.ALL_CONCEPTS}

        # Maximum knowledge/experience; neutral aggression latent so style does
        # not contaminate pure-logic inspection.
        prof["latent"] = {"study": 10.0, "aggro": 5.0, "exp": 10.0}

        # Ability-like temperament axes maxed; style axes neutralized.
        prof["temper"] = {
            "aggression": 5.0,
            "looseness": 5.0,
            "gamble": 5.0,
            "tilt_prone": 0.0,
            "tilt_recovery": 10.0,
            "discipline": 10.0,
            "adaptability": 10.0,
            "consistency": 10.0,
            "attention": 10.0,
            "slowplay_taste": 5.0,
            "tilt_swing": 5.0,
            "tilt_stack": 0.0,
        }

        # Refresh compatibility/derived fields used throughout the engine.
        prof.update(PS.derive(prof))
        pv["prof"] = prof

    # Eliminate accumulated tilt/read-personality contamination in this audit.
    st["field"]["tilt"] = {}
    st["book"] = {}
    L.save(st)


def main():
    actions = json.loads(ACTIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(actions, list):
        raise SystemExit("manual_hand_actions.json must be a list")

    L.new_game(
        entries=ENTRIES, start_stack=START_STACK, seed=SEED,
        hands_per_level=12, fmt="standard")
    force_max_logic_profiles()

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

    # Exact replay diagnostic for the suspicious table-2 BTN Q8s cold-call.
    q = f.players[71]["prof"]
    q8 = ["Qs", "8s"]
    for nc in (0, 1):
        lik = PF.defend_action_likelihoods(
            q, "BTN", "HJ", q8, 146.0, 4.0, nc,
            raise_level=1, stack_bb=146.0, exploit=None,
            bf=1.0, seats=8, ante=False, opener_allin=False,
            can_raise=True, pot_bb=(1.5 + 4.0 + 1.0), to_call_bb=4.0)
        print("Q8S_DEFEND_NCALLERS_%d %s" % (
            nc, json.dumps(lik, sort_keys=True, default=str)))

    # Continue one step into the next tournament round so the next hero
    # decision can be driven manually after auditing all other tables.
    nxt = L.step(defer_others=True)
    print("=== NEXT_ROUND_HERO_DECISION ===")
    print(json.dumps(compact_raw(nxt.get("raw")), ensure_ascii=False, sort_keys=True))
    print(nxt.get("view") or "")

    next_path = ROOT / "tools" / "manual_next_hand_actions.json"
    if next_path.exists():
        next_actions = json.loads(next_path.read_text(encoding="utf-8"))
        for act, amt in next_actions:
            if nxt.get("done"):
                break
            nxt = L.step(str(act), int(amt), defer_others=True)
        if nxt.get("done"):
            print("=== NEXT_HERO_HAND_DONE ===")
            print(json.dumps({"result": nxt.get("result"), "view": nxt.get("view")}, ensure_ascii=False, default=str))
            st2 = L.load()
            if st2.get("others_pending"):
                L.resume_others(st2, None)
            st2 = L.load()
            f2 = L._load_field(st2["field"])
            rows2 = TM.read_bot_round(SP.sidecar_path("bot_log"), f2.hand_no)
            audit2 = [{
                "table": h.get("table"),
                "pos": h.get("pos"),
                "hole": h.get("hole"),
                "board": h.get("board"),
                "full_log": h.get("full_log"),
                "result": h.get("result"),
                "reads": h.get("reads"),
                "range_fallback_audit": h.get("range_fallback_audit"),
                "intents": h.get("intents"),
                "plans": h.get("plans"),
                "pids": h.get("pids"),
            } for h in rows2]
            print("=== NEXT_OTHER_TABLE_AUDIT ===")
            print(json.dumps(audit2, ensure_ascii=False, sort_keys=True, default=str))
            nxt2 = L.step(defer_others=True)
            print("=== FOLLOWING_HERO_DECISION ===")
            print(json.dumps(compact_raw(nxt2.get("raw")), ensure_ascii=False, sort_keys=True))
            print(nxt2.get("view") or "")
        else:
            print("=== NEXT_HAND_DECISION_CONTINUES ===")
            print(json.dumps(compact_raw(nxt.get("raw")), ensure_ascii=False, sort_keys=True))
            print(nxt.get("view") or "")


if __name__ == "__main__":
    main()
