#!/usr/bin/env python3
"""Fast two-human online tournament smoke test.

Covers:
- two distinct authenticated owners (engine-level UIDs)
- humans may be on different 9-max tables
- private hole cards stay user-scoped
- both tables accept human actions and settle one tournament round
- total chips are conserved
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import live2 as L
from online_server.config import Settings
from online_server.duo_engine import DuoTournamentEngine


def settings(path: str) -> Settings:
    return Settings(
        auth_mode="dev",
        firebase_project_id=None,
        single_user_uid=None,
        allow_dev_auth=True,
        dev_token="0123456789abcdef0123456789abcdef",
        online_data_dir=path,
    ).validate()


def different_table_seed() -> int:
    for seed in range(1, 500):
        f = FS.Field(
            entries=18,
            start_stack=30000,
            hero_pid=0,
            human_pids=[0, 1],
            seed=seed,
            fmt="standard",
        )
        if f.players[0]["table"] != f.players[1]["table"]:
            return seed
    raise AssertionError("could not find deterministic different-table seed")


def choose_action(payload):
    legal = payload["table"]["legal"]
    if legal.get("fold"):
        return "fold", 0
    if legal.get("check"):
        return "check", 0
    if legal.get("call"):
        return "call", 0
    raise AssertionError("no safe action exposed for human decision")


def main() -> None:
    root = tempfile.mkdtemp(prefix="t2_duo_verify_")
    old_bot_log = FS.Field.BOT_LOG
    FS.Field.BOT_LOG = 0
    try:
        eng = DuoTournamentEngine(settings(root))

        state = eng._blank()
        state["seed"] = different_table_seed()
        eng._save(state)

        p1 = eng._sync_join("verify-user-1")
        assert p1["phase"] == "waiting_player"

        p2 = eng._sync_join("verify-user-2")
        assert p2["started"]
        assert p2["tournament"]["entries"] == 18

        room = eng._load()
        base = room["round"]["base"]
        f = L._load_field(base)
        assert f.players[0]["table"] != f.players[1]["table"]
        assert f.human_pids == {0, 1}

        s1 = eng._sync_state("verify-user-1")
        s2 = eng._sync_state("verify-user-2")
        for s in (s1, s2):
            if s["phase"] in ("decision", "waiting_other"):
                assert len(s["table"]["hole"]) == 2
                assert all("hole" not in seat for seat in s["table"]["seats"])

        started_round = room["round_no"]
        acted = 0
        for _ in range(80):
            progressed = False
            for uid in ("verify-user-1", "verify-user-2"):
                cur = eng._sync_state(uid)
                if cur.get("phase") != "decision":
                    continue
                action, amount = choose_action(cur)
                eng._sync_action(uid, cur["token"], action, amount)
                acted += 1
                progressed = True

            room = eng._load()
            if room["round_no"] > started_round:
                break
            if not progressed:
                # One user may be waiting for the other browser's table to
                # settle; loop once more after reading both states.
                continue
        else:
            raise AssertionError("duo round did not settle")

        assert acted >= 2
        field_dump = room["round"]["base"] if room.get("round") else room["field"]
        f2 = L._load_field(field_dump)
        assert f2.total_chips() == f2.entries * f2.start_stack
        assert f2.human_pids == {0, 1}

        print(
            "duo online verifier: PASS "
            f"(seed={state['seed']}, actions={acted}, round={room['round_no']})"
        )
    finally:
        FS.Field.BOT_LOG = old_bot_log
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
