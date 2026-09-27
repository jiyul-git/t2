#!/usr/bin/env python3
"""Baseline field/persona difficulty diagnosis using the real HandRun engine.

No strategy values are changed here. We run real 100-entry fields, preserve the
actual persona vectors, and aggregate observed actions by skill tier and style.
"""
import collections
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fieldsim as FS
import persona as PS
import play
import session as SE


SEEDS = [91001, 91002, 91003]
ROUNDS = 8


def style_bucket(prof):
    """Diagnostic 2D style label. This does not affect strategy."""
    t = prof.get("temper") or {}
    loose = float(t.get("looseness", 5.0))
    aggr = float(t.get("aggression", 5.0))
    if loose >= 7.2 and aggr >= 7.8:
        return "MANIAC"
    if loose >= 5.7 and aggr >= 5.8:
        return "LAG"
    if loose >= 5.7:
        return "LOOSE_PASSIVE"
    if loose <= 3.8 and aggr <= 4.2:
        return "NIT"
    if aggr >= 5.5:
        return "TAG"
    return "TIGHT_PASSIVE"


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def fresh_counter():
    return collections.Counter()


def add_profile_dist(f, dist):
    for pid, p in f.players.items():
        if pid == f.hero_pid:
            continue
        prof = p["prof"]
        tier = PS.tier(prof)[0]
        style = style_bucket(prof)
        label = prof.get("type", "?")
        dist["tier"][tier] += 1
        dist["style"][style] += 1
        dist["label"][label] += 1
        dist["skill"].append(PS.overall_skill(prof))
        tm = prof.get("temper") or {}
        dist["loose"].append(float(tm.get("looseness", 5.0)))
        dist["aggr"].append(float(tm.get("aggression", 5.0)))


def key_views(f, pid):
    prof = f.players[int(pid)]["prof"]
    return [
        ("ALL", "ALL"),
        ("TIER", PS.tier(prof)[0]),
        ("STYLE", style_bucket(prof)),
        ("LABEL", prof.get("type", "?")),
    ]


def bump(stats, f, pid, metric, n=1):
    if int(pid) == int(f.hero_pid):
        return
    for grp, key in key_views(f, pid):
        stats[(grp, key)][metric] += n


def play_table(f, tb):
    alive = tb.ordered_alive()
    if len(alive) < 2:
        return None
    layout = tb.hand_layout()
    seats = [tb.seat_of(p["pid"]) for p in alive]
    profs = {str(tb.seat_of(p["pid"])): p["prof"] for p in alive}
    stacks = {tb.seat_of(p["pid"]): p["stack"] for p in alive}
    sb, bb = f.blinds()

    h = play.Hand(
        seats, profs, stacks, layout["button"], sb, bb, hero=None,
        seed=f.rng.randrange(10**9),
        position_map=layout["pos"],
        pre_seats=layout["pre_seats"],
        post_seats=layout["post_seats"],
        sb_seat=layout["sb"],
        bb_seat=layout["bb"])
    h.seat_pid = {tb.seat_of(p["pid"]): p["pid"] for p in alive}
    h.table_id = tb.id
    h.table_max_seat = tb.max_seat
    f.stamp(h)

    run = SE.HandRun(h)
    run.start()
    result = run.result or {}

    for p in alive:
        s = tb.seat_of(p["pid"])
        p["stack"] = int(h.stacks.get(s, p["stack"]))

    tb.advance_button()
    tb.hands += 1
    return {
        "log": list(result.get("full_log") or []),
        "seat_pid": dict(h.seat_pid),
        "pos": dict(h.pos),
        "board": list(result.get("board") or []),
        "intents": list(getattr(h, "intents", []) or []),
    }


def analyze_hand(f, rec, stats, examples):
    rows = rec["log"]
    seat_pid = rec["seat_pid"]
    if not rows:
        return

    seats_in_hand = set(seat_pid)
    for s in seats_in_hand:
        bump(stats, f, seat_pid[s], "hands")

    by_street = collections.defaultdict(list)
    for row in rows:
        if len(row) < 4:
            continue
        st, s, a, amt = row[:4]
        by_street[st].append((int(s), str(a), amt))

    # ---------- preflop ----------
    pf = by_street.get("preflop", [])
    first = {}
    raised = False
    raise_count = 0
    last_raiser = None
    for s, a, amt in pf:
        pid = seat_pid.get(s)
        if pid is None:
            continue
        if s not in first:
            first[s] = a
            bump(stats, f, pid, "pf_opp")
            if a in ("call", "raise", "bet", "allin"):
                bump(stats, f, pid, "vpip")
            if a in ("raise", "bet", "allin"):
                bump(stats, f, pid, "pfr")
            if a == "call" and not raised:
                bump(stats, f, pid, "limp")
        if raised and a in ("fold", "call", "raise", "allin"):
            bump(stats, f, pid, "vs_raise_opp")
            if a in ("raise", "allin"):
                bump(stats, f, pid, "threebet")
            elif a == "fold":
                bump(stats, f, pid, "fold_to_pf_raise")
            elif a == "call":
                bump(stats, f, pid, "call_pf_raise")
        if a in ("raise", "bet", "allin"):
            raised = True
            raise_count += 1
            last_raiser = s

    # ---------- postflop response and aggression ----------
    aggressive_by_street = {}
    for st in ("flop", "turn", "river"):
        rr = by_street.get(st, [])
        outstanding = False
        aggr_n = 0
        for s, a, amt in rr:
            pid = seat_pid.get(s)
            if pid is None:
                continue
            bump(stats, f, pid, st + "_actions")
            if outstanding and a in ("fold", "call", "raise", "allin"):
                bump(stats, f, pid, st + "_face_bet")
                if a == "fold":
                    bump(stats, f, pid, st + "_fold_bet")
                elif a == "call":
                    bump(stats, f, pid, st + "_call_bet")
                else:
                    bump(stats, f, pid, st + "_raise_bet")
            if a in ("bet", "raise", "allin"):
                aggr_n += 1
                bump(stats, f, pid, st + "_aggr")
                outstanding = True
            elif a == "check":
                bump(stats, f, pid, st + "_check")
            # call does not close the wager for players still behind;
            # for our response-rate denominator it is enough to keep outstanding.
        aggressive_by_street[st] = aggr_n

    # ---------- cbet / barrel chain ----------
    if last_raiser is not None:
        cbetter = last_raiser
        pid = seat_pid.get(cbetter)
        chain_ok = True
        for idx, st in enumerate(("flop", "turn", "river")):
            rr = by_street.get(st, [])
            if not rr or pid is None:
                break
            prior_aggr = False
            actor_action = None
            for s, a, amt in rr:
                if s == cbetter:
                    actor_action = a
                    break
                if a in ("bet", "raise", "allin"):
                    prior_aggr = True
            if prior_aggr or actor_action is None:
                chain_ok = False
                break
            if idx == 0:
                bump(stats, f, pid, "cbet_opp")
                if actor_action in ("bet", "raise", "allin"):
                    bump(stats, f, pid, "cbet")
                else:
                    chain_ok = False
            elif idx == 1 and chain_ok:
                bump(stats, f, pid, "turn_barrel_opp")
                if actor_action in ("bet", "raise", "allin"):
                    bump(stats, f, pid, "turn_barrel")
                else:
                    chain_ok = False
            elif idx == 2 and chain_ok:
                bump(stats, f, pid, "river_barrel_opp")
                if actor_action in ("bet", "raise", "allin"):
                    bump(stats, f, pid, "river_barrel")
                else:
                    chain_ok = False

    # Capture a few extreme passive examples for later hand review.
    post = sum((by_street.get(st, []) for st in ("flop", "turn", "river")), [])
    if post and len(examples) < 30:
        ag = sum(a in ("bet", "raise", "allin") for _s, a, _amt in post)
        checks = sum(a == "check" for _s, a, _amt in post)
        if ag == 0 and checks >= 4:
            examples.append({
                "kind": "passive_postflop",
                "board": rec["board"],
                "positions": rec["pos"],
                "log": rows,
                "pids": seat_pid,
            })


def rate_line(name, c):
    return {
        "n_hands": c["hands"],
        "VPIP": round(pct(c["vpip"], c["pf_opp"]), 1),
        "PFR": round(pct(c["pfr"], c["pf_opp"]), 1),
        "3bet_vs_raise": round(pct(c["threebet"], c["vs_raise_opp"]), 1),
        "limp": round(pct(c["limp"], c["pf_opp"]), 1),
        "cbet": round(pct(c["cbet"], c["cbet_opp"]), 1),
        "turn_barrel": round(pct(c["turn_barrel"], c["turn_barrel_opp"]), 1),
        "river_barrel": round(pct(c["river_barrel"], c["river_barrel_opp"]), 1),
        "flop_fold_vs_bet": round(pct(c["flop_fold_bet"], c["flop_face_bet"]), 1),
        "turn_fold_vs_bet": round(pct(c["turn_fold_bet"], c["turn_face_bet"]), 1),
        "river_fold_vs_bet": round(pct(c["river_fold_bet"], c["river_face_bet"]), 1),
        "postflop_aggr_actions": c["flop_aggr"] + c["turn_aggr"] + c["river_aggr"],
        "postflop_actions": c["flop_actions"] + c["turn_actions"] + c["river_actions"],
    }


def main():
    stats = collections.defaultdict(fresh_counter)
    dist = {
        "tier": collections.Counter(),
        "style": collections.Counter(),
        "label": collections.Counter(),
        "skill": [], "loose": [], "aggr": [],
    }
    examples = []
    table_hands = 0
    errors = []

    for seed in SEEDS:
        f = FS.Field(entries=100, start_stack=30000, hero_pid=0,
                     seed=seed, hands_per_level=12, fmt="standard")
        add_profile_dist(f, dist)

        for _round in range(ROUNDS):
            f.hand_no += 1
            f.advance_level()
            for tid in sorted(list(f.tables)):
                tb = f.tables.get(tid)
                if tb is None or tb.n() < 2:
                    continue
                try:
                    rec = play_table(f, tb)
                except Exception as e:
                    errors.append("%s:%s seed=%s table=%s hand=%s"
                                  % (type(e).__name__, e, seed, tid, f.hand_no))
                    continue
                if rec:
                    table_hands += 1
                    analyze_hand(f, rec, stats, examples)
            f._collect_busts()
            f._balance(notify=False)

    if errors:
        print("ERRORS", len(errors))
        for e in errors[:10]:
            print(" ", e)
        raise SystemExit(2)

    print("=== FIELD DISTRIBUTION ===")
    print("players=%d fields=%d table_hands=%d"
          % (len(dist["skill"]), len(SEEDS), table_hands))
    print("skill mean=%.2f median=%.2f p25=%.2f p75=%.2f"
          % (statistics.mean(dist["skill"]),
             statistics.median(dist["skill"]),
             statistics.quantiles(dist["skill"], n=4)[0],
             statistics.quantiles(dist["skill"], n=4)[2]))
    print("looseness mean=%.2f aggression mean=%.2f"
          % (statistics.mean(dist["loose"]), statistics.mean(dist["aggr"])))
    print("tier", json.dumps(dict(dist["tier"].most_common()), sort_keys=True))
    print("style", json.dumps(dict(dist["style"].most_common()), sort_keys=True))
    print("labels", json.dumps(dict(dist["label"].most_common()), sort_keys=True))

    print("\n=== OBSERVED ALL ===")
    print(json.dumps(rate_line("ALL", stats[("ALL", "ALL")]), sort_keys=True))

    for grp in ("TIER", "STYLE", "LABEL"):
        print("\n=== %s ===" % grp)
        keys = sorted(
            (k for (g, k) in stats if g == grp),
            key=lambda k: -stats[(grp, k)]["hands"])
        for k in keys:
            c = stats[(grp, k)]
            if c["hands"] < 15:
                continue
            print("%-24s %s" % (
                k, json.dumps(rate_line(k, c), sort_keys=True)))

    print("\n=== PASSIVE EXAMPLES ===")
    for x in examples[:8]:
        print(json.dumps(x, ensure_ascii=False, sort_keys=True))

    # Machine-readable summary for follow-up tuning scripts.
    out = {
        "field": {
            "players": len(dist["skill"]),
            "fields": len(SEEDS),
            "table_hands": table_hands,
            "skill_mean": statistics.mean(dist["skill"]),
            "skill_median": statistics.median(dist["skill"]),
            "tier": dict(dist["tier"]),
            "style": dict(dist["style"]),
            "label": dict(dist["label"]),
        },
        "all": rate_line("ALL", stats[("ALL", "ALL")]),
        "tier": {
            k: rate_line(k, stats[("TIER", k)])
            for k in dist["tier"]
        },
        "style": {
            k: rate_line(k, stats[("STYLE", k)])
            for k in dist["style"]
        },
    }
    Path("/tmp/field_difficulty.json").write_text(
        json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print("\nWROTE /tmp/field_difficulty.json")


if __name__ == "__main__":
    main()
