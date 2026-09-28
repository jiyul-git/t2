#!/usr/bin/env python3
"""Generate the GTOpen preflop configs used by the T2 architecture/perf audit.

Base = the committed 9-max 30bb DB pilot (tools/run_gtopen_9max_db_pilot.py):
9 seats, posts SB 0.5 / BB 1, uniform ante 1/9bb (near-BBA), open 2bb (SB 2.5bb),
3bet x3.0 IP / x3.5 blinds, 4bet+ x2.2, jam always offered, jam threshold 85%.
Variants only change the ACTION MENU (raise cap, size menus, limp) so tree-size
and runtime effects of each menu decision can be measured separately.
"""
import copy, json, os, sys

POS = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"]


def base(stack=30.0, max_raises=2, realization="static"):
    per_open = [[2.0] for _ in POS]
    per_open[7] = [2.5]
    return {
        "positions": POS, "stack": stack, "posts": [0, 0, 0, 0, 0, 0, 0, 0.5, 1.0],
        "ante": 1.0 / 9.0, "limp": False, "open_raises": [2.0], "raise_mults": [3.0],
        "max_raises": max_raises, "add_allin": True, "allin_threshold": 0.85,
        "rake_pct": 0.0, "rake_cap": 0.0, "no_flop_no_drop": True,
        "realization": realization, "call_only_seats": [],
        "open_raises_by_seat": per_open,
        "raise_mults_by_seat": [[3.0]] * 7 + [[3.5], [3.5]],
        "fourbet_mults": [2.2], "fourbet_mults_by_seat": [[2.2] for _ in POS],
    }


def variants():
    out = {}
    for mr in (2, 3, 4, 5):
        out["mr%d" % mr] = base(max_raises=mr)
    c = base(max_raises=4); c["open_raises_by_seat"] = [[2.0, 2.5]] * 7 + [[2.5, 3.5], []]
    out["mr4_open2"] = c
    c = base(max_raises=4); c["raise_mults_by_seat"] = [[2.5, 3.0]] * 7 + [[3.5, 4.5], [3.5, 4.5]]
    out["mr4_3bet2"] = c
    c = base(max_raises=4); c["fourbet_mults_by_seat"] = [[2.0, 2.4] for _ in POS]
    out["mr4_4bet2"] = c
    # SB-only limp is not expressible (limp flag is global): measure global limp.
    c = base(max_raises=4); c["limp"] = True
    out["mr4_limp_all"] = c
    c = base(max_raises=2); c["limp"] = True
    out["mr2_limp_all"] = c
    for st in (20.0, 25.0, 40.0):
        out["mr4_%dbb" % st] = base(stack=st, max_raises=4)
    return out


if __name__ == "__main__":
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    for k, v in variants().items():
        json.dump(v, open(os.path.join(d, k + ".json"), "w"), indent=1)
    print(" ".join(sorted(variants())))
