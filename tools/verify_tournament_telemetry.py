#!/usr/bin/env python3
"""End-to-end verification for whole-tournament telemetry.

Runs real HandRun hands on an 18-player / 2-table field, builds one tournament
round bundle, then mirrors it through the same git sync path into a local bare
remote. No network or strategy changes are involved.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Full bot-table provenance must be enabled before fieldsim is imported.
os.environ["T2_BOT_LOG"] = "2"

import fieldsim as FS
import live2 as L
import storage_paths as SP
import telemetry_sync as TM


REQUIRED_HAND_KEYS = {
    "hand_no", "table", "pids", "pos", "board", "hole",
    "stacks_before", "stacks", "full_log", "full_action_meta",
    "intents", "plans", "decision_cache", "money_jump_obs", "reads",
    "book_before", "book_after", "tilt_before", "tilt_after",
    "street_outcomes", "uncalled_returns", "field_context", "result",
}


def run(cmd, cwd=None):
    p = subprocess.run(
        cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    if p.returncode:
        raise RuntimeError("%r failed:\n%s" % (cmd, p.stdout))
    return p.stdout


def real_round():
    f = FS.Field(
        entries=18, start_stack=30000, hero_pid=0,
        seed=20260927, hands_per_level=12, fmt="standard")
    before = L._dump(f)

    suffix = "_verify_telemetry_%d" % os.getpid()
    old_suffix = FS.BOT_SUFFIX
    old_log = FS.BOT_LOG
    FS.BOT_SUFFIX = suffix
    FS.BOT_LOG = 2
    path = Path(SP.path_for("bot_log", suffix, FS.D))
    try:
        if path.exists():
            path.unlink()

        table_ids = [
            tid for tid, tb in sorted(f.tables.items()) if tb.n() >= 2
        ]
        if len(table_ids) < 2:
            raise RuntimeError("fixture did not create >=2 tables")

        for tid in table_ids:
            ok = f._play_table(f.tables[tid])
            if not ok:
                raise RuntimeError("table %s did not play" % tid)

        f._collect_busts()
        f._balance(notify=False)

        text = path.read_text(encoding="utf-8")
        hands = TM.parse_bot_log(text)
    finally:
        FS.BOT_SUFFIX = old_suffix
        FS.BOT_LOG = old_log
        try:
            path.unlink()
        except OSError:
            pass

    if len(hands) != len(table_ids):
        raise RuntimeError(
            "expected %d table hands, got %d"
            % (len(table_ids), len(hands)))

    for h in hands:
        missing = sorted(REQUIRED_HAND_KEYS - set(h))
        if missing:
            raise RuntimeError(
                "table %s missing telemetry keys: %s"
                % (h.get("table"), missing))

        pids = set((h.get("pids") or {}).values())
        tb = h.get("tilt_before") or {}
        ta = h.get("tilt_after") or {}
        if not {str(x) for x in pids}.issubset(set(tb) | set(ta)):
            raise RuntimeError("tilt coverage missing for table %s" % h.get("table"))

        ctx = h.get("field_context") or {}
        for k in ("remaining", "itm", "avg_stack", "progress", "money_jump"):
            if k not in ctx:
                raise RuntimeError(
                    "field_context missing %s on table %s" % (k, h.get("table")))

    hero_tid = before["players"]["0"]["table"]
    hero = next(h for h in hands if int(h["table"]) == int(hero_tid))
    bots = [h for h in hands if h is not hero]

    st = {
        "seed": 20260927,
        "telemetry_session_id": "verify_telemetry",
        "book": {},
        "field": L._dump(f),
    }
    bundle = TM.build_round_bundle(
        st, f, hero, bots, source="verify", round_before=before)

    if len(bundle["all_hands"]) != len(table_ids):
        raise RuntimeError("all_hands does not cover every table")
    if len(bundle["players_after"]) != 18:
        raise RuntimeError("players_after does not cover the whole field")
    if len((bundle["round_before"] or {}).get("players") or {}) != 18:
        raise RuntimeError("round_before does not cover the whole field")
    if set(bundle["changes"]) != {"chip_delta", "busts", "moves"}:
        raise RuntimeError("round changes incomplete: %r" % bundle["changes"])
    if sum(bundle["changes"]["chip_delta"].values()) != 0:
        raise RuntimeError("chip conservation failed in telemetry delta")

    manifest = TM._manifest(st, f)
    if len(manifest["profiles"]) != 18:
        raise RuntimeError("manifest does not contain all player personas")
    for pid, row in manifest["profiles"].items():
        if not row.get("profile"):
            raise RuntimeError("empty profile pid=%s" % pid)
        if row.get("tier") is None or row.get("overall_skill") is None:
            raise RuntimeError("profile classification missing pid=%s" % pid)

    return st, f, hero, bots, bundle


def verify_git_sync(st, f, hero, bots):
    with tempfile.TemporaryDirectory(prefix="t2telemetry_") as td:
        td = Path(td)
        bare = td / "remote.git"
        seed = td / "seed"
        work = td / "work"
        spool = td / "spool"
        cfg = td / "telemetry_config.json"

        run(["git", "init", "--bare", str(bare)])
        run(["git", "init", "-b", "telemetry/live", str(seed)])
        run(["git", "config", "user.name", "verify"], cwd=seed)
        run(["git", "config", "user.email", "verify@local"], cwd=seed)
        (seed / "README.md").write_text("telemetry\n", encoding="utf-8")
        run(["git", "add", "README.md"], cwd=seed)
        run(["git", "commit", "-m", "seed telemetry"], cwd=seed)
        run(["git", "remote", "add", "origin", str(bare)], cwd=seed)
        run(["git", "push", "-u", "origin", "telemetry/live"], cwd=seed)

        cfg.write_text(json.dumps({
            "enabled": True,
            "branch": "telemetry/live",
            "remote": str(bare),
            "workdir": str(work),
        }), encoding="utf-8")

        old_cfg, old_spool = TM.CONFIG, TM.SPOOL
        old_ensure = TM._ensure_worker
        try:
            TM.CONFIG = cfg
            TM.SPOOL = spool
            # Keep this test deterministic; sync explicitly below.
            TM._ensure_worker = lambda: None
            out = TM.emit_round(
                st, f, hero, bots, source="verify_git",
                round_before=L._dump(
                    FS.Field(
                        entries=18, start_stack=30000, hero_pid=0,
                        seed=20260927, hands_per_level=12, fmt="standard")))
            if not out or not Path(out).exists():
                raise RuntimeError("emit_round did not spool a file")

            TM._sync_once()

            show = run([
                "git", "--git-dir", str(bare), "ls-tree", "-r",
                "--name-only", "telemetry/live"
            ])
            expected = "telemetry/verify_telemetry/round_%06d.json" % f.hand_no
            if expected not in show.splitlines():
                raise RuntimeError("remote branch missing %s\n%s" % (expected, show))
            if "telemetry/verify_telemetry/manifest.json" not in show.splitlines():
                raise RuntimeError("remote branch missing manifest")

            if list(spool.glob("*/*.json")):
                raise RuntimeError("spool was not cleared after successful push")
        finally:
            TM.CONFIG = old_cfg
            TM.SPOOL = old_spool
            TM._ensure_worker = old_ensure


def main():
    st, f, hero, bots, bundle = real_round()
    verify_git_sync(st, f, hero, bots)
    print("PASS whole-tournament telemetry")
    print("  entries=%d tables=%d hands=%d" % (
        f.entries, len(bundle["tables_after"]), len(bundle["all_hands"])))
    print("  profile_count=%d tilt_players=%d" % (
        len(TM._manifest(st, f)["profiles"]),
        sum(1 for x in bundle["players_after"].values() if "tilt" in x)))
    print("  git_sync=PASS branch=telemetry/live")


if __name__ == "__main__":
    main()
