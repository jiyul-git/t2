#!/usr/bin/env python3
"""Play the real UI/API at a 100-entry tournament final table.

This is an end-to-end wiring test, not a strategy test:
- keep entries=100 / ITM=15 / total chips=3,000,000
- collapse the live field to 9 survivors
- launch the actual UI HTTP server
- play HERO decisions through /api/step-stream
- ACK every streamed motion before the next bot calculation
- while the stream is blocked waiting for ACK, query settings/history/memos
  from separate HTTP connections and measure their latency
"""

import http.client
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

RUN = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/t2_final_table_play").resolve()
PORT = int(os.environ.get("T2_PLAYTEST_PORT", "18765"))
HOST = "127.0.0.1"

if not (RUN / "ui_server.py").exists():
    raise SystemExit("run dir missing ui_server.py: %s" % RUN)

sys.path.insert(0, str(RUN))
os.chdir(RUN)
os.environ.pop("T2_LIVE_STATE", None)
os.environ.setdefault("T2_BOT_LOG", "0")

import fieldsim as FS
import live2 as L


def jreq(method, path, body=None, timeout=5.0):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    t0 = time.perf_counter()
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    dt = time.perf_counter() - t0
    conn.close()
    try:
        obj = json.loads(raw.decode() or "{}")
    except Exception:
        obj = {"_raw": raw.decode(errors="replace")}
    return resp.status, obj, dt


def make_final_table():
    # Real 100-entry tournament context, not entries=9.
    f = FS.Field(
        entries=100,
        start_stack=30000,
        hero_pid=0,
        seed=20260927,
        hands_per_level=12,
        itm_frac=0.15,
        fmt="standard",
    )

    # Sum = 3,000,000 = original 100 * 30,000 chips.
    survivor_stacks = {
        0: 320000,  # HERO
        1: 600000,
        2: 500000,
        3: 420000,
        4: 360000,
        5: 280000,
        6: 220000,
        7: 180000,
        8: 120000,
    }
    for pid, p in f.players.items():
        p["stack"] = int(survivor_stacks.get(pid, 0))

    f._collect_busts()
    f._balance(notify=False)

    # Late-tournament blind level: 5k/10k on the current schedule.
    f.hand_no = 180
    f.advance_level()
    f.notes = []

    alive = [p for p in f.players.values() if p["stack"] > 0]
    active_tables = [tb for tb in f.tables.values() if tb.n() > 0]

    assert f.entries == 100
    assert f.itm == 15
    assert f.remaining() == 9
    assert len(active_tables) == 1
    assert sum(p["stack"] for p in alive) == 3000000
    assert f.players[f.hero_pid]["stack"] > 0

    st = {
        "field": L._dump(f),
        "actions": [],
        "decisions": [],
        "hand_seed": None,
        "seed": f.seed,
        "hero_memos": {},
        "notes": [],
        "busted": False,
        "rank": None,
    }
    L.save(st)
    sb, bb = f.blinds()
    return {
        "entries": f.entries,
        "remaining": f.remaining(),
        "itm": f.itm,
        "hand_no": f.hand_no,
        "level": f.level,
        "sb": sb,
        "bb": bb,
        "hero_stack": f.players[f.hero_pid]["stack"],
    }


def pick_action(payload):
    v = (payload or {}).get("view") or {}
    legal = v.get("legal") or {}
    if legal.get("check"):
        return "check", 0
    if legal.get("call") is not None:
        return "call", 0
    if legal.get("fold"):
        return "fold", 0
    rr = legal.get("raise")
    if rr:
        return rr.get("kind") or "raise", int(rr.get("min_to") or 0)
    raise RuntimeError("no legal HERO action: %r" % legal)


def wait_server(proc):
    last = None
    for _ in range(120):
        if proc.poll() is not None:
            break
        try:
            status, obj, dt = jreq("GET", "/api/stats", timeout=0.5)
            if status == 200:
                return dt
            last = (status, obj)
        except Exception as e:
            last = repr(e)
        time.sleep(0.05)
    raise RuntimeError("server did not become ready: %r" % (last,))


def stream_step(payload, metrics):
    action, amount = pick_action(payload)
    token = payload.get("token")
    if not token:
        raise RuntimeError("decision payload has no token")

    conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
    body = json.dumps({
        "action": action,
        "amount": int(amount or 0),
        "token": token,
    }).encode()

    t_req = time.perf_counter()
    conn.request(
        "POST",
        "/api/step-stream",
        body=body,
        headers={"Content-Type": "application/json"},
    )
    resp = conn.getresponse()
    if resp.status != 200:
        raw = resp.read().decode(errors="replace")
        conn.close()
        raise RuntimeError("step-stream %s: %s" % (resp.status, raw))

    stream_id = None
    final = None
    last_ack_at = t_req
    events_this_step = 0

    while True:
        raw = resp.readline()
        if not raw:
            break
        obj = json.loads(raw.decode())
        typ = obj.get("type")

        if typ == "stream_start":
            stream_id = obj.get("stream_id")
            continue

        if typ == "error":
            raise RuntimeError("stream error: %s" % obj.get("error"))

        if typ == "final":
            final = obj.get("payload")
            break

        if typ != "bot_action":
            continue

        if not stream_id:
            raise RuntimeError("bot event before stream_start")

        now = time.perf_counter()
        metrics["compute_gaps"].append(now - last_ack_at)
        events_this_step += 1
        metrics["events"] += 1

        # The server is now blocked in _stream_gate_wait(). These read-only
        # requests must still complete promptly on independent connections.
        for ep in ("/api/tournament", "/api/history", "/api/memos"):
            st, _obj, dt = jreq("GET", ep, timeout=3.0)
            if st != 200:
                raise RuntimeError("%s returned HTTP %s" % (ep, st))
            metrics["read_latency"].setdefault(ep, []).append(dt)

        # Deliberately hold the ACK briefly. If the server were still
        # single-threaded, the reads above would have stalled here.
        time.sleep(0.05)

        seq = int(obj.get("seq") or 0)
        st, ack, ack_dt = jreq(
            "POST",
            "/api/step-ack",
            {"stream_id": stream_id, "seq": seq},
            timeout=3.0,
        )
        if st != 200 or not ack.get("ok"):
            raise RuntimeError("ACK failed: HTTP %s %r" % (st, ack))
        metrics["ack_latency"].append(ack_dt)
        last_ack_at = time.perf_counter()

    conn.close()
    if final is None:
        raise RuntimeError("stream ended without final payload")

    metrics["hero_steps"] += 1
    metrics["events_per_step"].append(events_this_step)
    return final


def main():
    meta = make_final_table()
    print("FINAL TABLE FIXTURE", json.dumps(meta, sort_keys=True))

    env = os.environ.copy()
    env["IP"] = HOST
    env["PORT"] = str(PORT)
    env["T2_BOT_LOG"] = "0"
    proc = subprocess.Popen(
        [sys.executable, "ui_server.py", "--port", str(PORT)],
        cwd=str(RUN),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )

    metrics = {
        "hero_steps": 0,
        "events": 0,
        "events_per_step": [],
        "compute_gaps": [],
        "ack_latency": [],
        "read_latency": {},
    }

    try:
        startup = wait_server(proc)
        print("SERVER READY %.4fs" % startup)

        st, payload, state_dt = jreq("GET", "/api/state", timeout=30.0)
        if st != 200:
            raise RuntimeError("/api/state failed: %s %r" % (st, payload))
        print("INITIAL STATE %.4fs type=%s" % (
            state_dt, ((payload.get("view") or {}).get("type"))))

        # Play enough HERO decisions to exercise multiple post-HERO bot actions.
        guard = 0
        while metrics["events"] < 10 and metrics["hero_steps"] < 12:
            guard += 1
            if guard > 30:
                break

            v = (payload or {}).get("view") or {}
            typ = v.get("type")

            if typ == "decision":
                payload = stream_step(payload, metrics)
                continue

            if typ == "result":
                # Start the next hand through the same public API the UI uses.
                st, payload, dt = jreq(
                    "POST",
                    "/api/step",
                    {"action": None, "amount": 0, "token": payload.get("token")},
                    timeout=30.0,
                )
                if st != 200:
                    raise RuntimeError("next hand failed: %s %r" % (st, payload))
                print("NEXT HAND %.4fs" % dt)
                continue

            # Tournament may end if HERO busts very early; enough events before
            # that is still a valid wiring test.
            break

        st, stats, stats_dt = jreq("GET", "/api/stats", timeout=3.0)
        if st != 200:
            raise RuntimeError("/api/stats failed")
        counters = stats.get("counters") or {}

        if metrics["events"] <= 0:
            raise RuntimeError("no streamed bot events observed")
        if int(counters.get("motion_ack_timeout", 0) or 0) != 0:
            raise RuntimeError("motion ACK timeout: %r" % counters)
        if int(counters.get("motion_ack", 0) or 0) < metrics["events"]:
            raise RuntimeError(
                "ACK counter too small: events=%d counters=%r"
                % (metrics["events"], counters)
            )

        read_all = [
            x
            for vals in metrics["read_latency"].values()
            for x in vals
        ]
        if not read_all:
            raise RuntimeError("read-only latency was not measured")

        worst_read = max(read_all)
        if worst_read > 2.0:
            raise RuntimeError(
                "read-only UI endpoint blocked during bot compute: %.3fs" % worst_read
            )

        gaps = metrics["compute_gaps"]
        print("PLAYTEST OK")
        print("  hero_steps=%d streamed_events=%d events_per_step=%r"
              % (metrics["hero_steps"], metrics["events"], metrics["events_per_step"]))
        print("  compute_gap_s min=%.4f avg=%.4f max=%.4f"
              % (min(gaps), sum(gaps)/len(gaps), max(gaps)))
        print("  ack_latency_s avg=%.4f max=%.4f"
              % (sum(metrics["ack_latency"])/len(metrics["ack_latency"]),
                 max(metrics["ack_latency"])))
        for ep, vals in sorted(metrics["read_latency"].items()):
            print("  %s latency_s avg=%.4f max=%.4f"
                  % (ep, sum(vals)/len(vals), max(vals)))
        print("  stats_latency_s=%.4f motion_ack=%s timeout=%s"
              % (stats_dt, counters.get("motion_ack"),
                 counters.get("motion_ack_timeout")))

    finally:
        # ui_server may own a ProcessPool child whose inherited stdout pipe keeps
        # communicate() open after only the parent is terminated. Kill the whole
        # test process group so teardown cannot turn a successful playtest red.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, _ = proc.communicate(timeout=5)
        print("--- ui_server tail ---")
        lines = (out or "").splitlines()
        print("\n".join(lines[-80:]))


if __name__ == "__main__":
    main()
