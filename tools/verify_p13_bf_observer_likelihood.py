#!/usr/bin/env python3
"""P13/P8: impact of complete-field BF on action likelihood ON vs OFF.

P8 observes actor decisions through a model, not true private actor skills.
Use the existing neutral PERCEIVED profile and public-action model;
no new fitted coefficient or solver prior. Inspect derivative/non-derivative
segments separately. This is not the original 288-combo HAND130 posterior.
"""
import json
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import icm as I
import ranges as R
import range_posterior_v1 as RP
import reads as RD
from tools.verify_p13_complete_field_bf import ORIGINAL, LOCAL, FULL, PAYOUTS

def main():
    table=[ORIGINAL[s] for s in LOCAL]
    field=[ORIGINAL[s] for s in FULL]
    bf_before=I.bubble_factor(table,PAYOUTS,LOCAL.index(3))
    bf_after=I.bubble_factor(field,PAYOUTS,FULL.index(3))
    assert bf_after != bf_before

    neutral=RD.range_profile(None)
    dead={'Ac','Kh'}
    event={
        'kind':'first_in_shove',
        'actor_pos':'CO',
        'stack_bb':9.0, 'seats':8, 'ante':True,
    }
    ctx={
        'behind_stacks_bb':[8.,19.], 'field_q':0.6,
        'erosion':0.0, 'field_avg_bb':11.25, 'tilt':0.0,
        'payout_flat':0.0, 'reentry':False, 'progress':0.0,
    }
    available=sorted(c for c in R.ALL if not (set(c)&dead))
    before=[RP._first_in_likelihood(neutral,c,event,dict(ctx,bubble_factor=bf_before))
            for c in available]
    after=[RP._first_in_likelihood(neutral,c,event,dict(ctx,bubble_factor=bf_after))
           for c in available]
    assert all(math.isfinite(v) and 0 <= v <= 1 for v in before+after)
    changed=[(c,u,v) for c,u,v in zip(available,before,after)
             if not math.isclose(u,v,abs_tol=1e-12,rel_tol=0)]
    # P8 OFF does NOT consume observer_context.bubble_factor, and its
    # comparator below does not accept a BF parameter.
    off=R.preflop_range(neutral,'CO','open',9.0,dead,seats=8,ante=True)
    signature=R.range_signature(off)
    assert signature == R.range_signature(
        R.preflop_range(neutral,'CO','open',9.0,dead,seats=8,ante=True))
    print(json.dumps({
        'source':'observer_profile_neutral_synthetic_first_in_shove',
        'bf_before_wrong_five_table':bf_before,
        'bf_after_complete_eight':bf_after,
        'p8_off_bf_consumed':False,
        'p8_off_signature_stable':True,
        'p8_off_support':len(off),
        'p8_on_source':'existing_P8_first_in_likelihood',
        'p8_on_combos_evaluated':len(available),
        'p8_on_likelihood_changed_combos':len(changed),
        'p8_on_sum_likelihood_before':sum(before),
        'p8_on_sum_likelihood_after':sum(after),
        'p8_on_first_changed_combos':[
            {'combo':list(c),'before':u,'after':v}
            for c,u,v in changed[:8]],
        'threebet_shove_bf_direct_dependence':False,
        'original_hand130_288_posterior_rebuilt':False,
    }, sort_keys=True))
    print('PASS P8 ON/OFF BF-likelihood path and explicit fixed neutral-observer input')

if __name__ == '__main__':
    main()
