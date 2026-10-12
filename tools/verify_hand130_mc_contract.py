#!/usr/bin/env python3
"""P9 HAND130 MC sample validity, provenance, and P5/P8 consumer contract.

No simulated opponent equity is treated as exact population equity.
Every check fixes seed, pools and/or mocked rejection pattern.
"""
import math
import os
import random
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bot
import preflop as PF
import session as S

HERO = ['Ah', 'Ad']
BOARD = ['Ks', 'Qs', 'Js', 'Ts', '9s']
ONE = [('2c', '3c')]
TWO_BAD = [('2c', '4c')]
TWO_GOOD = [('4c', '5c')]


def _layer(opp_seats):
    return {'hero_eligible': True,
            'eligible_seats': [1] + list(opp_seats),
            'amount': 150, 'level': 150}


def zero_valid_samples():
    audit = {}
    rng_before = random.getstate()
    v = bot.equity_vs_pools(
        HERO, BOARD, [ONE, TWO_BAD], sims=4, seed=41, audit=audit)
    assert random.getstate() == rng_before
    assert v is None and audit['mean_share'] is None, (v, audit)
    assert (audit['requested'], audit['accepted'], audit['rejected']) == (4, 0, 4)
    assert audit['reason'] == 'no_valid_mc_samples'
    assert audit['complete'] is False
    assert audit['sample_variance'] is None
    assert audit['split_pot_draws'] == 0

    rows = S.layer_equities_by_pot_layer(
        1, HERO, BOARD, [_layer([2, 3])],
        {2: ONE, 3: TWO_BAD}, {}, sims=4, seed=17,
        capture_sampling=True)
    r = rows[0]
    assert not r['complete'] and r['equity'] is None, r
    assert r['reason'] == 'no_valid_mc_samples'
    assert r['requested_samples'] == 4 and r['valid_samples'] == 0
    assert r['observed_sample_mean'] is None
    assert r['sampling']['accepted'] == 0
    summary = S._layer_call_summary(50, [_layer([2, 3])], rows)
    assert summary['complete'] is False and summary['call_chip_ev'] is None
    assert summary['effective_equity'] is None
    assert summary['incomplete_reasons'][0]['reason'] == 'no_valid_mc_samples'
    sh = dict(summary, pure_calloff=True)
    assert PF.calloff_layer_judgment({}, sh, seed=44) is None
    assert PF.calloff_ev_comparison(HERO, 'fold', 0.2, sh) is None


def partial_samples():
    counter = {'trial': 0}

    def forced_sampling(rng, pool):
        if pool == ONE:
            counter['trial'] += 1
            return ONE[0]
        # First trial: 40 rejected pair collisions, next trial: valid pair.
        return TWO_BAD[0] if counter['trial'] == 1 else TWO_GOOD[0]

    audit = {}
    with patch.object(bot, '_sample_pool_combo', side_effect=forced_sampling):
        result = bot.equity_vs_pools(
            HERO, BOARD, [ONE, TWO_BAD], sims=2, seed=32, audit=audit)
    assert result is None, (result, audit)
    assert (audit['requested'], audit['accepted'], audit['rejected']) == (2, 1, 1)
    assert audit['reason'] == 'insufficient_valid_samples'
    assert audit['complete'] is False
    assert math.isclose(audit['mean_share'], 1/3, rel_tol=0, abs_tol=1e-15)
    assert audit['split_pot_draws'] == 1
    assert audit['sample_variance'] is None

    counter['trial'] = 0
    with patch.object(bot, '_sample_pool_combo', side_effect=forced_sampling):
        rows = S.layer_equities_by_pot_layer(
            1, HERO, BOARD, [_layer([2, 3])],
            {2: ONE, 3: TWO_BAD}, {}, sims=2, seed=32)
    r = rows[0]
    assert r['complete'] is False and r['equity'] is None, r
    assert r['valid_samples'] == 1 and r['requested_samples'] == 2
    assert r['reason'] == 'insufficient_valid_samples'
    assert math.isclose(r['observed_sample_mean'], 1/3, abs_tol=1e-15)
    summary = S._layer_call_summary(50, [_layer([2,3])], rows)
    assert summary['incomplete_reasons'][0]['valid_samples'] == 1
    assert summary['call_chip_ev'] is None


def complete_and_true_zero():
    board = ['Ah', 'Kd', '7s', '9c', 'Jd']
    hero = ['2c', '3d']
    pool = [('Ac', 'Ad')]
    audit = {}
    v = bot.equity_vs_pools(hero, board, [pool], sims=8,
                            seed=15, audit=audit)
    assert v == 0.0 and audit['mean_share'] == 0.0
    assert audit['complete'] is True and audit['reason'] == 'computed'
    assert (audit['requested'], audit['accepted'], audit['rejected']) == (8,8,0)
    rows = S.layer_equities_by_pot_layer(
        1, hero, board, [_layer([2])], {2: pool}, {},
        sims=8, seed=15, capture_sampling=True)
    r = rows[0]
    assert r['complete'] is True and r['equity'] == 0.0, r
    assert r['reason'] == 'computed' and r['valid_samples'] == 8
    summary = S._layer_call_summary(50, [_layer([2])], rows)
    assert summary['complete'] is True and summary['call_chip_ev'] == -50.0
    # This negative EV is a valid zero-equity result, not a missing-sample fold.

    tie = {}
    tie_board = ['As', 'Ks', 'Qs', 'Js', 'Ts']
    tie_eq = bot.equity_vs_pools(
        ['2c','3d'], tie_board, [[('4c','5d')]],
        sims=6, seed=6, audit=tie)
    assert tie_eq == 0.5 and tie['split_pot_draws'] == 6
    assert tie['sample_variance'] == 0.0 and tie['complete'] is True


def empty_ranges_unsupported_and_replay():
    no_pool = {}
    assert bot.equity_vs_pools(HERO, BOARD, [], 3, 21, audit=no_pool) == 1.0
    assert no_pool['reason'] == 'no_opponents' and no_pool['complete']
    missing = {}
    assert bot.equity_vs_pools(HERO, BOARD, [[]], 3, 21, audit=missing) is None
    assert missing['reason'] == 'missing_opponent_range'
    zero_sims = {}
    assert bot.equity_vs_pools(HERO, BOARD, [ONE], 0, 21,
                               audit=zero_sims) is None
    assert zero_sims['reason'] == 'no_requested_samples'

    meta = {2: {'complete': False, 'missing': ['action_class_not_supported']}}
    rows = S.layer_equities_by_pot_layer(
        1, HERO, BOARD, [_layer([2])], {2: ONE}, {},
        range_metadata=meta, sims=6, seed=7)
    assert not rows[0]['complete'] and rows[0]['equity'] is None
    assert rows[0]['reason'] == 'unsupported_opponent_model', rows[0]
    s = S._layer_call_summary(25, [_layer([2])], rows)
    assert s['incomplete_reasons'][0]['reason'] == 'unsupported_opponent_model'
    assert s['incomplete_reasons'][0]['missing_range_details']['2'] == meta[2]

    rows = S.layer_equities_by_pot_layer(
        1, HERO, BOARD, [_layer([2])], {}, {}, sims=6, seed=7)
    assert not rows[0]['complete'] and rows[0]['reason'] == 'missing_opponent_range'

    # MC audit opt-in and repeated fixed-seed runs must have the same
    # estimates. Neither path touches the module-global Random state.
    hero = ['Ah','Kd']
    board = []
    pool = [('2s','2h'), ('Qh','Qs'), ('5c','6c')]
    a = {}
    global_state = random.getstate()
    eq1 = bot.equity_vs_pools(hero, board, [pool], sims=40, seed=91)
    eq2 = bot.equity_vs_pools(hero, board, [pool], sims=40, seed=91, audit=a)
    assert eq1 == eq2 and random.getstate() == global_state
    assert a['complete'] and a['accepted'] == 40
    assert a['sample_variance'] is not None and math.isfinite(a['sample_variance'])
    assert a['sample_variance'] >= 0.0
    b = {}
    eq3 = bot.equity_vs_pools(hero, board, [pool], sims=40, seed=91, audit=b)
    assert eq2 == eq3 and a == b


def main():
    random.seed(6153)
    zero_valid_samples()
    partial_samples()
    complete_and_true_zero()
    empty_ranges_unsupported_and_replay()
    print('PASS P9 MC: zero/partial/complete, true 0, tie, variance, seed, global RNG')
    print('PASS P5/P8: incomplete per-layer provenance, no fabricated equity/EV')


if __name__ == '__main__':
    main()
