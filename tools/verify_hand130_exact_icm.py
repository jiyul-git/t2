#!/usr/bin/env python3
"""Exact HAND130 payout-ICM terminal state reconstruction; no guessed rates."""
import json
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.verify_hand130_b37_replay import original
import session as S
import icm as I
import plan as PL
import random

def nearly(got, want, name, tol=0.000000001):
    assert abs(got-want) <= tol, (name,got,want)

def main():
    h = original()
    shadow=h['actor_pf_seed']['pf_call_ev_shadow']
    ante=1250
    current={int(x):float(v)-ante for x,v in h['stacks_before'].items()}
    current[3]-=20000
    current[8]-=5000
    current[9]-=73442
    assert current[9] == 0
    contrib={3:20000,8:5000,9:73442}
    folded={1,2,4,5,7,8}
    layers=shadow['layers']
    # Verify the exact committed layer numbers against the original pot.
    assert [int(x['amount']) for x in layers] == [25000,136884]
    x = S._terminal_hu_call_icm(
        current, contrib, folded, list(current),
        3,9,shadow['call_cost'],h['field_context']['ante'],
        layers,h['field_context']['payouts'],
        h['field_context']['remaining'],shadow['effective_equity'])
    assert x and x['objective_action_with_fixed_equity']=='call', x
    nearly(x['fold_prize'],17.700552609563854,'fold')
    nearly(x['lose_prize'],15.461616393763215,'lose')
    nearly(x['win_prize'],21.487760646031855,'win')
    nearly(x['tie_prize'],18.733849424660832,'tie')
    nearly(x['no_tie_breakeven_equity'],0.3715371093145927,'price')
    nearly(x['equivalent_bubble_factor'],1.1996025358246731,'risk BF')
    assert x['payout_ev_lower'] > 0 and x['payout_ev_upper'] > 0
    # Exercise the actual planner consumer of the price-specific ICM factor
    # with the original B37 actor profile and decision RNG seed.
    calibrated_shadow = dict(shadow)
    calibrated_shadow['exact_hu_icm'] = x
    seed = h['actor_pf_seed']
    rng = random.Random(18)
    rng_state = rng.getstate()
    action, cost_bb, pseed = PL.preflop_plan(
        h['actor_profile'], 'LJ', ['Kh', 'Ac'], seed['pf_stack_bb'], rng,
        aggressor_pos='BB', open_bb=seed['pf_open_bb'],
        n_callers=0, raise_level=2, bb_chips=10000,
        bf=seed['pf_calloff_consumer']['objective_bubble_factor'],
        seats=8, ante=True, opener_allin=True, can_raise=False,
        pot_bb=seed['pf_pot_bb'], to_call_bb=seed['pf_to_call_bb'],
        prior_pf={'pf_act':'raise','pf_role':'open'},
        call_ev_shadow=calibrated_shadow,
        calloff_decision_seed=3365551903,
        cold_context=seed['pf_cold_context'])
    assert action == 'call' and cost_bb == 5.3442
    assert rng.getstate() == rng_state
    used=pseed['pf_calloff_consumer']
    nearly(used['objective_spot_bf'],x['equivalent_bubble_factor'],'planner BF')
    nearly(pseed['pf_calloff_compare']['icm_required_equity'],
           x['no_tie_breakeven_equity'],'planner price')
    assert used['gate_pass'] is False and used['strategy_consumer'] is True
    assert used['decision_quantity'] == 'perceived_layer_equity_vs_spot_icm_price'
    print('PASS full HAND130 objective-spot BF propagation to personal planner')

    # Nonterminal multi-opponent and incomplete-field contexts have no
    # manufactured exact-ICM prize estimate.
    assert S._terminal_hu_call_icm(current,contrib,folded-{8},
        list(current),3,9,shadow['call_cost'],10000,layers,
        h['field_context']['payouts'],8,shadow['effective_equity']) is None
    assert S._terminal_hu_call_icm(current,contrib,folded,
        list(current),3,9,shadow['call_cost'],10000,layers,
        h['field_context']['payouts'],16,shadow['effective_equity']) is None
    print(json.dumps(x,sort_keys=True))
    print('PASS exact terminal HUD ICM: payout states, actual risk, tie bounds')

if __name__=='__main__':
    main()
