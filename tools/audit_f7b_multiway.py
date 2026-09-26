#!/usr/bin/env python3
"""F7-B multiway downstream semantics audit.

Diagnostic-only for strategy paths.  It documents places where session preserves
seat-keyed ranges but downstream planning collapses them back into a union or
one representative opponent.

The only production fix covered by this verifier is plan._eq_current's
record-only multiway tie share.
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot
import plan as PL
import ranges as R
import session as SE


def _fixture():
    board = ['2c','7d','Jh','4s','3c']
    hero = ['As','Ad']
    dead = set(board) | set(hero)

    # Seat A always beats hero: set of jacks.
    tight = [('Js','Jd')]
    used = dead | {'Js','Jd'}

    # Seat B has a wide range consisting only of hands hero beats.
    mine = bot.eval7(hero + board)
    weak = []
    for c in bot._ALLCOMBOS:
        if set(c) & used:
            continue
        if bot.eval7(list(c) + board) < mine:
            weak.append(c)
        if len(weak) >= 40:
            break
    assert len(weak) == 40, len(weak)
    union = sorted(set(tight + weak))
    return hero, board, tight, weak, union


def check_union_relative_strength_distortion():
    hero, board, tight, weak, union = _fixture()

    rel_tight = PL.relative_strength(hero, board, tight)
    rel_weak = PL.relative_strength(hero, board, weak)
    rel_union = PL.relative_strength(hero, board, union)
    equal_seat_mean = 0.5 * (rel_tight + rel_weak)

    # Exact multiway current-board share is zero: seat A always beats hero.
    exact = bot.equity_vs_combos(
        hero, board, [tight, weak], sims=200, seed=71)

    assert rel_tight == 0.0, rel_tight
    assert rel_weak == 1.0, rel_weak
    assert rel_union > 0.90, rel_union
    assert abs(equal_seat_mean - 0.50) < 1e-12, equal_seat_mean
    assert exact == 0.0, exact

    return {
        'seat_A_rel': rel_tight,
        'seat_B_rel': rel_weak,
        'equal_seat_mean_rel': equal_seat_mean,
        'union_rel': round(rel_union, 6),
        'exact_multiway_current_share': exact,
        'union_overweights_wide_range': True,
    }


def check_union_range_advantage_weighting():
    hero, board, tight, weak, union = _fixture()
    my_range = [tuple(hero)]

    a = R.range_advantage(my_range, tight, board, sims=300, seed=1)
    b = R.range_advantage(my_range, weak, board, sims=300, seed=1)
    union_adv = R.range_advantage(my_range, union, board, sims=800, seed=1)
    equal_seat = 0.5 * (a + b)

    assert a == -1.0, a
    assert b == 1.0, b
    assert abs(equal_seat) < 1e-12, equal_seat
    assert union_adv > 0.70, union_adv

    return {
        'vs_tight': a,
        'vs_wide_weak': b,
        'equal_seat_mean': equal_seat,
        'union_range_advantage': round(union_adv, 6),
        'combo_count_weighting_confirmed': True,
    }


def check_partial_pool_fallback_is_invented():
    hero, board, tight, weak, union = _fixture()

    pools = PL._normalize_opp_pools(
        union, 2, {2: tight, 3: []})

    # Current behavior silently fills the missing seat from union/fallback.
    assert len(pools) == 2, pools
    assert pools[0] == tight, pools
    assert pools[1] == union, pools

    return {
        'known_seat_n': len(pools[0]),
        'missing_seat_fallback_n': len(pools[1]),
        'fallback_is_union': True,
        'unknown_preserved': False,
    }


def check_eq_current_exact_multiway_tie():
    board = ['As','Ks','Qs','Js','Ts']
    hero = ['2c','3d']
    pools = {
        2: [('4c','5d')],
        3: [('6c','7d')],
    }
    union = [pools[2][0], pools[3][0]]

    got = PL._eq_current(
        hero, board, union, 2, sims=20, seed=11,
        opp_ranges=pools)
    assert abs(got - (1.0/3.0)) < 1e-12, got

    src = inspect.getsource(PL._eq_current)
    assert "bot._showdown_share" in src
    assert "tie*0.5" not in src.replace(" ", "")

    return {
        'three_way_board_tie_share': round(got, 6),
        'record_only': True,
        'strategy_consumer': False,
    }


def check_downstream_source_map():
    ssrc = inspect.getsource(SE.HandRun._run)
    msrc = inspect.getsource(PL.make_plan)
    rsrc = inspect.getsource(PL.refresh)
    osrc = inspect.getsource(PL.overbet_frac)
    csrc = inspect.getsource(PL.cbet_freq)
    rvsrc = inspect.getsource(PL.river_fix)

    # Upstream keeps both representations.
    assert "opp_ranges[o] = orange" in ssrc
    assert "opp_r.extend(orange)" in ssrc
    assert "opp_ranges=opp_ranges" in ssrc

    # Equity and the two repaired field-strength metrics are seat-aware.
    assert "_eq_vs(hero, board, opp_range" in msrc
    assert "opp_ranges=opp_ranges" in msrc
    assert "_decision_relative_strength(" in msrc
    assert "_decision_range_advantage(" in msrc
    assert "_eq_vs(hero, board, opp_range" in rsrc

    # Strategy metrics still consume the union.
    for needle in (
        "R.blocker_score(hero, opp_range, board)",
        "R.blocker_effect(hero, opp_range",
        "R.nut_advantage(my_range, opp_range, board)",
    ):
        assert needle in msrc, needle

    assert "_decision_relative_strength(" in rsrc
    assert "R.nut_advantage(_mr, opp_range, board)" in rsrc
    assert "_decision_range_advantage(" in rsrc
    assert "R.nut_advantage(my_range, opp_range, board)" in osrc
    assert "R.blocker_effect(hero, opp_range" in rvsrc

    # Multiway planning still chooses one representative read/stack.
    assert "_main = aggressor if" in ssrc
    assert "opp_est=_est, opp_stack_bb=_ostk" in ssrc
    assert "if opp_est:" in csrc

    return {
        'already_seat_keyed': [
            'showdown equity',
            'F8 layer equity',
            'range provenance',
        ],
        'union_strategy_consumers': [
            'blocker_score/effect',
            'nut_advantage',
            'river blocker',
            'overbet nut advantage',
        ],
        'single_main_opponent_consumers': [
            'fold/read adjustment',
            'cbet frequency',
            'overbet response read',
            'effective-stack planning',
        ],
        'strategy_fixed_in_this_patch': False,
    }



def check_joint_relative_strength_consumer():
    hero, board, tight, weak, union = _fixture()

    joint = PL.joint_relative_strength(
        hero, board, {2: tight, 3: weak}, n_opp=2,
        sims=300, seed=17)
    assert joint == 0.0, joint

    hu = PL.joint_relative_strength(
        hero, board, {3: weak}, n_opp=1,
        sims=10, seed=1)
    legacy_hu = PL.relative_strength(hero, board, weak)
    assert abs(hu - legacy_hu) < 1e-12, (hu, legacy_hu)

    missing = PL.joint_relative_strength(
        hero, board, {2: tight, 3: []}, n_opp=2,
        sims=100, seed=1)
    assert missing is None, missing

    chosen, meta = PL._decision_relative_strength(
        hero, board, union, n_opp=2,
        opp_ranges={2: tight, 3: weak}, sims=300, seed=17)
    assert chosen == 0.0, (chosen, meta)
    assert meta['source'] == 'joint_seat_pools', meta

    fallback, fmeta = PL._decision_relative_strength(
        hero, board, union, n_opp=2,
        opp_ranges={2: tight, 3: []}, sims=100, seed=1)
    assert abs(fallback - PL.relative_strength(hero, board, union)) < 1e-12
    assert fmeta['source'] == 'union_fallback_incomplete', fmeta

    msrc = inspect.getsource(PL.make_plan)
    rsrc = inspect.getsource(PL.refresh)
    dsrc = inspect.getsource(PL.decide_response)
    asrc = inspect.getsource(PL.act_with_plan)

    assert "_decision_relative_strength(" in msrc
    assert "_decision_relative_strength(" in rsrc
    assert "_decision_relative_strength(" in dsrc
    assert "opp_ranges=opp_ranges, n_opp=n_opp" in asrc

    return {
        'fixed_joint_rel': joint,
        'heads_up_parity': True,
        'missing_pool_joint': None,
        'complete_source': meta['source'],
        'incomplete_fallback_source': fmeta['source'],
        'make_plan_consumer': True,
        'refresh_consumer': True,
        'response_consumer': True,
        'range_adv_nut_blocker_unchanged': True,
    }



def check_joint_range_advantage_consumer():
    hero, board, tight, weak, union = _fixture()
    my_range = [tuple(hero)]

    joint = R.joint_range_advantage(
        my_range, {2: tight, 3: weak}, board,
        n_opp=2, sims=500, seed=1)
    assert joint == -1.0, joint

    hu = R.joint_range_advantage(
        my_range, {3: weak}, board,
        n_opp=1, sims=400, seed=9)
    hu0 = R.range_advantage(
        my_range, weak, board, sims=400, seed=9)
    assert abs(hu - hu0) < 1e-12, (hu, hu0)

    missing = R.joint_range_advantage(
        my_range, {2: tight, 3: []}, board,
        n_opp=2, sims=100, seed=1)
    assert missing is None, missing

    chosen, meta = PL._decision_range_advantage(
        my_range, board, union, n_opp=2,
        opp_ranges={2: tight, 3: weak},
        sims=500, seed=1, joint_seed=1)
    assert chosen == -1.0, (chosen, meta)
    assert meta['source'] == 'joint_seat_pools', meta

    fallback, fmeta = PL._decision_range_advantage(
        my_range, board, union, n_opp=2,
        opp_ranges={2: tight, 3: []},
        sims=100, seed=1, joint_seed=1)
    legacy = R.range_advantage(
        my_range, union, board, sims=100, seed=1)
    assert abs(fallback - legacy) < 1e-12, (fallback, legacy)
    assert fmeta['source'] == 'union_fallback_incomplete', fmeta

    msrc = inspect.getsource(PL.make_plan)
    rsrc = inspect.getsource(PL.refresh)
    assert "_decision_range_advantage(" in msrc
    assert "_decision_range_advantage(" in rsrc
    assert "R.nut_advantage(my_range, opp_range, board)" in msrc
    assert "R.nut_advantage(_mr, opp_range, board)" in rsrc

    return {
        'fixed_joint_range_adv': joint,
        'heads_up_parity': True,
        'missing_pool_joint': None,
        'complete_source': meta['source'],
        'incomplete_fallback_source': fmeta['source'],
        'make_plan_consumer': True,
        'refresh_consumer': True,
        'nut_adv_unchanged': True,
        'blocker_unchanged': True,
    }


def main():
    a = check_union_relative_strength_distortion()
    b = check_union_range_advantage_weighting()
    c = check_partial_pool_fallback_is_invented()
    d = check_eq_current_exact_multiway_tie()
    e = check_downstream_source_map()
    f = check_joint_relative_strength_consumer()
    g = check_joint_range_advantage_consumer()

    print("PASS F7-B1 union relative-strength distortion reproduced", a)
    print("PASS F7-B1 union range-advantage weighting distortion reproduced", b)
    print("PASS F7-B1 partial opponent pool currently invents union fallback", c)
    print("PASS F7-B-T record-only current-board tie share is exact", d)
    print("PASS F7-B downstream source map classified", e)
    print("PASS F7-B1A joint relative-strength consumer is isolated", f)
    print("PASS F7-B1B joint range-advantage consumer is isolated", g)
    print("7/7 F7-B diagnostic checks passed")
    print("NOTE: relative_strength + range_adv are repaired; nut/blocker/read remain audited.")


if __name__ == '__main__':
    main()
