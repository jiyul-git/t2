# -*- coding: utf-8 -*-
"""Asynchronous whole-tournament telemetry sync.

This module is deliberately outside strategy. Gameplay writes a durable local
spool first; a daemon thread mirrors completed files to a dedicated Git branch.
Network/git failure must never block or change a poker decision.

Enable by placing telemetry_config.json next to this module. setup_run_dir.sh
creates it when T2_TELEMETRY=1 is supplied.
"""
import copy
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import persona as PS

D = Path(__file__).resolve().parent
CONFIG = D / "telemetry_config.json"
SPOOL = D / "telemetry_spool"

_LOCK = threading.Lock()
_WAKE = threading.Event()
_THREAD = None
_STATUS = {
    "enabled": False,
    "queued": 0,
    "uploaded": 0,
    "last_success": None,
    "last_error": None,
    "worker_alive": False,
}


def _load_config():
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(cfg, dict) or not cfg.get("enabled"):
        return {}
    return cfg


def enabled():
    return bool(_load_config())


def status():
    cfg = _load_config()
    with _LOCK:
        out = dict(_STATUS)
    out["enabled"] = bool(cfg)
    out["branch"] = cfg.get("branch") if cfg else None
    out["workdir"] = cfg.get("workdir") if cfg else None
    out["spool"] = str(SPOOL)
    out["queued"] = len(list(SPOOL.glob("*/*.json"))) if SPOOL.exists() else 0
    return out


def _json_safe(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))


def _session_id(st):
    sid = st.get("telemetry_session_id")
    if sid:
        return str(sid)
    # Old live states can enter telemetry without restarting a tournament.
    seed = st.get("seed")
    hand = ((st.get("field") or {}).get("hand_no") or 0)
    sid = "adopted_%s_h%s" % (seed if seed is not None else "noseed", hand)
    st["telemetry_session_id"] = sid
    return sid


def _code_identity():
    cfg = _load_config()
    src = cfg.get("source_repo") if cfg else None
    if src:
        src = os.path.expanduser(str(src))
        if os.path.exists(src):
            sha = _run(["git", "-C", src, "rev-parse", "HEAD"], timeout=10)
            br = _run(["git", "-C", src, "branch", "--show-current"], timeout=10)
            return {
                "sha": sha.stdout.strip() if sha.returncode == 0 else None,
                "branch": br.stdout.strip() if br.returncode == 0 else None,
            }
    return {"sha": None, "branch": None}


def _manifest(st, f):
    profiles = {}
    for pid, p in sorted(f.players.items()):
        prof = copy.deepcopy(p.get("prof") or {})
        profiles[str(pid)] = {
            "profile": prof,
            "label": prof.get("type"),
            "tier": PS.tier(prof)[0] if prof else None,
            "overall_skill": PS.overall_skill(prof) if prof else None,
        }
    fmt = copy.deepcopy(getattr(f, "fmt", {}) or {})
    return {
        "schema": "t2_tournament_telemetry_v1",
        "session_id": _session_id(st),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "seed": st.get("seed"),
        "entries": int(f.entries),
        "start_stack": int(f.start_stack),
        "itm": int(f.itm),
        "format": fmt,
        "hero_pid": int(f.hero_pid),
        "hands_per_level": int(f.hands_per_level),
        "code": _code_identity(),
        "profiles": profiles,
    }


def _dynamic_players(f):
    tilt = copy.deepcopy(getattr(getattr(f, "tilt", None), "state", {}) or {})
    out = {}
    for pid, p in sorted(f.players.items()):
        out[str(pid)] = {
            "stack": int(p.get("stack", 0) or 0),
            "table": p.get("table"),
            "seat": p.get("seat"),
            "alive": bool((p.get("stack", 0) or 0) > 0),
            "tilt": tilt.get(str(pid), {}),
        }
    return out


def _tables(f):
    out = {}
    for tid, tb in sorted(f.tables.items()):
        out[str(tid)] = {
            "button": tb.button,
            "button_seat": tb.dealer_seat(),
            "sb_seat": getattr(tb, "sb_seat", None),
            "bb_seat": getattr(tb, "bb_seat", None),
            "hands": int(tb.hands),
            "pids": [int(p["pid"]) for p in tb.players],
            "seats": list(tb.seats),
        }
    return out


def parse_bot_log(text):
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def read_bot_round(path, hand_no):
    out = []
    try:
        with open(path, encoding="utf-8") as fp:
            for line in fp:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if int(row.get("hand_no", -1)) == int(hand_no):
                    out.append(row)
    except OSError:
        pass
    return out


def emit_round(st, f, hero_hand, bot_hands=None, source="live"):
    """Durably spool one completed tournament round and wake async sync."""
    cfg = _load_config()
    if not cfg:
        return None

    sid = _session_id(st)
    d = SPOOL / sid
    d.mkdir(parents=True, exist_ok=True)

    manifest_path = d / "manifest.json"
    if not manifest_path.exists():
        _atomic_json(manifest_path, _manifest(st, f))

    hand_no = int(getattr(f, "hand_no", 0) or 0)
    bundle = {
        "schema": "t2_tournament_round_v1",
        "session_id": sid,
        "source": source,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "code": _code_identity(),
        "hand_no": hand_no,
        "level": int(f.level),
        "blinds": list(f.blinds()),
        "field_status": copy.deepcopy(f.status()),
        "players_after": _dynamic_players(f),
        "tables_after": _tables(f),
        "busted_order": list(f.busted_order),
        # HERO-table book is tournament-persistent today. Other-table books are
        # recorded per hand below, which also makes a missing persistence boundary visible.
        "hero_book_after": copy.deepcopy(st.get("book") or {}),
        "hero_hand": copy.deepcopy(hero_hand),
        "bot_hands": list(copy.deepcopy(bot_hands or [])),
    }

    path = d / ("round_%06d.json" % hand_no)
    _atomic_json(path, _json_safe(bundle))
    _ensure_worker()
    _WAKE.set()
    return str(path)


def _atomic_json(path, obj):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _run(args, cwd=None, timeout=60):
    return subprocess.run(
        args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=timeout, check=False)


def _sanitize_remote(remote):
    # Never persist credentials embedded in an https URL into logs/status.
    if not isinstance(remote, str):
        return remote
    if remote.startswith("https://") and "@" in remote:
        return "https://" + remote.split("@", 1)[1]
    return remote


def _ensure_clone(cfg):
    wd = Path(os.path.expanduser(str(cfg.get("workdir") or "~/t2_telemetry_live")))
    branch = str(cfg.get("branch") or "telemetry/live")
    source_repo = cfg.get("source_repo")
    source_repo = (Path(os.path.expanduser(str(source_repo))).resolve()
                   if source_repo else None)

    # Preferred path on Termux: use the user's existing ~/t2 repository as the
    # git owner and create a worktree. This reuses the exact same remote/auth
    # configuration that already makes git fetch/pull work for the player.
    if source_repo and (source_repo / ".git").exists():
        wd.parent.mkdir(parents=True, exist_ok=True)
        r = _run(["git", "-C", str(source_repo), "fetch", "origin", branch],
                 timeout=60)
        if r.returncode:
            raise RuntimeError("git fetch failed: " + r.stdout[-500:])

        if not (wd / ".git").exists():
            if wd.exists():
                shutil.rmtree(wd)
            r = _run([
                "git", "-C", str(source_repo), "worktree", "add",
                "-B", branch, str(wd), "origin/" + branch
            ], timeout=120)
            if r.returncode:
                raise RuntimeError("git worktree add failed: " + r.stdout[-700:])
        else:
            _run(["git", "reset", "--hard", "origin/" + branch], cwd=str(wd))
    else:
        # Portable fallback used by CI or non-worktree installations.
        remote = _sanitize_remote(cfg.get("remote"))
        if not remote:
            raise RuntimeError("telemetry source_repo/remote missing")
        if not (wd / ".git").exists():
            wd.parent.mkdir(parents=True, exist_ok=True)
            r = _run(["git", "clone", "--depth", "1", "--single-branch",
                      "--branch", branch, remote, str(wd)], timeout=120)
            if r.returncode:
                raise RuntimeError("git clone failed: " + r.stdout[-500:])
        else:
            r = _run(["git", "fetch", "origin", branch], cwd=str(wd), timeout=60)
            if r.returncode:
                raise RuntimeError("git fetch failed: " + r.stdout[-500:])
            _run(["git", "reset", "--hard", "origin/" + branch], cwd=str(wd))

    _run(["git", "config", "user.name", "T2 Telemetry"], cwd=str(wd))
    _run(["git", "config", "user.email", "t2-telemetry@local"], cwd=str(wd))
    return wd, branch


def _pending_files():
    if not SPOOL.exists():
        return []
    manifests = sorted(SPOOL.glob("*/manifest.json"))
    rounds = sorted(SPOOL.glob("*/round_*.json"))
    return manifests + rounds


def _sync_once():
    cfg = _load_config()
    if not cfg:
        return False
    files = _pending_files()
    if not files:
        return False

    wd, branch = _ensure_clone(cfg)
    copied = []
    for src in files:
        sid = src.parent.name
        dst = wd / "telemetry" / sid / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append((src, dst))

    r = _run(["git", "add", "telemetry"], cwd=str(wd))
    if r.returncode:
        raise RuntimeError("git add failed: " + r.stdout[-500:])

    diff = _run(["git", "diff", "--cached", "--quiet"], cwd=str(wd))
    if diff.returncode != 0:
        latest = max((p for p, _ in copied if p.name.startswith("round_")),
                     default=None)
        msg = "telemetry sync"
        if latest is not None:
            msg = "telemetry " + latest.parent.name + " " + latest.stem
        r = _run(["git", "commit", "-m", msg], cwd=str(wd))
        if r.returncode:
            raise RuntimeError("git commit failed: " + r.stdout[-500:])

        r = _run(["git", "push", "origin", "HEAD:" + branch],
                 cwd=str(wd), timeout=120)
        if r.returncode:
            raise RuntimeError("git push failed: " + r.stdout[-700:])

    # Remote now contains identical bytes. Remove local spool copies.
    for src, _dst in copied:
        try:
            src.unlink()
        except OSError:
            pass
    for d in sorted(SPOOL.glob("*")):
        try:
            d.rmdir()
        except OSError:
            pass

    with _LOCK:
        _STATUS["uploaded"] += sum(
            1 for src, _ in copied if src.name.startswith("round_"))
        _STATUS["last_success"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        _STATUS["last_error"] = None
    return True


def _worker():
    with _LOCK:
        _STATUS["worker_alive"] = True
    try:
        while True:
            _WAKE.wait(30.0)
            _WAKE.clear()
            try:
                while _sync_once():
                    pass
            except Exception as e:
                with _LOCK:
                    _STATUS["last_error"] = "%s: %s" % (type(e).__name__, e)
                # Keep spool files. A later round or restart retries them.
                time.sleep(2.0)
    finally:
        with _LOCK:
            _STATUS["worker_alive"] = False


def _ensure_worker():
    global _THREAD
    if not enabled():
        return
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _THREAD = threading.Thread(
            target=_worker, name="t2-telemetry-sync", daemon=True)
        _THREAD.start()


def start():
    """Start retry worker at server boot so old spool is retried immediately."""
    if enabled():
        _ensure_worker()
        _WAKE.set()
    return status()
