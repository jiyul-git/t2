#!/usr/bin/env python3
"""Print canonical poker decision-event classes.

This is a design/audit matrix, not a simulator and not production strategy.
It enumerates the finite strategic state classes while allowing raise recursion.
"""

STREETS = ("preflop", "flop", "turn", "river")

POST_STATES = [
    ("A0", "hero unacted; no wager", "check/bet"),
    ("B0", "hero unacted; faces bet", "fold/call/raise"),
    ("C0", "hero checked; faces bet", "fold/call/check-raise"),
    ("D0", "hero bet/raised; faces raise", "fold/call/re-raise"),
    ("E0", "hero called; later raise reopens action", "fold/call/backraise"),
]

OPP_EVENTS_NO_WAGER = (
    "check",
    "bet:small", "bet:normal", "bet:large", "bet:overbet", "bet:allin",
)
OPP_EVENTS_WAGER = (
    "fold", "call", "call:allin",
    "raise:small", "raise:normal", "raise:large", "raise:overbet",
    "raise:allin_full", "raise:allin_incomplete",
)

OVERLAYS = (
    "HU",
    "multiway_players_behind",
    "multiway_action_closing",
    "sidepot_live_opponent",
    "all_opponents_allin",
    "raise_right_open",
    "raise_right_closed_incomplete_allin",
)

def main():
    n=0
    print("# canonical opponent-action decision matrix")
    print()
    print("## postflop")
    for street in ("flop","turn","river"):
        for sid, state, hero_actions in POST_STATES:
            future = "no_semibluff" if street == "river" else "semibluff_available"
            print(f"{street:6} {sid} | {state:40} | hero={hero_actions:24} | {future}")
            n += 1
        print()

    print("## opponent event alphabet")
    print("no wager :", ", ".join(OPP_EVENTS_NO_WAGER))
    print("wager    :", ", ".join(OPP_EVENTS_WAGER))
    print()

    print("## legality/context overlays")
    for x in OVERLAYS:
        print(" -", x)
    print()

    print("## preflop canonical states")
    pre = [
        ("P1","unopened"),
        ("P2","limpers/no raise"),
        ("P3","face first raise"),
        ("P4","hero opened, face 3bet"),
        ("P5","hero called, later raise/squeeze"),
        ("P6","hero raised, face re-raise"),
        ("P7","face all-in / call-off"),
        ("P8","BB option after limp-around"),
    ]
    for sid,state in pre:
        print(f"{sid} | {state}")
        n += 1

    print()
    print("canonical hero decision-state rows:", n)
    print("Raise states D0/P6 are recursive after every legal full raise.")
    print("Exact chip amounts are continuous inputs and are not discretely enumerated.")
    print("No production code is imported or changed.")

if __name__ == "__main__":
    main()
