#!/usr/bin/env python3
"""P8 -> P5 B37: paired counterfactual comparison of two observer ranges.

These are neutral perceived-profile PROXIES, NOT the archived HAND130 288-combo
weighted range or its original MC trace. Every projected pot layer is
recomputed for EACH model and seed. A synthetic single effective-equity
replacement is expressly forbidden in the consumer path.
"""
import json
import math
import random
import statistics
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plan as PL
import ranges as R
import range_posterior_v1 as RP
import reads as RD
import session as S
from tools.verify_hand130_b37_replay import original
from tools.verify_hand130_conditioned_posterior import rows

UNIT = 5000
ODD_ORDER = [8, 9, 1, 2, 3, 4, 5, 7]
TIE_B37 = 231422
TIE_BB = 86884
TIE_PRIZE_B37 = 18.515842285449054


def hand130_icm(case, layers, effective_equity):
    """Call the production payout-ICM geometry with real odd-chip settlement."""
    pf = case['actor_pf_seed']
    ante = 1250
    assert case['blinds'][0] == UNIT, case['blinds']
    current = {int(x): float(v)-ante for x, v
               in case['stacks_before'].items()}
    current[3] -= 20000
    current[8] -= 5000
    current[9] -= 73442
    assert current[9] == 0
    contrib = {3: 20000, 8: 5000, 9: 73442}
    result = S._terminal_hu_call_icm(
        current, contrib, {1, 2, 4, 5, 7, 8},
        list(current), 3, 9, pf['pf_call_ev_shadow']['call_cost'],
        case['field_context']['ante'], layers,
        case['field_context']['payouts'],
        case['field_context']['remaining'], effective_equity,
        unit=UNIT, odd_order=ODD_ORDER)
    assert result is not None
    assert result['tie_stacks'][3] == TIE_B37, result['tie_stacks']
    assert result['tie_stacks'][9] == TIE_BB, result['tie_stacks']
    assert math.isclose(result['tie_prize'], TIE_PRIZE_B37,
                        abs_tol=1e-10, rel_tol=0), result['tie_prize']
    assert result['no_tie_breakeven_equity'] > 0
    return result


def actor_point(case, pool, seed):
    """Recompute ALL layers and feed one consistent set to P5's real planner."""
    pf = case['actor_pf_seed']
    old_shadow = pf['pf_call_ev_shadow']
    layers = old_shadow['layers']
    assert [int(x['amount']) for x in layers] == [25000, 136884]
    layer_rows = S.layer_equities_by_pot_layer(
        3, case['hole']['3'], [], layers,
        {}, {9: pool}, sims=800, seed=seed,
        capture_sampling=True)
    assert len(layer_rows) == len(layers)
    assert all(x['complete'] and x['equity'] is not None
               for x in layer_rows), layer_rows
    for row in layer_rows:
        assert row['amount'] == layers[row['idx']]['amount']
        mc = row['sampling']
        assert mc['requested'] == 800 and mc['accepted'] > 0, mc
        assert mc['accepted'] + mc['rejected'] == 800

    summary = S._layer_call_summary(
        old_shadow['call_cost'], layers, layer_rows)
    assert summary['complete'] and not summary['missing_equity_layers']
    mass = sum(float(r['amount']) for r in layers if r['hero_eligible'])
    gross = sum(float(r['amount'])*float(layer_rows[i]['equity'])
                for i, r in enumerate(layers) if r['hero_eligible'])
    assert math.isclose(summary['gross_return'], gross, abs_tol=1e-5)
    assert summary['contestable_after_call'] == mass
    assert math.isclose(summary['effective_equity'],
                        round(gross/mass, 6), abs_tol=1e-12)

    # Replace the *whole* computed equity summary, not just the effective
    # value. The previously archived layer_equities MUST NOT survive here.
    sh = dict(old_shadow)
    sh.update(summary)
    sh['layer_equities'] = layer_rows
    sh['layers'] = layers
    sh['complete'] = summary['complete']
    sh['exact_hu_icm'] = hand130_icm(
        case, layers, summary['effective_equity'])
    assert sh['effective_equity'] == summary['effective_equity']
    assert sh['gross_return'] == summary['gross_return']
    assert sh['call_chip_ev'] == summary['call_chip_ev']
    assert sh['layer_equities'] is layer_rows

    rng = random.Random(919)
    state = rng.getstate()
    action, size, record = PL.preflop_plan(
        case['actor_profile'], 'LJ', ['Kh', 'Ac'],
        pf['pf_stack_bb'], rng, aggressor_pos='BB',
        open_bb=pf['pf_open_bb'], n_callers=0, n_limpers=0,
        raise_level=2,
        bf=pf['pf_calloff_consumer']['objective_bubble_factor'],
        seats=8, ante=True, bb_chips=10000,
        opener_allin=True, can_raise=False,
        pot_bb=pf['pf_pot_bb'], to_call_bb=pf['pf_to_call_bb'],
        prior_pf={'pf_act': 'raise', 'pf_role': 'open'},
        call_ev_shadow=sh, calloff_decision_seed=3365551903,
        cold_context=pf['pf_cold_context'])
    assert state == rng.getstate(), 'pure calloff consumed shared RNG'
    used = record['pf_calloff_consumer']
    assert used['legacy_evaluated'] is False
    assert used['mathematically_justified'] is False
    return {
        'action': action, 'size_bb': size,
        'effective_equity': summary['effective_equity'],
        'gross_return': summary['gross_return'],
        'chip_ev': summary['call_chip_ev'],
        'layer_equities': layer_rows,
        'rng_preserved': True,
        'icm_objective_fixed_equity_verdict':
            sh['exact_hu_icm']['objective_action_with_fixed_equity'],
        'icm_ev_lower': sh['exact_hu_icm']['payout_ev_lower'],
        'icm_ev_upper': sh['exact_hu_icm']['payout_ev_upper'],
        'icm_tie_prize': sh['exact_hu_icm']['tie_prize'],
        'icm_tie_stacks': {
            '3': sh['exact_hu_icm']['tie_stacks'][3],
            '9': sh['exact_hu_icm']['tie_stacks'][9]},
        'icm_no_tie_break_even':
            sh['exact_hu_icm']['no_tie_breakeven_equity'],
        'perceived_required_equity': used.get('perceived_required_equity'),
        'legacy_evaluated': used['legacy_evaluated'],
        'mathematically_justified': used['mathematically_justified'],
    }


def main():
    case = original()
    hero = case['hole']['3']
    dead = set(hero)
    prof = RD.range_profile(None)
    legacy = R.preflop_range(
        prof, 'BB', '3bet', 6.3442, dead,
        opener_pos='LJ', open_bb=2.0, seats=8, ante=True, raise_level=1)
    event = RP.classify_public_action(
        rows(), 9, 10000, 'BB', seats=8, effective_stack_bb=6.3442)
    conditional, meta = RP.conditioned_preflop_range(
        prof, event, dead, observer_context={'opener_pos': 'LJ'})
    assert meta['complete'] and conditional
    assert R.range_signature(legacy) != R.range_signature(conditional)

    seeds = [zlib.crc32(('%s|paired|%d' % (case['hash'], j)).encode())
             for j in range(4)]
    out = {}
    for name, pool in [('legacy_general_3bet', legacy),
                       ('conditional_3bet_shove', conditional)]:
        results = []
        for seed in seeds:
            result = actor_point(case, pool, seed)
            results.append({'seed': seed, 'p5': result})
        out[name] = {
            'support': len(pool), 'mass': R.range_mass(pool),
            'equity_seed_mean': statistics.mean(
                x['p5']['effective_equity'] for x in results),
            'equity_seed_sd': statistics.stdev(
                x['p5']['effective_equity'] for x in results),
            'actions': [x['p5']['action'] for x in results],
            'objective_icm_actions': [
                x['p5']['icm_objective_fixed_equity_verdict'] for x in results],
            'icm_ev_bounds': [
                [x['p5']['icm_ev_lower'],x['p5']['icm_ev_upper']]
                for x in results],
            'rows': results,
        }
    delta = (out['conditional_3bet_shove']['equity_seed_mean']
             - out['legacy_general_3bet']['equity_seed_mean'])
    print(json.dumps({
        'parent_5_sha': '6f0d912d7a6c6f62c2f82a38746ca588953544e8',
        'hand': case['hash'],
        'status': 'paired_counterfactual_proxy_not_archived_288',
        'original_288_posterior_reconstructed': False,
        'original_800_equity_recomputed': False,
        'original_archived_equity': case['actor_pf_seed']['pf_call_ev_shadow']['effective_equity'],
        'icm_unit': UNIT, 'icm_odd_order': ODD_ORDER,
        'tie_stacks': {'B37': TIE_B37, 'BB': TIE_BB},
        'tie_prize_pct': TIE_PRIZE_B37,
        'paired_seeds': seeds, 'models': out,
        'model_difference_equity_mean': delta,
    }, sort_keys=True))
    print('PASS P8/P5/P13 B37 recomputed-layer proxy comparison with exact odd chips')


if __name__ == '__main__':
    main()
