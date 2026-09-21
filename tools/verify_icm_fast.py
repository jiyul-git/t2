#!/usr/bin/env python3
"""Verify the 9-player exact-ICM fast path against the historical recursion."""

import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import icm


PAYOUTS = [100, 62, 44, 34, 27, 22, 18, 15, 12]


def max_abs(a, b):
    return max(abs(float(x) - float(y)) for x, y in zip(a, b)) if a else 0.0


def bubble_ref(stacks, payouts, seat_idx):
    own = stacks[seat_idx]
    others = [stacks[i] for i in range(len(stacks)) if i != seat_idx] or [0]
    risk = min(own, max(others))
    if risk <= 0:
        return 1.0
    base = icm._icm_equity_reference(stacks, payouts)[seat_idx]
    up = list(stacks); up[seat_idx] = own + risk
    dn = list(stacks); dn[seat_idx] = max(0.0, own - risk)
    gain = icm._icm_equity_reference(up, payouts)[seat_idx] - base
    loss = base - icm._icm_equity_reference(dn, payouts)[seat_idx]
    if gain <= 1e-9 and loss <= 1e-9:
        return 1.0
    if gain <= 1e-9:
        return 4.0
    return max(1.0, min(4.0, loss / gain))


def main():
    rng = random.Random(20260921)
    states = [
        [30000 + i * 5000 for i in range(9)],
        [90000, 80000, 70000, 60000, 50000, 40000, 30000, 20000, 10000],
        [42000, 39000, 36000, 33000, 30000, 27000, 24000, 21000, 18000],
    ]
    for _ in range(5):
        states.append([rng.randint(12000, 90000) for _ in range(9)])

    worst_eq = 0.0
    worst_bf = 0.0
    fast_states = 0
    for stacks in states:
        safe = icm._subset_path_prune_safe(stacks, 9)
        if safe:
            fast_states += 1
        ref = icm._icm_equity_reference(stacks, PAYOUTS)
        got = icm.icm_equity(stacks, PAYOUTS)
        worst_eq = max(worst_eq, max_abs(ref, got))
        for seat in (0, 4, 8):
            a = bubble_ref(stacks, PAYOUTS, seat)
            b = icm.bubble_factor(stacks, PAYOUTS, seat)
            worst_bf = max(worst_bf, abs(a - b))

    skew = [1, 1, 1, 1, 1, 1, 1, 1, 1000000]
    if icm._subset_path_prune_safe(skew, 9):
        raise SystemExit('FAIL skewed fallback case unexpectedly marked safe')
    if icm.icm_equity(skew, PAYOUTS) != icm._icm_equity_reference(skew, PAYOUTS):
        raise SystemExit('FAIL skewed fallback differs from historical recursion')

    bench = [30000 + i * 5000 for i in range(9)]
    t0 = time.perf_counter()
    ref = icm._icm_equity_reference(bench, PAYOUTS)
    t_ref = time.perf_counter() - t0
    t0 = time.perf_counter()
    got = icm.icm_equity(bench, PAYOUTS)
    t_fast = time.perf_counter() - t0
    if max_abs(ref, got) > 1e-9:
        raise SystemExit('FAIL balanced 9-max equity mismatch > 1e-9')
    if worst_eq > 1e-8:
        raise SystemExit('FAIL equity mismatch > 1e-8: %.12g' % worst_eq)
    if worst_bf > 1e-8:
        raise SystemExit('FAIL BF mismatch > 1e-8: %.12g' % worst_bf)

    print('PASS 9-player ICM fast path')
    print('states=%d fast_path=%d worst_equity_diff=%.12g worst_bf_diff=%.12g'
          % (len(states), fast_states, worst_eq, worst_bf))
    print('balanced9 equity reference=%.4fs fast=%.4fs speedup=%.1fx'
          % (t_ref, t_fast, t_ref / max(t_fast, 1e-9)))


if __name__ == '__main__':
    main()
