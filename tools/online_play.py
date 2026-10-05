#!/usr/bin/env python3
"""Tiny interactive client for the T2 online-server prototype.

Usage:
  export T2_DEV_TOKEN=...
  python3 tools/online_play.py

Commands:
  f / fold
  c / call
  k / check
  r 1400 / raise 1400
  b 800 / bet 800
  a / allin
  n / next
  s / state
  q / quit
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = (os.getenv("T2_ONLINE_URL") or "http://127.0.0.1:8000").rstrip("/")
AUTH = (os.getenv("T2_DEV_TOKEN") or "").strip()


def request(method: str, path: str, body=None):
    headers = {"Authorization": f"Bearer {AUTH}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"detail": raw}
        print(f"[HTTP {exc.code}] {json.dumps(payload, ensure_ascii=False)}")
        return None


def state():
    return request("GET", "/v1/game/state")


def show(payload):
    if not payload:
        return
    view = payload.get("view")
    if view:
        print()
        print(view)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    summary = payload.get("summary") or {}
    print(
        "\n[online] "
        f"phase={payload.get('phase')} "
        f"hand={summary.get('hand_no')} "
        f"remaining={summary.get('remaining')} "
        f"stack={summary.get('hero_stack')}"
    )


def current_token():
    s = state()
    if not s or not s.get("exists"):
        return None, s
    return s.get("token"), s


def send_action(action, amount=0):
    token, s = current_token()
    if not token:
        show(s)
        return
    out = request(
        "POST",
        "/v1/game/action",
        {"token": token, "action": action, "amount": int(amount or 0)},
    )
    show(out)


def next_hand():
    token, s = current_token()
    if not token:
        show(s)
        return
    show(request("POST", "/v1/game/next", {"token": token}))


def new_game():
    show(request("POST", "/v1/game/new", {"start_stack": 30000}))


def main():
    if not AUTH:
        print("T2_DEV_TOKEN is not set.")
        print("export T2_DEV_TOKEN='your-dev-token'")
        return 2

    s = state()
    if not s or not s.get("exists"):
        print("No online game. Creating a 9-max game...")
        new_game()
    else:
        show(s)

    while True:
        try:
            raw = input("\nT2> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue

        parts = raw.lower().split()
        cmd = parts[0]

        if cmd in {"q", "quit", "exit"}:
            break
        if cmd in {"s", "state"}:
            show(state())
            continue
        if cmd in {"n", "next"}:
            next_hand()
            continue
        if cmd in {"new", "restart"}:
            new_game()
            continue
        if cmd in {"f", "fold"}:
            send_action("fold")
            continue
        if cmd in {"c", "call"}:
            send_action("call")
            continue
        if cmd in {"k", "check"}:
            send_action("check")
            continue
        if cmd in {"a", "allin", "all-in"}:
            send_action("allin")
            continue
        if cmd in {"r", "raise", "b", "bet"}:
            if len(parts) != 2:
                print("amount required, e.g. r 1400 or b 800")
                continue
            try:
                amount = int(parts[1].replace(",", ""))
            except ValueError:
                print("amount must be an integer")
                continue
            send_action("raise" if cmd in {"r", "raise"} else "bet", amount)
            continue

        print("commands: f c k r <amount> b <amount> a n s new q")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
