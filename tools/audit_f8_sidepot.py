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



def check_d2_locked_range_preservation():
    from types import SimpleNamespace

    hr = object.__new__(SE.HandRun)
    hr.h = SimpleNamespace(
        pf_seed={1: {
            'pf_act': 'call', 'pf_role': 'defend', 'pf_vs': 'BTN',
            'pf_level': 1, 'pf_open_bb': 2.5, 'pf_n_callers': 0,
            'pf_stack_bb': 23.5,
        }},
        _start_stacks={1: 5000},
        bb=100,
        pos={1: 'BB', 2: 'BTN'},
        book=object(),
        dyn=object(),
        hole={2: ['Ah', 'Kd']},
    )
    hr._pid = lambda s: s
    hr._dseed = lambda *a, **k: 123
    hr._was_3bettor = lambda s: False
    hr._acts_of = lambda *a, **k: [('flop', 'raise', 0.75)]

    seen = {}
    old_pp = SE.RD.perceived_profile
    old_rp = SE.RD.range_profile
    old_ro = SE.PS.read_opponent
    old_pf = SE.R.preflop_range
    old_pr = SE.R.perceived_range
    old_adj = SE.RU.adjust_range_by_history
    try:
        SE.RD.perceived_profile = lambda *a, **k: {'x': 1}
        SE.RD.range_profile = lambda est: {'type': 'TAG'}
        SE.PS.read_opponent = lambda *a, **k: {'tb_polar': 0.0, 'w': 0.0}

        def fake_pf(profile, pos, action, stack_bb, dead, **kw):
            seen['stack_bb'] = stack_bb
            seen['action'] = action
            return [('As', 'Ks'), ('Qh', 'Qd')]

        def fake_perceived(base, board, acts, profile=None, actor_read=None):
            seen['acts'] = list(acts)
            return list(base)

        SE.R.preflop_range = fake_pf
        SE.R.perceived_range = fake_perceived
        SE.RU.adjust_range_by_history = (
            lambda orange, dyn, pid, board, dead=None: (orange, None))

        rnd = SimpleNamespace(log=[], action_meta=[])
        out, meta = SE.HandRun._locked_postflop_range(
            hr, 2, 1, {'type': 'TAG'}, ['2c', '7d', 'Jh'], 'turn',
            rnd, 2, 2, True)
    finally:
        SE.RD.perceived_profile = old_pp
        SE.RD.range_profile = old_rp
        SE.PS.read_opponent = old_ro
        SE.R.preflop_range = old_pf
        SE.R.perceived_range = old_pr
        SE.RU.adjust_range_by_history = old_adj

    assert seen['stack_bb'] == 23.5, seen
    assert seen['acts'] == [('flop', 'raise', 0.75)], seen
    assert out == [('As', 'Ks'), ('Qh', 'Qd')], out
    assert meta['stack_bb'] == 23.5, meta

    src = inspect.getsource(SE.HandRun._run)
    assert "locked_opp_ranges = {}" in src
    assert "locked_opp_ranges[o] = _lr" in src
    # Exact stripped source lines only.  A raw substring test here falsely matched
    # "locked_opp_ranges[o] = _lr" as if it were "opp_ranges[o] = _lr".
    src_lines = {line.strip() for line in src.splitlines()}
    assert "opp_r.extend(_lr)" not in src_lines
    assert "opp_ranges[o] = _lr" not in src_lines

    return {
        'stack_bb': meta['stack_bb'],
        'acts': meta['acts'],
        'range_n': len(out),
        'strategy_merge': False,
    }



def check_d3_layer_equities():
    # Full board makes the fixture exact rather than Monte-Carlo noisy.
    # Hero (seat 2) beats active seat 3 but loses to locked all-in seat 1.
    hero = ['Ah', 'Kd']
    board = ['2c', '7d', 'Jh', '4s', '3c']
    layers = SE._decision_pot_layers(
        {1: 20, 2: 50, 3: 50}, {}, folded=set(),
        stacks={1: 0, 2: 100, 3: 100}, hero=2, dead=0)

    active = {3: [('9s', '8s')]}
    locked = {1: [('Jc', 'Jd')]}
    eqs = SE._diagnostic_layer_equities(
        2, hero, board, layers, active, locked, sims=40)

    assert len(eqs) == 2, eqs
    assert eqs[0]['opponents'] == [1, 3], eqs
    assert eqs[0]['range_sources'] == {
        '1': 'locked_allin', '3': 'active'}, eqs
    assert eqs[0]['complete'] is True, eqs
    assert eqs[0]['equity'] == 0.0, eqs

    assert eqs[1]['opponents'] == [3], eqs
    assert eqs[1]['range_sources'] == {'3': 'active'}, eqs
    assert eqs[1]['complete'] is True, eqs
    assert eqs[1]['equity'] == 1.0, eqs

    # Missing range must stay explicitly unknown; never invent a fallback pool.
    missing = SE._diagnostic_layer_equities(
        2, hero, board, [layers[0]], active, {}, sims=40)
    assert missing[0]['complete'] is False, missing
    assert missing[0]['equity'] is None, missing
    assert missing[0]['missing_ranges'] == [1], missing

    # An unmatched upper layer before a call is not a current hero equity layer.
    pending = SE._decision_pot_layers(
        {1: 20, 2: 20, 3: 20}, {3: 30}, folded=set(),
        stacks={1: 0, 2: 100, 3: 100}, hero=2, dead=0)
    pending_eq = SE._diagnostic_layer_equities(
        2, hero, board, pending, active, locked, sims=40)
    assert pending_eq[-1]['hero_eligible'] is False, pending_eq
    assert pending_eq[-1]['equity'] is None, pending_eq
    assert pending_eq[-1]['reason'] == 'hero_not_currently_eligible', pending_eq

    src = inspect.getsource(SE.HandRun._run)
    assert "layer_equities = (" in src
    assert "'layer_equities': layer_equities" in src
    # D3 must not become a plan/action argument.
    assert "layer_equities=layer_equities" not in src
    assert "layer_equities = _pl" not in src

    return {
        'main_equity': eqs[0]['equity'],
        'main_opponents': eqs[0]['opponents'],
        'side_equity': eqs[1]['equity'],
        'side_opponents': eqs[1]['opponents'],
        'missing_is_unknown': missing[0]['equity'] is None,
        'pending_is_unknown': pending_eq[-1]['equity'] is None,
    }



def check_d4_call_ev_shadow():
    # Locked main pot is large, new side-pot wager is small.
    #
    # Before call:
    #   A locked all-in 100, hero 100, C 110 (C bet 10 this street)
    # After hero calls 10:
    #   main 300 (A/H/C), side 20 (H/C)
    #
    # Synthetic equities:
    #   main = 0.00, side = 0.20
    # Gross return = 300*0 + 20*.20 = 4
    # Incremental call cost = 10 -> chip EV = -6.
    #
    # This is the failure class scalar active-only equity can hide:
    # a huge locked main pot must not be priced using only side opponent equity.
    prior = {1: 100, 2: 100, 3: 100}
    current = {3: 10}
    stacks = {1: 0, 2: 100, 3: 90}

    call_layers, cost = SE._project_call_layers(
        prior, current, folded=set(), stacks=stacks,
        hero=2, tocall=10, dead=0)

    assert cost == 10.0, (call_layers, cost)
    assert [
        (x['amount'], x['eligible_seats'], x['hero_eligible'])
        for x in call_layers
    ] == [
        (300.0, [1, 2, 3], True),
        (20.0, [2, 3], True),
    ], call_layers

    synthetic_eq = [
        {'idx': 0, 'complete': True, 'equity': 0.0},
        {'idx': 1, 'complete': True, 'equity': 0.20},
    ]
    summary = SE._layer_call_summary(cost, call_layers, synthetic_eq)
    assert summary['complete'] is True, summary
    assert summary['contestable_after_call'] == 320.0, summary
    assert summary['gross_return'] == 4.0, summary
    assert summary['call_chip_ev'] == -6.0, summary
    assert summary['effective_equity'] == 0.0125, summary
    assert summary['breakeven_equity'] == 0.03125, summary

    # Unknown main equity must make the whole call summary unknown.
    incomplete = SE._layer_call_summary(
        cost, call_layers,
        [{'idx': 0, 'complete': False, 'equity': None},
         {'idx': 1, 'complete': True, 'equity': 0.20}])
    assert incomplete['complete'] is False, incomplete
    assert incomplete['call_chip_ev'] is None, incomplete
    assert incomplete['missing_equity_layers'] == [0], incomplete

    src = inspect.getsource(SE.HandRun._run)
    assert "call_ev_shadow = _layer_call_summary(" in src
    assert "'call_ev_shadow': call_ev_shadow" in src
    assert "_layer_call_value = None" in src
    assert "call_value=_layer_call_value" in src

    # Objective break-even enters the existing perception chain without altering
    # the legacy scalar need.  Neutral/no-concept profile keeps it exact.
    neutral = {'type': 'TAG', 'aggr': 5, 'gamble': 5, 'bluff': 5}
    n0, cn0 = SE.PL.calldown_need(
        neutral, ['Ah', 'Kd'], ['2c', '7d', 'Jh'], 'flop',
        310, 10, 1.0, None, 0, None, n_opp=1,
        rng=__import__('random').Random(1),
        objective_breakeven=summary['breakeven_equity'])
    assert round(cn0, 6) == 0.03125, (n0, cn0)
    assert round(n0, 6) == round(10/320, 6), (n0, cn0)

    # Same active-only eq would call under legacy scalar price, but layer call value folds.
    ps = {'plan': 'giveup', 'made': 0, 'rel': 0.2, 'outs': 0}
    act_layer = SE.PL.decide_response(
        neutral, ['Ah', 'Kd'], ['2c', '7d', 'Jh'], 'flop',
        'giveup', dict(ps), 0.20, 0.03125, 0, [],
        310, 10, 100, False, __import__('random').Random(2),
        allow_raise=False, call_eq=0.0125, call_need=0.03125)
    act_legacy = SE.PL.decide_response(
        neutral, ['Ah', 'Kd'], ['2c', '7d', 'Jh'], 'flop',
        'giveup', dict(ps), 0.20, 0.03125, 0, [],
        310, 10, 100, False, __import__('random').Random(2),
        allow_raise=False)
    assert act_layer[0] == 'fold', (act_layer, act_legacy)
    assert act_legacy[0] == 'call', (act_layer, act_legacy)

    # Raise producer still uses legacy eq/need: a deterministic zero roll must raise
    # even when layer call value itself would fold.
    class ZeroRng:
        def random(self): return 0.0
    value_state = {'plan': 'value_3street', 'made': 5, 'rel': 0.99,
                   'outs': 0, 'stackoff': {}}
    raised = SE.PL.decide_response(
        neutral, ['Jh', 'Jd'], ['Jc', '7d', '2c'], 'flop',
        'value_3street', value_state, 0.90, 0.20, 5, [],
        200, 20, 100, False, ZeroRng(),
        allow_raise=True, call_eq=0.01, call_need=0.20)
    fallback = SE.PL.decide_response(
        neutral, ['Jh', 'Jd'], ['Jc', '7d', '2c'], 'flop',
        'value_3street', dict(value_state), 0.90, 0.20, 5, [],
        200, 20, 100, False, ZeroRng(),
        allow_raise=False, call_eq=0.01, call_need=0.20)
    assert raised[0] == 'raise', (raised, fallback)
    assert fallback[0] == 'fold', (raised, fallback)

    return {
        'call_cost': summary['call_cost'],
        'contestable_after_call': summary['contestable_after_call'],
        'gross_return': summary['gross_return'],
        'call_chip_ev': summary['call_chip_ev'],
        'effective_equity': summary['effective_equity'],
        'breakeven_equity': summary['breakeven_equity'],
        'incomplete_stays_unknown': incomplete['call_chip_ev'] is None,
        'legacy_same_spot': act_legacy[0],
        'layer_same_spot': act_layer[0],
        'raise_with_bad_call_ev': raised[0],
        'raise_declined_bad_call_ev': fallback[0],
        'strategy_consumer': True,
    }



def check_d5_bet_outcome_shadow():
    # Locked A, hero H, active C each have 100 in the main pot.
    # Hero bets 20 into C.
    #
    # Full-board exact fixture:
    #   hero loses to locked A, but beats active C.
    #
    # If C folds:
    #   main 300 -> A/H only, hero equity 0
    #   hero's unmatched 20 -> sole-eligible return
    #   gross 20 - bet cost 20 = EV 0
    #
    # If C calls:
    #   main 300 -> A/H/C, hero equity 0
    #   side 40 -> H/C, hero equity 1
    #   gross 40 - bet cost 20 = EV +20
    #
    # This proves "C folds" does NOT mean hero wins the locked main pot.
    hero = ['Ah', 'Kd']
    board = ['2c', '7d', 'Jh', '4s', '3c']
    prior = {1: 100, 2: 100, 3: 100}
    current = {}
    stacks = {1: 0, 2: 100, 3: 100}
    active = {3: [('9s', '8s')]}
    locked = {1: [('Jc', 'Jd')]}

    fold_layers, hcost_f, tcost_f = SE._project_bet_outcome_layers(
        prior, current, set(), stacks, 2, 3, 20, 'fold')
    call_layers, hcost_c, tcost_c = SE._project_bet_outcome_layers(
        prior, current, set(), stacks, 2, 3, 20, 'call')

    assert hcost_f == 20.0 and hcost_c == 20.0, (hcost_f, hcost_c)
    assert tcost_f == 0.0 and tcost_c == 20.0, (tcost_f, tcost_c)

    assert [(x['amount'], x['eligible_seats']) for x in fold_layers] == [
        (300.0, [1, 2]), (20.0, [2])
    ], fold_layers
    assert [(x['amount'], x['eligible_seats']) for x in call_layers] == [
        (300.0, [1, 2, 3]), (40.0, [2, 3])
    ], call_layers

    fold_eq = SE._diagnostic_layer_equities(
        2, hero, board, fold_layers, active, locked, sims=40)
    call_eq = SE._diagnostic_layer_equities(
        2, hero, board, call_layers, active, locked, sims=40)

    fold_sum = SE._layer_investment_summary(hcost_f, fold_layers, fold_eq)
    call_sum = SE._layer_investment_summary(hcost_c, call_layers, call_eq)

    assert fold_eq[0]['equity'] == 0.0, fold_eq
    assert fold_eq[1]['equity'] == 1.0, fold_eq
    assert fold_sum['chip_ev'] == 0.0, fold_sum

    assert call_eq[0]['equity'] == 0.0, call_eq
    assert call_eq[1]['equity'] == 1.0, call_eq
    assert call_sum['chip_ev'] == 20.0, call_sum

    # Naive "fold wins current 300 pot" interpretation would be +300 before bet cost
    # and is explicitly not the layer result.
    assert fold_sum['gross_return'] == 20.0, fold_sum
    assert fold_sum['gross_return'] != 320.0, fold_sum

    src = inspect.getsource(SE.HandRun._run)
    assert "bet_ev_shadow = None" in src
    assert "'bet_ev_shadow': bet_ev_shadow" in src
    assert "'strategy_consumer': False" in src
    # D5-A owns conditional geometry only.  D5-B, added later, now attaches
    # a fold probability to the same shadow, so this check must not assert
    # the historical D5-A-only value False.

    return {
        'fold_layers': [(x['amount'], x['eligible_seats']) for x in fold_layers],
        'fold_chip_ev': fold_sum['chip_ev'],
        'call_layers': [(x['amount'], x['eligible_seats']) for x in call_layers],
        'call_chip_ev': call_sum['chip_ev'],
        'fold_does_not_win_locked_main': True,
        'conditional_geometry_only': True,
        'raise_branch_modeled': False,
        'strategy_consumer': False,
    }



def check_d5b_fold_probability_and_exhaustive_ev():
    # No estimate -> exact existing population prior.
    neutral = {'type': 'TAG', 'aggr': 5, 'gamble': 5, 'bluff': 5}
    p0, meta0 = SE._perceived_fold_to_bet_probability(
        neutral, None, 'river')
    assert p0 == SE.RD.PRIOR['fold_to_bet'] == 0.52, (p0, meta0)

    # Reuse the already-preregistered D5-A conditional values:
    # fold EV 0, call EV +20.
    fs = {'complete': True, 'chip_ev': 0.0}
    cs = {'complete': True, 'chip_ev': 20.0}

    # If continuation is all-in/call-only, fold/call are exhaustive.
    ex = SE._combine_fold_call_ev(p0, fs, cs, raise_possible=False)
    assert ex['complete'] is True, ex
    assert ex['p_fold'] == 0.52, ex
    assert ex['p_call'] == 0.48, ex
    assert ex['expected_chip_ev'] == 9.6, ex

    # If target has chips to raise, do not invent a raise frequency from aggression
    # or fold-to-raise.  Expected EV must remain unknown.
    blocked = SE._combine_fold_call_ev(p0, fs, cs, raise_possible=True)
    assert blocked['complete'] is False, blocked
    assert blocked['reason'] == 'raise_branch_unmodeled', blocked
    assert blocked['expected_chip_ev'] is None, blocked

    src = inspect.getsource(SE.HandRun._run)
    assert "_perceived_fold_to_bet_probability(" in src
    assert "_combine_fold_call_ev(" in src
    assert "'fold_probability_modeled': True" in src
    assert "'strategy_consumer': False" in src

    return {
        'population_prior_fold': p0,
        'allin_continue_expected_ev': ex['expected_chip_ev'],
        'raise_possible_is_unknown': blocked['expected_chip_ev'] is None,
        'raise_frequency_invented': False,
        'strategy_consumer': False,
    }


def check_d5c_response_conditioning_and_check_benchmark():
    # Use a broad deterministic range so ordinary call vs all-in continue differs.
    board = ['2c', '7d', 'Jh', '4s', '3c']
    dead = set(board)
    base = [c for c in SE.R.ALL if not (set(c) & dead)]
    ranked = SE.R._ranked(base, board)

    normal_call = SE.R.perceived_facing_bet_response(
        base, board, 'river', 0.50, profile=None, raise_possible=True)
    allin_continue = SE.R.perceived_facing_bet_response(
        base, board, 'river', 0.50, profile=None, raise_possible=False)
    short_allin_continue = SE.R.perceived_facing_bet_response(
        base, board, 'river', 0.20, profile=None, raise_possible=False)

    # A strong combo in the ordinary top-raise slice must be absent from the
    # call-only branch but present when raise is impossible.
    probe = ranked[max(5, int(len(ranked)*0.10))]
    assert probe not in normal_call, (probe, len(normal_call))
    assert probe in allin_continue, (probe, len(allin_continue))
    assert len(allin_continue) > len(normal_call), (
        len(normal_call), len(allin_continue))
    assert len(short_allin_continue) > len(allin_continue), (
        len(short_allin_continue), len(allin_continue))

    # Bet EV must be compared to a terminal-check EV, not zero.
    check = {'complete': True, 'chip_ev': 15.0}
    bet = {'complete': True, 'expected_chip_ev': 9.6}
    delta = round(bet['expected_chip_ev'] - check['chip_ev'], 6)
    assert delta == -5.4, delta

    src = inspect.getsource(SE.HandRun._run)
    assert "R.perceived_facing_bet_response(" in src
    assert "_response_size_frac = (" in src
    assert "float(_target_call_cost) / max(1.0, float(pot_live))" in src
    assert "_check_terminal = bool(street == 'river' and behind == 0)" in src
    assert "'bet_minus_check_ev': _bet_vs_check" in src
    assert "'response_range_conditioned': True" in src
    assert "'strategy_consumer': False" in src

    return {
        'normal_call_n': len(normal_call),
        'allin_continue_n': len(allin_continue),
        'short_allin_continue_n': len(short_allin_continue),
        'effective_call_price_widens_short_allin_range': True,
        'top_raise_slice_restored_when_raise_impossible': True,
        'example_bet_ev': 9.6,
        'example_check_ev': 15.0,
        'example_bet_minus_check': delta,
        'terminal_check_scope': 'river_and_behind0',
        'strategy_consumer': False,
    }



def check_d5_size_unit_boundary():
    # Strategic sizing contract is a pot fraction: 0.60 means 60% pot.
    # Execution rounds in 100-chip units:
    #   round((pot * fraction) / 100) * 100
    # so the /100 is paired with the final *100; it is not a percent conversion.
    state = {
        'plan': 'value_3street',
        'intents': {
            'river': SE.PL.mk_intent('bet', 0.60, 'fixture')
        }
    }
    prof = {
        'type': 'TAG',
        'aggr': 5.0,
        'bluff': 5.0,
        'gamble': 5.0,
    }
    act, _eq, _need = SE.PL.act_with_plan(
        ['Ah', 'Ad'], ['2c', '7d', 'Jh', '4s', '3c'],
        prof, state, pot=10000, tocall=0, stack=20000, street='river',
        initiative=True, opp_range=[], bf=1.0, seed=1,
        n_opp=1, to_act_behind=0)

    current_amount = act[1]
    strategic_amount = int(round((10000 * 0.60) / 100.0)) * 100

    assert SE.PL.intent_of(state, 'river')['size'] == 0.60, state
    assert strategic_amount == 6000, strategic_amount
    assert current_amount == strategic_amount == 6000, act

    src = inspect.getsource(SE.PL.act_with_plan)
    assert "pot*it['size']/100" in src
    assert "*100" in src

    return {
        'intent_size': 0.60,
        'contract': 'pot_fraction',
        'pot': 10000,
        'strategic_amount': strategic_amount,
        'current_execution_amount': current_amount,
        'ratio_current_to_intended': 1.0,
        'rounding_unit': 100,
        'defect_confirmed': False,
        'boundary_consistent': True,
    }



def check_d5c2_terminal_bet_ev_consumer():
    st = {
        'plan': 'value_3street',
        'why': [],
        'intents': {'river': SE.PL.mk_intent('bet', 0.60, 'fixture')},
    }

    # Negative incremental value: judgment layer must revise bet -> check.
    out, changed = SE.PL.apply_layer_bet_ev_judgment(st, 'river', -5.4)
    assert changed is True, out
    assert SE.PL.intent_of(out, 'river')['act'] == 'check', out
    assert st['intents']['river']['act'] == 'bet', st
    assert out['layer_bet_ev_judgments'][-1]['reason'] == (
        'terminal_layer_ev_negative'), out

    # Non-negative value keeps the original strategy intent.
    keep, changed2 = SE.PL.apply_layer_bet_ev_judgment(
        st, 'river', 3.25)
    assert changed2 is False, keep
    assert SE.PL.intent_of(keep, 'river')['act'] == 'bet', keep

    # Unknown stays unchanged.
    unknown, changed3 = SE.PL.apply_layer_bet_ev_judgment(
        st, 'river', None)
    assert changed3 is False, unknown
    assert SE.PL.intent_of(unknown, 'river')['act'] == 'bet', unknown

    psrc = inspect.getsource(SE.PL.apply_layer_bet_ev_judgment)
    assert "delta < 0" in psrc
    assert "mk_intent('check'" in psrc

    src = inspect.getsource(SE.HandRun._run)
    for needle in (
        "street == 'river'",
        "behind == 0",
        "not _raise_possible",
        "_bet_expected.get('complete')",
        "_check_sum.get('complete')",
        "PL.apply_layer_bet_ev_judgment(",
        "bet_ev_shadow['bet_vetoed_to_check']",
    ):
        assert needle in src, needle

    # Execution layer must not know bet_minus_check_ev.
    asrc = inspect.getsource(SE.PL.act_with_plan)
    assert "bet_minus_check_ev" not in asrc

    return {
        'negative_delta': 'bet->check',
        'positive_delta': 'bet-kept',
        'unknown_delta': 'bet-kept',
        'activation_scope': (
            'river, behind0, locked-main, one-active, raise-impossible, complete'),
        'execution_override': False,
        'strategy_consumer': True,
    }



def check_d6a_preflop_layer_provenance():
    # Same-street preflop geometry:
    # hero seat 1 has 10 in + 40 behind; seat 2 is all-in for 20;
    # seat 3 has raised to 50.  Dead BB ante 5 belongs only to first layer.
    layers = SE._decision_pot_layers(
        {}, {1: 10, 2: 20, 3: 50}, folded=set(),
        stacks={1: 40, 2: 0, 3: 50}, hero=1, dead=5)

    got = [
        (x['level'], x['amount'], x['eligible_seats'],
         x['hero_eligible'], x['locked_allin_seats'])
        for x in layers
    ]
    assert got == [
        (10.0, 35.0, [1, 2, 3], True, [2]),
        (20.0, 20.0, [2, 3], False, [2]),
        (50.0, 30.0, [3], False, []),
    ], got

    # Legal scalar cap and layer provenance describe the same reachable price
    # but layers preserve who owns each piece.
    r = SE.RU.Round(
        None, [1, 2, 3], {1: 40, 2: 0, 3: 50}, 10,
        current_bet=50, min_raise=30,
        contrib={1: 10, 2: 20, 3: 50})
    r.allin.add(2)
    assert r.to_call(1) == 40, r.to_call(1)
    assert r.contestable_contrib(1) == 80, r.contestable_contrib(1)

    psrc = inspect.getsource(SE.PL.preflop_plan)
    assert "'pf_pot_layers'" in psrc
    assert "pot_layers=None" in psrc
    ssrc = inspect.getsource(SE.HandRun._run)
    assert "_pf_pot_layers = _decision_pot_layers(" in ssrc
    assert "pot_layers=_pf_pot_layers" in ssrc

    # D6-A is provenance only: preflop strategy functions do not consume layers.
    dsrc = inspect.getsource(SE.pf.defend_decision)
    csrc = inspect.getsource(SE.pf.calloff_decision)
    assert "pot_layers" not in dsrc
    assert "pot_layers" not in csrc

    return {
        'layers': got,
        'to_call': 40,
        'contestable_scalar': 80,
        'schema_reused_from_postflop': True,
        'strategy_consumer': False,
    }


def main():
    layers = check_layer_geometry()
    tc, contestable = check_current_street_contestable_cap()
    gap = check_postflop_locked_opponent_gap()
    d1, pending = check_d1_provenance()
    d2 = check_d2_locked_range_preservation()
    d3 = check_d3_layer_equities()
    d4 = check_d4_call_ev_shadow()
    d5 = check_d5_bet_outcome_shadow()
    d5b = check_d5b_fold_probability_and_exhaustive_ev()
    d5c = check_d5c_response_conditioning_and_check_benchmark()
    d5u = check_d5_size_unit_boundary()
    d5c2 = check_d5c2_terminal_bet_ev_consumer()
    d6a = check_d6a_preflop_layer_provenance()

    print("PASS settlement geometry distinguishes main and side layers", layers)
    print("PASS current-street contestable cap is sound",
          {'to_call': tc, 'contestable_contrib': contestable})
    print("PASS F8 gap reproduced: cumulative pot includes locked all-in chips")
    print("     while current postflop opponent pools exclude that seat", gap)
    print("PASS F8-D1 decision-time pot-layer provenance is wired", d1)
    print("     pending upper layer keeps hero ineligible before call", pending[-1])
    print("PASS F8-D2 locked all-in opponent range is reconstructed", d2)
    print("PASS F8-D3 layer-specific equity diagnostics are separated", d3)
    print("PASS F8-D4 layer-aware call/fold consumer is isolated from raises", d4)
    print("PASS F8-D5-A proactive bet fold/call outcomes are layer-separated", d5)
    print("PASS F8-D5-B existing fold read combines EV only when raise is impossible", d5b)
    print("PASS F8-D5-C1 response-conditioned continue range and terminal check benchmark", d5c)
    print("PASS F8-D5-U sizing-unit boundary is consistent", d5u)
    print("PASS F8-D5-C2 terminal bet/check consumer stays in judgment layer", d5c2)
    print("PASS F8-D6-A preflop reuses decision-time pot-layer provenance", d6a)
    print("13/13 F8 diagnostic checks passed")
    print("NOTE: D6-A is provenance-only; preflop calloff strategy is still scalar.")


if __name__ == '__main__':
    main()
