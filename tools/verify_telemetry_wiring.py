#!/usr/bin/env python3
"""Verify whole-tournament telemetry captures real engine provenance without strategy changes."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fieldsim as FS
import live2 as L
import telemetry_sync as TM


REQUIRED_HAND_KEYS = {
    "full_log", "full_action_meta", "intents", "plans", "decision_cache",
    "money_jump_obs", "reads", "book_before", "book_after",
    "tilt_before", "tilt_after", "field_context", "result",
    "stacks_before", "stacks", "compute_ms",
}


def main():
    f = FS.Field(
        entries=18, start_stack=30000, hero_pid=0,
        seed=20260927, hands_per_level=12, itm_frac=0.15, fmt="standard")
    f.hand_no = 1
    f.advance_level()

    ht = f.players[f.hero_pid]["table"]
    tb = next(t for tid, t in sorted(f.tables.items()) if tid != ht and t.n() >= 2)

    old_suffix = FS.BOT_SUFFIX
    old_log = FS.Field.BOT_LOG
    suffix = "_verify_telemetry_%d" % os.getpid()
    path = Path(FS._SP.path_for("bot_log", suffix, FS.D))
    FS.BOT_SUFFIX = suffix
    FS.Field.BOT_LOG = 2
    try:
        ok = f._play_table(tb)
        if not ok:
            raise SystemExit("FAIL: bot table hand did not run")
        rows = [
            json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
    finally:
        FS.BOT_SUFFIX = old_suffix
        FS.Field.BOT_LOG = old_log
        try:
            path.unlink()
        except OSError:
            pass

    if not rows:
        raise SystemExit("FAIL: no bot telemetry row")
    hand = rows[-1]
    missing = sorted(REQUIRED_HAND_KEYS - set(hand))
    if missing:
        raise SystemExit("FAIL: bot hand missing keys: %r" % missing)
    if not hand["full_log"]:
        raise SystemExit("FAIL: full_log empty")
    if not isinstance(hand["plans"], dict):
        raise SystemExit("FAIL: plans not dict")
    if not isinstance(hand["tilt_before"], dict) or not isinstance(hand["tilt_after"], dict):
        raise SystemExit("FAIL: tilt snapshots malformed")

    before = L._dump(f)
    st = {
        "seed": f.seed,
        "telemetry_session_id": "verify_session",
        "book": {},
    }
    bundle = TM.build_round_bundle(
        st, f, hand, [hand], source="verify", round_before=before)

    required_round = {
        "code", "field_status", "round_before", "players_after", "tables_after",
        "changes", "busted_order", "field_notes", "field_errors",
        "hero_book_after", "hero_hand", "bot_hands", "all_hands",
    }
    missing_round = sorted(required_round - set(bundle))
    if missing_round:
        raise SystemExit("FAIL: round bundle missing: %r" % missing_round)

    if len(bundle["players_after"]) != 18:
        raise SystemExit("FAIL: expected 18 player states")
    if len(bundle["round_before"]["players"]) != 18:
        raise SystemExit("FAIL: expected 18 before-player states")
    if len(bundle["all_hands"]) != 2:
        raise SystemExit("FAIL: all_hands aggregation")
    if bundle["all_hands"][0].get("table_role") != "hero":
        raise SystemExit("FAIL: hero role missing")
    if bundle["all_hands"][1].get("table_role") != "bot":
        raise SystemExit("FAIL: bot role missing")

    manifest = TM._manifest(st, f)
    if len(manifest.get("profiles") or {}) != 18:
        raise SystemExit("FAIL: manifest profiles incomplete")
    p0 = next(iter(manifest["profiles"].values()))
    for k in ("profile", "label", "tier", "overall_skill"):
        if k not in p0:
            raise SystemExit("FAIL: manifest profile missing %s" % k)

    print("PASS whole-tournament telemetry schema")
    print("bot_full_log=%d intents=%d plans=%d reads=%d"
          % (len(hand["full_log"]), len(hand["intents"]),
             len(hand["plans"]), len(hand["reads"])))
    print("players=%d tables=%d compute_ms=%s"
          % (len(bundle["players_after"]), len(bundle["tables_after"]),
             hand.get("compute_ms")))


if __name__ == "__main__":
    main()
