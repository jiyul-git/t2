#!/usr/bin/env python3
"""F8 diagnostic: reproduce the locked-main / live-side-pot information mismatch.

This is an audit tool, not a strategy test.  It intentionally verifies that current
settlement/legal primitives are sound while the postflop decision layer lacks the
locked all-in opponent.

No production behavior is changed.
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import runner as RU
import session as SE


def pot_layers(contrib, folded=()):
    """Audit-only contribution-level decomposition matching award_pots geometry."""
    folded = set(folded or ())
    levels = sorted(set(v for v in contrib.values() if v > 0))
    out = []
    prev = 0
    for lv in levels:
        contributors = [s for s, v in contrib.items() if v >= lv]
        amount = (lv - prev) * len(contributors)
        eligible = [s for s in contributors if s not in folded]
        out.append({
            'amount': amount,
            'contributors': contributors,
            'eligible': eligible,
        })
        prev = lv
    return out


def check_layer_geometry():
    # A is locked all-in at 20.  B/C already built a 30-each side pot.
    contrib = {1: 20, 2: 50, 3: 50}
    layers = pot_layers(contrib)
    assert layers == [
        {'amount': 60, 'contributors': [1, 2, 3], 'eligible': [1, 2, 3]},
        {'amount': 60, 'contributors': [2, 3], 'eligible': [2, 3]},
    ], layers
    return layers


def check_current_street_contestable_cap():
    # Seat 2 has only 10 chips left and cannot contest seat 3's full 50 current-street
    # contribution.  The existing legal primitive correctly caps it at 10.
    r = RU.Round(None, [2, 3], {2: 10, 3: 100}, 10,
                 current_bet=50, contrib={2: 0, 3: 50})
    assert r.to_call(2) == 10, r.to_call(2)
    assert r.contestable_contrib(2) == 10, r.contestable_contrib(2)
    return r.to_call(2), r.contestable_contrib(2)


def check_postflop_locked_opponent_gap():
    # Previous-street state:
    #   seat 1: all-in, total 20
    #   seats 2/3: live, total 50 each
    # Current session code forms the next-street Round only from positive-stack
    # active seats while pot_now still sums every cumulative contribution.
    live = [1, 2, 3]
    stacks = {1: 0, 2: 100, 3: 100}
    contrib = {1: 20, 2: 50, 3: 50}

    active = [x for x in live if stacks[x] > 0]
    r2 = RU.Round(None, active, stacks, 10)
    pot_now = sum(contrib.values())

    assert active == [2, 3], active
    assert r2.live() == [2, 3], r2.live()
    assert pot_now == 120, pot_now
    assert 1 not in r2.live()
    assert contrib[1] > 0

    # Lock this to the actual production wiring, not only the reconstructed fixture.
    src = inspect.getsource(SE.HandRun._run)
    assert "active = [x for x in live if h.stacks[x] > 0]" in src
    assert "pot_now = sum(contrib.values()) + dead" in src
    assert "for o in r2.live():" in src
    assert "n_opp = len(r2.live())-1" in src

    return {
        'pot_now': pot_now,
        'active_equity_seats': r2.live(),
        'locked_allin_missing_from_equity': 1,
    }


def check_d1_provenance():
    # Previous street: all three reached 20, seat 1 is locked all-in.
    # Current street: seats 2/3 each reached 50 total. Dead money belongs to main only.
    prior = {1: 20, 2: 20, 3: 20}
    current = {2: 30, 3: 30}
    stacks = {1: 0, 2: 100, 3: 100}
    layers = SE._decision_pot_layers(
        prior, current, folded=set(), stacks=stacks, hero=2, dead=5)

    assert layers == [
        {
            'level': 20.0,
            'amount': 65.0,
            'contributors': [1, 2, 3],
            'eligible_seats': [1, 2, 3],
            'hero_eligible': True,
            'locked_allin_seats': [1],
            'active_seats': [2, 3],
            'locked_allin_opponents': [1],
            'active_opponents': [3],
        },
        {
            'level': 50.0,
            'amount': 60.0,
            'contributors': [2, 3],
            'eligible_seats': [2, 3],
            'hero_eligible': True,
            'locked_allin_seats': [],
            'active_seats': [2, 3],
            'locked_allin_opponents': [],
            'active_opponents': [3],
        },
    ], layers

    # Facing an unmatched current-street wager, the upper contribution layer exists
    # before hero acts but hero is not yet eligible for it.  D1 must preserve that.
    pending = SE._decision_pot_layers(
        prior, {3: 30}, folded=set(), stacks=stacks, hero=2, dead=0)
    assert pending[-1]['amount'] == 30.0, pending
    assert pending[-1]['eligible_seats'] == [3], pending
    assert pending[-1]['hero_eligible'] is False, pending

    src = inspect.getsource(SE.HandRun._run)
    assert "_pot_layers = _decision_pot_layers(" in src
    assert "'pot_layers': _pot_layers" in src

    return layers, pending


def main():
    layers = check_layer_geometry()
    tc, contestable = check_current_street_contestable_cap()
    gap = check_postflop_locked_opponent_gap()
    d1, pending = check_d1_provenance()

    print("PASS settlement geometry distinguishes main and side layers", layers)
    print("PASS current-street contestable cap is sound",
          {'to_call': tc, 'contestable_contrib': contestable})
    print("PASS F8 gap reproduced: cumulative pot includes locked all-in chips")
    print("     while current postflop opponent pools exclude that seat", gap)
    print("PASS F8-D1 decision-time pot-layer provenance is wired", d1)
    print("     pending upper layer keeps hero ineligible before call", pending[-1])
    print("4/4 F8 diagnostic checks passed")
    print("NOTE: the gap reproduction PASS confirms the architecture defect;")
    print("      D1 only records pot layers and does not change strategy.")


if __name__ == '__main__':
    main()
