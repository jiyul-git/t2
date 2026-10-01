#!/usr/bin/env python3
"""Manual one-hand runner for ChatGPT-driven hero decisions.

Reads manual action fixtures. Replays one fixed 100-player tournament
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
import runner as RU

ACTIONS_PATH = ROOT / "tools" / "manual_hand_actions.json"
SEED = 202609271937
ENTRIES = 99
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


def print_pending_hero_audit(label):
    """Print the just-finished HERO table's internal reasoning before settlement.

    live2.finish stores the full hero archive in pending_archive while other
    tables are deferred.  Consume it only for diagnostics; resume_others keeps
    ownership of settlement/archive writing.
    """
    st = L.load()
    rec = st.get("pending_archive") or {}
    if not rec:
        print("=== %s ===" % label)
        print("{}")
        return
    compact = {
        "hand_no": rec.get("hand_no"),
        "hash": rec.get("hash"),
        "pos": rec.get("pos"),
        "hole": rec.get("hole"),
        "board": rec.get("board"),
        "full_log": rec.get("full_log"),
        "pf_seed": rec.get("pf_seed"),
        "intents": rec.get("intents"),
        "plans": rec.get("plans"),
        "reads": rec.get("reads"),
        "range_fallback_audit": rec.get("range_fallback_audit"),
        "decision_cache": rec.get("decision_cache"),
    }
    print("=== %s ===" % label)
    print(json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str))



def force_logic_execution_surface():
    """Manual audit only: execute the judgment layer's exact sizing."""
    RU.shape_size = lambda amount, ptype, rng, pot=None: int(round(float(amount)))


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

    # Human-logic audit is a 9-max primary experiment.  100 entries creates
    # partially filled tables after balancing; 99 gives 11 full 9-handed
    # tables at hand 1.  Fail loudly rather than silently auditing 8-max again.
    _st0 = L.load()
    _f0 = L._load_field(_st0["field"])
    _ht0 = _f0.hero_table()
    _hero_n0 = len(_ht0.alive()) if _ht0 else 0
    if _f0.max_seat != 9 or _hero_n0 != 9:
        raise RuntimeError(
            "manual human audit must start 9-max: max_seat=%s hero_n=%s"
            % (_f0.max_seat, _hero_n0))

    force_max_logic_profiles()
    force_logic_execution_surface()

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

    print_pending_hero_audit("HERO_INTERNAL_AUDIT")
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

    print("MANUAL_AUDIT_TABLE_MODE 9max")

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
            print_pending_hero_audit("NEXT_HERO_INTERNAL_AUDIT")
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
                "pf_seed": h.get("pf_seed"),
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

            following_path = ROOT / "tools" / "manual_following_hand_actions.json"
            if following_path.exists():
                following_actions = json.loads(following_path.read_text(encoding="utf-8"))
                for act, amt in following_actions:
                    if nxt2.get("done"):
                        break
                    nxt2 = L.step(str(act), int(amt), defer_others=True)
                if nxt2.get("done"):
                    print("=== FOLLOWING_HERO_HAND_DONE ===")
                    print(json.dumps({"result": nxt2.get("result"), "view": nxt2.get("view")}, ensure_ascii=False, default=str))
                    print_pending_hero_audit("FOLLOWING_HERO_INTERNAL_AUDIT")
                    st3 = L.load()
                    if st3.get("others_pending"):
                        L.resume_others(st3, None)
                    st3 = L.load()
                    f3 = L._load_field(st3["field"])
                    rows3 = TM.read_bot_round(SP.sidecar_path("bot_log"), f3.hand_no)
                    audit3 = [{
                        "table": h.get("table"),
                        "pos": h.get("pos"),
                        "hole": h.get("hole"),
                        "board": h.get("board"),
                        "full_log": h.get("full_log"),
                        "pf_seed": h.get("pf_seed"),
                        "result": h.get("result"),
                        "reads": h.get("reads"),
                        "range_fallback_audit": h.get("range_fallback_audit"),
                        "intents": h.get("intents"),
                        "plans": h.get("plans"),
                        "pids": h.get("pids"),
                    } for h in rows3]
                    print("=== FOLLOWING_OTHER_TABLE_AUDIT ===")
                    print(json.dumps(audit3, ensure_ascii=False, sort_keys=True, default=str))
                    nxt3 = L.step(defer_others=True)
                    print("=== HAND4_HERO_DECISION ===")
                    print(json.dumps(compact_raw(nxt3.get("raw")), ensure_ascii=False, sort_keys=True))
                    print(nxt3.get("view") or "")
                    hand4_path = ROOT / "tools" / "manual_hand4_actions.json"
                    if hand4_path.exists():
                        hand4_actions = json.loads(hand4_path.read_text(encoding="utf-8"))
                        for act, amt in hand4_actions:
                            if nxt3.get("done"):
                                break
                            nxt3 = L.step(str(act), int(amt), defer_others=True)
                        if nxt3.get("done"):
                            print("=== HAND4_HERO_HAND_DONE ===")
                            print(json.dumps({"result": nxt3.get("result"), "view": nxt3.get("view")}, ensure_ascii=False, default=str))
                            print_pending_hero_audit("HAND4_HERO_INTERNAL_AUDIT")
                            st4 = L.load()
                            if st4.get("others_pending"):
                                L.resume_others(st4, None)
                            st4 = L.load()
                            f4 = L._load_field(st4["field"])
                            rows4 = TM.read_bot_round(SP.sidecar_path("bot_log"), f4.hand_no)
                            audit4 = [{
                                "table": h.get("table"),
                                "pos": h.get("pos"),
                                "hole": h.get("hole"),
                                "board": h.get("board"),
                                "full_log": h.get("full_log"),
                                "pf_seed": h.get("pf_seed"),
                                "result": h.get("result"),
                                "reads": h.get("reads"),
                                "range_fallback_audit": h.get("range_fallback_audit"),
                                "intents": h.get("intents"),
                                "plans": h.get("plans"),
                                "pids": h.get("pids"),
                            } for h in rows4]
                            print("=== HAND4_OTHER_TABLE_AUDIT ===")
                            print(json.dumps(audit4, ensure_ascii=False, sort_keys=True, default=str))

                            # HAND 5+ uses one reusable loop. Each element in
                            # manual_more_hands.json is that hand's hero action list.
                            more_path = ROOT / "tools" / "manual_more_hands.json"
                            more_hands = (
                                json.loads(more_path.read_text(encoding="utf-8"))
                                if more_path.exists() else [])
                            cur = L.step(defer_others=True)
                            hand_no = 5
                            while True:
                                print("=== HAND%d_HERO_DECISION ===" % hand_no)
                                print(json.dumps(
                                    compact_raw(cur.get("raw")),
                                    ensure_ascii=False, sort_keys=True))
                                print(cur.get("view") or "")

                                ix = hand_no - 5
                                if ix >= len(more_hands):
                                    break
                                actions_n = more_hands[ix]
                                for act, amt in actions_n:
                                    if cur.get("done"):
                                        break
                                    cur = L.step(
                                        str(act), int(amt), defer_others=True)

                                if not cur.get("done"):
                                    print("=== HAND%d_DECISION_CONTINUES ===" % hand_no)
                                    print(json.dumps(
                                        compact_raw(cur.get("raw")),
                                        ensure_ascii=False, sort_keys=True))
                                    print(cur.get("view") or "")
                                    break

                                print("=== HAND%d_HERO_HAND_DONE ===" % hand_no)
                                print(json.dumps({
                                    "result": cur.get("result"),
                                    "view": cur.get("view"),
                                }, ensure_ascii=False, default=str))

                                print_pending_hero_audit("HAND%d_HERO_INTERNAL_AUDIT" % hand_no)
                                stn = L.load()
                                if stn.get("others_pending"):
                                    L.resume_others(stn, None)
                                stn = L.load()
                                fn = L._load_field(stn["field"])
                                rowsn = TM.read_bot_round(
                                    SP.sidecar_path("bot_log"), fn.hand_no)
                                auditn = [{
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
                                } for h in rowsn]
                                print("=== HAND%d_OTHER_TABLE_AUDIT ===" % hand_no)
                                print(json.dumps(
                                    auditn, ensure_ascii=False,
                                    sort_keys=True, default=str))

                                cur = L.step(defer_others=True)
                                hand_no += 1
                        else:
                            print("=== HAND4_DECISION_CONTINUES ===")
                            print(json.dumps(compact_raw(nxt3.get("raw")), ensure_ascii=False, sort_keys=True))
                            print(nxt3.get("view") or "")
                else:
                    print("=== FOLLOWING_HAND_DECISION_CONTINUES ===")
                    print(json.dumps(compact_raw(nxt2.get("raw")), ensure_ascii=False, sort_keys=True))
                    print(nxt2.get("view") or "")
        else:
            print("=== NEXT_HAND_DECISION_CONTINUES ===")
            print(json.dumps(compact_raw(nxt.get("raw")), ensure_ascii=False, sort_keys=True))
            print(nxt.get("view") or "")


if __name__ == "__main__":
    main()
