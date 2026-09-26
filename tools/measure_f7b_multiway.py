#!/usr/bin/env python3
"""Measure F7-B1 union-collapse exposure without changing production policy.

Wraps plan.update_plan during deterministic tournament fixtures and records
multiway spots where both the union range and seat-keyed ranges are available.

No production state or strategy formula is modified.
"""
import argparse
import inspect
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot
import plan as PL
import ranges as R
import tourney as T


def _q(xs, p):
    if not xs:
        return None
    ys = sorted(float(x) for x in xs)
    if len(ys) == 1:
        return ys[0]
    pos = (len(ys)-1) * p
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return ys[lo]
    w = pos-lo
    return ys[lo]*(1-w) + ys[hi]*w


def _summary(xs):
    xs = [float(x) for x in xs]
    if not xs:
        return {'n': 0}
    return {
        'n': len(xs),
        'mean': round(statistics.mean(xs), 6),
        'p50': round(_q(xs, 0.50), 6),
        'p90': round(_q(xs, 0.90), 6),
        'p99': round(_q(xs, 0.99), 6),
        'max': round(max(xs), 6),
    }


def _parse_seeds(s):
    out = []
    for part in str(s).split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a,b = part.split('-',1)
            out.extend(range(int(a), int(b)+1))
        else:
            out.append(int(part))
    return out


def run(seeds, hands):
    original = PL.update_plan
    sig = inspect.signature(original)
    rows = []
    counters = {
        'all_update_calls': 0,
        'multiway_calls': 0,
        'multiway_with_2plus_nonempty_pools': 0,
        'partial_or_empty_pool_calls': 0,
        'unequal_pool_size_calls': 0,
    }

    def wrapped(*args, **kwargs):
        bound = sig.bind_partial(*args, **kwargs)
        d = bound.arguments

        counters['all_update_calls'] += 1
        n_opp = int(d.get('n_opp') or 1)
        opp_ranges = d.get('opp_ranges')
        if n_opp > 1:
            counters['multiway_calls'] += 1

        if n_opp > 1 and isinstance(opp_ranges, dict):
            pools_all = list(opp_ranges.items())
            nonempty = [(k, list(v or [])) for k,v in pools_all if v]
            if len(nonempty) < n_opp:
                counters['partial_or_empty_pool_calls'] += 1

            if len(nonempty) >= 2:
                counters['multiway_with_2plus_nonempty_pools'] += 1
                sizes = [len(v) for _,v in nonempty]
                if len(set(sizes)) > 1:
                    counters['unequal_pool_size_calls'] += 1

                hero = d.get('hero')
                board = list(d.get('board') or [])
                my_range = list(d.get('my_range') or [])
                union = list(d.get('opp_range') or [])
                street = d.get('street')
                if hero and len(board) >= 3 and union:
                    rel_u = PL.relative_strength(hero, board, union)
                    rel_s = [
                        PL.relative_strength(hero, board, r)
                        for _,r in nonempty
                    ]
                    rel_mean = statistics.mean(rel_s)

                    adv_u = None; adv_mean = None
                    nut_u = None; nut_mean = None
                    if my_range:
                        seed = d.get('seed')
                        adv_u = R.range_advantage(
                            my_range, union, board, seed=seed)
                        adv_s = [
                            R.range_advantage(
                                my_range, r, board,
                                seed=(None if seed is None else int(seed)+i+1))
                            for i,(_,r) in enumerate(nonempty)
                        ]
                        adv_mean = statistics.mean(adv_s)
                        nut_u = R.nut_advantage(my_range, union, board)
                        nut_mean = statistics.mean(
                            R.nut_advantage(my_range, r, board)
                            for _,r in nonempty)

                    blk_u = R.blocker_score(hero, union, board)
                    blk_mean = statistics.mean(
                        R.blocker_score(hero, r, board)
                        for _,r in nonempty)
                    typ = {'flop':0.60,'turn':0.70,'river':0.78}.get(
                        street, 0.65)
                    bnet_u = R.blocker_effect(
                        hero, union, board, street, typ, False)
                    bnet_mean = statistics.mean(
                        R.blocker_effect(
                            hero, r, board, street, typ, False)
                        for _,r in nonempty)

                    rows.append({
                        'street': street,
                        'n_opp': n_opp,
                        'pool_sizes': sizes,
                        'pool_size_ratio': (
                            max(sizes)/max(1,min(sizes))),
                        'rel_union': rel_u,
                        'rel_seat_mean': rel_mean,
                        'rel_abs_delta': abs(rel_u-rel_mean),
                        'range_adv_union': adv_u,
                        'range_adv_seat_mean': adv_mean,
                        'range_adv_abs_delta': (
                            None if adv_u is None
                            else abs(adv_u-adv_mean)),
                        'nut_union': nut_u,
                        'nut_seat_mean': nut_mean,
                        'nut_abs_delta': (
                            None if nut_u is None
                            else abs(nut_u-nut_mean)),
                        'blocker_union': blk_u,
                        'blocker_seat_mean': blk_mean,
                        'blocker_abs_delta': abs(blk_u-blk_mean),
                        'blocker_net_union': bnet_u,
                        'blocker_net_seat_mean': bnet_mean,
                        'blocker_net_abs_delta': abs(bnet_u-bnet_mean),
                    })

        return original(*args, **kwargs)

    PL.update_plan = wrapped
    try:
        for sd in seeds:
            t = T.Tournament(
                entries=100, start_stack=30000, hero_seat=7,
                seed=sd, hands_per_level=200)
            for _ in range(hands):
                if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                    break
                st = t.next_hand()
                guard = 0
                while st and not st.get('done') and guard < 200:
                    st = t.submit('fold')
                    guard += 1
                t.finish_hand()
    finally:
        PL.update_plan = original

    def vals(key):
        return [r[key] for r in rows if r.get(key) is not None]

    top_rel = sorted(rows, key=lambda r:r['rel_abs_delta'], reverse=True)[:8]
    top_adv = sorted(
        [r for r in rows if r.get('range_adv_abs_delta') is not None],
        key=lambda r:r['range_adv_abs_delta'], reverse=True)[:8]

    result = {
        'seeds': seeds,
        'hands_per_seed': hands,
        'counts': counters,
        'pool_size_ratio': _summary(vals('pool_size_ratio')),
        'rel_abs_delta': _summary(vals('rel_abs_delta')),
        'range_adv_abs_delta': _summary(vals('range_adv_abs_delta')),
        'nut_abs_delta': _summary(vals('nut_abs_delta')),
        'blocker_abs_delta': _summary(vals('blocker_abs_delta')),
        'blocker_net_abs_delta': _summary(vals('blocker_net_abs_delta')),
        'top_rel_examples': top_rel,
        'top_range_adv_examples': top_adv,
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    a = ap.parse_args()

    res = run(_parse_seeds(a.seeds), a.hands)
    print(json.dumps(res, indent=2, sort_keys=True))

    c = res['counts']
    assert c['multiway_calls'] >= c['multiway_with_2plus_nonempty_pools']
    print()
    print('PASS F7-B1 measurement completed without strategy patch')
    print('NOTE: deltas are measurements, not tuning thresholds.')


if __name__ == '__main__':
    main()
