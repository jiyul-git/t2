#!/usr/bin/env python3
"""Unified read-only lookup across canonical v2 spots and the legacy 616-row DB.

The legacy DB is intentionally NOT migrated or rewritten here.  If its JSONL is
not present in the current worktree, it is read through Git with:

    git show <legacy-ref>:data/gto_db/preflop_9max_pushfold_v1.jsonl

That keeps state identity/path policy unchanged while making old and new
knowledge queryable from one command.
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from gto_db_schema import face_open_state, rfi_state, spot_key, spot_path

LEGACY_PATH = "data/gto_db/preflop_9max_pushfold_v1.jsonl"
DEFAULT_LEGACY_REF = "chatgpt/gto-reference-20260928"


def _quality_rank(sol):
    """Deterministic preference only; never relabels source quality."""
    q = sol.get("quality") or {}
    exact = 1 if q.get("exact_target_match") is True else 0
    status = str(q.get("status") or "")
    status_rank = {
        "exact": 5,
        "qualified_exact": 5,
        "qualified_near_t2_bba": 4,
        "near": 3,
        "limited": 2,
        "rejected": 0,
    }.get(status, 1)
    gap = (sol.get("solver") or {}).get("gap_total")
    try:
        gap_key = -float(gap)
    except (TypeError, ValueError):
        gap_key = float("-inf")
    # Later array position is final tie-breaker in caller.
    return exact, status_rank, gap_key


def _choose_solution(doc):
    sols = list(doc.get("solutions") or [])
    if not sols:
        return None
    return max(enumerate(sols), key=lambda x: (_quality_rank(x[1]), x[0]))[1]


def canonical_lookup(args):
    if args.scenario not in ("rfi", "face_open"):
        return None
    if not args.hero:
        raise SystemExit("--hero required for canonical rfi/face_open lookup")

    if args.scenario == "rfi":
        state = rfi_state(args.stack, args.hero)
    else:
        if not args.opener:
            raise SystemExit("--opener required for face_open")
        state = face_open_state(
            args.stack,
            args.opener,
            args.hero,
            2.5 if args.opener == "SB" else 2.0,
        )

    key = spot_key(state)
    path = spot_path(ROOT, key)
    if not path.exists():
        return {
            "status": "MISS",
            "source_layer": "canonical_v2",
            "spot_key": key,
            "state": state,
        }

    doc = json.loads(path.read_text())
    sol = _choose_solution(doc)
    if sol is None:
        return {
            "status": "MISS",
            "source_layer": "canonical_v2",
            "spot_key": key,
            "state": state,
            "reason": "spot file has no solutions",
        }

    out = {
        "status": "FOUND",
        "source_layer": "canonical_v2",
        "spot_key": key,
        "state": state,
        "quality": sol.get("quality"),
        "solver": sol.get("solver"),
    }
    if args.hand:
        pol = sol.get("strategy") or {}
        hands = pol.get("hands") or {}
        if args.hand not in hands:
            raise SystemExit(f"unknown hand class {args.hand}")
        out["hand"] = args.hand
        out["frequencies"] = [
            {"action": act, "freq": fr}
            for act, fr in zip(pol.get("actions") or [], hands[args.hand])
        ]
    return out


def _legacy_stream(ref):
    local = ROOT / LEGACY_PATH
    if local.exists():
        return local.open(), "worktree"

    refs = [ref]
    if not ref.startswith("origin/"):
        refs.append("origin/" + ref)
    for candidate in refs:
        cp = subprocess.run(
            ["git", "show", f"{candidate}:{LEGACY_PATH}"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if cp.returncode == 0:
            return io.StringIO(cp.stdout), f"git:{candidate}"
    return None, "unavailable"


def legacy_lookup(args):
    f, source = _legacy_stream(args.legacy_ref)
    if f is None:
        return {
            "status": "MISS",
            "source_layer": "legacy_v1_read_through",
            "reason": f"legacy DB unavailable from worktree or {args.legacy_ref}",
        }

    matches = []
    try:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if int((r.get("game") or {}).get("table_players", 0) or 0) != 9:
                continue
            c = r.get("conditions") or {}
            stack = c.get("prehand_stack_bb", c.get("effective_stack_bb"))
            if stack is None or abs(float(stack) - float(args.stack)) > 1e-9:
                continue
            if args.scenario and c.get("scenario") != args.scenario:
                continue
            if args.hero and c.get("hero_position") != args.hero:
                continue
            villain = c.get("shover_position") or c.get("opener_position")
            if args.villain and villain != args.villain:
                continue
            if args.opener and villain != args.opener:
                continue
            if args.ante_model and (c.get("ante") or {}).get("model") != args.ante_model:
                continue

            rec = {
                "status": "FOUND",
                "source_layer": "legacy_v1_read_through",
                "read_from": source,
                "dataset": Path(LEGACY_PATH).name,
                "spot_id": r.get("spot_id"),
                "stack_bb": stack,
                "scenario": c.get("scenario"),
                "hero_position": c.get("hero_position"),
                "villain_position": villain,
                "ante": c.get("ante"),
                "quality": r.get("quality"),
            }
            if args.hand:
                rec["hand"] = args.hand
                rec["strategy"] = ((r.get("strategy") or {}).get("hands") or {}).get(args.hand)
            matches.append(rec)
    finally:
        f.close()

    return {
        "status": "FOUND" if matches else "MISS",
        "source_layer": "legacy_v1_read_through",
        "matches": matches[: args.limit],
        "match_count": len(matches),
    }


def inventory(ref):
    canonical = len(list((ROOT / "data/gto_db/spots").glob("*/*.json")))
    f, source = _legacy_stream(ref)
    legacy = None
    if f is not None:
        try:
            legacy = sum(1 for line in f if line.strip())
        finally:
            f.close()
    return {
        "canonical_v2_spot_files": canonical,
        "legacy_v1_records": legacy,
        "legacy_read_from": source,
        "note": "counts are separate knowledge layers; they are not summed as unique semantic spots",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", type=float)
    ap.add_argument("--scenario")
    ap.add_argument("--hero")
    ap.add_argument("--opener")
    ap.add_argument("--villain")
    ap.add_argument("--hand")
    ap.add_argument("--ante-model")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--legacy-ref", default=DEFAULT_LEGACY_REF)
    ap.add_argument("--inventory", action="store_true")
    args = ap.parse_args()

    if args.inventory:
        print(json.dumps(inventory(args.legacy_ref), ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.stack is None:
        raise SystemExit("--stack required unless --inventory is used")

    # Canonical normal raise-tree states take precedence only for the two
    # scenarios that have a canonical state constructor today.
    if args.scenario in ("rfi", "face_open"):
        out = canonical_lookup(args)
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0 if out.get("status") == "FOUND" else 2)

    # Push/fold and other legacy scenarios remain a distinct evidence layer.
    out = legacy_lookup(args)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if out.get("status") == "FOUND" else 2)


if __name__ == "__main__":
    main()
