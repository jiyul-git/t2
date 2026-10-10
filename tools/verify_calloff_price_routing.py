#!/usr/bin/env python3
"""Synthetic price/ICM/hand-type routing cases, not solved hand equities.

No row supplies a GTO equity or asserts any poker hand is intrinsically a call.
The dummy numerical equity verifies that the actual decision layer consumes
the caller price, perceived BF and available pot layers, rather than a rank cap.
"""
import os
import random
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import icm as ICM
import preflop as PF
import plan as PL

def run_case(cards, eq, cost, pot_before, bf, expected):
    profile = {'type': 'TAG'}
    shadow = {'pure_calloff': True, 'complete': True,
              'effective_equity': eq, 'call_cost': cost,
              'contestable_after_call': cost + pot_before,
              'breakeven_equity': cost / (cost + pot_before)}
    seed = 428173
    rng = random.Random(799)
    state = rng.getstate()
    action, size, trace = PL.preflop_plan(
        profile, 'LJ', cards, 21.0, rng,
        aggressor_pos='BB', open_bb=7.3442, n_callers=0,
        raise_level=2, opener_allin=True, can_raise=False,
        pot_bb=pot_before, to_call_bb=cost,
        bf=bf, seats=8, ante=True,
        prior_pf={'pf_act': 'raise', 'pf_role': 'open'},
        call_ev_shadow=shadow, calloff_decision_seed=seed)
    assert rng.getstate() == state, 'shared RNG moved'
    need = ICM.required_equity(pot_before, cost, bf)
    assert (eq >= need) == (expected == 'call'), (eq, need, expected)
    assert action == expected, (cards, eq, cost, pot_before, bf, need, action)
    assert trace['pf_calloff_consumer']['decision_quantity'] == 'perceived_layer_equity_vs_price'
    assert (size == cost) if action == 'call' else size == 0
    return {'cards':cards, 'hypothetical_equity':eq, 'cost':cost,
            'pre_call_pot':pot_before, 'bf':bf, 'required':need, 'action':action}

def main():
    rows = [
        (['As','Ah'], 0.70, 5.3442, 10.8442, 1.0, 'call'),
        (['Ks','Kd'], 0.29, 5.3442, 10.8442, 1.0, 'fold'),
        (['Qs','Qd'], 0.60, 5.3442, 10.8442, 3.0, 'fold'),
        (['Ac','Kh'], 0.64, 5.3442, 10.8442, 3.0, 'call'),
        (['Ac','Kh'], 0.64, 5.3442, 10.8442, 4.0, 'fold'),
        (['Ac','Kh'], 0.35, 5.3442, 10.8442, 1.0, 'call'),
        (['Ac','Kh'], 0.35, 6.8442, 10.8442, 1.0, 'fold'),
    ]
    import json
    print(json.dumps([run_case(*r) for r in rows]))
    print('%s/%s synthetic price/ICM routing cases PASS' % (len(rows),len(rows)))

if __name__ == '__main__':
    main()
