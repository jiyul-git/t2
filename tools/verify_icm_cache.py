#!/usr/bin/env python3
"""Verify that cached production ICM is numerically identical to the old path."""

import math
import random

import icm


def oracle(stacks, payouts):
    n = len(stacks)
    k = min(len(payouts), n)
    if n == 9 and icm._subset_path_prune_safe(stacks, k):
        return icm._icm_equity_subset(stacks, payouts)
    return icm._icm_equity_reference(stacks, payouts)


def close(a, b, tol=1e-12):
    return len(a) == len(b) and all(
        math.isclose(float(x), float(y), rel_tol=tol, abs_tol=tol)
        for x, y in zip(a, b)
    )


def main():
    rng = random.Random(20260927)
    cases = []

    fixed = [
        [100] * 9,
        [300, 200, 150, 100, 80, 70, 50, 30, 20],
        [1000, 300, 100, 50, 25, 10, 5, 2, 1],
    ]
    for x in fixed:
        cases.append(x)

    for n in range(2, 10):
        for _ in range(40):
            cases.append([rng.randint(1, 200000) for _ in range(n)])

    payouts9 = [30, 20, 15, 10, 8, 6, 5, 4, 2]

    if hasattr(icm._icm_equity_cached, 'cache_clear'):
        icm._icm_equity_cached.cache_clear()

    for idx, stacks in enumerate(cases):
        payouts = payouts9[:len(stacks)]
        got = icm.icm_equity(stacks, payouts)
        want = oracle(stacks, payouts)
        if not close(got, want):
            raise SystemExit(
                'FAIL case=%d stacks=%r\n got=%r\nwant=%r'
                % (idx, stacks, got, want)
            )

        # 같은 입력을 한 번 더 호출해 실제 cache hit도 확인한다.
        got2 = icm.icm_equity(stacks, payouts)
        if not close(got2, want):
            raise SystemExit('FAIL repeat case=%d' % idx)

    info = (
        icm._icm_equity_cached.cache_info()
        if hasattr(icm._icm_equity_cached, 'cache_info')
        else None
    )
    if info is not None and info.hits < len(cases):
        raise SystemExit('FAIL cache hits too small: %r' % (info,))

    print('OK: %d ICM cases; %s' % (len(cases), info))


if __name__ == '__main__':
    main()
