#!/usr/bin/env python3
"""Rank flop-reaching preflop terminals from t2_cont_census output.

Default ranking is reach-only and is explicitly provisional.  If --impact is
provided, the ranking uses:

    priority = reach_probability * mean_abs_solved_minus_legacy_bb

Impact JSON may be either:
  {"<terminal_node>": <delta_bb>, ...}
or:
  {"terminals": [{"terminal_node": N,
                  "mean_abs_solved_minus_legacy_bb": X}, ...]}

The script never edits the census or drops outliers.
"""
import argparse
import json
from collections import defaultdict


def load_impact(path):
    if not path:
        return {}
    raw = json.load(open(path))
    if "terminals" in raw:
        out = {}
        for row in raw["terminals"]:
            out[int(row["terminal_node"])] = float(
                row["mean_abs_solved_minus_legacy_bb"]
            )
        return out
    return {int(k): float(v) for k, v in raw.items()}


def fmt_path(row):
    return " -> ".join(row.get("path_labels", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("census")
    ap.add_argument("--impact")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--hu-only", action="store_true")
    ap.add_argument("--srp-only", action="store_true")
    ap.add_argument("--exclude-current", action="store_true")
    ap.add_argument("--json-out")
    a = ap.parse_args()

    census = json.load(open(a.census))
    impact = load_impact(a.impact)
    rows = list(census["terminals"])

    if a.hu_only:
        rows = [r for r in rows if int(r["live_count"]) == 2]
    if a.srp_only:
        rows = [r for r in rows if int(r["raise_count"]) == 1]
    if a.exclude_current:
        rows = [r for r in rows if not r.get("current_injected_terminal", False)]

    for r in rows:
        node = int(r["terminal_node"])
        d = impact.get(node)
        r["_impact_bb"] = d
        r["_priority"] = (
            float(r["reach_probability"]) * d if d is not None else None
        )

    if impact:
        rows.sort(
            key=lambda r: (
                r["_priority"] is not None,
                r["_priority"] if r["_priority"] is not None else -1.0,
                float(r["reach_probability"]),
            ),
            reverse=True,
        )
    else:
        rows.sort(key=lambda r: float(r["reach_probability"]), reverse=True)

    groups = defaultdict(lambda: {"reach": 0.0, "count": 0})
    for r in census["terminals"]:
        key = f'{r["pot_type"]}/{"HU" if int(r["live_count"]) == 2 else str(r["live_count"])+"way"}'
        groups[key]["reach"] += float(r["reach_probability"])
        groups[key]["count"] += 1

    total = float(census["summary"]["total_flop_reach_probability"])
    print("=== FLOP-REACH COVERAGE ===")
    for k, v in sorted(groups.items(), key=lambda kv: kv[1]["reach"], reverse=True):
        share = v["reach"] / total if total else 0.0
        print(f'{k:14s}  terminals={v["count"]:4d}  reach={v["reach"]:.6f}  share={share:.3%}')

    print()
    print("=== TERMINAL RANKING ===")
    if not impact:
        print("PROVISIONAL: reach-only. Do not treat this as the final expansion priority.")
    else:
        print("priority = reach_probability * mean_abs_solved_minus_legacy_bb")
    print()

    shown = rows[: a.top]
    for i, r in enumerate(shown, 1):
        p = float(r["reach_probability"])
        sh = float(r["share_of_flop_reach"])
        d = r["_impact_bb"]
        score = r["_priority"]
        extra = (
            f"  delta={d:.4f}bb  score={score:.8f}"
            if d is not None
            else ""
        )
        print(
            f'{i:2d}. node={int(r["terminal_node"]):6d} '
            f'{r["pot_type"]:5s} {int(r["live_count"])}way '
            f'reach={p:.8f} flop_share={sh:.3%}{extra}'
        )
        print(f'    {fmt_path(r)}')

    if a.json_out:
        clean = []
        for r in rows:
            x = dict(r)
            x["impact_bb"] = x.pop("_impact_bb")
            x["priority_score"] = x.pop("_priority")
            clean.append(x)
        json.dump(
            {
                "schema": "t2_terminal_ranking_v1",
                "source_census": a.census,
                "impact_file": a.impact,
                "ranking": (
                    "reach_x_mean_abs_solved_minus_legacy"
                    if impact
                    else "reach_only_provisional"
                ),
                "terminals": clean,
            },
            open(a.json_out, "w"),
            indent=2,
        )


if __name__ == "__main__":
    main()
