#!/usr/bin/env python3
"""Targeted verifier for per-opponent postflop range preservation.

No simulation baseline is modified.  This checks wiring/invariants only.
"""
import plan as PL
import session as SE


def check_current_street_actions():
    h = object.__new__(SE.HandRun)
    h.full_log = [('flop', 3, 'check', 0)]
    h._pot_at = {'flop': 200}
    cur = [(1, 'bet', 100), (2, 'call', 100)]
    a1 = SE.HandRun._acts_of(h, 1, current_street='flop', current_log=cur)
    a2 = SE.HandRun._acts_of(h, 2, current_street='flop', current_log=cur)
    assert a1[-1][0:2] == ('flop', 'bet'), a1
    assert abs(a1[-1][2] - 0.50) < 1e-9, a1
    # caller puts 100 into the 300 pot that exists after the bet
    assert a2[-1][0:2] == ('flop', 'call'), a2
    assert abs(a2[-1][2] - (100/300)) < 1e-9, a2
    return a1, a2


def check_distinct_pools_reach_equity():
    r1 = [('As', 'Ah'), ('Ks', 'Kh')]
    r2 = [('2c', '3c'), ('4c', '5c')]
    union = sorted(set(r1 + r2))
    opp = {1: r1, 2: r2}

    seen = {}
    orig = PL.bot.equity_vs_combos
    try:
        def fake(hero, board, pools, sims=500, seed=None):
            seen['pools'] = [list(x) for x in pools]
            return 0.5
        PL.bot.equity_vs_combos = fake
        out = PL._eq_vs(['Qh','Qd'], ['7c','8d','9s'], union, 2,
                        sims=10, opp_ranges=opp)
    finally:
        PL.bot.equity_vs_combos = orig

    assert out == 0.5
    assert seen['pools'][0] != seen['pools'][1], seen
    assert len(seen['pools']) == 2, seen
    return seen['pools']


def check_signature_detects_same_union_redistribution():
    a = {1: [('As','Ah')], 2: [('2c','3c')]}
    b = {1: [('2c','3c')], 2: [('As','Ah')]}
    assert sorted(set(a[1] + a[2])) == sorted(set(b[1] + b[2]))
    sa = PL._opp_ranges_signature(a)
    sb = PL._opp_ranges_signature(b)
    assert sa != sb, (sa, sb)
    return sa, sb


def main():
    a1, a2 = check_current_street_actions()
    pools = check_distinct_pools_reach_equity()
    sa, sb = check_signature_detects_same_union_redistribution()

    print("PASS current-street action visibility")
    print("  bettor:", a1[-1])
    print("  caller:", a2[-1])
    print("PASS distinct opponent pools reach equity")
    print("  pool sizes:", [len(x) for x in pools])
    print("PASS per-opponent signature catches redistribution with unchanged union")
    print("  signatures differ:", sa != sb)
    print("3/3 structural checks passed")


if __name__ == '__main__':
    main()
