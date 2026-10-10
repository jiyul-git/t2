#!/usr/bin/env python3
"""P8 -> P5 B37 impact: compare existing observer proxy vs action-conditioned proxy.

This is NOT a reconstruction of the original 288-combo opponent posterior.
Both counterfactual distributions use the same observer-perceived neutral
profile and publicly known B37 geometry; the actor's real private profile
is never supplied as a range prior. Monte Carlo seeds are paired.
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
import bot
import plan as PL
import ranges as R
import range_posterior_v1 as RP
import reads as RD
import session as S
from tools.verify_hand130_b37_replay import original
from tools.verify_hand130_conditioned_posterior import rows


def exact_icm(case, eq):
    pf = case['actor_pf_seed']
    ante = 1250
    current = {int(x): float(v)-ante for x, v
               in case['stacks_before'].items()}
    current[3] -= 20000
    current[8] -= 5000
    current[9] -= 73442
    contrib = {3: 20000, 8: 5000, 9: 73442}
    return S._terminal_hu_call_icm(
        current, contrib, {1, 2, 4, 5, 7, 8},
        list(current), 3, 9, pf['pf_call_ev_shadow']['call_cost'],
        case['field_context']['ante'], pf['pf_call_ev_shadow']['layers'],
        case['field_context']['payouts'],
        case['field_context']['remaining'], eq)


def actor_point(case, eq):
    pf = case['actor_pf_seed']
    sh = dict(pf['pf_call_ev_shadow'])
    sh['effective_equity'] = float(eq)
    sh['gross_return'] = float(eq) * sh['contestable_after_call']
    sh['call_chip_ev'] = sh['gross_return'] - sh['call_cost']
    sh['exact_hu_icm'] = exact_icm(case, eq)
    assert sh['exact_hu_icm'] and sh['exact_hu_icm']['equivalent_bubble_factor']
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
    assert state == rng.getstate()
    return {
        'action': action, 'size_bb': size,
        'icm_objective_fixed_equity_verdict':
            sh['exact_hu_icm']['objective_action_with_fixed_equity'],
        'icm_ev_lower': sh['exact_hu_icm']['payout_ev_lower'],
        'icm_ev_upper': sh['exact_hu_icm']['payout_ev_upper'],
        'icm_no_tie_break_even':
            sh['exact_hu_icm']['no_tie_breakeven_equity'],
        'perceived_required_equity':
            record['pf_calloff_consumer'].get('perceived_required_equity'),
        'legacy_evaluated':
            record['pf_calloff_consumer'].get('legacy_evaluated'),
        'mathematically_justified':
            record['pf_calloff_consumer'].get('mathematically_justified'),
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
        rows(), 9, 10000, 'BB', seats=8,
        effective_stack_bb=6.3442)
    conditional, meta = RP.conditioned_preflop_range(
        prof, event, dead, observer_context={'opener_pos': 'LJ'})
    assert meta['complete'] and conditional
    assert R.range_signature(legacy) != R.range_signature(conditional)
    # No hidden actor data enters either estimated opponent posterior.
    seeds = [zlib.crc32(('%s|paired|%d' % (case['hash'], j)).encode())
             for j in range(4)]
    out = {}
    for name, pool in [('legacy_general_3bet', legacy),
                       ('conditional_3bet_shove', conditional)]:
        rows_out = []
        for seed in seeds:
            stats = {}
            eq = bot.equity_vs_combos(
                hero, [], [pool], sims=800, seed=seed, audit=stats)
            row = {'seed': seed, 'equity': eq, 'mc': stats,
                   'p5': actor_point(case, eq)}
            assert stats['requested'] == 800 and stats['accepted'] > 0
            rows_out.append(row)
        out[name] = {
            'support': len(pool), 'mass': R.range_mass(pool),
            'range_signature': repr(R.range_signature(pool))[:200],
            'equity_seed_mean': statistics.mean(x['equity'] for x in rows_out),
            'equity_seed_sd': statistics.stdev(x['equity'] for x in rows_out),
            'actions': [x['p5']['action'] for x in rows_out],
            'objective_icm_actions': [
                x['p5']['icm_objective_fixed_equity_verdict'] for x in rows_out],
            'rows': rows_out,
        }
    result = {
        'parent_5_sha': '0786d970c769198d2649c75fc520d447ab9b6e9a',
        'hand': case['hash'],
        'original_288_posterior_reconstructed': False,
        'original_800_equity_recomputed': False,
        'actual_B37_saved_equity': case['actor_pf_seed']['pf_call_ev_shadow']['effective_equity'],
        'paired_seeds': seeds, 'models': out,
        'model_difference_equity_mean': (
            out['conditional_3bet_shove']['equity_seed_mean']
            - out['legacy_general_3bet']['equity_seed_mean']),
    }
    print(json.dumps(result, sort_keys=True))
    print('PASS P8 -> P5 paired B37 counterfactual equity/decision impact')


if __name__ == '__main__':
    main()
