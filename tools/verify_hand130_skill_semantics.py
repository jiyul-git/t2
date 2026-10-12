#!/usr/bin/env python3
"""Observe knowledge axes without assigning new behavior probabilities.

pf_defend gate no longer switches to wrong legacy percentile; its diagnostic
probability still moves with skill. Perceived ICM and potodds calculation are
the actual current personal-error channels, independently seeded. No special
AA/AK behavior is introduced.
"""
import copy
import os
import sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
import preflop as PF
from tools.verify_hand130_b37_replay import original

def main():
    hand=original(); shadow=hand['actor_pf_seed']['pf_call_ev_shadow']
    base=hand['actor_profile']; seed=3365551903
    true_bf=hand['actor_pf_seed']['pf_calloff_consumer']['objective_bubble_factor']
    def calc(concept,score):
        p=copy.deepcopy(base)
        p['concepts'][concept]=score
        return PF.calloff_layer_judgment(p,shadow,bubble_factor=true_bf,seed=seed)
    weak=calc('pf_defend',0)
    strong=calc('pf_defend',10)
    assert weak['pf_defend_gate_p']<strong['pf_defend_gate_p']
    assert weak['layer_action']==strong['layer_action']
    assert weak['perceived_required_equity']==strong['perceived_required_equity']
    assert weak['gate_seed']==strong['gate_seed']
    untrained_icm=calc('icm',0)
    trained_icm=calc('icm',10)
    assert untrained_icm['perceived_bubble_factor']!=trained_icm['perceived_bubble_factor']
    weak_potodds=calc('potodds',0)
    trained_potodds=calc('potodds',10)
    assert weak_potodds['potodds_noise']!=trained_potodds['potodds_noise']
    assert weak_potodds['noise_seed']==trained_potodds['noise_seed']
    print('PASS pf_defend changes diagnostic gate only, never cap fallback')
    print('PASS current ICM and potodds concepts change perceived calculation')
    print('ICM perceived BF:',untrained_icm['perceived_bubble_factor'],
        '->',trained_icm['perceived_bubble_factor'])
    print('potodds noise:',weak_potodds['potodds_noise'],
        '->',trained_potodds['potodds_noise'])

if __name__=='__main__':
    main()
