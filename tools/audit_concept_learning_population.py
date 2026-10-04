#!/usr/bin/env python3
"""Population audit for independent concept difficulty/learning structure.

Hard cap: at most 1000 generated players per run.
"""

import argparse
import json
import pathlib
import random
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS

MAX_N = 1000


def pct(xs, pred):
    return round(100.0 * sum(1 for x in xs if pred(x)) / len(xs), 1)


def q(xs, p):
    ys = sorted(float(x) for x in xs)
    if not ys:
        return 0.0
    return round(ys[min(len(ys)-1, int((len(ys)-1)*p))], 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--field-quality", type=float, default=0.78)
    args = ap.parse_args()
    n = max(1, min(MAX_N, int(args.n)))

    rr = random.Random(args.seed)
    players = [PS.make_player(rr, args.field_quality, pid=i) for i in range(n)]

    rows = []
    for concept, difficulty in PS.INDEPENDENT_CONCEPT_DIFFICULTY.items():
        xs = [float(p["concepts"][concept]) for p in players]
        rows.append({
            "concept": concept,
            "difficulty": difficulty,
            "mean": round(statistics.mean(xs), 2),
            "median": round(statistics.median(xs), 2),
            "q10": q(xs, .10),
            "q90": q(xs, .90),
            "low_0_3_pct": pct(xs, lambda x: x <= 3.0),
            "mid_4_6_pct": pct(xs, lambda x: 4.0 <= x <= 6.0),
            "high_7_10_pct": pct(xs, lambda x: x >= 7.0),
            "elite_8_10_pct": pct(xs, lambda x: x >= 8.0),
        })

    rows.sort(key=lambda r: (r["difficulty"], r["concept"]))

    hard = {}
    for pre, post in PS.HARD_CONCEPT_PREREQUISITES:
        gaps = [float(p["concepts"][post]) - float(p["concepts"][pre]) for p in players]
        hard[f"{pre}->{post}"] = {
            "max_gap": round(max(gaps), 2),
            "violations": sum(1 for g in gaps if g > PS.HARD_PREREQ_MARGIN + 1e-9),
        }

    learning = {}
    for post, pres in PS.LEARNING_PREREQUISITES.items():
        gaps = []
        for p in players:
            c = p["concepts"]
            base = sum(float(c[x]) for x in pres) / len(pres)
            gaps.append(float(c[post]) - base)
        learning[post] = {
            "prerequisites": list(pres),
            "max_gap": round(max(gaps), 2),
            "violations": sum(1 for g in gaps if g > PS.LEARNING_SUPPORT_MARGIN + 0.11),
        }

    out = {
        "n": n,
        "field_quality": args.field_quality,
        "seed": args.seed,
        "rows": rows,
        "hard_prerequisites": hard,
        "learning_prerequisites": learning,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
